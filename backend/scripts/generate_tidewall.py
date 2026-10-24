"""Deterministic, seeded synthetic world for Tidewall Climbing Co. (all numbers synthetic).

Writes every source document version to data/generated/<doc_id>/<version_id>.json and loads them
into the SQLite store (sources, source_versions, claims, claim_versions). Corrections that belong to
history are loaded as later versions here; build_history.py applies them through the engine at their
transaction time so findings are recorded. The live E11 group and Scenario B (E20) are written as
pending versions in data/generated/pending/ and applied on stage.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from trackback import claims, config, db, v2world as W  # noqa: E402

rng = random.Random(7089)
OUT = config.GENERATED_DIR
PENDING = OUT / "pending"


def C(line_item, value, period=None, entity="", unit="USD", account=None, text=None, period_end=None):
    """Claim helper. period 'YYYY-MM' expands to month start/end; 'YYYY-Qn' to quarter; 'YYYY' to year."""
    ps, pe = claims.period_bounds(period)
    if period_end:
        pe = period_end
    return {"entity": entity, "line_item": line_item, "unit": unit, "account": account, "period_start": ps, "period_end": pe,
            "value_num": None if text is not None else value, "value_text": text}


DOCS: list[dict] = []     # loaded into the DB now
PENDING_DOCS: list[dict] = []  # applied live


def doc(doc_id, kind, system, title, tx, body, *, document_date=None, version=1, supersedes=None, correction_id=None, pending=False):
    body = dict(body); body.setdefault("title", title)
    d = {"doc_id": doc_id, "kind": kind, "system": system, "title": title, "version_id": f"{doc_id}@v{version}",
         "tx_from": tx, "document_date": document_date, "supersedes": supersedes, "correction_id": correction_id, "body": body}
    (PENDING_DOCS if pending else DOCS).append(d)
    return d["version_id"]


# ------------------------------------------------------------------ policies and reference documents
doc("credit_agreement", "generic", "contracts", "Redwood Commercial Credit: Term Loan Credit Agreement (synthetic)", "2025-06-01T10:00:00-07:00", {
    "text": ("CREDIT AGREEMENT dated June 1, 2025 between Tidewall Climbing Co. (Borrower) and Redwood Commercial Credit (Lender). "
             "Section 1.01 Definitions. 'Consolidated Adjusted EBITDA' means, for any trailing twelve-month period, consolidated net income "
             "plus income tax expense, interest expense and depreciation, and excluding realized foreign exchange gains and losses. "
             "For the avoidance of doubt, legal fees and route-setting contract labor are operating expenses and are NOT added back. "
             "Section 7.11 Financial Covenant. The Borrower shall not permit the Net Leverage Ratio (Net Debt divided by Consolidated Adjusted EBITDA) "
             "as of the last day of any fiscal quarter to exceed 3.00 to 1.00. Section 6.02(c) Compliance Certificate due within 45 days after quarter end. "
             "Section 6.02(f) If any financial statement previously delivered is corrected, the Borrower shall deliver a corrected Compliance Certificate within 10 business days. "
             "Term Loan principal: $18,000,000."),
    "claims": [C("covenant_max_leverage", 3.00, unit="x"), C("term_loan_principal", 18_000_000),
               C("adjusted_ebitda_definition", None, text="net income + income tax + interest + depreciation; excludes realized FX gains/losses; legal and route-setting are NOT added back"),
               C("corrected_certificate_clause", None, text="corrected Compliance Certificate within 10 business days of any correction to delivered financial statements"),
               C("certificate_due_days", 45, unit="days")]}, document_date="2025-06-01")

doc("materiality_memo", "generic", "controller", "FY2026 Materiality Memo (Dana Ortiz, Controller)", "2026-01-05T09:00:00-08:00", {
    "text": ("MATERIALITY MEMO FY2026. Overall annual materiality $160,000 (5% of budgeted pretax income of $3.2M). Quarterly performance materiality $60,000. "
             "Clearly trivial threshold $8,000: items below this are logged, not booked individually. Flux commentary threshold: variance greater than 10% AND greater than $25,000 "
             "versus prior quarter or budget (company policy; common practice, no published standard). Cash forecast tolerance $2,500 per week. "
             "Qualitative overrides: anything affecting covenant compliance, a bonus tier, or the sign of a reported change is material regardless of size (SAB 99 factors)."),
    "claims": [C("materiality_annual", 160_000), C("materiality_quarterly_performance", 60_000), C("clearly_trivial", 8_000),
               C("flux_threshold_pct", 0.10, unit="ratio"), C("flux_threshold_abs", 25_000), C("cash_tolerance", 2_500)]}, document_date="2026-01-05")

doc("comp_plan", "generic", "hr", "FY2026 Incentive Compensation Plan (GM bonus and sales commission)", "2026-01-05T09:30:00-08:00", {
    "text": ("GM QUARTERLY BONUS: 4% of gym quarterly EBITDA above target, paid within 60 days of quarter end, subject to true-up: any overpayment arising from a later correction "
             "of gym EBITDA is offset against the next quarterly bonus (no ad-hoc payroll deduction). SALES COMMISSION: 8% of first-year contract value on new and amended "
             "corporate wellness contracts, paid in the month following signature; overpayments are offset against future commissions. Q1 2026 gym EBITDA targets: "
             "Oakland $380,000; San Jose $280,000; Sacramento $310,000; Fresno $340,000; Santa Cruz $240,000; Berkeley $310,000."),
    "claims": [C("gm_bonus_rate", W.GM_BONUS_RATE, unit="ratio"), C("commission_rate", W.COMMISSION_RATE, unit="ratio"),
               C("bonus_offset_clause", None, text="overpayment from a later EBITDA correction is offset against the next quarterly bonus"),
               C("commission_offset_clause", None, text="commission overpayments are offset against future commissions")]
              + [C("gym_ebitda_target", W.GYM_EBITDA_TARGET_Q1[g], "2026-Q1", entity=g) for g in W.GYMS]}, document_date="2026-01-05")

doc("fy2026_budget", "generic", "fpa", "FY2026 Budget (board approved)", "2026-01-05T10:00:00-08:00", {
    "claims": [C("budget_revenue", W.BUDGET["revenue"], "2026"), C("budget_ebitda", W.BUDGET["ebitda"], "2026"), C("budget_pretax", W.BUDGET["pretax"], "2026"),
               C("budget_revenue", W.BUDGET["q1_revenue"], "2026-Q1"), C("budget_membership_revenue", W.BUDGET["q1_membership"], "2026-Q1"),
               C("budget_utilities", W.BUDGET["q1_utilities"], "2026-Q1"), C("budget_route_setting", W.BUDGET["q1_route_setting"], "2026-Q1"),
               C("budget_legal", W.BUDGET["q1_legal"], "2026-Q1"), C("budget_payroll_tax", W.BUDGET["q1_payroll_tax"], "2026-Q1"),
               C("budget_ebitda", W.BUDGET["q1_ebitda"], "2026-Q1"),
               C("budget_utilities", 150_000, "2026-04", entity=""), C("budget_utilities", 52_000, "2026-06", entity="G3"), C("budget_payroll_tax", 380_000, "2026-H1"),
               C("weekly_opex_cash", 215_000, "2026"), C("federal_tax_rate", W.TAX_RATE, "2026", unit="ratio"), C("avg_monthly_dues", 105, "2026")]}, document_date="2026-01-05")

doc("company_policies", "generic", "controller", "Accounting and Treasury Policies (excerpts)", "2026-01-05T10:30:00-08:00", {
    "text": ("POLICY T-4 ACH returns (company policy; the NACHA re-presentment limit is unverified and labeled as such): R01 insufficient-funds returns may be re-presented once "
             "after 5 banking days. R05, R07 and R10 returns are authorization disputes: never re-present without new written authorization; suspend future debits and open a Member Services case. "
             "POLICY X-2 Estimated tax overpayments are applied against the next installment rather than refunded (company policy; IRS rule to be verified by the tax advisor). "
             "POLICY C-1 Period locks: only the Controller may unlock a period; corrections to a locked period are booked in the open period tagged with the original period. "
             "POLICY V-3 Vendor master changes require the AP Specialist (owner) and a callback to the number on file; bank-detail changes by email are never accepted."),
    "claims": [C("r01_retry_policy", None, text="company policy: R01 may be re-presented once after 5 banking days (NACHA limit unverified)"),
               C("r10_policy", None, text="R05/R07/R10: never re-present without new authorization; suspend debits; open a case"),
               C("tax_overpayment_policy", None, text="company policy: apply estimated-tax overpayment to the next installment (IRS rule to be verified)"),
               C("period_lock_policy", None, text="only the Controller unlocks; book in the open period with an out-of-period tag"),
               C("vendor_master_policy", None, text="bank-detail changes by email are never accepted; callback required; owner Priya Nair")]}, document_date="2026-01-05")

# ------------------------------------------------------------------ FY2025 history
fy25 = []
monthly_rev = [3_050_000, 3_000_000, 3_200_000, 3_180_000, 3_250_000, 3_300_000, 3_400_000, 3_420_000, 3_350_000, 3_300_000, 3_200_000, 3_450_000]
assert sum(monthly_rev) == W.FY2025_REVENUE
for i, r in enumerate(monthly_rev, start=1):
    fy25.append(C("revenue", r, f"2025-{i:02d}"))
fy25.append(C("membership_revenue", W.FY2025_MEMBERSHIP_DEC, "2025-12"))
for qn, v in enumerate(W.FY2025_QUARTER_EBITDA.values(), start=1):
    fy25.append(C("ebitda", v, f"2025-Q{qn}"))
fy25 += [C("revenue", W.Q1_2025_REVENUE, "2025-Q1"), C("revenue", W.FY2025_REVENUE, "2025"), C("ebitda", sum(W.FY2025_QUARTER_EBITDA.values()), "2025"),
         C("pretax", W.FY2025_PRETAX, "2025"), C("route_setting", W.ROUTE_SETTING_Q4_2025, "2025-Q4"), C("net_debt", W.NET_DEBT_2025_12_31, "2025-12-31"),
         C("deferred_revenue_memberships", 310_000, "2025-12-31")]
doc("fy2025_monthly_summary", "generic", "gl", "FY2025 monthly summary (membership system + GL)", "2026-01-20T09:00:00-08:00", {"claims": fy25}, document_date="2025-12-31")
# E20 (Scenario B, live): December annual memberships ($95k of 2026 service) were fully recognized in December 2025
fy25_v2 = json.loads(json.dumps(fy25))
for c in fy25_v2:
    key = (c["line_item"], c["period_start"], c["period_end"])
    if key in (("revenue", "2025-12-01", "2025-12-31"), ("revenue", "2025-01-01", "2025-12-31"), ("membership_revenue", "2025-12-01", "2025-12-31"),
               ("ebitda", "2025-10-01", "2025-12-31"), ("ebitda", "2025-01-01", "2025-12-31")):
        c["value_num"] -= W.E20_AMOUNT
    if c["line_item"] == "pretax":
        c["value_num"] -= W.E20_AMOUNT
    if c["line_item"] == "deferred_revenue_memberships":
        c["value_num"] += W.E20_AMOUNT
doc("fy2025_monthly_summary", "generic", "gl", "FY2025 monthly summary (membership system + GL)", "2026-07-08T09:30:00-07:00", {"claims": fy25_v2,
    "note": "v2: $95,000 of annual memberships sold December 2025 for 2026 service were fully recognized in December 2025 (prior-year error, little r)"},
    document_date="2025-12-31", version=2, supersedes="fy2025_monthly_summary@v1", correction_id="E20", pending=True)

# Bayline Power history for the accrual-bias norm (ten winter months)
bay = []
winter = [("2024-11", 44_000, 47_500), ("2024-12", 49_000, 52_800), ("2025-01", 51_000, 54_900), ("2025-02", 49_500, 53_380), ("2025-03", 46_000, 49_700),
          ("2025-11", 45_000, 48_600), ("2025-12", 50_000, 53_800), ("2026-01", 50_000, 52_000), ("2026-02", 48_500, 50_500), ("2026-03", 48_000, 51_900)]
for p, acc, inv in winter:
    bay += [C("utilities_accrual", acc, p, entity="G3"), C("utilities_invoice", inv, p, entity="G3")]
for p, acc, inv in [("2025-06", 30_000, 30_200), ("2025-07", 31_000, 30_700), ("2025-08", 31_500, 31_900)]:
    bay += [C("utilities_accrual", acc, p, entity="G3"), C("utilities_invoice", inv, p, entity="G3")]
doc("bayline_history", "generic", "ap", "Bayline Power (Sacramento) accrual vs invoice history", "2026-06-30T08:00:00-07:00", {"claims": bay, "vendor": "Bayline Power"},
    document_date="2026-06-30")

# Pacific Lumen short-pay history (12 wires)
pl = []
shorts = [15, 25, 35, 20, 30, 15, 0, 25, 35, 20, 30, 25]
for i, s in enumerate(shorts, start=1):
    p = f"2025-{i:02d}" if i <= 6 else f"2025-{i:02d}"
    inv = 24_000
    pl += [C("invoice_amount", inv, p, entity="Pacific Lumen Labs"), C("cash_received", inv - s, p, entity="Pacific Lumen Labs")]
doc("pacific_lumen_history", "generic", "ar", "Pacific Lumen Labs wire remittance history (12 months)", "2026-06-30T08:00:00-07:00", {"claims": pl}, document_date="2026-06-30")

# ------------------------------------------------------------------ billing exports (membership system, migrated February 2026)
def billing_rows(period: str, dup: bool = False):
    rows = []
    for g in W.GYMS:
        sp = W.membership_split(g)
        d = sp["dues"].get(period, sp["dues"]["2026-03"])
        rows.append({"gym": g, "period": period, "line": "monthly_dues", "members": round(d / 105), "amount": d, "batch": f"DUES-{period}-{g}"})
        if sp["annual"]:
            rows.append({"gym": g, "period": period, "line": "annual_release", "members": round(sp["annual"] / 95), "amount": sp["annual"], "batch": f"ANN-{period}-{g}"})
            if dup:
                rows.append({"gym": g, "period": period, "line": "annual_release", "members": round(sp["annual"] / 95), "amount": sp["annual"], "batch": f"ANN-{period}-{g}"})
    return rows

for p, tx in [("2026-01", "2026-02-05T09:00:00-08:00"), ("2026-02", "2026-03-05T09:00:00-08:00")]:
    doc(f"billing_export_{p.replace('-', '_')}", "billing_export", "billing", f"Billing export {p} (deferred revenue release)", tx, {"rows": billing_rows(p)}, document_date=claims._month_end(p))
doc("billing_export_2026_03", "billing_export", "billing", "Billing export 2026-03 (deferred revenue release)", "2026-04-09T14:02:00-07:00",
    {"rows": billing_rows("2026-03", dup=True), "note": "exported by the migrated billing system"}, document_date="2026-03-31")
doc("billing_export_2026_03", "billing_export", "billing", "Billing export 2026-03 (deferred revenue release)", "2026-07-08T09:05:00-07:00",
    {"rows": billing_rows("2026-03"), "note": "v2: vendor notice 2026-07-08: the February migration emitted the March annual-prepaid release twice for gyms with annual plans; duplicates removed"},
    document_date="2026-03-31", version=2, supersedes="billing_export_2026_03@v1", correction_id="E11", pending=True)
for p, tx in [("2026-04", "2026-05-05T09:00:00-07:00"), ("2026-05", "2026-06-04T09:00:00-07:00"), ("2026-06", "2026-06-01T10:00:00-07:00")]:
    rows = billing_rows(p)
    if p == "2026-06":
        for r in rows:
            if r["line"] == "monthly_dues":
                r["amount"] = round(W.JUNE_DUES_BILLED * r["amount"] / sum(x["amount"] for x in rows if x["line"] == "monthly_dues"))
    doc(f"billing_export_{p.replace('-', '_')}", "billing_export", "billing", f"Billing export {p} (deferred revenue release)", tx, {"rows": rows}, document_date=claims._month_end(p))

doc("pos_summary_2026_q1", "generic", "pos", "Point-of-sale summary Q1 2026 (day passes and retail)", "2026-04-02T09:00:00-07:00",
    {"claims": [C("daypass_retail_revenue", W.DAYPASS_Q1[g], "2026-Q1", entity=g) for g in W.GYMS]}, document_date="2026-03-31")
doc("member_stats_2026", "generic", "billing", "Member counts by gym (June 2026)", "2026-06-02T08:00:00-07:00",
    {"claims": [C("active_members", n, "2026-06", entity=g, unit="count") for g, n in zip(W.GYMS, [1_940, 1_460, 1_480, 1_700, 1_290, 1_530])] + [C("active_members", W.MEMBERS_TOTAL, "2026-06", unit="count")]},
    document_date="2026-06-01")
doc("member_stats_2026", "generic", "billing", "Member counts by gym (June 2026)", "2026-07-05T09:00:00-07:00",
    {"claims": [C("active_members", n, "2026-06", entity=g, unit="count") for g, n in zip(W.GYMS, [1_940, 1_460, 1_480, 1_700, 1_290, 1_530])],
     "note": "v2: the billing vendor withdrew the company-wide active-member total pending a recount of migrated annual plans; no replacement figure yet"},
    document_date="2026-07-05", version=2, supersedes="member_stats_2026@v1", correction_id="E25")

# ------------------------------------------------------------------ contracts
def northgate_claims(blended_from_june: bool):
    cl = [C("seats", 200, unit="count", entity="Northgate Biotech"), C("seat_price", 60, entity="Northgate Biotech", unit="USD/seat"),
          C("term_months", 24, unit="months", entity="Northgate Biotech"), C("payment_terms", None, text="net 30", entity="Northgate Biotech")]
    for y in (2026, 2027):
        for m in range(1, 13):
            per = f"{y}-{m:02d}"
            v = W.WELLNESS_NORTHGATE_BLENDED if (blended_from_june and per >= "2026-06") else W.WELLNESS_NORTHGATE_MONTHLY
            cl.append(C("wellness_revenue", v, per, entity="Northgate Biotech"))
    if blended_from_june:
        cl += [C("amendment_seats", 50, unit="count", entity="Northgate Biotech"), C("amendment_seat_price", 45, entity="Northgate Biotech", unit="USD/seat"),
               C("amendment_effective", None, text="2026-06-01", entity="Northgate Biotech")]
    return cl
doc("contract_northgate", "generic", "contracts", "Northgate Biotech corporate wellness MSA + order form", "2026-01-05T11:00:00-08:00",
    {"text": "Northgate Biotech corporate wellness contract: 200 seats at $60 per seat per month, 24 months from January 1, 2026 ($12,000 per month). Payment terms net 30.",
     "claims": northgate_claims(False)}, document_date="2025-12-20")
doc("contract_northgate", "generic", "contracts", "Northgate Biotech corporate wellness MSA + order form", "2026-06-09T11:00:00-07:00",
    {"text": ("Amendment No. 1 signed May 15, 2026, effective June 1, 2026: adds 50 seats at $45 per seat per month (standalone price $60) for the remaining 19 months. "
              "ASC 606-10-25-13(a) prospective modification: remaining $228,000 + $42,750 = $270,750 over 19 months = $14,250 per month."),
     "claims": northgate_claims(True)}, document_date="2026-05-15", version=2, supersedes="contract_northgate@v1", correction_id="E06")

doc("wellness_other_schedule_2026", "generic", "contracts", "Other corporate wellness contracts: monthly schedule 2026", "2026-01-05T11:30:00-08:00",
    {"claims": [C("wellness_revenue", W.WELLNESS_OTHER_MONTHLY, f"2026-{m:02d}", entity="Other wellness") for m in range(1, 13)]}, document_date="2026-01-05")
doc("wellness_billing_2026_05", "generic", "ar", "Corporate wellness billing May 2026", "2026-06-01T09:00:00-07:00",
    {"claims": [C("wellness_billed", 12_000, "2026-05", entity="Northgate Biotech"), C("wellness_billed", 20_000, "2026-05", entity="Other wellness"), C("sla_credit", 0, "2026-05", entity="Northgate Biotech")]},
    document_date="2026-05-31")
doc("wellness_billing_2026_05", "generic", "ar", "Corporate wellness billing May 2026", "2026-06-18T10:00:00-07:00",
    {"claims": [C("wellness_billed", 12_000, "2026-05", entity="Northgate Biotech"), C("wellness_billed", 20_000, "2026-05", entity="Other wellness"), C("sla_credit", -W.E08_CREDIT, "2026-05", entity="Northgate Biotech")],
     "note": "v2: $6,500 SLA credit for the San Jose flood closure May 10-24 (incident report dated May 25)"},
    document_date="2026-05-31", version=2, supersedes="wellness_billing_2026_05@v1", correction_id="E08")

doc("contract_uc_sierra", "generic", "contracts", "UC Sierra climbing wall: fixed-price construction contract", "2025-11-15T10:00:00-08:00",
    {"text": "UC Sierra Recreation Center wall build. Contract price $900,000. Estimated total cost $600,000. Revenue recognized over time, cost-to-cost.",
     "claims": [C("contract_price", W.WALLBUILD_PRICE_V1, entity="UC Sierra"), C("estimated_total_cost", W.WALLBUILD_COST_V1, entity="UC Sierra")]}, document_date="2025-11-15")
doc("contract_uc_sierra", "generic", "contracts", "UC Sierra climbing wall: fixed-price construction contract", "2026-04-20T11:00:00-07:00",
    {"text": "Change Order 1 (April 20, 2026): adds a 12 m speed wall to the same performance obligation. Price +$150,000 (total $1,050,000). Estimated cost +$60,000 (total $660,000).",
     "claims": [C("contract_price", W.WALLBUILD_PRICE_V2, entity="UC Sierra"), C("estimated_total_cost", W.WALLBUILD_COST_V2, entity="UC Sierra")]},
    document_date="2026-04-20", version=2, supersedes="contract_uc_sierra@v1", correction_id="E07")
doc("wallbuild_costs_2026_03", "generic", "gl", "Wall Build job cost report, UC Sierra, through March 31, 2026", "2026-04-08T09:00:00-07:00",
    {"claims": [C("cost_incurred_to_date", W.WALLBUILD_INCURRED_Q1, "2026-03-31", entity="UC Sierra"), C("cost_materials", 150_000, "2026-Q1", entity="UC Sierra"), C("cost_labor", 90_000, "2026-Q1", entity="UC Sierra")]}, document_date="2026-03-31")
doc("wallbuild_costs_2026_03", "generic", "gl", "Wall Build job cost report, UC Sierra, through March 31, 2026", "2026-07-03T10:00:00-07:00",
    {"claims": [C("cost_incurred_to_date", W.WALLBUILD_INCURRED_Q1, "2026-03-31", entity="UC Sierra"), C("cost_materials", 160_000, "2026-Q1", entity="UC Sierra"), C("cost_labor", 80_000, "2026-Q1", entity="UC Sierra")],
     "note": "v2: $10,000 of installer labor reclassified to materials (sub-contracted anchors); total cost unchanged"}, document_date="2026-07-03", version=2, supersedes="wallbuild_costs_2026_03@v1", correction_id="E24")

doc("contract_pacific_lumen", "generic", "contracts", "Pacific Lumen Labs wellness contract", "2025-09-01T10:00:00-07:00",
    {"text": "Pacific Lumen Labs corporate wellness contract, $24,000 per month, payment terms net 45.", "claims": [C("payment_terms_days", 45, unit="days", entity="Pacific Lumen Labs"), C("monthly_fee", W.E21_INVOICE, entity="Pacific Lumen Labs")]},
    document_date="2025-09-01")
doc("customer_master", "generic", "erp", "Customer master (AR)", "2026-01-05T12:00:00-08:00",
    {"claims": [C("payment_terms_days", 30, unit="days", entity="Pacific Lumen Labs"), C("payment_terms_days", 30, unit="days", entity="Northgate Biotech")]}, document_date="2026-01-05")
doc("customer_master", "generic", "erp", "Customer master (AR)", "2026-06-22T10:00:00-07:00",
    {"claims": [C("payment_terms_days", 45, unit="days", entity="Pacific Lumen Labs"), C("payment_terms_days", 30, unit="days", entity="Northgate Biotech")],
     "note": "v2: Pacific Lumen terms corrected to net 45 per contract (owner: Priya Nair approved)"}, document_date="2026-06-22", version=2, supersedes="customer_master@v1", correction_id="E16")
doc("ar_invoices_2026_05", "generic", "ar", "Corporate AR invoices issued May 2026", "2026-05-31T18:00:00-07:00",
    {"claims": [C("invoice_amount", W.E16_INVOICE, "2026-05-16", entity="Pacific Lumen Labs"), C("invoice_amount", 12_000, "2026-05-01", entity="Northgate Biotech"),
                C("ar_balance", 48_000, "2026-05-31", entity="Northgate Biotech"), C("ar_balance", 18_000, "2026-05-31", entity="Pacific Lumen Labs"),
                C("invoice_age_days", 31, "2026-06-16", entity="Pacific Lumen Labs", unit="days")]}, document_date="2026-05-31")

doc("order_form_northgate_amendment", "generic", "crm", "Order form: Northgate amendment (sales CRM)", "2026-06-17T09:00:00-07:00",
    {"claims": [C("seats", W.E13_SEATS, unit="count", entity="Northgate Biotech"), C("seat_price", W.E13_LIST_PRICE, entity="Northgate Biotech", unit="USD/seat"), C("term_months", 12, unit="months", entity="Northgate Biotech")]},
    document_date="2026-06-17")
doc("order_form_northgate_amendment", "generic", "crm", "Order form: Northgate amendment (sales CRM)", "2026-06-24T10:00:00-07:00",
    {"claims": [C("seats", W.E13_SEATS, unit="count", entity="Northgate Biotech"), C("seat_price", W.E13_ACTUAL_PRICE, entity="Northgate Biotech", unit="USD/seat"), C("term_months", 12, unit="months", entity="Northgate Biotech")],
     "note": "v2: sales keyed the list price; actual contracted price is $45"}, document_date="2026-06-24", version=2, supersedes="order_form_northgate_amendment@v1", correction_id="E13")

# ------------------------------------------------------------------ Q1 operations: AP, accruals, utilities, opex, payroll tax, FX
def ap_claims(legal_mar, route_mar):
    cl = []
    for p, v in W.ROUTE_SETTING_MONTHLY.items():
        cl.append(C("route_setting", route_mar if p == "2026-03" else v, p, account="6200"))
    for p, v in W.LEGAL_MONTHLY.items():
        cl.append(C("legal", legal_mar if p == "2026-03" else v, p, account="6300"))
    cl += [C("corporate_payroll", W.CORP_PAYROLL_Q1, "2026-Q1"), C("corporate_ga", W.CORP_GA_Q1, "2026-Q1")]
    return cl
doc("ap_invoices_2026_q1", "generic", "ap", "AP invoices and corporate costs, Q1 2026", "2026-04-09T10:00:00-07:00", {"claims": ap_claims(W.LEGAL_MONTHLY["2026-03"], W.ROUTE_SETTING_MONTHLY["2026-03"])}, document_date="2026-03-31")
doc("ap_invoices_2026_q1", "generic", "ap", "AP invoices and corporate costs, Q1 2026", "2026-05-20T14:00:00-07:00",
    {"claims": ap_claims(W.LEGAL_MONTHLY["2026-03"] + 14_000, W.ROUTE_SETTING_MONTHLY["2026-03"]), "note": "v2: March employment-counsel invoice $14,000 (dated March 28, received March 30) found un-accrued"},
    document_date="2026-03-31", version=2, supersedes="ap_invoices_2026_q1@v1", correction_id="E10")
doc("ap_invoices_2026_q1", "generic", "ap", "AP invoices and corporate costs, Q1 2026", "2026-05-27T10:00:00-07:00",
    {"claims": ap_claims(W.LEGAL_MONTHLY["2026-03"] + 14_000, W.ROUTE_SETTING_MONTHLY["2026-03"] + 22_500), "note": "v3: March route-setting invoice $22,500 dated April 3 surfaced in the AP inbox; signed March timesheets were in the contractor portal on March 31"},
    document_date="2026-03-31", version=3, supersedes="ap_invoices_2026_q1@v2", correction_id="E02")

util = []
for g in W.GYMS:
    for p, v in W.UTILITIES_Q1[g].items():
        if g == "G3" and p == "2026-03":
            continue
        util.append(C("utilities", v, p, entity=g, account="6100"))
doc("utilities_invoices_2026_q1", "generic", "ap", "Utilities invoices received, Q1 2026", "2026-04-08T15:00:00-07:00", {"claims": util}, document_date="2026-03-31")
doc("accrual_workpaper_2026_03", "generic", "gl", "March 2026 accrual workpaper", "2026-04-09T16:00:00-07:00",
    {"text": "Bayline Power, Sacramento (G3), March 2026: invoice not yet received. Accrued at $48,000 based on the March 2025 invoice and January-February 2026 usage.",
     "claims": [C("utilities", W.G3_MARCH_ACCRUAL, "2026-03", entity="G3", account="6100"), C("accrual_basis", None, text="estimate from prior-year March and Jan-Feb 2026 usage", entity="G3")]},
    document_date="2026-03-31")
doc("accrual_workpaper_2026_03", "generic", "gl", "March 2026 accrual workpaper", "2026-04-12T09:00:00-07:00",
    {"text": "Bayline Power invoice BP-33817 received April 12, 2026 for March service: $51,900 (+8.1% vs the $48,000 accrual). True-up booked in April.",
     "claims": [C("utilities", W.G3_MARCH_INVOICE, "2026-03", entity="G3", account="6100"), C("accrual_basis", None, text="actual invoice BP-33817 dated April 11, 2026", entity="G3"),
                C("utilities_trueup", W.G3_MARCH_INVOICE - W.G3_MARCH_ACCRUAL, "2026-04", entity="G3", account="6100")]},
    document_date="2026-04-11", version=2, supersedes="accrual_workpaper_2026_03@v1", correction_id="E01")
doc("gym_opex_2026_q1", "generic", "gl", "Gym operating expenses Q1 2026 (payroll, rent, other; excludes utilities)", "2026-04-09T11:00:00-07:00",
    {"claims": [C("gym_opex_ex_utilities", W.GYM_OPEX_Q1[g] - sum(W.UTILITIES_Q1[g].values()), "2026-Q1", entity=g) for g in W.GYMS]
               + [C("depreciation", W.DEPRECIATION_Q1, "2026-Q1", account="6700"), C("interest_expense", W.INTEREST_Q1, "2026-Q1"), C("realized_fx", 0, "2026-Q1", account="7100")]},
    document_date="2026-03-31")

def payroll_tax_claims(trueup: bool):
    cl = [C("sui_rate", 0.039 if trueup else 0.034, "2026", unit="ratio")]
    for m in range(1, 7):
        cl.append(C("payroll_tax", W.PAYROLL_TAX_MONTHLY_2026 + (round(W.E18_YTD_TRUEUP / 6) if trueup else 0), f"2026-{m:02d}", account="6500"))
    return cl
doc("payroll_tax_2026", "generic", "payroll", "Payroll tax register 2026", "2026-04-05T09:00:00-07:00", {"claims": payroll_tax_claims(False)}, document_date="2026-03-31")
doc("payroll_tax_2026", "generic", "payroll", "Payroll tax register 2026", "2026-06-04T09:00:02-07:00",
    {"claims": payroll_tax_claims(True), "note": "v2: EDD revised the 2026 UI rate to 3.9% retroactive to January 1; +$6,200 YTD"},
    document_date="2026-06-04", version=2, supersedes="payroll_tax_2026@v1", correction_id="E18")

doc("fx_rates_2026_03", "generic", "rate_vendor", "EUR/USD daily rates March 2026 (rate vendor)", "2026-03-20T17:00:00-07:00",
    {"claims": [C("eurusd", W.E09_RATE_V1, "2026-03-20", unit="rate"), C("eurusd", 1.0810, "2026-03-19", unit="rate"), C("eurusd", 1.0835, "2026-03-23", unit="rate")]}, document_date="2026-03-20")
doc("fx_rates_2026_03", "generic", "rate_vendor", "EUR/USD daily rates March 2026 (rate vendor)", "2026-07-02T10:00:00-07:00",
    {"claims": [C("eurusd", W.E09_RATE_V2, "2026-03-20", unit="rate"), C("eurusd", 1.0810, "2026-03-19", unit="rate"), C("eurusd", 1.0835, "2026-03-23", unit="rate")],
     "note": "v2: vendor correction notice: 2026-03-20 EUR/USD was published with transposed digits (1.0280); the correct fixing is 1.0820"},
    document_date="2026-03-20", version=2, supersedes="fx_rates_2026_03@v1", correction_id="E09")
doc("kletterwerk_invoice_2026_03", "generic", "ap", "Kletterwerk GmbH invoice KW-5520 (climbing holds)", "2026-03-21T09:00:00-07:00",
    {"claims": [C("invoice_amount_eur", W.E09_EUR, "2026-03-20", entity="Kletterwerk GmbH", unit="EUR"), C("useful_life_months", 60, unit="months", entity="Kletterwerk GmbH")]}, document_date="2026-03-20")
doc("vendor_master", "generic", "erp", "Vendor master (AP)", "2026-01-05T12:30:00-08:00",
    {"claims": [C("iban", None, text="DE89 3704 0044 0532 0130 00", entity="Kletterwerk GmbH"), C("email_domain", None, text="kletterwerk.de", entity="Kletterwerk GmbH"),
                C("owner", None, text="Priya Nair (AP Specialist)", entity="Kletterwerk GmbH"), C("iban", None, text="US12 SUMMIT 0099 2231", entity="Summit Mats Supply")]}, document_date="2026-01-05")
doc("email_kletterwerk_iban_2026_06_10", "generic", "ap_inbox", "Email: 'Updated bank details' from billing@kletterwerk-gmbh.co", "2026-06-10T09:30:00-07:00",
    {"text": "From: billing@kletterwerk-gmbh.co. Subject: Updated bank details. Please update our IBAN to LT12 1000 0111 0100 1000 for all future payments, effective immediately.",
     "claims": [C("iban", None, text="LT12 1000 0111 0100 1000", entity="Kletterwerk GmbH"), C("sender_domain", None, text="kletterwerk-gmbh.co", entity="Kletterwerk GmbH")]}, document_date="2026-06-10")

# ------------------------------------------------------------------ cash, bank, ACH
doc("bank_statement_2026_03", "generic", "bank", "Redwood Bank statement, March 2026", "2026-04-03T08:00:00-07:00",
    {"claims": [C("cash_balance", W.CASH_2026_03_31, "2026-03-31", account="1010"), C("cash_collected", 9_900_000, "2026-Q1")]}, document_date="2026-03-31")
doc("bank_statement_2026_05", "generic", "bank", "Redwood Bank statement, May 2026", "2026-06-01T08:00:00-07:00",
    {"claims": [C("cash_balance", W.CASH_2026_05_31_V1, "2026-05-31", account="1010"), C("cash_collected", W.MAY_COLLECTED_V1, "2026-05"),
                C("wire_credit", W.E05_WIRE, "2026-05-30", entity="Northgate Biotech")]}, document_date="2026-05-31")
doc("bank_statement_2026_05", "generic", "bank", "Redwood Bank statement, May 2026", "2026-06-16T14:00:00-07:00",
    {"claims": [C("cash_balance", W.CASH_2026_05_31_V2, "2026-05-31", account="1010"), C("cash_collected", W.MAY_COLLECTED_V2, "2026-05"),
                C("wire_credit", 0, "2026-05-30", entity="Northgate Biotech")],
     "note": "v2: corrected statement: the $40,000 wire credited May 30 belonged to another bank customer and was reversed by the bank"},
    document_date="2026-05-31", version=2, supersedes="bank_statement_2026_05@v1", correction_id="E05")
doc("gl_cash_2026_05", "generic", "gl", "GL cash account 1010, May 2026", "2026-05-31T20:00:00-07:00",
    {"claims": [C("book_cash_balance", 1_580_000, "2026-05-31", account="1010")]}, document_date="2026-05-31")
util_q2 = []
for g in W.GYMS:
    base = W.UTILITIES_Q1[g]["2026-03"]
    for p, f in (("2026-04", 0.92), ("2026-05", 0.85), ("2026-06", 0.80)):
        util_q2.append(C("utilities", round(base * f / 100) * 100, p, entity=g, account="6100"))
doc("utilities_invoices_2026_q2", "generic", "ap", "Utilities invoices received, April-June 2026 (June: five of six gyms)", "2026-07-07T16:00:00-07:00", {"claims": util_q2}, document_date="2026-06-30")


def ach(collected, r01n, r01, r10):
    return [C("debits_presented", W.ACH_0601_COLLECTED_V1, "2026-06-01"), C("collected", collected, "2026-06-01"),
            C("returns_r01_count", r01n, "2026-06-01", unit="count"), C("returns_r01", r01, "2026-06-01"), C("returns_r10", r10, "2026-06-01")]
doc("ach_batch_2026_06_01", "generic", "ach", "ACH dues batch June 1, 2026", "2026-06-01T12:00:00-07:00", {"claims": ach(W.ACH_0601_COLLECTED_V1, 0, 0, 0)}, document_date="2026-06-01")
doc("ach_batch_2026_06_01", "generic", "ach", "ACH dues batch June 1, 2026", "2026-06-03T16:00:00-07:00",
    {"claims": ach(W.ACH_0601_COLLECTED_V1 - W.E03_R01_AMOUNT, W.E03_R01_COUNT, W.E03_R01_AMOUNT, 0), "note": "v2: return file June 3: 14 R01 (insufficient funds) returns totaling $2,310"},
    document_date="2026-06-03", version=2, supersedes="ach_batch_2026_06_01@v1", correction_id="E03")
doc("ach_batch_2026_06_01", "generic", "ach", "ACH dues batch June 1, 2026", "2026-07-07T15:00:00-07:00",
    {"claims": ach(W.ACH_0601_COLLECTED_V1 - W.E03_R01_AMOUNT - W.E04_R10_AMOUNT, W.E03_R01_COUNT, W.E03_R01_AMOUNT, W.E04_R10_AMOUNT),
     "note": "v3: return file July 7: one R10 (customer advises not authorized) for $189, member M-48812, with a signed Written Statement of Unauthorized Debit. 36 days after the entry."},
    document_date="2026-07-07", version=3, supersedes="ach_batch_2026_06_01@v2", correction_id="E04")
doc("bank_feed_2026_06_w1", "generic", "bank", "Bank feed, week of June 1, 2026", "2026-06-02T08:00:00-07:00",
    {"claims": [C("bank_fee", W.E17_FEE_V1, "2026-06-02", account="6400"), C("deposits", 987_000, "2026-06-01")]}, document_date="2026-06-02")
doc("bank_feed_2026_06_w1", "generic", "bank", "Bank feed, week of June 1, 2026", "2026-06-04T09:00:00-07:00",
    {"claims": [C("bank_fee", W.E17_FEE_V2, "2026-06-02", account="6400"), C("deposits", 987_000, "2026-06-01")], "note": "v2: fee revised by the bank from $25.00 to $25.40"},
    document_date="2026-06-04", version=2, supersedes="bank_feed_2026_06_w1@v1", correction_id="E17")
doc("ap_aging_2026_06_12", "generic", "ap", "AP aging for the June 12 payment run", "2026-06-11T17:00:00-07:00",
    {"claims": [C("payable", W.E14_INVOICE, "2026-06-12", entity="Summit Mats Supply INV-2231"), C("payable", W.E14_INVOICE, "2026-06-12", entity="Summit Mats Supply 2231"),
                C("payable", 42_000, "2026-06-12", entity="Bayline Power BP-33840"), C("payable", 15_500, "2026-06-12", entity="Holdfast Route Setting RS-118"),
                C("min_cash_buffer", 500_000)]}, document_date="2026-06-11")
doc("ap_aging_2026_06_12", "generic", "ap", "AP aging for the June 12 payment run", "2026-06-12T09:20:00-07:00",
    {"claims": [C("payable", W.E14_INVOICE, "2026-06-12", entity="Summit Mats Supply INV-2231"), C("payable", 0, "2026-06-12", entity="Summit Mats Supply 2231"),
                C("payable", 42_000, "2026-06-12", entity="Bayline Power BP-33840"), C("payable", 15_500, "2026-06-12", entity="Holdfast Route Setting RS-118"),
                C("min_cash_buffer", 500_000)], "note": "v2: '2231' is a duplicate of INV-2231 (same PO 7781, same lines, same $18,750); removed before release"},
    document_date="2026-06-12", version=2, supersedes="ap_aging_2026_06_12@v1", correction_id="E14")
doc("remittance_pacific_lumen_2026_07_06", "generic", "bank", "Wire remittance: Pacific Lumen Labs, July 6, 2026", "2026-07-06T11:00:00-07:00",
    {"claims": [C("invoice_amount", W.E21_INVOICE, "2026-06-30", entity="Pacific Lumen Labs"), C("cash_received", W.E21_RECEIVED, "2026-07-06", entity="Pacific Lumen Labs")]}, document_date="2026-07-06")
doc("memo_backdated_2026_03_15", "generic", "ap_inbox", "Vendor memo claiming a March 15 date (captured July 1)", "2026-07-01T10:00:00-07:00",
    {"text": "Dated March 15, 2026. This memo confirms the revised route-setting rates effective March 1.", "claims": [C("claimed_date", None, text="2026-03-15")]}, document_date="2026-03-15")

# ------------------------------------------------------------------ writer
def write_files():
    OUT.mkdir(parents=True, exist_ok=True); PENDING.mkdir(parents=True, exist_ok=True)
    for d in DOCS:
        p = OUT / d["doc_id"]; p.mkdir(exist_ok=True)
        (p / f"{d['version_id'].split('@')[1]}.json").write_text(json.dumps(d, indent=1, default=str))
    for d in PENDING_DOCS:
        (PENDING / f"{d['correction_id']}_{d['version_id'].replace('@', '_')}.json").write_text(json.dumps(d, indent=1, default=str))
    index = [{k: d[k] for k in ("doc_id", "kind", "system", "title", "version_id", "tx_from", "correction_id")} for d in DOCS + PENDING_DOCS]
    (OUT / "index.json").write_text(json.dumps(index, indent=1))


def load_initial():
    """Load sources and only the FIRST version of each document. Later versions are applied by build_history (engine) in order."""
    conn = db.get_conn()
    for d in DOCS:
        if db.q1("SELECT 1 FROM sources WHERE source_id=?", (d["doc_id"],)) is None:
            db.insert("sources", {"source_id": d["doc_id"], "uri_r": f"/r/{d['doc_id']}", "system": d["system"], "kind": d["kind"], "title": d["title"]})
    for d in DOCS:
        if d["supersedes"] is None:
            claims.load_version(d["doc_id"], d["version_id"], d["kind"], d["body"], d["tx_from"], document_date=d["document_date"], supersedes=None, correction_id=None)
    conn.commit()


def later_versions():
    return [d for d in DOCS if d["supersedes"] is not None]


def pending_versions():
    return list(PENDING_DOCS)


if __name__ == "__main__":
    if config.DB_PATH.exists():
        config.DB_PATH.unlink()
        for suf in ("-wal", "-shm"):
            p = Path(str(config.DB_PATH) + suf)
            if p.exists():
                p.unlink()
    db.reset_connection()
    write_files()
    load_initial()
    from trackback.core.llm import gateway as _gw
    n_seed = _gw.import_cache()
    print(f"seeded llm_cache with {n_seed} recorded responses from {config.LLM_CACHE_EXPORT.name}")
    n_src = db.q1("SELECT COUNT(*) n FROM sources")["n"]; n_ver = db.q1("SELECT COUNT(*) n FROM source_versions")["n"]; n_cl = db.q1("SELECT COUNT(*) n FROM claim_versions")["n"]
    print(f"generated: {len(DOCS)} versions written ({len(PENDING_DOCS)} pending live); loaded {n_src} sources, {n_ver} initial versions, {n_cl} claim versions")
