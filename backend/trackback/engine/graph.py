"""The context graph and the ripple (SPEC.md Section 6.5), plus the iteration-2 hand-off: what each owner must look at.

Nodes: the correction, ledger slices, metrics, traced items in files, agents' own work products, and executed actions.

For a correction (balanced adjusting lines with orig_period):
1. Reach: seeds are metrics with a slice that `touches` a correction line; then everything downstream. Anything not reached is cleared
   structurally with no recompute (not_consumed, different_line_item, policy).
2. Recompute: before and after (Books(as_of=snapshot) vs the same plus the correction) for each snapshot artifacts were built from.
   Metrics whose value does not move are early cutoffs.
3. Verdicts with reasons: value_changed, conclusion_flipped, stale_and_value_changed, input_changed, display_unchanged, value_unchanged,
   conclusion_unchanged, not_consumed, different_line_item, policy, inputs_unchanged, unlinked.
4. Actions: an amount change gives the over- or underpayment and the compensation; a status flip on the certificate gives the lender
   compensation.
5. Agent work products whose inputs moved materially come back `suspect`: the hub pings their owner (one ping per owner per wave).
6. The naive source-level baseline: everything that reads any corrected account, in any period or scope, plus every action.
"""
from __future__ import annotations

import time
from typing import Any

from .. import config as C
from .books import Books, MetricLibrary, conclusion_state

COMPENSATIONS = {
    "corrected_certificate_and_lender_notice": {"title": "Corrected compliance certificate and lender notice (credit agreement correction clause)", "approver": "sam"},
    "offset_next_bonus": {"title": "Offset the overpayment against the Q2 bonus (plan terms; no ad-hoc payroll deductions)", "approver": "lena"},
    "reduce_next_installment": {"title": "Reduce the Q3 estimated tax installment by the overpayment", "approver": "dana"},
    "redraft": {"title": "Re-draft from the corrected inputs", "approver": None},
    "correction_note": {"title": "Publish a correction note", "approver": "editor"},
    "unwind_order": {"title": "Review the filled order with the PM (unwind or hold)", "approver": "pm"},
    "correcting_release": {"title": "CORRECTING and REPLACING release and 8-K exhibit", "approver": "cfo"},
}


def _region(entity: str) -> str | None:
    return C.GYM_REGION.get(entity)


def _leaves(lib: MetricLibrary, mid: str, seen=None) -> list:
    seen = seen if seen is not None else set()
    if mid in seen:
        return []
    seen.add(mid)
    m = lib.metrics[mid]
    out = list(m.slices.values())
    for d in m.deps:
        out += _leaves(lib, d, seen)
    return out


def structural_reason(lib: MetricLibrary, mid: str, lines: list[dict]) -> str:
    m = lib.metrics.get(mid)
    if m is None:
        return "different_line_item"
    if m.family == "policy":
        return "policy"
    overlap = period_miss = scope_miss = False
    for s in _leaves(lib, mid):
        for l in lines:
            if l["account"] not in s.accounts:
                continue
            overlap = True
            per = l.get("orig_period") or l["period"]
            if (per > s.periods[-1]) if s.balance else (per not in s.periods):
                period_miss = True
            elif s.scope != "company":
                scope_miss = True
    if scope_miss:
        return "not_consumed"
    if overlap and period_miss:
        return "different_period"
    return "different_line_item"


def material_change(unit: str, old, new, conclusion_moved: bool) -> bool:
    if conclusion_moved:
        return True
    if isinstance(old, str) or isinstance(new, str):
        return old != new
    if old is None or new is None:
        return True
    d = abs(new - old)
    if unit == "ratio":
        return d >= 0.005
    if unit == "pct":
        return d >= 0.05
    return d >= max(C.MATERIALITY_V3["clearly_trivial"], 0.01 * abs(old))


def ripple(*, correction: dict, lib: MetricLibrary, entries: list[dict], snapshots: dict[str, str], links: list[dict], actions: list[dict],
           agent_nodes: list[dict] | None = None, compensations: dict | None = None) -> dict[str, Any]:
    """correction: {id, title, lines:[{entity, account, amount_cents, orig_period}]}; links: trace links; actions: executed actions;
    agent_nodes: [{id, owner, kind, label, consumes:[metric ids], snapshot, content}]."""
    t0 = time.time()
    comps = {**COMPENSATIONS, **(compensations or {})}
    lines = correction["lines"]
    seeds = {mid for mid, m in lib.metrics.items() if m.slices and any(m.touches(l["account"], l.get("orig_period") or l["period"], _region(l["entity"]), l["entity"]) for l in lines)}
    reached = lib.downstream(seeds)
    used_snaps = {l.get("snapshot") or "close" for l in links} | {"close"} | {n.get("snapshot", "close") for n in (agent_nodes or [])}
    before = {s: lib.evaluate(Books(entries, snapshots[s])) for s in used_snaps}
    after = {s: lib.evaluate(Books(entries, snapshots[s], lines)) for s in used_snaps}
    depth = lib.depth()

    def moved(mid: str, snap: str) -> bool:
        b, a = before[snap].get(mid), after[snap].get(mid)
        if isinstance(b, str) or isinstance(a, str):
            return b != a
        return b is not None and a is not None and abs(a - b) > 0.005

    metrics_out = {}
    for mid in sorted(reached, key=lambda x: (depth[x], x)):
        m = lib.metrics[mid]
        b, a = before["close"].get(mid), after["close"].get(mid)
        ch = moved(mid, "close")
        cb, ca = conclusion_state(m, b), conclusion_state(m, a)
        metrics_out[mid] = {"label": m.label, "unit": m.unit, "old": b, "new": a, "changed": ch, "seed": mid in seeds, "depth": depth[mid],
                            "conclusion_old": cb, "conclusion_new": ca, "reason": ("conclusion_flipped" if cb != ca else "value_changed") if ch else "early_cutoff"}

    def metric_vals(mid: str, snap: str):
        if mid.startswith("sum:"):
            parts = mid[4:].split("+")
            return sum(before[snap][p] for p in parts), sum(after[snap][p] for p in parts), any(p in reached for p in parts), parts
        return before[snap].get(mid), after[snap].get(mid), mid in reached, [mid]

    items: dict[str, dict] = {}
    by_id = {l["item_id"]: l for l in links}
    for l in sorted(links, key=lambda x: x["status"] == "derived"):
        base = {"item_id": l["item_id"], "file": l["file"], "locator": l["locator"], "label": l["label"], "owner": l.get("owner"), "metric": l.get("metric_id"),
                "snapshot": l.get("snapshot"), "display": l.get("display"), "stale": l["status"] == "stale", "link_status": l["status"], "confidence": l.get("confidence")}
        st = l["status"]
        if st == "policy":
            items[l["item_id"]] = {**base, "verdict": "still_valid", "reason": "policy"}
            continue
        if st == "unlinked":
            items[l["item_id"]] = {**base, "verdict": "needs_review", "reason": "unlinked"}
            continue
        if st == "derived":
            changed_refs = [r for r in l.get("refs", []) if items.get(r, {}).get("verdict") == "invalidated"]
            items[l["item_id"]] = {**base, "verdict": "invalidated" if changed_refs else "still_valid", "reason": "input_changed" if changed_refs else "inputs_unchanged", "inputs": changed_refs or l.get("refs", [])}
            continue
        snap = l.get("snapshot") or "close"
        b, a, was_reached, parts = metric_vals(l["metric_id"], snap)
        if not was_reached:
            items[l["item_id"]] = {**base, "verdict": "still_valid", "reason": structural_reason(lib, parts[0], lines), "old": b, "new": b}
            continue
        m = lib.metrics.get(parts[0])
        ch = (b != a) if isinstance(b, str) else abs(a - b) > 0.005
        if not ch:
            items[l["item_id"]] = {**base, "verdict": "still_valid", "reason": "conclusion_unchanged" if (m and m.conclusion and len(parts) == 1) else "value_unchanged", "old": b, "new": a}
            continue
        cb, ca = (conclusion_state(m, b), conclusion_state(m, a)) if (m and len(parts) == 1) else (None, None)
        if st == "stale":
            v, r = "invalidated", "stale_and_value_changed"
        elif cb is not None and cb != ca:
            v, r = "invalidated", "conclusion_flipped"
        elif not l.get("exact") and isinstance(b, (int, float)) and round(a / (2 * l["tolerance"])) == round(b / (2 * l["tolerance"])):
            v, r = "still_valid", "display_unchanged"
        else:
            v, r = "invalidated", "value_changed"
        items[l["item_id"]] = {**base, "verdict": v, "reason": r, "old": b, "new": a, "conclusion_old": cb, "conclusion_new": ca}

    acts: dict[str, dict] = {}
    for ac in actions:
        snap = ac.get("snapshot", "close")
        b, a, was_reached, parts = metric_vals(ac["metric"], snap)
        base = {"action_id": ac["id"], "label": ac["label"], "kind": ac["kind"], "owner": ac.get("owner"), "metric": ac["metric"], "executed_at": ac.get("executed_at"), "old": b, "new": a}
        if not was_reached:
            acts[ac["id"]] = {**base, "verdict": "still_valid", "reason": structural_reason(lib, parts[0], lines), "new": b}
            continue
        m = lib.metrics.get(parts[0])
        if isinstance(b, str):
            if b != a:
                c = comps[ac["compensation"]]
                acts[ac["id"]] = {**base, "verdict": "invalidated", "reason": "conclusion_flipped", "compensation": {"kind": ac["compensation"], **c, "approver": ac.get("comp_approver") or c["approver"]}}
            else:
                acts[ac["id"]] = {**base, "verdict": "still_valid", "reason": "conclusion_unchanged"}
            continue
        if abs(a - b) > 0.005:
            c = comps[ac["compensation"]]
            over = round(b - a, 2)
            acts[ac["id"]] = {**base, "verdict": "invalidated", "reason": "value_changed",
                              "compensation": {"kind": ac["compensation"], **c, "approver": ac.get("comp_approver") or c["approver"], "amount": abs(over), "direction": "overpaid" if over > 0 else "underpaid"}}
        else:
            acts[ac["id"]] = {**base, "verdict": "still_valid", "reason": "conclusion_unchanged" if (m and m.conclusion) else "value_unchanged"}

    nodes: dict[str, dict] = {}
    for n in agent_nodes or []:
        snap = n.get("snapshot", "close")
        changed_fields, any_reached = [], False
        for mid in n["consumes"]:
            b, a, was_reached, parts = metric_vals(mid, snap)
            any_reached |= was_reached
            if not was_reached:
                continue
            m = lib.metrics.get(parts[0])
            cb, ca = (conclusion_state(m, b), conclusion_state(m, a)) if m else (None, None)
            if (isinstance(b, str) and b != a) or (not isinstance(b, str) and abs(a - b) > 0.005):
                changed_fields.append({"field": mid, "label": m.label if m else mid, "old": b, "new": a, "delta": None if isinstance(b, str) else a - b,
                                       "crossed_threshold": cb != ca, "material": material_change(m.unit if m else "usd", b, a, cb != ca)})
        base = {"node_id": n["id"], "owner": n["owner"], "kind": n["kind"], "label": n.get("label"), "content": n.get("content"), "consumes": n["consumes"]}
        if not any_reached:
            nodes[n["id"]] = {**base, "verdict": "still_valid", "reason": structural_reason(lib, n["consumes"][0], lines), "skipped": True}
        elif not any(c["material"] for c in changed_fields):
            nodes[n["id"]] = {**base, "verdict": "still_valid", "reason": "below_materiality" if changed_fields else "value_unchanged", "skipped": True, "changed_fields": changed_fields}
        else:
            nodes[n["id"]] = {**base, "verdict": "suspect", "reason": "pending_owner", "changed_fields": changed_fields}

    accts = {l["account"] for l in lines}
    naive_items = [l["item_id"] for l in links if l.get("metric_id") and any(accts & set(s.accounts) for p in (l["metric_id"][4:].split("+") if l["metric_id"].startswith("sum:") else [l["metric_id"]])
                                                                              if p in lib.metrics for s in _leaves(lib, p))]
    naive_nodes = [n["id"] for n in agent_nodes or [] if any(accts & set(s.accounts) for p in n["consumes"] if p in lib.metrics for s in _leaves(lib, p))]
    naive = len(naive_items) + len(actions) + len(naive_nodes)

    def cnt(d: dict, v: str) -> int:
        return sum(1 for x in d.values() if x["verdict"] == v)

    counts = {"invalidated": cnt(items, "invalidated") + cnt(acts, "invalidated"), "still_valid": cnt(items, "still_valid") + cnt(acts, "still_valid"),
              "needs_review": cnt(items, "needs_review"), "compensations": sum(1 for x in acts.values() if x.get("compensation")),
              "agent_suspect": cnt(nodes, "suspect"), "agent_skipped": sum(1 for x in nodes.values() if x.get("skipped")),
              "metrics_total": len(lib.metrics), "metrics_reached": len(reached), "metrics_recomputed": len(reached), "metrics_changed": sum(1 for x in metrics_out.values() if x["changed"]),
              "naive": naive, "trackback_flagged": cnt(items, "invalidated") + cnt(acts, "invalidated") + cnt(nodes, "suspect")}
    order = ([{"kind": "correction", "id": correction["id"]}] +
             [{"kind": "ledger", "id": f"{l['account']}@{l.get('orig_period')}:{l['entity']}"} for l in lines[:12]] +
             [{"kind": "metric", "id": mid, "depth": metrics_out[mid]["depth"]} for mid in sorted(metrics_out, key=lambda x: (metrics_out[x]["depth"], x)) if metrics_out[mid]["changed"]] +
             [{"kind": "item", "id": i} for i, x in items.items() if x["verdict"] == "invalidated"] +
             [{"kind": "agent", "id": i} for i, x in nodes.items() if x["verdict"] == "suspect"] +
             [{"kind": "action", "id": i} for i, x in acts.items() if x["verdict"] == "invalidated"])
    return {"correction": {k: v for k, v in correction.items() if k != "lines"}, "n_lines": len(lines), "seeds": sorted(seeds), "metrics": metrics_out,
            "items": items, "actions": acts, "agent_nodes": nodes, "counts": counts, "order": order, "seconds": round(time.time() - t0, 3),
            "ledger_slices": sorted({f"{l['account']} {l.get('orig_period')}" for l in lines})}
