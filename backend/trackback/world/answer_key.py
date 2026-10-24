"""The answer key (SPEC.md Section 5.7), written from the generator's own knowledge and refcalc's arithmetic, never from the engines.

Contents: calibration; the six exceptions with classification, knowable_at, size, materiality, treatment and approver; the noise
list; the lineage truth for every number in the human files; the X1 impact sets (Appendix A); compensations; aggregate materiality;
the H1 finding; and expected outcomes for the iteration-2 behaviours (who gets pinged, who answers what)."""
from __future__ import annotations

import hashlib
import json

from .. import config as C
from .human_files import ACTIONS
from .refcalc import Ref, item_verdict, metric_value


def correction_lines(kind: str, facts: dict) -> list[dict]:
    """Balanced correcting lines with orig_period, from the generator's knowledge of each planted case."""
    if kind == "X1":   # reverse the extra import line by line
        return [{"entity": l["entity"], "account": l["account"], "amount_cents": -l["amount_cents"], "orig_period": "2026-03"} for l in facts["x1_lines"]]
    if kind == "X2":
        return [{"entity": "HQ", "account": "6400", "amount_cents": 140_000_00, "orig_period": "2026-03"}, {"entity": "HQ", "account": "2010", "amount_cents": -140_000_00, "orig_period": "2026-03"}]
    if kind == "X4":
        return [{"entity": "HQ", "account": "2010", "amount_cents": 18_750_00, "orig_period": "2026-06"}, {"entity": "HQ", "account": "6700", "amount_cents": -18_750_00, "orig_period": "2026-06"}]
    if kind == "X5":
        return [{"entity": "HQ", "account": "1210", "amount_cents": 2_310_00, "orig_period": "2026-06"}, {"entity": "HQ", "account": "1010", "amount_cents": -2_310_00, "orig_period": "2026-06"}]
    if kind == "X6":
        return [{"entity": "HQ", "account": "6500", "amount_cents": 312_40, "orig_period": "2026-06"}, {"entity": "HQ", "account": "1010", "amount_cents": -312_40, "orig_period": "2026-06"}]
    return []


def sizes(lines: list[dict]) -> dict:
    """SAB 108: rollover = P&L amounts in the current fiscal year (positive: income overstated); iron curtain = minus the asset and
    liability amounts (positive: net assets overstated)."""
    roll = sum(l["amount_cents"] for l in lines if C.ACCOUNTS[l["account"]][1] in ("revenue", "expense") and l["orig_period"] >= "2026-01") / 100
    iron = -sum(l["amount_cents"] for l in lines if C.ACCOUNTS[l["account"]][1] in ("asset", "liability")) / 100
    return {"rollover": roll, "iron_curtain": iron}


def impact(entries: list[dict], items: list[dict], targets: dict, lines: list[dict]) -> dict:
    snaps = {k: C.SNAPSHOTS[k] for k in ("draft", "close", "now")}
    before = {k: Ref(entries, t) for k, t in snaps.items()}
    after = {k: Ref(entries, t, lines) for k, t in snaps.items()}
    touched_regions = {C.GYM_REGION[l["entity"]] for l in lines if l["entity"] in C.GYM_REGION}
    out_items, invalid = {}, set()
    ordered = [i for i in items if i["link"] != "derived"] + [i for i in items if i["link"] == "derived"]
    for it in ordered:
        snap = it.get("snapshot", "close")
        mids = [it["metric"]] if it.get("metric") and it["link"] != "policy" else []
        b = {m: metric_value(before[snap], m, targets) for m in mids}
        a = {m: metric_value(after[snap], m, targets) for m in mids}
        v, reason = item_verdict(it, b, a, touched_regions, invalid)
        if v == "invalidated":
            invalid.add(it["id"])
        out_items[it["id"]] = {"verdict": v, "reason": reason, "old": b.get(it.get("metric")), "new": a.get(it.get("metric")), "owner": it["owner"], "file": it["file"]}
    out_actions = {}
    for ac in ACTIONS:
        m = ac["metric"]
        b, a = metric_value(before["close"], m, targets), metric_value(after["close"], m, targets)
        reg = ac.get("region")
        if isinstance(b, str):
            v, reason = ("invalidated", "conclusion_flipped") if b != a else ("still_valid", "conclusion_unchanged")
            amount = None
        elif abs(a - b) > 0.005:
            v, reason, amount = "invalidated", "value_changed", round(b - a, 2)
        else:
            v = "still_valid"
            reason = "not_consumed" if (reg and reg not in touched_regions) else "conclusion_unchanged"
            amount = None
        out_actions[ac["id"]] = {"verdict": v, "reason": reason, "old": b, "new": a, "compensation": ac["compensation"] if v == "invalidated" else None,
                                 "approver": ac["comp_approver"] if v == "invalidated" else None, "amount": amount, "owner": ac["owner"]}
    return {"items": out_items, "actions": out_actions,
            "counts": {"invalidated": sum(1 for x in out_items.values() if x["verdict"] == "invalidated") + sum(1 for x in out_actions.values() if x["verdict"] == "invalidated"),
                       "still_valid": sum(1 for x in out_items.values() if x["verdict"] == "still_valid") + sum(1 for x in out_actions.values() if x["verdict"] == "still_valid"),
                       "compensations": sum(1 for x in out_actions.values() if x["verdict"] == "invalidated")}}


def build(w, items: list[dict], files: dict) -> dict:
    E = w.entries
    targets = w.targets
    close, draft, now = Ref(E, C.KEY_DATES["q1_close"]), Ref(E, C.KEY_DATES["draft_tb"]), Ref(E, C.KEY_DATES["now"])
    x1 = correction_lines("X1", w.facts)
    x2 = correction_lines("X2", w.facts)
    p1_lines_ttm = 342_000.00   # logged values (prior-year item)
    after_x1 = Ref(E, C.KEY_DATES["q1_close"], x1)
    after_all = Ref(E, C.KEY_DATES["q1_close"], x1 + x2)
    lev_all = after_all.net_debt("2026Q1") / (after_all.ttm_ebitda("2026Q1") - p1_lines_ttm)
    s1, s2 = sizes(x1), sizes(x2)
    agg_roll = s1["rollover"] + s2["rollover"] + (-228_000.0)
    agg_iron = s1["iron_curtain"] + s2["iron_curtain"] + 228_000.0
    bonus_over = {r: round(metric_value(close, f"bonus.{r}@2026Q1", targets) - metric_value(after_x1, f"bonus.{r}@2026Q1", targets), 2) for r in C.REGIONS}
    key = {
        "world": "tidewall", "synthetic": True, "frozen_at": C.KEY_DATES["now"],
        "calibration": {
            "ttm_adj_ebitda_close": close.ttm_ebitda("2026Q1"), "ttm_adj_ebitda_draft": draft.ttm_ebitda("2026Q1"), "cash_q1": close.cash("2026Q1"),
            "term_loan_q1": close.term_loan("2026Q1"), "net_debt_q1": close.net_debt("2026Q1"), "leverage_q1": round(close.leverage("2026Q1"), 4),
            "ttm_after_x1": after_x1.ttm_ebitda("2026Q1"), "leverage_after_x1": round(after_x1.leverage("2026Q1"), 4), "leverage_after_all": round(lev_all, 4),
            "leverage_after_x2_only": round(Ref(E, C.KEY_DATES["q1_close"], x2).leverage("2026Q1"), 4),
            "bonus_overpaid": bonus_over, "tax_overpaid_x1": round(metric_value(close, "tax_installment@2026Q2", targets) - metric_value(after_x1, "tax_installment@2026Q2", targets), 2),
            "headroom_close": round(close.headroom("2026Q1"), 2), "headroom_after_x1": round(after_x1.headroom("2026Q1"), 2),
            "q1_close_accruals": {"route_setting_6300": 410_000.0, "utilities_6200": 190_000.0},
            "membership_growth_close": round(close.growth("2026Q1", "2025Q4"), 3), "membership_growth_after_x1": round(after_x1.growth("2026Q1", "2025Q4"), 3),
        },
        "exceptions": [
            {"id": "X1", "recon": "billing_to_gl", "kind": "duplicate_import", "classification": "error", "knowable_at": C.KEY_DATES["billing_capture_1"], "original_made_at": C.KEY_DATES["q1_close"],
             "amount": 750_000.0, **s1, "by_region": w.facts["b07_by_region"], "material": True, "triggers": ["covenant_flip", "compensation", "lender_document", "aggregate_iron_curtain"],
             "treatment": "correct_in_open_period", "posting_period": C.OPEN_PERIOD, "orig_period": "2026-03", "approver": "dana", "lender_documents_to": "sam",
             "documents_to_reissue": ["Compliance_Certificate_Q1-26_signed.pdf", "Board_Deck_Q1-26.pptx", "Covenant_Q1-26_PN.xlsx"], "system_of_record": "billing_release_lines"},
            {"id": "X2", "recon": "ap_review", "kind": "unaccrued_invoice", "classification": "error", "knowable_at": "2026-04-02T08:41:00-07:00", "original_made_at": C.KEY_DATES["q1_close"],
             "amount": 140_000.0, **s2, "material": True, "material_alone": False, "treatment": "correct_in_open_period", "posting_period": C.OPEN_PERIOD, "orig_period": "2026-03",
             "approver": "dana", "assigned_to": "priya", "delegate": "marco", "system_of_record": "ap_invoices"},
            {"id": "X3", "recon": "ap_review", "kind": "accrual_true_up", "classification": "estimate_change", "knowable_at": C.KEY_DATES["route_invoice"], "original_made_at": C.KEY_DATES["q1_close"],
             "amount": 58_000.0, "rollover": 0.0, "iron_curtain": 0.0, "material": False, "treatment": "no_action", "already_booked": "2026-05", "approver": None, "system_of_record": "ap_invoices"},
            {"id": "X4", "recon": "ap_review", "kind": "duplicate_vendor_invoice", "classification": "error", "knowable_at": "2026-06-03T16:40:00-07:00", "amount": 18_750.0,
             **sizes(correction_lines("X4", w.facts)), "trivial": True, "material": False, "treatment": "vendor_credit_and_hold", "approver": "marco", "system_of_record": "ap_invoices"},
            {"id": "X5", "recon": "bank_to_book", "kind": "ach_return", "classification": "fact_update", "knowable_at": "2026-06-03T00:00:00-07:00", "amount": 2_310.0,
             "trivial": True, "material": False, "treatment": "reverse_receipt_reinstate_ar", "re_present": "once (R01, company policy)", "approver": "dana", "system_of_record": "bank_statement"},
            {"id": "X6", "recon": "bank_to_book", "kind": "unbooked_bank_fee", "classification": "fact_update", "knowable_at": "2026-06-30T00:00:00-07:00", "amount": 312.40,
             "trivial": True, "material": False, "treatment": "draft_entry", "approver": "dana", "system_of_record": "bank_statement"},
        ],
        "known_items": [{"id": "P1", "recon": "billing_to_gl", "batch": "B09", "months": ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"], "rollover": -228_000.0, "iron_curtain": 228_000.0, "ttm_ebitda_effect": 342_000.0}],
        "noise": {"deposit_in_transit": 12, "outstanding_check": 3, "fx_rounding": 1, "subset_sum": {"customer": "Northgate Biotech Inc.", "invoices": [62_000.0, 74_400.0, 50_000.0], "wire": 186_400.0},
                  "known_short_pay": {"customer": "Pacific Lumen Labs", "short": 25.0, "habit": "11 of 12 wires short by $15 to $35"},
                  "alias": {"customer": "Sierra State University", "payer": "SSU FOUNDATION ACCTS PAYABLE", "suggest_alias": True}, "rounding": 0},
        "materiality": {"overall": C.MATERIALITY_V3["overall"], "performance": C.MATERIALITY_V3["performance"], "clearly_trivial": C.MATERIALITY_V3["clearly_trivial"],
                        "aggregate_rollover": agg_roll, "aggregate_iron_curtain": agg_iron, "aggregate_items": ["X1", "X2", "P1"], "excluded_trivial": ["X4", "X5", "X6"],
                        "rollover_passes": agg_roll < C.MATERIALITY_V3["overall"], "iron_curtain_fails": agg_iron > C.MATERIALITY_V3["overall"],
                        "x1_pct_budgeted_pretax": round(750_000 / C.MATERIALITY_V3["budgeted_pretax"] * 100, 2), "leverage_x1": round(after_x1.leverage("2026Q1"), 4), "leverage_all": round(lev_all, 4)},
        "lineage": [{k: it.get(k) for k in ("id", "file", "locator", "label", "kind", "link", "metric", "value", "stale", "owner", "refs", "snapshot", "display")} for it in items],
        "impact": {"X1": impact(E, items, targets, x1), "X2": impact(E, items, targets, x2), "X4": impact(E, items, targets, correction_lines("X4", w.facts)),
                   "X6": impact(E, items, targets, correction_lines("X6", w.facts))},
        "h1": {"item": "DECK.s2.l2", "finding": "stale", "typed": 32_600_000.0, "books_when_made": close.ttm_ebitda("2026Q1"), "typed_from": "draft"},
        "agent_mistakes": {"X1": ["materiality_immaterial", "lender_routing_controller"], "X3": ["classification_error_should_be_estimate"], "X1_posting": ["locked_period"]},
        "iteration2": {
            "X1_pings": {"close_accountant": "reworked", "covenant_comp": "needs_human", "reporting_analyst": "reworked"},
            "X1_notices": {"priya": "marco", "sam": "sam"},
            "X1_still_valid_agent_answers": ["RA.commentary.membership_growth", "RA.commentary.regions_profitable"],
            "X1_skipped": "RA.cash_forecast",
            "S1": {"revises": "CA.june_accrual.utilities", "pings": ["reporting_analyst"], "not_pinged": ["covenant_comp"], "reason": "different_period"},
            "S2": {"coalesced": ["X5", "X6"], "pings": ["reporting_analyst"], "x6_pings": 0},
            "S3": {"from": "reporting_analyst", "target": "CA.q1_close_memo", "to": "dana", "wave_started": False},
        },
    }
    return key


def key_hash(key: dict) -> str:
    return hashlib.sha256(json.dumps(key, sort_keys=True, default=str).encode()).hexdigest()
