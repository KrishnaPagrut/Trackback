"""Learned norms: mine residuals from history, propose policies as versioned claims, inactive until the Controller approves."""
from __future__ import annotations

import json
import statistics

from ... import config
from ...core import claims as CL, db, graph

DENY_LIST = [
    {"pattern": "retry policy for R10 returns", "why": "R10 is an authorization dispute (NACHA): never re-present without new written authorization"},
    {"pattern": "retry policy for R05 returns", "why": "R05 is an unauthorized consumer debit: same rule"},
    {"pattern": "retry policy for R07 returns", "why": "R07 is a revoked authorization: same rule"},
    {"pattern": "auto-clearing short-pays above the fee band", "why": "a short-pay larger than a wire fee is a dispute, not a fee"},
]
MIN_SAMPLE = 6
MAX_FACTOR = 1.25


def mine_vendor_accrual_bias(vendor_doc: str, entity: str, months_filter) -> dict | None:
    rows = db.q("SELECT c.line_item, c.period_start, cv.value_num, cv.claim_version_id FROM claims c JOIN claim_versions cv ON cv.claim_id=c.claim_id "
                "WHERE c.source_id=? AND c.entity=? AND cv.tx_to=? ORDER BY c.period_start", (vendor_doc, entity, config.TX_CURRENT))
    by_period: dict[str, dict] = {}
    for r in rows:
        by_period.setdefault(r["period_start"], {})[r["line_item"]] = (r["value_num"], r["claim_version_id"])
    residuals, evidence = [], []
    for p, d in sorted(by_period.items()):
        if "utilities_accrual" in d and "utilities_invoice" in d and months_filter(p):
            acc, inv = d["utilities_accrual"][0], d["utilities_invoice"][0]
            res = (inv - acc) / acc
            residuals.append(res)
            evidence.append({"period": p[:7], "accrual": acc, "invoice": inv, "residual_pct": round(res * 100, 2), "claims": [d["utilities_accrual"][1], d["utilities_invoice"][1]]})
    if len(residuals) < MIN_SAMPLE:
        return None
    med = statistics.median(residuals)
    factor = min(MAX_FACTOR, round(1 + med, 2))
    return {"name": "Bayline Power winter accrual factor", "entity": entity, "rule": {"kind": "accrual_factor", "vendor": "Bayline Power", "gym": "G3", "factor": factor, "months": [11, 12, 1, 2, 3]},
            "evidence": {"n": len(residuals), "median_residual_pct": round(med * 100, 1), "min_pct": round(min(residuals) * 100, 1), "max_pct": round(max(residuals) * 100, 1), "loops": evidence},
            "summary": f"{entity}: +{med*100:.1f}% median over {len(residuals)} winter months. Accrue at {factor:.2f}x, November to March"}


def mine_short_pay(doc: str, entity: str) -> dict | None:
    rows = db.q("SELECT c.line_item, c.period_start, cv.value_num, cv.claim_version_id FROM claims c JOIN claim_versions cv ON cv.claim_id=c.claim_id "
                "WHERE c.source_id=? AND c.entity=? AND cv.tx_to=? ORDER BY c.period_start", (doc, entity, config.TX_CURRENT))
    by_p: dict[str, dict] = {}
    for r in rows:
        by_p.setdefault(r["period_start"], {})[r["line_item"]] = (r["value_num"], r["claim_version_id"])
    shorts, ev = [], []
    for p, d in sorted(by_p.items()):
        if "invoice_amount" in d and "cash_received" in d:
            s = d["invoice_amount"][0] - d["cash_received"][0]
            shorts.append(s)
            ev.append({"period": p[:7], "short_pay": s, "claims": [d["invoice_amount"][1], d["cash_received"][1]]})
    if len(shorts) < MIN_SAMPLE:
        return None
    nonzero = [s for s in shorts if s > 0]
    lo, hi = min(nonzero), max(nonzero)
    typical = statistics.median(nonzero)
    cap = 50.0
    return {"name": "Pacific Lumen Labs short-pay rule", "entity": entity, "rule": {"kind": "short_pay_auto_clear", "customer": entity, "auto_clear_max": cap, "typical_wire_fee": typical, "account": "6400"},
            "evidence": {"n": len(shorts), "n_short": len(nonzero), "min": lo, "max": hi, "median": typical, "loops": ev},
            "summary": f"{entity} short-pays ${lo:.0f} to ${hi:.0f}, {len(nonzero)} of {len(shorts)} times, matching intermediary bank fees. Auto-clear to 6400 under ${cap:.0f}"}


def propose(norm_id: str, mined: dict, ts: str) -> None:
    cur = db.q1("SELECT * FROM norms WHERE norm_id=? ORDER BY version DESC LIMIT 1", (norm_id,))
    v = (cur["version"] + 1) if cur else 1
    if cur is not None:
        db.close_tx("norms", "norm_id", norm_id, db.norm_ts(ts))
    db.insert("norms", {"norm_id": norm_id, "version": v, "name": mined["name"], "entity": mined["entity"], "rule_json": db.dumps(mined["rule"]), "evidence_json": db.dumps(mined["evidence"]),
                        "status": "proposed", "valid_from": None, "approved_by": None, "tx_from": db.norm_ts(ts), "tx_to": config.TX_CURRENT})
    db.log_event("norm_proposed", f"Norm {norm_id} v{v} proposed: {mined['summary']}", actor="trackback:norms", ts=ts, detail={"norm_id": norm_id, "version": v})
    db.commit()


def approve(norm_id: str, approver: str, ts: str) -> str:
    """Approval makes the norm a source document with claims, valid from the approval date. Never retroactive."""
    cur = db.q1("SELECT * FROM norms WHERE norm_id=? AND tx_to=? ORDER BY version DESC LIMIT 1", (norm_id, config.TX_CURRENT))
    v = cur["version"] + 1
    db.close_tx("norms", "norm_id", norm_id, db.norm_ts(ts))
    db.insert("norms", {"norm_id": norm_id, "version": v, "name": cur["name"], "entity": cur["entity"], "rule_json": cur["rule_json"], "evidence_json": cur["evidence_json"],
                        "status": "approved", "valid_from": ts[:10], "approved_by": approver, "tx_from": db.norm_ts(ts), "tx_to": config.TX_CURRENT})
    rule = json.loads(cur["rule_json"])
    doc_id = f"norm_{norm_id}"
    body = {"title": cur["name"], "text": f"Approved norm {norm_id} ({approver}, valid from {ts[:10]}, prospective only): {db.dumps(rule)}", "claims": []}
    for k, val in rule.items():
        if isinstance(val, (int, float)):
            body["claims"].append({"entity": cur["entity"], "line_item": k, "unit": "USD" if k != "factor" else "ratio", "period_start": "", "period_end": "", "value_num": val, "value_text": None})
    if db.q1("SELECT 1 FROM sources WHERE source_id=?", (doc_id,)) is None:
        db.insert("sources", {"source_id": doc_id, "uri_r": f"/r/{doc_id}", "system": "norms", "kind": "generic", "title": cur["name"]})
    prev = db.source_version_as_of(doc_id, ts)
    CL.load_version(doc_id, f"{doc_id}@v{v}", "generic", body, ts, document_date=ts[:10], supersedes=prev["version_id"] if prev else None, correction_id=None)
    db.log_event("norm_approved", f"Norm {norm_id} approved by {approver}, valid from {ts[:10]}", actor=approver, ts=ts, detail={"norm_id": norm_id})
    db.commit()
    return doc_id


def list_norms() -> list[dict]:
    out = []
    for r in db.q("SELECT * FROM norms WHERE tx_to=? ORDER BY norm_id", (config.TX_CURRENT,)):
        d = dict(r); d["rule"] = json.loads(d["rule_json"]); d["evidence"] = json.loads(d["evidence_json"]); out.append(d)
    return out
