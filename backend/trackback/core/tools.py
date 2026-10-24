"""The only data tools agents get. Every read goes through the Memento service over HTTP (localhost or in-process ASGI)."""
from __future__ import annotations

import json
import os
import uuid
from typing import Any

import httpx

from .. import config
from . import db, graph
from . import formula as F


class ToolError(Exception):
    pass


TOOL_SPECS = [
    {"name": "get_document", "description": "Fetch a source document as of this run's pinned time via the Memento service. Returns version id, Memento-Datetime, body and the claim ids it contains. Documents published after the pin are refused.",
     "input_schema": {"type": "object", "properties": {"doc_id": {"type": "string"}}, "required": ["doc_id"], "additionalProperties": False}},
    {"name": "search_claims", "description": "Search claims visible as of the pin. Filters: query (matches line_item/entity/doc), entity, line_item, period (YYYY-MM, YYYY-Qn or YYYY).",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "entity": {"type": "string"}, "line_item": {"type": "string"}, "period": {"type": "string"}}, "required": ["query"], "additionalProperties": False}},
    {"name": "get_claim", "description": "Fetch one claim (as of the pin) by claim id.",
     "input_schema": {"type": "object", "properties": {"claim_id": {"type": "string"}}, "required": ["claim_id"], "additionalProperties": False}},
    {"name": "get_artifact", "description": "Read another agent's artifact (or your own earlier one) as of this run's pin: value, content, stated conclusions, who built it and when. Writes a consumption receipt (the hub records exactly what you read). Use it before building on someone else's output.",
     "input_schema": {"type": "object", "properties": {"artifact_id": {"type": "string"}, "fields": {"type": "array", "items": {"type": "string"}, "description": "fields you intend to use (value, content, conclusions); default all"}}, "required": ["artifact_id"], "additionalProperties": False}},
    {"name": "emit_number", "description": "Produce a number. Trackback evaluates `formula` over the named `inputs` (alias -> claim id or artifact id you have read or produced in this run). You never do arithmetic yourself.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "formula": {"type": "string"}, "inputs": {"type": "object", "additionalProperties": {"type": "string"}},
                                                        "period": {"type": "string"}, "line_item": {"type": "string"}, "conclusions": {"type": "object"}, "description": {"type": "string"}},
                      "required": ["name", "formula", "inputs", "period", "line_item"], "additionalProperties": False}},
    {"name": "emit_sentence", "description": "Produce one report sentence. Give the request (what the sentence should say) and the claim ids / artifact ids it rests on; Trackback writes it through the citations path and stores the citation edges.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "text_request": {"type": "string"}, "claim_ids": {"type": "array", "items": {"type": "string"}},
                                                        "artifact_ids": {"type": "array", "items": {"type": "string"}}, "period": {"type": "string"}, "line_item": {"type": "string"}, "conclusions": {"type": "object"}},
                      "required": ["name", "text_request", "claim_ids", "period", "line_item"], "additionalProperties": False}},
    {"name": "propose_journal_entry", "description": "Draft a journal entry for the Controller to approve. lines: [{account, amount_cents, gym}] must sum to zero. posting_period defaults to orig_period (the period the entry belongs to).",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "lines": {"type": "array", "items": {"type": "object"}}, "orig_period": {"type": "string"}, "posting_period": {"type": "string"},
                                                        "memo": {"type": "string"}, "correction_id": {"type": "string"}, "supporters": {"type": "array", "items": {"type": "string"}}, "approver": {"type": "string"}},
                      "required": ["name", "lines", "orig_period", "memo"], "additionalProperties": False}},
    {"name": "propose_action", "description": "Propose an action (certificate_send, bonus_payout, commission_payout, payment_run, tax_payment, deck_publish, dunning_email, collections_task). Goes through the pre-execution fence and the approvals inbox.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "kind": {"type": "string"}, "params": {"type": "object"}, "supporters": {"type": "array", "items": {"type": "string"}}, "approver_role": {"type": "string"}, "period": {"type": "string"}, "line_item": {"type": "string"}},
                      "required": ["name", "kind", "params", "supporters", "approver_role"], "additionalProperties": False}},
    {"name": "route_to_human", "description": "Ask a person when timing or materiality is ambiguous. Marks the artifacts as needs_review.",
     "input_schema": {"type": "object", "properties": {"reason": {"type": "string"}, "artifact_ids": {"type": "array", "items": {"type": "string"}}, "to_role": {"type": "string"}}, "required": ["reason", "artifact_ids"], "additionalProperties": False}},
    {"name": "finish", "description": "Signal that the task is complete, with a short summary.",
     "input_schema": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"], "additionalProperties": False}},
]


class ToolContext:
    def __init__(self, run_id: str, pinned_at: str, agent: str, prose_writer=None):
        self.run_id = run_id
        self.pinned_at = db.norm_ts(pinned_at)
        self.agent = agent
        self.prose_writer = prose_writer  # callable(text_request, blocks, conclusions) -> (text, cited_claim_ids)
        self.read_versions: dict[str, str] = {}          # source_version_id -> doc_id
        self.read_claim_versions: dict[str, dict] = {}   # claim_id -> claim version dict (as of pin)
        self.produced: dict[str, int] = {}               # artifact_id -> version produced in this run
        self.artifact_reads: dict[str, dict] = {}        # artifact_id -> {version, fields} read through get_artifact in this run
        self.refusals: list[dict] = []
        self.events: list[dict] = []
        base = os.environ.get("TRACKBACK_MEMENTO_URL")
        if base:
            self.http = httpx.Client(base_url=base, timeout=10)
        else:
            from fastapi.testclient import TestClient
            from ..main import app
            self.http = TestClient(app, base_url="http://trackback.local")  # in-process HTTP: same headers, status codes, reads log

    # ---- reads -----------------------------------------------------------------------------
    def _headers(self, tool_call_id: str | None = None) -> dict:
        h = {"X-Trackback-Run": self.run_id}
        if tool_call_id:
            h["X-Trackback-Tool-Call"] = tool_call_id
        return h

    def get_document(self, doc_id: str, tool_call_id: str | None = None) -> dict:
        r = self.http.get(f"/r/{doc_id}", headers=self._headers(tool_call_id))
        if r.status_code != 200:
            body = r.json() if r.headers.get("content-type", "").startswith("application/problem+json") else {"detail": r.text}
            self.refusals.append({"doc_id": doc_id, "status": r.status_code, **body})
            return {"error": "refused", "status": r.status_code, "problem": body}
        d = r.json()
        self.read_versions[d["version_id"]] = doc_id
        for c in d["claims"]:
            info = graph.claim_info(c["claim_id"]) or {}
            c.update({k: info.get(k) for k in ("entity", "line_item", "period_start", "period_end", "unit", "account")})
            self.read_claim_versions[c["claim_id"]] = c
        return {"doc_id": doc_id, "version_id": d["version_id"], "memento_datetime": r.headers.get("Memento-Datetime"), "uri_m": r.headers["link"].split(";")[0] if "link" in r.headers else None,
                "document_date": d["document_date"], "body": d["body"], "claims": d["claims"]}

    def search_claims(self, query: str, entity: str | None = None, line_item: str | None = None, period: str | None = None, tool_call_id: str | None = None) -> dict:
        qs = f"%{query.lower()}%"
        sql = ("SELECT DISTINCT c.source_id FROM claims c JOIN sources s ON s.source_id=c.source_id WHERE (LOWER(c.line_item) LIKE ? OR LOWER(c.entity) LIKE ? OR LOWER(s.title) LIKE ? OR LOWER(c.source_id) LIKE ?)")
        params: list[Any] = [qs, qs, qs, qs]
        if entity:
            sql += " AND c.entity=?"; params.append(entity)
        if line_item:
            sql += " AND c.line_item=?"; params.append(line_item)
        docs = [r["source_id"] for r in db.q(sql, params)][:12]
        out = []
        for d in docs:
            got = self.get_document(d, tool_call_id)
            if "error" in got:
                continue
            for c in got["claims"]:
                if entity and c.get("entity") != entity:
                    continue
                if line_item and c.get("line_item") != line_item:
                    continue
                if period and not _period_match(period, c.get("period_start") or ""):
                    continue
                out.append({k: c.get(k) for k in ("claim_id", "claim_version_id", "entity", "line_item", "period_start", "period_end", "value_num", "value_text")} | {"doc_id": d})
        return {"results": out[:60]}

    def get_claim(self, claim_id: str, tool_call_id: str | None = None) -> dict:
        info = graph.claim_info(claim_id)
        if not info:
            return {"error": "no such claim"}
        got = self.get_document(info["source_id"], tool_call_id)
        if "error" in got:
            return got
        c = self.read_claim_versions.get(claim_id)
        return c or {"error": "claim not in the version visible as of the pin"}

    def get_artifact(self, artifact_id: str, fields: list[str] | None = None) -> dict:
        """Hub read of another artifact as of the pin. Logged as a read; a consumption receipt is written when this run builds on it."""
        row = db.q1("SELECT * FROM artifacts WHERE artifact_id=? AND tx_from<=? ORDER BY version DESC LIMIT 1", (artifact_id, self.pinned_at))
        if row is None:
            later = db.q1("SELECT MIN(tx_from) t FROM artifacts WHERE artifact_id=?", (artifact_id,))
            if later and later["t"]:
                self.refusals.append({"artifact_id": artifact_id, "status": 404, "detail": f"did not exist as of the pin (first version {later['t']})"})
                return {"error": "refused", "status": 404, "detail": f"artifact {artifact_id} did not exist as of {self.pinned_at} (first version {later['t']})"}
            return {"error": f"no such artifact {artifact_id}"}
        d = graph.artifact_dict(row)
        want = fields or ["value", "content", "conclusions"]
        self.artifact_reads[artifact_id] = {"version": d["version"], "fields": want}
        db.insert("reads", {"read_id": uuid.uuid4().hex[:16], "run_id": self.run_id, "tool_call_id": None, "uri_m": f"/artifact/{artifact_id}@{d['version']}",
                            "source_version_id": None, "memento_datetime": d["tx_from"], "pinned_at": self.pinned_at, "http_status": 200, "ts": self.pinned_at})
        # the model sees the content; the version, hash and status go into the receipt (keeping replays byte-identical)
        return {"artifact_id": artifact_id, "kind": d["kind"], "agent_id": d.get("agent_id"), "period": d["period"], "line_item": d["line_item"], "metric": d.get("metric"),
                "value": d["value_num"], "content": d["content"], "conclusions": d["conclusions"]}

    def _receipts(self, consumer_id: str, consumer_version: int, resolved: list[tuple[str, str, str]], default_field: str) -> None:
        for kind, sid, sver in resolved:
            if kind != "artifact":
                continue
            read = self.artifact_reads.get(sid)
            fields = read["fields"] if read else [default_field]
            graph.add_receipt(consumer_id=consumer_id, consumer_version=consumer_version, consumed_id=sid, consumed_version=int(sver), fields_read=fields,
                              run_id=self.run_id, agent_id=self.agent, ts=self.pinned_at)

    # ---- writes ------------------------------------------------------------------------------
    def _resolve_input(self, ref: str) -> tuple[str, str, str, float | None]:
        """ref -> (supporter_kind, supporter_id, supporter_version, value)."""
        if ref in self.read_claim_versions:
            c = self.read_claim_versions[ref]
            return "claim", ref, c["claim_version_id"], c["value_num"]
        if ref in self.produced:
            row = db.q1("SELECT * FROM artifacts WHERE artifact_id=? AND version=?", (ref, self.produced[ref]))
            return "artifact", ref, str(row["version"]), row["value_num"]
        cur = db.q1("SELECT * FROM artifacts WHERE artifact_id=? AND tx_from<=? ORDER BY version DESC LIMIT 1", (ref, self.pinned_at))
        if cur is not None:
            # an artifact produced by an earlier run (latest version that existed at the pin): allowed as an input
            return "artifact", ref, str(cur["version"]), cur["value_num"]
        raise ToolError(f"input '{ref}' was not read in this run (every input must come from get_document/search_claims/get_claim or be an artifact of this run)")

    def emit_number(self, name: str, formula: str, inputs: dict[str, str], period: str, line_item: str, conclusions: dict | None = None, description: str | None = None) -> dict:
        resolved = {}
        values = {}
        for alias, ref in inputs.items():
            kind, sid, sver, val = self._resolve_input(ref)
            resolved[alias] = {"kind": kind, "id": sid, "version": sver}
            values[alias] = val
        try:
            value = F.evaluate(formula, values)
        except F.FormulaError as e:
            raise ToolError(f"formula rejected: {e}") from e
        v = graph.new_artifact(artifact_id=name, kind="forecast_cell" if line_item.startswith("cash_forecast") or line_item.endswith("_forecast") else "number",
                               run_id=self.run_id, pinned_at=self.pinned_at, period=period, line_item=line_item, content=description,
                               value_num=value, formula={"expr": formula, "inputs": resolved}, conclusions=conclusions, agent_id=self.agent, metric=line_item,
                               fields={"inputs": {a: r["id"] for a, r in resolved.items()}})
        for alias, r in resolved.items():
            graph.add_edge(consumer_id=name, consumer_version=v, supporter_kind=r["kind"], supporter_id=r["id"], supporter_version=r["version"],
                           dep_kind="numeric", capture="structured", predicate=f"{alias} == {values[alias]}")
        self._receipts(name, v, [(r["kind"], r["id"], r["version"]) for r in resolved.values()], "value")
        self.produced[name] = v
        return {"artifact_id": name, "value": value}

    def emit_sentence(self, name: str, text_request: str, claim_ids: list[str], period: str, line_item: str, conclusions: dict | None = None, artifact_ids: list[str] | None = None) -> dict:
        blocks = []
        for cid in claim_ids:
            if cid not in self.read_claim_versions:
                raise ToolError(f"claim '{cid}' was not read in this run")
            c = self.read_claim_versions[cid]
            blocks.append({"id": cid, "text": _claim_text(c)})
        art_refs = []
        for aid in artifact_ids or []:
            kind, sid, sver, val = self._resolve_input(aid)
            row = db.q1("SELECT * FROM artifacts WHERE artifact_id=? AND version=?", (sid, int(sver)))
            blocks.append({"id": aid, "text": f"{aid} ({row['line_item']}, {row['period']}): {_fmt(val)}" + (f" — {row['content']}" if row["content"] else "")})
            art_refs.append((sid, sver))
        text, cited = self.prose_writer(text_request, blocks, conclusions, self) if self.prose_writer else (text_request, [b["id"] for b in blocks])
        from ..agents.prose import templatize
        slot_values = {sid: db.q1("SELECT value_num FROM artifacts WHERE artifact_id=? AND version=?", (sid, int(sver)))["value_num"] for sid, sver in art_refs}
        template = templatize(text, slot_values) if slot_values else None
        v = graph.new_artifact(artifact_id=name, kind="sentence", run_id=self.run_id, pinned_at=self.pinned_at, period=period, line_item=line_item,
                               content=text, value_num=None, formula=None, conclusions=conclusions, agent_id=self.agent, metric=line_item,
                               fields={"claims": claim_ids, "artifacts": list(artifact_ids or []), "template": template})
        uncited = []
        for b in blocks:
            is_cited = b["id"] in cited
            if b["id"] in self.read_claim_versions and b["id"] in claim_ids:
                graph.add_edge(consumer_id=name, consumer_version=v, supporter_kind="claim", supporter_id=b["id"], supporter_version=self.read_claim_versions[b["id"]]["claim_version_id"],
                               dep_kind="prose", capture="citation" if is_cited else "tool_log", predicate=None if is_cited else "read_not_cited")
            else:
                sid, sver = next((a for a in art_refs if a[0] == b["id"]), (None, None))
                if sid:
                    graph.add_edge(consumer_id=name, consumer_version=v, supporter_kind="artifact", supporter_id=sid, supporter_version=sver,
                                   dep_kind="prose", capture="citation" if is_cited else "tool_log", predicate=None if is_cited else "read_not_cited")
            if not is_cited:
                uncited.append(b["id"])
        if not cited:
            db.log_event("prose_uncited", f"{name}: sentence has zero valid citations", ts=self.pinned_at, run_id=self.run_id)
        self._receipts(name, v, [("artifact", sid, sver) for sid, sver in art_refs], "value")
        self.produced[name] = v
        out = {"artifact_id": name, "text": text, "cited": cited, "read_not_cited": uncited}
        from . import fence
        fm = fence.figure_mismatch(db.q1("SELECT * FROM artifacts WHERE artifact_id=? AND version=?", (name, v)))
        if fm:
            db.log_event("figure_mismatch", f"{name}: {fm['message']}", ts=self.pinned_at, run_id=self.run_id, detail={"artifact_id": name, **fm})
            out["warning"] = fm["message"]
        return out

    def propose_journal_entry(self, name: str, lines: list[dict], orig_period: str, memo: str, posting_period: str | None = None, correction_id: str | None = None,
                              supporters: list[str] | None = None, approver: str | None = None) -> dict:
        posting_period = posting_period or orig_period  # the trap: default date is the original period
        total = sum(int(l["amount_cents"]) for l in lines)
        if total != 0:
            raise ToolError(f"entry does not sum to zero ({total} cents)")
        action_id = f"JE-{name}"
        params = {"lines": lines, "posting_period": posting_period, "orig_period": orig_period, "memo": memo, "correction_id": correction_id,
                  "out_of_period": posting_period != orig_period}
        from .domain import get_domain
        locked = not get_domain().can_post({"period": posting_period})[0]
        params["period_locked"] = locked
        v = graph.new_artifact(artifact_id=name, kind="action", run_id=self.run_id, pinned_at=self.pinned_at, period=posting_period, line_item="journal_entry",
                               content=memo, value_num=sum(abs(int(l["amount_cents"])) for l in lines) / 200, formula=None, conclusions=None, status="valid",
                               agent_id=self.agent, metric="journal_entry", fields={"lines": lines})
        rs = []
        for s in supporters or []:
            kind, sid, sver, _ = self._resolve_input(s)
            rs.append((kind, sid, sver))
            graph.add_edge(consumer_id=name, consumer_version=v, supporter_kind=kind, supporter_id=sid, supporter_version=sver, dep_kind="numeric", capture="structured")
        self._receipts(name, v, rs, "value")
        proposer = f"agent:{self.agent}"
        if db.q1("SELECT 1 FROM actions WHERE action_id=?", (action_id,)) is None:
            graph.new_action(action_id=action_id, artifact_id=name, kind="journal_entry", params=params, run_id=self.run_id, proposer=proposer,
                             approver_role="controller", created_at=self.pinned_at, state="proposed")
        result: dict[str, Any] = {"action_id": action_id, "artifact_id": name, "state": "proposed", "posting_period": posting_period}
        if locked:  # flagged in the event log and the inbox (not in the tool result: the Controller decides, and replays stay byte-identical)
            db.log_event("period_locked", f"{action_id} is dated into locked period {posting_period}; flagged for the Controller", actor=proposer, ts=self.pinned_at, run_id=self.run_id, correction_id=correction_id)
        if approver:
            # The workflow hole (E22): an agent trying to set approver = proposer. The schema CHECK rejects it.
            from . import approvals
            try:
                approvals.decide(action_id, approver, "approved", "auto-route", self.pinned_at)
                result["approval"] = "approved"
            except approvals.SelfApprovalError as e:
                result["approval_error"] = f"rejected by schema CHECK(proposer <> approver): {e}"
        db.commit()
        self.produced[name] = v
        return result

    def propose_action(self, name: str, kind: str, params: dict, supporters: list[str], approver_role: str, period: str | None = None, line_item: str | None = None) -> dict:
        value_num, formula = params.get("amount"), None
        if params.get("value_from"):
            _, sid, sver, val = self._resolve_input(params["value_from"])
            value_num, formula = val, {"value_from": sid, "version": sver}
        v = graph.new_artifact(artifact_id=name, kind="action", run_id=self.run_id, pinned_at=self.pinned_at, period=period, line_item=line_item or kind,
                               content=params.get("summary") or kind, value_num=value_num, formula=formula, conclusions=params.get("conclusions"), status="valid",
                               agent_id=self.agent, metric=kind, fields={"params": {k: v for k, v in params.items() if k != "conclusions"}})
        rs = []
        for s in supporters:
            k, sid, sver, _ = self._resolve_input(s)
            rs.append((k, sid, sver))
            graph.add_edge(consumer_id=name, consumer_version=v, supporter_kind=k, supporter_id=sid, supporter_version=sver, dep_kind="numeric", capture="structured")
        self._receipts(name, v, rs, "value")
        action_id = f"ACT-{name}"
        if db.q1("SELECT 1 FROM actions WHERE action_id=?", (action_id,)) is None:
            graph.new_action(action_id=action_id, artifact_id=name, kind=kind, params=params, run_id=self.run_id, proposer=f"agent:{self.agent}", approver_role=approver_role,
                             created_at=self.pinned_at, state="proposed")
        db.commit()
        self.produced[name] = v
        return {"action_id": action_id, "artifact_id": name, "state": "proposed"}

    def route_to_human(self, reason: str, artifact_ids: list[str], to_role: str = "controller") -> dict:
        for aid in artifact_ids:
            cur = db.artifact_current(aid)
            if cur is not None:
                graph.set_status(aid, cur["version"], "suspect", self.pinned_at, note=f"routed to {to_role}: {reason}")
        db.log_event("route_to_human", f"{self.agent} -> {to_role}: {reason}", actor=f"agent:{self.agent}", ts=self.pinned_at, run_id=self.run_id, detail={"artifact_ids": artifact_ids})
        db.commit()
        return {"routed_to": to_role, "artifact_ids": artifact_ids}

    def dispatch(self, name: str, args: dict, tool_call_id: str | None = None) -> dict:
        try:
            if name == "get_document":
                return self.get_document(args["doc_id"], tool_call_id)
            if name == "search_claims":
                return self.search_claims(args["query"], args.get("entity"), args.get("line_item"), args.get("period"), tool_call_id)
            if name == "get_claim":
                return self.get_claim(args["claim_id"], tool_call_id)
            if name == "get_artifact":
                return self.get_artifact(args["artifact_id"], args.get("fields"))
            if name == "emit_number":
                return self.emit_number(args["name"], args["formula"], args["inputs"], args["period"], args["line_item"], args.get("conclusions"), args.get("description"))
            if name == "emit_sentence":
                return self.emit_sentence(args["name"], args["text_request"], args["claim_ids"], args["period"], args["line_item"], args.get("conclusions"), args.get("artifact_ids"))
            if name == "propose_journal_entry":
                return self.propose_journal_entry(args["name"], args["lines"], args["orig_period"], args["memo"], args.get("posting_period"), args.get("correction_id"), args.get("supporters"), args.get("approver"))
            if name == "propose_action":
                return self.propose_action(args["name"], args["kind"], args["params"], args["supporters"], args["approver_role"], args.get("period"), args.get("line_item"))
            if name == "route_to_human":
                return self.route_to_human(args["reason"], args["artifact_ids"], args.get("to_role", "controller"))
            if name == "finish":
                return {"ok": True}
            return {"error": f"unknown tool {name}"}
        except ToolError as e:
            return {"error": str(e)}
        except KeyError as e:
            return {"error": f"missing argument {e}"}


def _period_match(period: str, period_start: str) -> bool:
    if not period_start:
        return False
    if "Q" in period:
        y, qn = int(period[:4]), int(period[-1])
        m = int(period_start[5:7])
        return period_start.startswith(str(y)) and (m - 1) // 3 + 1 == qn
    return period_start.startswith(period)


def _fmt(v) -> str:
    if v is None:
        return "n/a"
    return f"{v:,.4f}".rstrip("0").rstrip(".") if abs(v) < 100 else f"{v:,.2f}".rstrip("0").rstrip(".")


def _claim_text(c: dict) -> str:
    ent = f" for {c['entity']}" if c.get("entity") else ""
    per = f" ({c['period_start']} to {c['period_end']})" if c.get("period_start") else ""
    val = _fmt(c["value_num"]) if c.get("value_num") is not None else (c.get("value_text") or "")
    return f"{c['line_item']}{ent}{per}: {val} {c.get('unit') or ''}".strip()
