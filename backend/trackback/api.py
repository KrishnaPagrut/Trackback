"""Trackback API for the UI: artifacts, graph, corrections (the judge's red pen), approvals, norms, Memento helpers, proof."""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import approvals, config, corrections, db, graph, ledger, live, norms, scenarios
from .core import pings as PG
from .engine import fence, materiality as M, propagate
from .engine.propagate import REASON_LABEL
from .llm import gateway

router = APIRouter()
UNDO_DIR = config.DATA_DIR / "snapshots" / "undo"


# ------------------------------------------------------------------ basics
@router.get("/health")
def health():
    return {"ok": True, "now": config.DEMO_NOW, "mode": gateway.mode()}


@router.get("/state")
def state():
    c = lambda sql, p=(): db.q1(sql, p)["n"]  # noqa: E731
    return {"now": config.DEMO_NOW, "mode": gateway.mode(), "company": config.COMPANY, "agent_model": config.AGENT_MODEL, "judge_model": config.JUDGE_MODEL,
            "artifacts": c("SELECT COUNT(DISTINCT artifact_id) n FROM artifacts"), "edges": c("SELECT COUNT(*) n FROM justifications"),
            "sources": c("SELECT COUNT(*) n FROM sources"), "versions": c("SELECT COUNT(*) n FROM source_versions"), "claims": c("SELECT COUNT(*) n FROM claim_versions"),
            "corrections": [r["correction_id"] for r in db.q("SELECT correction_id FROM corrections ORDER BY tx_time")],
            "e11_applied": bool(db.q1("SELECT 1 FROM corrections WHERE correction_id='E11'")), "e20_applied": bool(db.q1("SELECT 1 FROM corrections WHERE correction_id='E20'")),
            "pending_approvals": c("SELECT COUNT(*) n FROM actions WHERE state='proposed'"), "undo_depth": len(list(UNDO_DIR.glob("*.sqlite"))) if UNDO_DIR.exists() else 0,
            "people": config.PEOPLE, "receipts": c("SELECT COUNT(*) n FROM consumption_receipts")}


def _finding_latest(artifact_id: str) -> dict | None:
    r = db.q1("SELECT f.* FROM impact_findings f JOIN corrections c ON c.correction_id=f.correction_id WHERE f.artifact_id=? ORDER BY c.tx_time DESC, f.rowid DESC LIMIT 1", (artifact_id,))
    return dict(r) if r else None


def _status_badge(art: dict, finding: dict | None) -> str:
    st = art["status"]
    if art["kind"] == "action":
        a = db.q1("SELECT state FROM actions WHERE artifact_id=?", (art["artifact_id"],))
        if a and a["state"] == "compensation_proposed":
            return "COMPENSATION PROPOSED"
        if a and a["state"] in ("blocked", "stale"):
            return "STALE"
    if st == "stale":
        return "STALE"
    if st == "suspect":
        return "NEEDS REVIEW"
    if st == "unprovable":
        return "UNPROVABLE"
    if art["version"] > 1 or "[recalculated" in (art["content"] or ""):
        return "RECALCULATED"
    return "VALID"


@router.get("/artifacts")
def artifacts(company: str = "tidewall"):
    rows = db.q("SELECT a.* FROM artifacts a WHERE a.version=(SELECT MAX(version) FROM artifacts b WHERE b.artifact_id=a.artifact_id) ORDER BY a.tx_from, a.artifact_id")
    out = []
    for r in rows:
        d = graph.artifact_dict(r)
        if (company == "lyft") != (d["artifact_id"].startswith("lyft_") or d["artifact_id"].startswith("comp_lyft_")):
            continue
        f = _finding_latest(d["artifact_id"])
        d["badge"] = _status_badge(d, f)
        d["latest_finding"] = f
        d.pop("formula", None)
        out.append(d)
    return {"artifacts": out}


@router.get("/artifact/{artifact_id}")
def artifact(artifact_id: str):
    versions = [graph.artifact_dict(r) for r in db.q("SELECT * FROM artifacts WHERE artifact_id=? ORDER BY version", (artifact_id,))]
    if not versions:
        raise HTTPException(404, "no such artifact")
    cur = versions[-1]
    sups = []
    for e in graph.supporters_of(artifact_id, cur["version"]):
        if e["supporter_kind"] == "claim":
            cv = db.q1("SELECT cv.*, c.entity, c.line_item, c.period_start, c.period_end, c.unit, c.source_id FROM claim_versions cv JOIN claims c ON c.claim_id=cv.claim_id WHERE cv.claim_version_id=?", (e["supporter_version"],))
            sups.append({**e, "claim": dict(cv) if cv else None, "lot": db.lot_code(e["supporter_id"], e["supporter_version"])})
        else:
            a = db.q1("SELECT * FROM artifacts WHERE artifact_id=? AND version=?", (e["supporter_id"], int(e["supporter_version"])))
            sups.append({**e, "artifact": graph.artifact_dict(a) if a else None, "lot": db.lot_code(e["supporter_id"], e["supporter_version"])})
    cons = [dict(e) for e in graph.consumers_of_artifact(artifact_id)]
    findings = [dict(r) for r in db.q("SELECT * FROM impact_findings WHERE artifact_id=? ORDER BY rowid", (artifact_id,))]
    action = db.q1("SELECT * FROM actions WHERE artifact_id=?", (artifact_id,))
    reads = db.q("SELECT * FROM reads WHERE run_id=? ORDER BY ts", (cur["run_id"],)) if cur["run_id"] else []
    return {"artifact": cur, "versions": versions, "supporters": sups, "consumers": cons, "findings": findings, "action": dict(action) if action else None,
            "run": dict(db.q1("SELECT * FROM runs WHERE run_id=?", (cur["run_id"],)) or {}) if cur["run_id"] else None, "reads": [dict(r) for r in reads][:60], "badge": _status_badge(cur, findings[-1] if findings else None)}


# ------------------------------------------------------------------ graph for React Flow
@router.get("/graph")
def graph_view(correction: str | None = None, company: str = "tidewall", limit: int = 400):
    """Nodes: sources (left), artifacts (right), with the correction's findings attached for the ripple."""
    findings = {}
    naive = set()
    corr = None
    if correction:
        corr = db.q1("SELECT * FROM corrections WHERE correction_id=?", (correction,))
        for r in db.q("SELECT * FROM impact_findings WHERE correction_id=?", (correction,)):
            findings[r["artifact_id"]] = dict(r)
    arts = {r["artifact_id"]: graph.artifact_dict(r) for r in db.q("SELECT a.* FROM artifacts a WHERE a.version=(SELECT MAX(version) FROM artifacts b WHERE b.artifact_id=a.artifact_id)")}
    arts = {k: v for k, v in arts.items() if (company == "lyft") == (k.startswith("lyft_") or k.startswith("comp_lyft_"))}
    nodes, edges, seen_docs = [], [], set()
    for aid, a in arts.items():
        f = findings.get(aid)
        nodes.append({"id": aid, "type": "artifact", "kind": a["kind"], "label": aid, "line_item": a["line_item"], "period": a["period"], "value": a["value_num"], "lot": a["lot"],
                      "status": a["status"], "badge": _status_badge(a, f), "run_id": a["run_id"], "content": (a["content"] or "")[:160],
                      "agent_id": a.get("agent_id"), "node_kind": a.get("node_kind"), "comp": bool((a["run_id"] or "").startswith("correction:") and a["kind"] == "action"), "origin": a.get("origin"),
                      "verdict": f["verdict"] if f else None, "reason": f["reason"] if f else None, "reason_label": REASON_LABEL.get(f["reason"], f["reason"]) if f else None,
                      "hop": f["hop"] if f else None, "old_value": f["old_value"] if f else None, "new_value": f["new_value"] if f else None, "rewrite": f["proposed_rewrite"] if f else None})
        for e in graph.supporters_of(aid, a["version"]):
            if e["supporter_kind"] == "artifact":
                if e["supporter_id"] in arts:
                    edges.append({"id": e["edge_id"], "source": e["supporter_id"], "target": aid, "dep": e["dep_kind"]})
            else:
                info = graph.claim_info(e["supporter_id"]) or {}
                doc = info.get("source_id")
                if doc:
                    if doc not in seen_docs:
                        seen_docs.add(doc)
                        src = db.q1("SELECT * FROM sources WHERE source_id=?", (doc,))
                        nv = db.q1("SELECT COUNT(*) n FROM source_versions WHERE source_id=?", (doc,))["n"]
                        is_corr = bool(corr and corr["source_id"] == doc)
                        nodes.append({"id": doc, "type": "source", "label": src["title"] if src else doc, "system": src["system"] if src else None, "versions": nv, "corrected": is_corr, "hop": -1 if is_corr else None})
                    eid = f"{doc}->{aid}"
                    if not any(x["id"] == eid for x in edges):
                        edges.append({"id": eid, "source": doc, "target": aid, "dep": e["dep_kind"], "claim_changed": bool(corr and findings.get(aid) and findings[aid]["hop"] == 0 and corr["source_id"] == doc)})
    counts = {"invalidated": 0, "unaffected": 0, "needs_review": 0, "unprovable": 0}
    for f in findings.values():
        counts[f["verdict"]] += 1
    naive_count = None
    if corr:
        ev = db.q1("SELECT detail_json, summary FROM events WHERE kind='correction_applied' AND correction_id=? ORDER BY event_id DESC LIMIT 1", (correction,))
        m = re.search(r"naive (\d+)", ev["summary"]) if ev else None
        naive_count = int(m.group(1)) if m else None
    return {"nodes": nodes, "edges": edges, "correction": dict(corr) if corr else None, "counts": counts, "naive_count": naive_count}


# ------------------------------------------------------------------ corrections (the judge's red pen)
class CorrectionForm(BaseModel):
    source_id: str | None = None
    claim_id: str | None = None
    new_value: float | None = None
    new_values: dict[str, float] | None = None       # claim_id -> value (several claims of one source)
    correction_type: str = "revised_invoice"
    knowable: str = "after"                           # "before" the original artifact was made (error) | "after" (estimate)
    knowable_at: str | None = None
    note: str = ""
    correction_id: str | None = None
    dry_run: bool = False
    free_text: str | None = None


def _parse_free_text(text: str) -> dict:
    """Deterministic parse of 'the March utilities invoice is actually $80k' style edits into the structured form."""
    t = text.lower()
    amount = None
    m = re.search(r"\$?\s*([\d,]+(?:\.\d+)?)\s*(k|m)?\b", t)
    if m:
        amount = float(m.group(1).replace(",", "")) * ({"k": 1e3, "m": 1e6}.get(m.group(2) or "", 1))
    months = {"january": "01", "february": "02", "march": "03", "april": "04", "may": "05", "june": "06", "jan": "01", "feb": "02", "mar": "03", "apr": "04", "jun": "06"}
    month = next((v for k, v in months.items() if re.search(rf"\b{k}\b", t)), None)
    period = f"2026-{month}" if month else None
    line = next((li for li in ("utilities", "route_setting", "legal", "payroll_tax", "monthly_dues", "annual_release", "cash_balance", "cash_collected", "contract_price", "estimated_total_cost", "seat_price", "payable", "eurusd")
                 if li.replace("_", " ") in t or li in t), None)
    if "route" in t:
        line = "route_setting"
    gym = next((g for g, name in config.GYMS.items() if name.lower() in t), None)
    knowable = "before" if re.search(r"before|in the inbox|was in|knowable|existed", t) else "after"
    sql = "SELECT c.claim_id, c.source_id, c.line_item, c.entity, c.period_start FROM claims c WHERE c.line_item=?"
    params: list[Any] = [line]
    if period:
        sql += " AND c.period_start LIKE ?"; params.append(period + "%")
    if gym:
        sql += " AND c.entity=?"; params.append(gym)
    cands = [dict(r) for r in db.q(sql, params)] if line else []
    cands = [c for c in cands if db.claim_version_current(c["claim_id"]) is not None]
    return {"parsed": {"line_item": line, "period": period, "entity": gym, "new_value": amount, "knowable": knowable}, "candidates": cands[:8],
            "ambiguous": len(cands) != 1 or amount is None, "claim_id": cands[0]["claim_id"] if len(cands) == 1 else None, "source_id": cands[0]["source_id"] if len(cands) == 1 else None}


@router.post("/corrections/parse")
def parse_correction(form: CorrectionForm):
    return _parse_free_text(form.free_text or "")


def _snapshot_for_undo() -> None:
    UNDO_DIR.mkdir(parents=True, exist_ok=True)
    n = len(list(UNDO_DIR.glob("*.sqlite")))
    dst = UNDO_DIR / f"undo_{n:03d}.sqlite"
    src = sqlite3.connect(str(config.DB_PATH)); d = sqlite3.connect(str(dst)); src.backup(d); d.close(); src.close()


@router.post("/corrections")
def post_correction(form: CorrectionForm):
    """Structured correction: pick a claim (or several of one source), give the new value, answer 'when did this fact first exist?'."""
    if form.free_text and not (form.claim_id or form.new_values):
        parsed = _parse_free_text(form.free_text)
        if parsed["ambiguous"]:
            return JSONResponse({"needs_confirmation": True, **parsed}, status_code=200)
        form.claim_id, form.source_id, form.new_value = parsed["claim_id"], parsed["source_id"], parsed["parsed"]["new_value"]
        form.knowable = parsed["parsed"]["knowable"]
    changes: dict[str, float] = dict(form.new_values or {})
    if form.claim_id is not None and form.new_value is not None:
        changes[form.claim_id] = form.new_value
    if not changes:
        raise HTTPException(400, "give a claim_id and new_value (or new_values)")
    for cid, val in changes.items():
        if not isinstance(val, (int, float)) or abs(val) > 1e12:
            raise HTTPException(400, f"value out of range for {cid}")
    source_ids = {graph.claim_info(c)["source_id"] for c in changes if graph.claim_info(c)}
    if len(source_ids) != 1:
        raise HTTPException(400, "all claims must belong to one source document")
    source_id = source_ids.pop()
    latest = db.source_versions_all(source_id)[-1]
    body = json.loads(latest["body"])
    src = db.q1("SELECT kind FROM sources WHERE source_id=?", (source_id,))
    applied = 0
    if src["kind"] == "billing_export":
        # scale the rows of each changed (gym, line) group so their sum equals the new value
        for cid, val in changes.items():
            info = graph.claim_info(cid)
            rows = [r for r in body["rows"] if r["gym"] == info["entity"] and r["line"] == info["line_item"]]
            total = sum(r["amount"] for r in rows)
            if rows:
                for r in rows:
                    r["amount"] = round(r["amount"] * (val / total), 2) if total else val / len(rows)
                applied += 1
    else:
        for c in body.get("claims", []):
            from . import claims as CL
            cid = CL.claim_id_for(source_id, c.get("entity") or "", c["line_item"], c.get("period_start") or "", c.get("period_end") or "", c.get("unit", "USD"))
            if cid in changes:
                c["value_num"] = changes[cid]; applied += 1
    if applied == 0:
        raise HTTPException(400, "claim not found in the latest version of its document")
    body["note"] = f"Judge's edit ({form.correction_type}): {form.note or form.free_text or ''}".strip()
    n = db.q1("SELECT COUNT(*) n FROM corrections WHERE correction_id LIKE 'J%'")["n"] + 1
    cid_new = form.correction_id or f"J{n:02d}"
    kind = "error" if form.knowable == "before" else "estimate"
    if form.correction_type in ("bank_revision", "duplicate_removal", "fx_fix"):
        kind = "fact_update" if form.knowable == "after" else "error"
    if form.correction_type == "retraction":
        kind = "fact_update"
        body["claims"] = [c for c in body.get("claims", []) if c["line_item"] not in {graph.claim_info(x)["line_item"] for x in changes}]
    knowable_at = form.knowable_at or ("2026-03-31T17:00:00-07:00" if form.knowable == "before" else config.DEMO_NOW)
    tx = config.DEMO_NOW
    last = db.q1("SELECT MAX(tx_time) m FROM corrections")["m"]
    if last and last >= db.norm_ts(tx):
        from datetime import datetime, timedelta
        tx = (datetime.fromisoformat(last) + timedelta(minutes=1)).isoformat()
    if form.dry_run:
        out = corrections.apply_correction(cid_new, body=body, tx_time=tx, kind=kind, knowable_at=knowable_at, source_id=source_id, version_id=f"{source_id}@{cid_new}", note=body["note"], dry_run=True)
        out["dry_run"] = True
        return out
    _snapshot_for_undo()
    out = corrections.apply_correction(cid_new, body=body, tx_time=tx, kind=kind, knowable_at=knowable_at, source_id=source_id, version_id=f"{source_id}@{cid_new}", note=body["note"])
    out["changes"] = changes
    return out


class DryRunReq(BaseModel):
    correction_id: str


@router.post("/corrections/dry-run")
def dry_run(req: DryRunReq):
    if req.correction_id not in scenarios.CORRECTIONS:
        raise HTTPException(404, "unknown scenario")
    if db.q1("SELECT 1 FROM corrections WHERE correction_id=?", (req.correction_id,)):
        return {"already_applied": True, "findings": [dict(r) for r in db.q("SELECT * FROM impact_findings WHERE correction_id=?", (req.correction_id,))]}
    return corrections.apply_correction(req.correction_id, dry_run=True)


@router.get("/corrections")
def list_corrections():
    out = []
    for r in db.q("SELECT * FROM corrections ORDER BY tx_time"):
        d = dict(r)
        d["counts"] = {v: db.q1("SELECT COUNT(*) n FROM impact_findings WHERE correction_id=? AND verdict=?", (r["correction_id"], v))["n"] for v in ("invalidated", "unaffected", "needs_review", "unprovable")}
        d["meta"] = scenarios.CORRECTIONS.get(r["correction_id"], {})
        out.append(d)
    pending = [{"correction_id": k, **v} for k, v in scenarios.CORRECTIONS.items() if v.get("live") and not db.q1("SELECT 1 FROM corrections WHERE correction_id=?", (k,))]
    return {"applied": out, "pending": pending, "non_source_items": scenarios.NON_SOURCE_ITEMS, "types": scenarios.TYPES}


@router.get("/corrections/{correction_id}")
def get_correction(correction_id: str):
    corr = db.q1("SELECT * FROM corrections WHERE correction_id=?", (correction_id,))
    if corr is None:
        raise HTTPException(404, "not applied")
    findings = [dict(r) for r in db.q("SELECT * FROM impact_findings WHERE correction_id=? ORDER BY hop, artifact_id", (correction_id,))]
    for f in findings:
        f["reason_label"] = REASON_LABEL.get(f["reason"], f["reason"])
        a = db.artifact_current(f["artifact_id"])
        f["kind"] = a["kind"] if a else None; f["line_item"] = a["line_item"] if a else None; f["period"] = a["period"] if a else None; f["content"] = (a["content"] or "")[:200] if a else None
        f["lot"] = db.lot_code(f["artifact_id"], f["artifact_version"])
    diffs = [dict(r) for r in db.q("SELECT d.*, c.entity, c.line_item, c.period_start, cv1.value_num old_value, cv2.value_num new_value FROM claim_diffs d JOIN claims c ON c.claim_id=d.claim_id LEFT JOIN claim_versions cv1 ON cv1.claim_version_id=d.old_cv LEFT JOIN claim_versions cv2 ON cv2.claim_version_id=d.new_cv WHERE d.correction_id=? ORDER BY d.change, c.entity", (correction_id,))]
    comps = [dict(r) for r in db.q("SELECT * FROM actions WHERE run_id=?", (f"correction:{correction_id}",))]
    ev = db.q1("SELECT summary FROM events WHERE kind='correction_applied' AND correction_id=? ORDER BY event_id DESC LIMIT 1", (correction_id,))
    m = re.search(r"naive (\d+)", ev["summary"]) if ev else None
    counts = {v: sum(1 for f in findings if f["verdict"] == v) for v in ("invalidated", "unaffected", "needs_review", "unprovable")}
    return {"correction": dict(corr), "meta": scenarios.CORRECTIONS.get(correction_id, {}), "findings": findings, "diffs": diffs, "compensations": comps, "naive_count": int(m.group(1)) if m else None, "counts": counts,
            "misstatement": [dict(r) for r in db.q("SELECT * FROM misstatement_log WHERE correction_id=?", (correction_id,))]}


# ------------------------------------------------------------------ live flows, reset, undo
@router.post("/live/e11")
def live_e11():
    _snapshot_for_undo()
    return live.drop_e11()


@router.post("/live/scenario-b")
def live_scenario_b():
    _snapshot_for_undo()
    return live.scenario_b()


@router.post("/reset")
def reset():
    db.restore_snapshot(config.SNAPSHOT_PATH)
    if UNDO_DIR.exists():
        for p in UNDO_DIR.glob("*.sqlite"):
            p.unlink()
    db.get_conn()
    return {"reset": True}


@router.post("/undo")
def undo():
    snaps = sorted(UNDO_DIR.glob("*.sqlite")) if UNDO_DIR.exists() else []
    if not snaps:
        return {"undone": False, "reason": "nothing to undo"}
    last = snaps[-1]
    db.restore_snapshot(last)
    last.unlink()
    db.get_conn()
    return {"undone": True, "remaining": len(snaps) - 1}


# ------------------------------------------------------------------ approvals
class Decision(BaseModel):
    approver: str
    decision: str
    reason: str = ""


@router.get("/approvals")
def get_inbox():
    items = approvals.inbox()
    for it in items:
        it["params"] = json.loads(it["params_json"]) if it["params_json"] else {}
        it["compensator"] = json.loads(it["compensator_json"]) if it["compensator_json"] else None
        it["approver_name"] = " + ".join(approvals.ROLE_NAMES.get(r, r) for r in (it["approver_role"] or "").split("+"))
    return {"actions": items, "roles": approvals.ROLE_NAMES}


@router.post("/approvals/{action_id}")
def decide(action_id: str, d: Decision):
    try:
        apr = approvals.decide(action_id, d.approver, d.decision, d.reason, config.DEMO_NOW)
    except approvals.SelfApprovalError as e:
        raise HTTPException(409, f"segregation of duties: {e}") from e
    except KeyError:
        raise HTTPException(404, "no such action")
    out: dict[str, Any] = {"approval_id": apr, "decision": d.decision}
    if d.decision == "rejected":
        a = db.q1("SELECT params_json FROM actions WHERE action_id=?", (action_id,))
        cid = (json.loads(a["params_json"]).get("correction_id") if a and a["params_json"] else None)
        if cid:
            from . import lessons
            out["lessons"] = [l["lesson_id"] for l in lessons.signal_rejection(cid, action_id, d.approver, d.reason, config.DEMO_NOW)]
    if d.decision == "approved":
        try:
            out["execution"] = corrections.execute_action(action_id, config.DEMO_NOW)
        except PermissionError as e:
            out["execution"] = {"executed": False, "error": str(e)}
    return out


@router.get("/fence/{action_id}")
def fence_check(action_id: str):
    a = db.q1("SELECT * FROM actions WHERE action_id=?", (action_id,))
    if a is None:
        raise HTTPException(404, "no such action")
    return {"action_id": action_id, "stale": fence.check(a["artifact_id"])}


# ------------------------------------------------------------------ Jade and the lessons memory
@router.get("/evaluations")
def list_evaluations():
    from . import review
    return {"evaluations": [{k: e[k] for k in ("correction_id", "ts", "playbook_version", "headline", "recalled")} | {"summary": e["jade"].get("summary")} for e in review.load_all()]}


@router.get("/evaluations/{correction_id}")
def get_evaluation(correction_id: str):
    from . import review
    ev = review.load(correction_id)
    if ev is None:
        raise HTTPException(404, "no evaluation for that correction")
    return ev


@router.get("/lessons")
def get_lessons():
    from . import lessons
    return {"lessons": lessons.all_lessons(), "playbook": lessons.playbook(), "events": [dict(r) for r in db.q("SELECT * FROM lesson_events ORDER BY seq")]}


@router.get("/playbook")
def get_playbook():
    from . import lessons
    return lessons.playbook()


class LessonDecision(BaseModel):
    approver: str


@router.post("/lessons/{lesson_id}/gate")
def run_gate(lesson_id: str):
    from . import lessons
    try:
        return lessons.gate(lesson_id)
    except KeyError:
        raise HTTPException(404, "no such lesson")


@router.post("/lessons/approve-pending")
def approve_pending_lessons(d: LessonDecision):
    from . import lessons
    try:
        out = lessons.approve_pending(d.approver, _live_ts())
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e
    return {"lessons": out, "playbook": lessons.playbook()}


@router.post("/lessons/{lesson_id}/approve")
def approve_lesson(lesson_id: str, d: LessonDecision):
    from . import lessons
    try:
        return lessons.approve(lesson_id, d.approver, _live_ts())
    except KeyError:
        raise HTTPException(404, "no such lesson")
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e


def _live_ts() -> str:
    """Live decisions happen after the newest event on the clock, so a lesson never applies backwards to the case it came from."""
    last = db.q1("SELECT MAX(ts) t FROM events")
    t = (last["t"] if last and last["t"] else db.norm_ts(config.DEMO_NOW))
    return max(t, db.norm_ts(config.DEMO_NOW))


# ------------------------------------------------------------------ norms
@router.get("/norms")
def get_norms():
    return {"norms": norms.list_norms(), "deny_list": norms.DENY_LIST, "min_sample": norms.MIN_SAMPLE, "max_factor": norms.MAX_FACTOR}


@router.post("/norms/{norm_id}/approve")
def approve_norm(norm_id: str, d: Decision):
    if d.decision != "approved":
        return {"norm_id": norm_id, "decision": d.decision}
    doc = norms.approve(norm_id, d.approver, config.DEMO_NOW)
    return {"norm_id": norm_id, "approved": True, "doc_id": doc, "valid_from": config.DEMO_NOW[:10]}


# ------------------------------------------------------------------ events, ledger, misstatements, runs
@router.get("/events")
def events(limit: int = 300):
    rows = db.q("SELECT * FROM events ORDER BY ts DESC, event_id DESC LIMIT ?", (limit,))
    out = []
    for r in rows:
        d = dict(r); d["detail"] = json.loads(d["detail_json"]) if d["detail_json"] else None; d.pop("detail_json", None); out.append(d)
    return {"events": out}


@router.get("/ledger")
def ledger_view(limit: int = 400):
    rows = [dict(r) for r in db.q("SELECT * FROM ledger_entries ORDER BY ts, tx_id, line LIMIT ?", (limit,))]
    return {"entries": rows, "unbalanced": ledger.all_balanced(), "locked_periods": [dict(r) for r in db.q("SELECT * FROM periods")]}


@router.get("/misstatement-log")
def misstatements():
    return {"entries": [dict(r) for r in db.q("SELECT * FROM misstatement_log ORDER BY ts")], "aggregate_q2": M.aggregate_unbooked("2026-0"), "thresholds": M.memo()}


@router.get("/runs")
def runs():
    return {"runs": [dict(r) for r in db.q("SELECT * FROM runs ORDER BY pinned_at")]}


# ------------------------------------------------------------------ Memento helpers for the scrubber and the judge doors
@router.get("/timemap/{doc_id}")
def timemap(doc_id: str):
    rows = db.source_versions_all(doc_id)
    if not rows:
        raise HTTPException(404, "no such source")
    src = db.q1("SELECT * FROM sources WHERE source_id=?", (doc_id,))
    return {"doc_id": doc_id, "title": src["title"], "versions": [{"version_id": r["version_id"], "tx_from": r["tx_from"], "document_date": r["document_date"], "correction_id": r["correction_id"], "supersedes": r["supersedes"]} for r in rows]}


@router.get("/sources")
def sources():
    out = []
    for s in db.q("SELECT * FROM sources ORDER BY system, source_id"):
        vs = db.source_versions_all(s["source_id"])
        out.append({**dict(s), "versions": [{"version_id": v["version_id"], "tx_from": v["tx_from"], "correction_id": v["correction_id"]} for v in vs]})
    return {"sources": out}


@router.get("/memento/{doc_id}")
def memento_as_of(doc_id: str, at: str, request: Request):
    """Scrubber read: the document as of `at` under the pinning profile (403/404 problem bodies pass through)."""
    from fastapi.testclient import TestClient
    from .main import app
    c = TestClient(app)
    r = c.get(f"/r/{doc_id}", headers={"X-Trackback-Pin": at})
    body = r.json()
    if r.status_code == 200:
        body["memento_datetime_http"] = r.headers.get("Memento-Datetime")
        body["pinned_at_http"] = r.headers.get(config.PIN_HEADER)
        body["text"] = _render(body["body"])
    return JSONResponse({"status": r.status_code, "problem": body if r.status_code != 200 else None, "memento": body if r.status_code == 200 else None, "pinned_at": r.headers.get(config.PIN_HEADER)}, status_code=200)


def _render(body: dict) -> str:
    from . import claims as CL
    return CL.render_text(body)


class CheatReq(BaseModel):
    doc_id: str
    pin: str = "2026-04-10T17:00:00-07:00"
    version_id: str | None = None


@router.post("/cheat")
def cheat(req: CheatReq):
    """Door 3: 'Feed it tomorrow's news'. Try to read a later version under an earlier pin; the resolver refuses with both timestamps."""
    from fastapi.testclient import TestClient
    from .main import app
    from .memento import ts14
    c = TestClient(app)
    versions = db.source_versions_all(req.doc_id)
    if not versions:
        raise HTTPException(404, "no such document")
    target = next((v for v in versions if v["version_id"] == req.version_id), versions[-1])
    r = c.get(f"/m/{req.doc_id}/{ts14(target['tx_from'])}", headers={"X-Trackback-Pin": req.pin})
    doc = db.q1("SELECT * FROM sources WHERE source_id=?", (req.doc_id,))
    return {"doc_id": req.doc_id, "title": doc["title"], "document_date": target["document_date"], "version_id": target["version_id"], "memento_datetime": target["tx_from"],
            "pin": db.norm_ts(req.pin), "status": r.status_code, "refused": r.status_code in (403, 404), "problem": r.json() if r.status_code != 200 else None,
            "pinned_at_header": r.headers.get(config.PIN_HEADER), "served": r.status_code == 200}


@router.get("/actions/executed")
def executed_actions():
    rows = db.q("SELECT * FROM actions WHERE executed_at IS NOT NULL ORDER BY executed_at")
    out = []
    for r in rows:
        d = dict(r); d["params"] = json.loads(d["params_json"]) if d["params_json"] else {}; d.pop("params_json", None); d.pop("compensator_json", None)
        art = db.q1("SELECT pinned_at, run_id FROM artifacts WHERE artifact_id=? ORDER BY version LIMIT 1", (r["artifact_id"],))
        d["pinned_at"] = art["pinned_at"] if art else None
        out.append(d)
    return {"actions": out}


@router.get("/actions/{action_id}/decision")
def decision_inputs(action_id: str):
    """Door 2: 'Why did you do this on that date?' The decision's inputs exactly as of its pin: lot codes, versions, values."""
    a = db.q1("SELECT * FROM actions WHERE action_id=?", (action_id,))
    if a is None:
        raise HTTPException(404, "no such action")
    art = db.q1("SELECT * FROM artifacts WHERE artifact_id=? ORDER BY version LIMIT 1", (a["artifact_id"],))
    run = db.q1("SELECT * FROM runs WHERE run_id=?", (art["run_id"],))
    inputs = []
    seen = set()
    stack = [(a["artifact_id"], art["version"], 0)]
    while stack:
        aid, ver, depth = stack.pop()
        if (aid, ver) in seen or depth > 4:
            continue
        seen.add((aid, ver))
        for e in graph.supporters_of(aid, ver):
            if e["supporter_kind"] == "claim":
                cv = db.q1("SELECT cv.*, c.entity, c.line_item, c.period_start, c.source_id FROM claim_versions cv JOIN claims c ON c.claim_id=cv.claim_id WHERE cv.claim_version_id=?", (e["supporter_version"],))
                if cv:
                    inputs.append({"kind": "claim", "id": e["supporter_id"], "version": e["supporter_version"], "lot": db.lot_code(e["supporter_id"], e["supporter_version"]), "label": f"{cv['line_item']} {cv['entity'] or ''} {(cv['period_start'] or '')[:7]}".strip(),
                                   "value": cv["value_num"], "text": cv["value_text"], "source_id": cv["source_id"], "memento_datetime": cv["tx_from"], "depth": depth, "current": cv["tx_to"] == config.TX_CURRENT})
            else:
                s = db.q1("SELECT * FROM artifacts WHERE artifact_id=? AND version=?", (e["supporter_id"], int(e["supporter_version"])))
                if s:
                    inputs.append({"kind": "artifact", "id": e["supporter_id"], "version": e["supporter_version"], "lot": db.lot_code(e["supporter_id"], e["supporter_version"]), "label": s["line_item"], "value": s["value_num"],
                                   "text": (s["content"] or "")[:120], "depth": depth, "current": db.artifact_current(e["supporter_id"])["version"] == s["version"]})
                    stack.append((e["supporter_id"], int(e["supporter_version"]), depth + 1))
    reads = [dict(r) for r in db.q("SELECT * FROM reads WHERE run_id=? ORDER BY ts", (art["run_id"],))]
    expl = db.q1("SELECT content FROM artifacts WHERE run_id=? AND kind='sentence' ORDER BY version LIMIT 1", (art["run_id"],))
    return {"action": dict(a), "artifact": graph.artifact_dict(art), "run": dict(run) if run else None, "pinned_at": art["pinned_at"], "inputs": inputs, "reads": reads,
            "explanation": expl["content"] if expl else None, "approvals": [dict(r) for r in db.q("SELECT * FROM approvals WHERE action_id=? ORDER BY ts", (action_id,))]}


# ------------------------------------------------------------------ proof
@router.get("/eval")
def eval_latest():
    if not config.EVAL_PATH.exists():
        raise HTTPException(404, "run make eval")
    return json.loads(config.EVAL_PATH.read_text())


@router.get("/eval_v2")
def eval_v2_latest():
    p = config.DATA_DIR / "eval" / "latest_v2.json"
    if not p.exists():
        raise HTTPException(404, "run backend/scripts/eval_v2.py")
    out = json.loads(p.read_text())
    # who wrote the cached model responses this world runs on (real model vs scripted stand-in vs offline fallback)
    rows = db.q("SELECT CASE WHEN model LIKE 'scripted:%' THEN 'scripted' WHEN model LIKE 'fallback:%' THEN 'fallback' ELSE 'real' END AS who, COUNT(*) n FROM llm_cache GROUP BY 1")
    out["cache_rows"] = {r["who"]: r["n"] for r in rows}
    runs = db.q("SELECT run_id, model FROM runs") if db.q1("SELECT 1 FROM sqlite_master WHERE name='runs'") else []
    out["runs_by_provider"] = {}
    for r in runs:
        who = "scripted" if str(r["model"] or "").startswith("scripted:") else "real"
        out["runs_by_provider"][who] = out["runs_by_provider"].get(who, 0) + 1
    return out


@router.get("/realworld/lyft")
def realworld_lyft():
    """Everything the Real world page shows: inside the finance team (reconstruction, with Trackback) and the outside world (real release,
    real correction, reconstructed dependents)."""
    import re
    from trackback.realworld import lyft as L
    def art(aid):
        r = db.artifact_current(aid)
        return graph.artifact_dict(r) if r else None
    model = art("lyft_margin_expansion_bps"); draft = art("lyft_s_outlook_margin"); script = art("lyft_s_call_script_margin")
    fence_ev = db.q1("SELECT * FROM events WHERE kind='fence_block' AND summary LIKE '%ACT-lyft_publish_release%' ORDER BY ts DESC LIMIT 1")
    detail = json.loads(fence_ev["detail_json"]) if fence_ev and fence_ev["detail_json"] else {}
    mism = next((x for x in detail.get("stale", []) if x.get("problem") == "figure_mismatch"), None)
    fix = None
    if draft and mism:
        fix = re.sub(r"(?<![\d.])" + re.escape(f"{mism['stated']:g}") + r"(?!\.?\d)", f"{mism['cited_value']:g}", draft["content"], count=1)
    actions = {a["action_id"]: dict(a) for a in db.q("SELECT action_id, kind, state, approver_role FROM actions WHERE action_id LIKE 'ACT-lyft%' OR action_id LIKE 'COMP-ACT-lyft%'")}
    appr = db.q1("SELECT approver, ts AS decided_at FROM approvals WHERE action_id='ACT-lyft_publish_release' AND decision='approved' ORDER BY ts LIMIT 1")
    inside = {"model": model, "draft": draft, "call_script": script, "fence": {"blocked": bool(fence_ev), "ts": fence_ev["ts"] if fence_ev else None, "mismatch": mism, "fix": fix},
              "approval": dict(appr) if appr else None, "actions": {k: v for k, v in actions.items() if not k.startswith("COMP-") and "_ext_" not in k}}
    try:
        corr = get_correction(L.CORR)
    except HTTPException:
        corr = None
    pings = [dict(r) for r in db.q("SELECT ping_id, target_agent_id, state, created_at, responded_at FROM pings WHERE correction_id=? ORDER BY created_at", (L.CORR,))]
    comps = [v for k, v in actions.items() if k.startswith("COMP-")]
    tl = [{"t": L.TAPE["release_filed"], "real": True, "what": "Release furnished on Form 8-K, Exhibit 99.1: 'approximately 500 basis points'"},
          {"t": "2024-02-13T16:15:00-05:00", "real": False, "what": "Newsroom publishes the headline on the 500 (reconstruction)"},
          {"t": "2024-02-13T16:20:00-05:00", "real": False, "what": "Sell-side flash note: 6.6% margin, ~$1.05B Adjusted EBITDA implied; 200,000-share buy filled 16:25 (reconstruction)"},
          {"t": L.TAPE["call_start"], "real": True, "what": "Earnings call. CFO: 'This is actually a correction from the press release ... 50 basis points.'"},
          {"t": "2024-02-13T17:00:00-05:00", "real": True, "what": "CORRECTING and REPLACING release; Trackback receives the correction (this is where the ripple below starts)"},
          {"t": "2024-02-13T17:52:00-05:00", "real": True, "what": f"Stock had been up as much as {L.TAPE['after_hours_peak_pct']}% after hours; +{L.TAPE['at_1752_pct']}% at 5:52 pm"},
          {"t": "2024-02-14T16:00:00-05:00", "real": True, "what": f"Next close: +{L.TAPE['next_close_pct']}% at ${L.TAPE['next_close_px']:.2f} (the quarter itself was good)"}]
    return {"inside": inside, "outside": {"correction": corr, "pings": pings, "compensations": comps, "timeline": tl, "tape": L.TAPE, "facts": L.FACTS}}


@router.get("/answer-key")
def answer_key():
    import yaml
    k = yaml.safe_load(config.ANSWER_KEY_PATH.read_text())
    import hashlib
    return {"sha256": hashlib.sha256(config.ANSWER_KEY_PATH.read_bytes()).hexdigest(), "frozen": k.get("frozen"), "n_corrections": len(k["corrections"]), "decoys": k.get("decoy_categories"),
            "changelog": (config.ANSWER_KEY_PATH.parent / "CHANGELOG.md").read_text() if (config.ANSWER_KEY_PATH.parent / "CHANGELOG.md").exists() else ""}


@router.get("/claims/search")
def claims_search(q: str = "", source_id: str | None = None, limit: int = 40):
    qs = f"%{q.lower()}%"
    sql = ("SELECT c.claim_id, c.source_id, c.entity, c.line_item, c.period_start, c.period_end, c.unit, cv.value_num, cv.value_text, cv.claim_version_id, s.title FROM claims c "
           "JOIN claim_versions cv ON cv.claim_id=c.claim_id AND cv.tx_to=? JOIN sources s ON s.source_id=c.source_id WHERE (LOWER(c.line_item) LIKE ? OR LOWER(c.entity) LIKE ? OR LOWER(s.title) LIKE ?)")
    params: list[Any] = [config.TX_CURRENT, qs, qs, qs]
    if source_id:
        sql += " AND c.source_id=?"; params.append(source_id)
    sql += " ORDER BY c.source_id, c.line_item, c.period_start LIMIT ?"; params.append(limit)
    return {"claims": [dict(r) for r in db.q(sql, params)]}
