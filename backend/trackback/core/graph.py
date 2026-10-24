"""Artifact and justification helpers: the claim graph's write side and common reads."""
from __future__ import annotations

import json
import uuid
from typing import Any

from .. import config
from . import db


NODE_KIND = {"number": "calc", "forecast_cell": "calc", "sentence": "prose", "action": "action", "judgment": "judgment"}


def content_hash(value_num: float | None, content: str | None, conclusions: dict | None = None) -> str:
    import hashlib
    return hashlib.sha256(db.dumps({"v": value_num, "c": content or "", "k": conclusions or {}}).encode()).hexdigest()[:16]


def new_artifact(*, artifact_id: str, kind: str, run_id: str, pinned_at: str, period: str | None, line_item: str | None,
                 content: str | None, value_num: float | None, formula: dict | None, conclusions: dict | None,
                 status: str = "valid", tx_from: str | None = None, version: int | None = None,
                 agent_id: str | None = None, origin: str = "initial", reason: str | None = None, approved_by: str | None = None,
                 metric: str | None = None, fields: dict | None = None, node_kind: str | None = None) -> int:
    cur = db.artifact_current(artifact_id)
    v = version or ((cur["version"] + 1) if cur is not None else 1)
    if agent_id is None:
        r = db.q1("SELECT agent FROM runs WHERE run_id=?", (run_id,))
        agent_id = r["agent"] if r else ("trackback" if run_id.startswith("correction:") else None)
    db.insert("artifacts", {"artifact_id": artifact_id, "version": v, "kind": kind, "run_id": run_id, "pinned_at": pinned_at,
                            "period": period, "line_item": line_item, "content": content, "value_num": value_num,
                            "formula": db.dumps(formula) if formula else None, "conclusions_json": db.dumps(conclusions) if conclusions else None,
                            "status": status, "tx_from": db.norm_ts(tx_from or pinned_at), "tx_to": config.TX_CURRENT,
                            "agent_id": agent_id, "node_kind": node_kind or NODE_KIND.get(kind, kind), "origin": origin,
                            "supersedes_version": cur["version"] if cur is not None else None, "content_hash": content_hash(value_num, content, conclusions),
                            "reason": reason, "approved_by": approved_by, "metric": metric or line_item, "fields_json": db.dumps(fields) if fields else None})
    return v


def add_receipt(*, consumer_id: str, consumer_version: int, consumed_id: str, consumed_version: int, fields_read: list[str],
                run_id: str, agent_id: str | None, ts: str) -> str:
    """A consumption receipt: the verified link TrackBack never had. Pings only travel along receipts whose hashes match."""
    row = db.q1("SELECT content_hash, value_num, content FROM artifacts WHERE artifact_id=? AND version=?", (consumed_id, int(consumed_version)))
    sha = (row["content_hash"] if row and row["content_hash"] else (content_hash(row["value_num"], row["content"]) if row else None))
    rid = "rcpt_" + db.hid(consumer_id, consumer_version, consumed_id, consumed_version)
    if db.q1("SELECT 1 FROM consumption_receipts WHERE receipt_id=?", (rid,)):
        return rid
    db.insert("consumption_receipts", {"receipt_id": rid, "consumer_artifact_id": consumer_id, "consumer_version": consumer_version, "consumed_artifact_id": consumed_id,
                                       "consumed_version": int(consumed_version), "consumed_sha256": sha, "fields_read_json": db.dumps(sorted(set(fields_read))),
                                       "run_id": run_id, "agent_id": agent_id, "ts": db.norm_ts(ts)})
    return rid


def receipts_for_consumed(artifact_id: str, version: int | None = None) -> list[dict]:
    if version is None:
        return [dict(r) for r in db.q("SELECT * FROM consumption_receipts WHERE consumed_artifact_id=?", (artifact_id,))]
    return [dict(r) for r in db.q("SELECT * FROM consumption_receipts WHERE consumed_artifact_id=? AND consumed_version=?", (artifact_id, version))]


def receipts_for_consumer(artifact_id: str, version: int) -> list[dict]:
    return [dict(r) for r in db.q("SELECT * FROM consumption_receipts WHERE consumer_artifact_id=? AND consumer_version=?", (artifact_id, version))]


def add_edge(*, consumer_id: str, consumer_version: int, supporter_kind: str, supporter_id: str, supporter_version: str,
             dep_kind: str, capture: str, predicate: str | None = None) -> str:
    edge_id = "e_" + db.hid(consumer_id, consumer_version, supporter_kind, supporter_id, supporter_version, dep_kind)
    if db.q1("SELECT 1 FROM justifications WHERE edge_id=?", (edge_id,)):
        return edge_id
    db.insert("justifications", {"edge_id": edge_id, "consumer_id": consumer_id, "consumer_version": consumer_version,
                                 "supporter_kind": supporter_kind, "supporter_id": supporter_id, "supporter_version": supporter_version,
                                 "dep_kind": dep_kind, "capture": capture, "validity_predicate": predicate})
    if supporter_kind == "artifact" and dep_kind != "control":
        # the receipt is the verified link a ping may travel along; every artifact edge has one, whoever wrote the version
        c = db.q1("SELECT run_id, agent_id, tx_from FROM artifacts WHERE artifact_id=? AND version=?", (consumer_id, consumer_version))
        try:
            add_receipt(consumer_id=consumer_id, consumer_version=consumer_version, consumed_id=supporter_id, consumed_version=int(supporter_version),
                        fields_read=["value" if dep_kind == "numeric" else "content"], run_id=c["run_id"] if c else "", agent_id=c["agent_id"] if c else None, ts=c["tx_from"] if c else config.DEMO_NOW)
        except (TypeError, ValueError):
            pass
    return edge_id


def set_status(artifact_id: str, version: int, status: str, ts: str, note: str = "") -> None:
    db.get_conn().execute("UPDATE artifacts SET status=? WHERE artifact_id=? AND version=?", (status, artifact_id, version))
    db.log_event("artifact_status", f"{artifact_id} v{version} -> {status}{(': ' + note) if note else ''}", ts=ts)


def supporters_of(artifact_id: str, version: int) -> list[dict]:
    return [dict(r) for r in db.q("SELECT * FROM justifications WHERE consumer_id=? AND consumer_version=?", (artifact_id, version))]


def consumers_of_claim_version(cv_id: str) -> list[dict]:
    return [dict(r) for r in db.q("SELECT * FROM justifications WHERE supporter_kind='claim' AND supporter_version=?", (cv_id,))]


def consumers_of_artifact(artifact_id: str, version: int | None = None) -> list[dict]:
    if version is None:
        return [dict(r) for r in db.q("SELECT * FROM justifications WHERE supporter_kind='artifact' AND supporter_id=?", (artifact_id,))]
    return [dict(r) for r in db.q("SELECT * FROM justifications WHERE supporter_kind='artifact' AND supporter_id=? AND supporter_version=?", (artifact_id, str(version)))]


def artifact_dict(row) -> dict[str, Any]:
    d = dict(row)
    d["formula"] = json.loads(d["formula"]) if d.get("formula") else None
    d["conclusions"] = json.loads(d["conclusions_json"]) if d.get("conclusions_json") else None
    d["fields"] = json.loads(d["fields_json"]) if d.get("fields_json") else None
    d["lot"] = db.lot_code(d["artifact_id"], d["version"])
    return d


def claim_value(cv_id: str) -> float | None:
    r = db.q1("SELECT value_num FROM claim_versions WHERE claim_version_id=?", (cv_id,))
    return None if r is None else r["value_num"]


def claim_info(claim_id: str) -> dict | None:
    r = db.q1("SELECT * FROM claims WHERE claim_id=?", (claim_id,))
    return dict(r) if r else None


def new_action(*, action_id: str, artifact_id: str, kind: str, params: dict, run_id: str, proposer: str, approver_role: str,
               created_at: str, state: str = "proposed") -> None:
    db.insert("actions", {"action_id": action_id, "artifact_id": artifact_id, "kind": kind, "params_json": db.dumps(params), "ledger_tx_id": None,
                          "executed_at": None, "compensator_json": None, "state": state, "run_id": run_id, "proposer": proposer,
                          "approver_role": approver_role, "created_at": db.norm_ts(created_at)})


def set_action_state(action_id: str, state: str, ts: str, *, ledger_tx_id: str | None = None, executed_at: str | None = None,
                     compensator: dict | None = None) -> None:
    conn = db.get_conn()
    sets, params = ["state=?"], [state]
    if ledger_tx_id:
        sets.append("ledger_tx_id=?"); params.append(ledger_tx_id)
    if executed_at:
        sets.append("executed_at=?"); params.append(db.norm_ts(executed_at))
    if compensator is not None:
        sets.append("compensator_json=?"); params.append(db.dumps(compensator))
    params.append(action_id)
    conn.execute(f"UPDATE actions SET {', '.join(sets)} WHERE action_id=?", params)
    db.log_event("action_state", f"{action_id} -> {state}", ts=ts, detail={"action_id": action_id, "state": state})
