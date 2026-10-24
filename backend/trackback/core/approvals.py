"""Approvals inbox. Segregation of duties is enforced by the schema CHECK (proposer <> approver)."""
from __future__ import annotations

import sqlite3
import uuid

from .. import config
from . import db

ROLE_NAMES = {
    "controller": f"{config.PEOPLE['controller']} (Controller)",
    "cfo": f"{config.PEOPLE['cfo']} (CFO)",
    "ap": f"{config.PEOPLE['ap']} (AP Specialist)",
    "vp_sales": f"{config.PEOPLE['vp_sales']} (VP Sales)",
    "hr": f"{config.PEOPLE['hr']} (HR)",
}


class SelfApprovalError(Exception):
    pass


def decide(action_id: str, approver: str, decision: str, reason: str, ts: str) -> str:
    """Record a decision. Raises SelfApprovalError if the proposer tries to approve its own action."""
    action = db.q1("SELECT * FROM actions WHERE action_id=?", (action_id,))
    if action is None:
        raise KeyError(action_id)
    approval_id = f"APR-{uuid.uuid4().hex[:8]}"
    try:
        db.insert("approvals", {"approval_id": approval_id, "action_id": action_id, "proposer": action["proposer"],
                                "approver": approver, "decision": decision, "reason": reason, "ts": ts})
    except sqlite3.IntegrityError as e:
        db.log_event("sod_violation", f"Rejected by schema: proposer and approver are both '{approver}' on {action_id}",
                     actor="sqlite CHECK(proposer <> approver)", ts=ts, detail={"error": str(e), "action_id": action_id})
        db.commit()
        raise SelfApprovalError(str(e)) from e
    new_state = {"approved": "approved", "rejected": "rejected"}[decision]
    db.get_conn().execute("UPDATE actions SET state=? WHERE action_id=?", (new_state, action_id))
    db.log_event("approval", f"{approver} {decision} {action_id}: {reason}", actor=approver, ts=ts,
                 detail={"action_id": action_id, "approval_id": approval_id})
    db.commit()
    return approval_id


def inbox(state: str | None = None) -> list[dict]:
    sql = "SELECT a.*, (SELECT COUNT(*) FROM approvals p WHERE p.action_id=a.action_id) n_decisions FROM actions a"
    rows = db.q(sql + (" WHERE a.state=?" if state else "") + " ORDER BY a.created_at", (state,) if state else ())
    out = []
    for r in rows:
        d = dict(r)
        d["approvals"] = [dict(x) for x in db.q("SELECT * FROM approvals WHERE action_id=? ORDER BY ts", (r["action_id"],))]
        out.append(d)
    return out
