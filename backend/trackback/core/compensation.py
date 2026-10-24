"""Fixed compensation menu. Every item has a named approver role who is not the preparer. Never auto-executes."""
from __future__ import annotations

import json
import uuid

from .. import config
from . import db, graph

from .domain import get_domain


def propose(correction_id: str, action_row, finding: dict, ts: str) -> dict | None:
    """Build the compensator for an executed action whose supporters were invalidated. Returns the compensation action dict."""
    spec = get_domain().compensation_for(dict(action_row))
    if not spec:
        return None
    comp_kind, approver, desc = spec["kind"], spec["approver"], spec["description"]
    old_v, new_v = finding.get("old_value"), finding.get("new_value")
    delta = finding.get("delta")
    if delta is None:
        delta = (new_v - old_v) if (old_v is not None and new_v is not None) else None
    params = {"summary": desc, "compensates": action_row["action_id"], "correction_id": correction_id, "old_value": old_v, "new_value": new_v, "delta": delta}
    if comp_kind in ("offset_next_bonus", "offset_next_commission", "reduce_next_installment") and delta is not None:
        params["amount"] = round(-delta, 2)  # overpayment to recover
        params["summary"] = f"{desc}: ${-delta:,.2f}"
    if comp_kind == "corrected_certificate" and new_v is not None:
        params["summary"] = f"{desc}. Recomputed ratio {new_v:.3f}x"
    comp_id = f"COMP-{action_row['action_id']}-{correction_id}"
    if db.q1("SELECT 1 FROM actions WHERE action_id=?", (comp_id,)):
        return {"action_id": comp_id, "kind": comp_kind, "existing": True}
    art_id = f"comp_{action_row['artifact_id']}_{correction_id}"
    v = graph.new_artifact(artifact_id=art_id, kind="action", run_id=f"correction:{correction_id}", pinned_at=ts, period=None, line_item=comp_kind,
                           content=params["summary"], value_num=params.get("amount"), formula=None, conclusions=None, status="valid", tx_from=ts)
    graph.add_edge(consumer_id=art_id, consumer_version=v, supporter_kind="artifact", supporter_id=action_row["artifact_id"],
                   supporter_version=str(finding.get("artifact_version", 1)), dep_kind="control", capture="structured")
    graph.new_action(action_id=comp_id, artifact_id=art_id, kind=comp_kind, params=params, run_id=f"correction:{correction_id}", proposer="trackback:engine",
                     approver_role=approver, created_at=ts, state="proposed")
    graph.set_action_state(action_row["action_id"], "compensation_proposed", ts, compensator={"action_id": comp_id, "kind": comp_kind, "approver": approver, **params})
    db.log_event("compensation", f"{comp_kind} proposed for {action_row['action_id']} ({correction_id}); approver {approver}", actor="trackback:engine", ts=ts, correction_id=correction_id,
                 detail={"compensation_id": comp_id, "params": params})
    return {"action_id": comp_id, "kind": comp_kind, "approver": approver, "params": params}
