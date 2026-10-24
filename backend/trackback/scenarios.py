"""Correction metadata for the 23 planted items (+ norm). Bodies come from data/generated. Part 1 timeline dates."""
from __future__ import annotations

import json
from pathlib import Path

from . import config

CORRECTIONS: dict[str, dict] = {
    "E01": {"source_id": "accrual_workpaper_2026_03", "version": 2, "tx_time": "2026-04-12T09:00:00-07:00", "kind": "estimate", "knowable_at": "2026-04-12T09:00:00-07:00", "booking_period": "2026-04",
            "type": "revised_invoice", "note": "Bayline invoice $51,900 vs $48,000 accrual (+8.1%). Estimate change: book +$3,900 in April; do not reopen March; under the $8k trivial line."},
    "E07": {"source_id": "contract_uc_sierra", "version": 2, "tx_time": "2026-04-20T11:00:00-07:00", "kind": "estimate", "knowable_at": "2026-04-20T11:00:00-07:00", "booking_period": "2026-04",
            "type": "contract_amendment", "note": "UC Sierra change order (+$150k price, +$60k cost), same performance obligation: ASC 606 cumulative catch-up of $21,818 in April. Q1 was right as of March."},
    "E10": {"source_id": "ap_invoices_2026_q1", "version": 2, "tx_time": "2026-05-20T14:00:00-07:00", "kind": "error", "knowable_at": "2026-03-30T17:00:00-07:00", "booking_period": "2026-05",
            "type": "revised_invoice", "note": "March employment-counsel invoice $14,000 found un-accrued. Error (knowable March 30). Out-of-period entry in May tagged March; misstatement log."},
    "E02": {"source_id": "ap_invoices_2026_q1", "version": 3, "tx_time": "2026-05-27T10:00:00-07:00", "kind": "error", "knowable_at": "2026-03-31T17:00:00-07:00", "booking_period": "2026-05",
            "type": "revised_invoice", "note": "March route-setting invoice $22,500 dated April 3; signed timesheets were in the contractor portal on March 31. Error. OOP entry tagged March."},
    "E03": {"source_id": "ach_batch_2026_06_01", "version": 2, "tx_time": "2026-06-03T16:00:00-07:00", "kind": "fact_update", "knowable_at": "2026-06-03T16:00:00-07:00", "booking_period": "2026-06",
            "type": "bank_revision", "note": "June 1 dues batch: 14 R01 returns, $2,310. Cash never arrived: reverse receipts, restore member AR, retry per company policy T-4."},
    "E17": {"source_id": "bank_feed_2026_06_w1", "version": 2, "tx_time": "2026-06-04T09:00:00-07:00", "kind": "fact_update", "knowable_at": "2026-06-04T09:00:00-07:00", "booking_period": "2026-06",
            "type": "bank_revision", "note": "Bank revises a June 2 fee from $25.00 to $25.40. Trivial: auto-adjust the recon line, nothing else."},
    "E06": {"source_id": "contract_northgate", "version": 2, "tx_time": "2026-06-09T11:00:00-07:00", "kind": "estimate", "knowable_at": "2026-05-15T12:00:00-07:00", "booking_period": "2026-06",
            "type": "contract_amendment", "note": "Northgate amendment: +50 seats at $45 (standalone $60), effective June 1. ASC 606 prospective modification: $14,250/month from June. Never reaches Q1."},
    "E14": {"source_id": "ap_aging_2026_06_12", "version": 2, "tx_time": "2026-06-12T09:20:00-07:00", "kind": "fact_update", "knowable_at": "2026-06-12T09:20:00-07:00", "booking_period": "2026-06",
            "type": "duplicate_removal", "note": "Summit Mats '2231' is a duplicate of INV-2231 ($18,750, same PO). Blocked before release by the pre-execution fence."},
    "E05": {"source_id": "bank_statement_2026_05", "version": 2, "tx_time": "2026-06-16T14:00:00-07:00", "kind": "fact_update", "knowable_at": "2026-06-16T14:00:00-07:00", "booking_period": "2026-06",
            "type": "bank_revision", "note": "Corrected May statement: the $40,000 wire credited May 30 to Northgate's AR was misdirected. May locked: reverse June 1 referencing May; reinstate Northgate AR (over 60 days); start collections."},
    "E16": {"source_id": "customer_master", "version": 2, "tx_time": "2026-06-22T10:00:00-07:00", "kind": "fact_update", "knowable_at": "2025-09-01T10:00:00-07:00", "booking_period": "2026-06",
            "type": "contract_amendment", "note": "Contract says net-45, customer master said net-30, so a dunning email went out on day 31. Contract wins: fix the master, send a retraction, re-age AR."},
    "E13": {"source_id": "order_form_northgate_amendment", "version": 2, "tx_time": "2026-06-24T10:00:00-07:00", "kind": "error", "knowable_at": "2026-05-15T12:00:00-07:00", "booking_period": "2026-07",
            "type": "revised_invoice", "note": "Commission computed at list ($60) instead of the contracted $45: $2,880 vs $2,160, $720 overpaid in June payroll. Offset against the next commission."},
    "E18": {"source_id": "payroll_tax_2026", "version": 2, "tx_time": "2026-06-04T09:00:02-07:00", "kind": "estimate", "knowable_at": "2026-06-04T09:00:00-07:00", "booking_period": "2026-06", "coalesce_with": "E17",
            "type": "revised_invoice", "note": "State revises the 2026 UI rate retroactive to January (+$6,200 YTD). New information: book the YTD true-up in June."},
    "E09": {"source_id": "fx_rates_2026_03", "version": 2, "tx_time": "2026-07-02T10:00:00-07:00", "kind": "error", "knowable_at": "2026-03-20T17:00:00-07:00", "booking_period": "2026-07",
            "type": "fx_fix", "note": "Vendor corrects the March 20 EUR/USD fixing 1.0280 -> 1.0820. Error from a bad input: adjust asset 1500 by +$4,590 in Q2, reclassify 7100, true up depreciation."},
    "E04": {"source_id": "ach_batch_2026_06_01", "version": 3, "tx_time": "2026-07-07T15:00:00-07:00", "kind": "fact_update", "knowable_at": "2026-07-07T15:00:00-07:00", "booking_period": "2026-07",
            "type": "bank_revision", "note": "$189 June 1 debit returned R10 with a signed WSUD. Reverse, suspend future debits, open a Member Services case, never re-present without new authorization."},
    "E08": {"source_id": "wellness_billing_2026_05", "version": 2, "tx_time": "2026-06-18T10:00:00-07:00", "kind": "error", "knowable_at": "2026-05-25T09:00:00-07:00", "booking_period": "2026-06",
            "type": "revised_invoice", "note": "$6,500 SLA credit to Northgate for the San Jose flood closure (May 10-24, known in May). Book in June to 4900 (immaterial); log the May omission."},
    "E11": {"source_id": "billing_export_2026_03", "version": 2, "tx_time": "2026-07-08T09:05:00-07:00", "kind": "error", "knowable_at": "2026-04-09T14:02:00-07:00", "booking_period": "2026-06", "live": True,
            "type": "duplicate_removal", "note": "February billing migration duplicated the March annual-prepaid release: Q1 revenue and EBITDA overstated by $118,000. Under annual materiality and the 5% rule of thumb; above performance materiality; the covenant breach makes it unambiguous."},
    "E24": {"source_id": "wallbuild_costs_2026_03", "version": 2, "tx_time": "2026-07-03T10:00:00-07:00", "kind": "fact_update", "knowable_at": "2026-07-03T10:00:00-07:00", "booking_period": "2026-07",
            "type": "revised_invoice", "note": "Decoy (offsetting): $10,000 reclassified from installer labor to materials on the UC Sierra job; total cost unchanged, so cost of revenue and margin do not move."},
    "E25": {"source_id": "member_stats_2026", "version": 2, "tx_time": "2026-07-05T09:00:00-07:00", "kind": "fact_update", "knowable_at": "2026-07-05T09:00:00-07:00", "booking_period": "2026-07",
            "type": "retraction", "note": "Decoy (retraction, no replacement): the billing vendor withdrew the company-wide member total pending a recount. Anything derived from it is unprovable until a replacement arrives."},
    "E26": {"source_id": "fy2025_monthly_summary", "version": 3, "tx_time": "2026-07-08T09:45:00-07:00", "kind": "error", "knowable_at": "2026-01-20T09:00:00-08:00", "booking_period": "2026-06", "live": True, "eval_only": True,
            "type": "revised_invoice", "transform": {"route_setting:2025-Q4": 130_000},
            "note": "Eval scenario (sign flip): Q4 2025 route-setting was $130,000, not $140,600, so Q1 2026 route-setting rose 6% rather than falling. The deck sentence's direction flips."},
    "E20": {"source_id": "fy2025_monthly_summary", "version": 2, "tx_time": "2026-07-08T09:30:00-07:00", "kind": "error", "knowable_at": "2025-12-31T17:00:00-08:00", "booking_period": "2026-06", "live": True,
            "type": "revised_invoice", "note": "December 2025 annual memberships ($95,000 of 2026 service) fully recognized in December 2025. Prior-year error, little r: revise FY2025 comparatives, adjust opening retained earnings and deferred revenue, disclose, recheck the Q4 2025 certificate."},
}

# Items that are not source corrections: E12/E23 are downstream compensations of E11; E22 is the controller rejection; E15 is a refused correction; E21 is a norm application; E19 is cut.
NON_SOURCE_ITEMS = {
    "X1": "Agent self-revision (July 2): after the Controller approves the Bayline winter accrual norm, the Close Accountant revises its own Q2 utilities accrual estimate and method note; only the Reporting Analyst is pinged (BvA utilities line, cash cell); the Covenant agent is not (different period)",
    "X2": "Coalesced corrections (June 4): E17 (the 40-cent bank fee) and E18 (the retroactive UI rate) arrive within the debounce window and merge into one wave: zero pings for E17, one ping to the Reporting Analyst for E18",
    "X3": "Upstream challenge (during E11): the Reporting Analyst questions the Close Accountant's gym allocation of the duplicate; it lands in the Controller's inbox and starts no wave",
    "E12": "Downstream of E11: G4 Fresno bonus overpaid $1,280, G1 Oakland $1,040 (compensation: offset next bonus)",
    "E15": "Spoofed IBAN email (kletterwerk-gmbh.co): correction refused, vendor master unchanged",
    "E19": "Cut: no ALFRED vintages on disk (see STATUS.md)",
    "E21": "Pacific Lumen $1,035 short-pay handled under norm N2 in the June close: $35 auto-cleared, $1,000 routed",
    "E22": "Controller rejects the March-dated E11 draft; schema rejects self-approval; agent re-drafts in June with an OOP tag",
    "E23": "Downstream of E11: Q2 estimated tax overpaid; reduce the Q3 installment (company policy)",
    "E-norm": "Bayline Power winter accrual factor 1.08 proposed from ten winter months; waiting for the Controller",
}

TYPES = ["revised_invoice", "bank_revision", "fx_fix", "duplicate_removal", "contract_amendment", "retraction"]


def load_body(source_id: str, version: int, correction_id: str | None = None) -> dict:
    p = config.GENERATED_DIR / source_id / f"v{version}.json"
    if not p.exists():
        hits = list(config.GENERATED_DIR.glob(f"pending/*_{source_id}_v{version}.json"))
        if hits:
            p = hits[0]
        else:  # derived version: apply a transform to the previous version's body
            meta = CORRECTIONS[correction_id]
            prev = load_body(source_id, version - 1)
            body = json.loads(json.dumps(prev["body"]))
            for key, val in meta["transform"].items():
                line, period = key.split(":")
                from . import claims as CL
                ps, _ = CL.period_bounds(period)
                for c in body["claims"]:
                    if c["line_item"] == line and c["period_start"] == ps:
                        c["value_num"] = val
            body["note"] = meta["note"]
            return {"doc_id": source_id, "version_id": f"{source_id}@v{version}", "body": body, "document_date": prev.get("document_date")}
    return json.loads(p.read_text())
