"""Materiality: delta + line item + stated conclusions -> verdict and reason. Thresholds come from the memo claim."""
from __future__ import annotations

import json
import math
from typing import Any

from ... import config
from ...core import db

# Line items that must be exact (any change recomputes): reconciliations, registers, schedules, payouts, payments.
EXACT_LINES = {"cash_recon", "recon", "capex", "fixed_assets", "depreciation_schedule", "bonus_payout", "commission_payout", "cash_actual",
               "payment", "payable", "ar_balance", "ar", "tax_payment", "member_ar", "deferred_revenue_schedule", "ar_aging"}
CASH_LINES = {"cash_forecast", "cash", "cash_kpi", "collections"}
# Ratios and percentages: a dollar threshold is meaningless; conclusions and display precision decide.
RATIO_LINES = {"leverage", "margin", "growth", "route_setting_growth", "ratio", "payout_ratio", "wallbuild_progress", "headroom_pct", "rate"}


def memo(as_of: str | None = None) -> dict[str, float]:
    """Thresholds from the materiality memo claims (version as of `as_of`, else current)."""
    out = dict(config.MATERIALITY_DEFAULTS)
    out["cash_tolerance"] = 2_500.0
    rows = db.q("SELECT c.line_item, cv.value_num, cv.tx_from, cv.tx_to FROM claims c JOIN claim_versions cv ON cv.claim_id=c.claim_id WHERE c.source_id='materiality_memo'")
    for r in rows:
        if as_of and db.norm_ts(r["tx_from"]) > db.norm_ts(as_of):
            continue
        if not as_of and r["tx_to"] != config.TX_CURRENT:
            continue
        key = {"materiality_annual": "annual", "materiality_quarterly_performance": "quarterly_performance", "clearly_trivial": "clearly_trivial",
               "flux_threshold_pct": "flux_pct", "flux_threshold_abs": "flux_abs", "cash_tolerance": "cash_tolerance"}.get(r["line_item"])
        if key and r["value_num"] is not None:
            out[key] = float(r["value_num"])
    return out


def is_exact(line_item: str | None) -> bool:
    li = (line_item or "").lower()
    return li in EXACT_LINES or any(li.startswith(p) for p in ("recon", "capex", "payout", "payment", "ar_"))


def is_ratio(line_item: str | None) -> bool:
    return (line_item or "").lower() in RATIO_LINES


def threshold_for(line_item: str | None, kind: str, thresholds: dict[str, float]) -> float:
    li = (line_item or "").lower()
    if is_exact(line_item) or is_ratio(line_item):
        return 0.0
    if "cash" in li or li in CASH_LINES:
        return thresholds["cash_tolerance"]
    return thresholds["clearly_trivial"]


from ...core.conclusions import conclusion_state  # noqa: E402


def classify_correction(total_delta: float, thresholds: dict[str, float], kind: str, prior_year: bool, flips_conclusion: bool) -> str:
    """Correction-level materiality verdict: log | book_oop | little_r | big_r | escalate."""
    d = abs(total_delta)
    if flips_conclusion:
        return "escalate"
    if kind == "estimate":
        return "book_prospective" if d > thresholds["clearly_trivial"] else "log"
    if prior_year:
        if d >= thresholds["annual"]:
            return "big_r"
        return "little_r" if d > thresholds["clearly_trivial"] else "log"
    if d <= thresholds["clearly_trivial"]:
        return "log"
    if d > thresholds["quarterly_performance"]:
        return "book_and_evaluate"
    return "book_oop"


def numeric_verdict(old: float | None, new: float | None, line_item: str | None, kind: str,
                    conclusions_json: str | None, thresholds: dict[str, float]) -> tuple[str, str, dict]:
    """Return (verdict, reason, detail) for a recomputed number."""
    detail: dict[str, Any] = {"old": old, "new": new}
    if new is None or (isinstance(new, float) and math.isnan(new)):
        return "unprovable", "supporter_retracted", detail
    if old is None:
        return "invalidated", "value_changed", detail
    delta = abs(new - old)
    detail["delta"] = delta
    conclusions = json.loads(conclusions_json) if conclusions_json else None
    if delta < 1e-9:
        if conclusions:
            detail["old_conclusion"] = detail["new_conclusion"] = conclusion_state(old, conclusions)
            return "unaffected", "conclusion_unchanged", detail
        return "unaffected", "early_cutoff", detail
    thr = threshold_for(line_item, kind, thresholds)
    detail["threshold"] = thr
    old_c, new_c = conclusion_state(old, conclusions), conclusion_state(new, conclusions)
    if old_c is not None:
        detail["old_conclusion"], detail["new_conclusion"] = old_c, new_c
    bool_old = {k: v for k, v in (old_c or {}).items() if k != "display"}
    bool_new = {k: v for k, v in (new_c or {}).items() if k != "display"}
    exact = is_exact(line_item)
    # 1. stated conclusions first (a covenant flip of 0.01x must never hide under a dollar threshold); forecast cells are not shielded
    if bool_old and kind != "forecast_cell":
        if bool_old != bool_new:
            return "invalidated", "conclusion_flipped", detail
        if not exact:
            if "display" in old_c and old_c.get("display") != new_c.get("display"):
                return "invalidated", "value_changed", detail  # the conclusion holds but the stated figure no longer does
            return "unaffected", "conclusion_unchanged", detail
    # 2. exact lines (payouts, registers, reconciliations, actuals): any change recomputes
    if exact:
        return "invalidated", "value_changed", detail
    # 3. dollar lines: the memo's threshold
    if delta <= thr:
        return "unaffected", "below_materiality", detail
    # 4. display precision (tiles): same displayed value -> cleared
    if old_c is not None and "display" in old_c:
        return ("unaffected", "conclusion_unchanged", detail) if old_c.get("display") == new_c.get("display") else ("invalidated", "value_changed", detail)
    return "invalidated", "value_changed", detail


def aggregate_unbooked(period_prefix: str) -> dict[str, Any]:
    rows = db.q("SELECT * FROM misstatement_log WHERE booked=0 AND period LIKE ?", (period_prefix + "%",))
    total = sum(float(r["amount"]) for r in rows)
    t = memo()
    return {"n": len(rows), "total": total, "exceeds_trivial": abs(total) > t["clearly_trivial"],
            "exceeds_performance": abs(total) > t["quarterly_performance"], "items": [dict(r) for r in rows]}
