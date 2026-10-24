"""Work orders: one per pinned run. Each is the task text + required outputs (what the real model gets in record mode)
plus the deterministic step list the scripted provider replays. Artifact names are the catalog the answer key references."""
from __future__ import annotations

from .. import claims as CL, v2world as W

GY = W.GYMS


def cid(doc: str, line: str, period: str | None = None, entity: str = "", unit: str = "USD") -> str:
    ps, pe = CL.period_bounds(period)
    return CL.claim_id_for(doc, entity, line, ps, pe, unit)


def read(doc):            return {"tool": "get_document", "args": {"doc_id": doc}, "parallel": True}
def num(name, formula, inputs, period, line, conclusions=None, desc=None):
    a = {"name": name, "formula": formula, "inputs": inputs, "period": period, "line_item": line}
    if conclusions: a["conclusions"] = conclusions
    if desc: a["description"] = desc
    return {"tool": "emit_number", "args": a}
def sent(name, text, claim_ids, period, line, artifacts=None, conclusions=None):
    a = {"name": name, "text_request": text, "claim_ids": claim_ids, "period": period, "line_item": line}
    if artifacts: a["artifact_ids"] = artifacts
    if conclusions: a["conclusions"] = conclusions
    return {"tool": "emit_sentence", "args": a}
def je(name, lines, orig, memo, posting=None, supporters=None, correction_id=None, approver=None):
    a = {"name": name, "lines": lines, "orig_period": orig, "memo": memo}
    if posting: a["posting_period"] = posting
    if supporters: a["supporters"] = supporters
    if correction_id: a["correction_id"] = correction_id
    if approver: a["approver"] = approver
    return {"tool": "propose_journal_entry", "args": a}
def act(name, kind, params, supporters, approver_role, period=None, line=None):
    a = {"name": name, "kind": kind, "params": params, "supporters": supporters, "approver_role": approver_role}
    if period: a["period"] = period
    if line: a["line_item"] = line
    return {"tool": "propose_action", "args": a}
def route(reason, artifact_ids, to_role="controller"):
    return {"tool": "route_to_human", "args": {"reason": reason, "artifact_ids": artifact_ids, "to_role": to_role}}
def finish(summary):     return {"tool": "finish", "args": {"summary": summary}}
def L(account, cents, gym=None): return {"account": account, "amount_cents": int(cents), "gym": gym}

MONTHS_Q1 = ["2026-01", "2026-02", "2026-03"]


# ---------------------------------------------------------------- R0: Q4 2025 certificate (history fixture)
def r0_q4_2025_cert():
    s = [read("credit_agreement"), read("fy2025_monthly_summary"),
         num("net_debt_2025_q4", "nd", {"nd": cid("fy2025_monthly_summary", "net_debt", "2025-12-31")}, "2025-Q4", "net_debt", desc="Net debt at December 31, 2025"),
         num("ttm_adj_ebitda_2025_q4", "q1+q2+q3+q4", {f"q{i}": cid("fy2025_monthly_summary", "ebitda", f"2025-Q{i}") for i in range(1, 5)}, "2025-Q4", "ttm_ebitda", desc="TTM Adjusted EBITDA, FY2025"),
         num("leverage_2025_q4", "nd/ttm", {"nd": "net_debt_2025_q4", "ttm": "ttm_adj_ebitda_2025_q4"}, "2025-Q4", "leverage", {"covenant_max": W.COVENANT_MAX}, "Net leverage ratio Q4 2025"),
         act("cert_send_q4_2025", "certificate_send", {"summary": "Q4 2025 compliance certificate to Redwood Commercial Credit", "recipient": "Redwood Commercial Credit", "period": "2025-Q4", "value_from": "leverage_2025_q4", "conclusions": {"covenant_max": W.COVENANT_MAX}},
             ["leverage_2025_q4", "net_debt_2025_q4", "ttm_adj_ebitda_2025_q4", cid("credit_agreement", "covenant_max_leverage", unit="x")], "cfo", "2025-Q4", "certificate"),
         finish("Q4 2025 certificate drafted at 2.87x")]
    return {"run_id": "R0_q4_2025_cert", "agent": "covenant_comp", "pinned_at": "2026-02-13T10:00:00-08:00",
            "task": "Draft the Q4 2025 compliance certificate for the lender.", "steps": s}


# ---------------------------------------------------------------- R1: Q1 close
def r1_q1_close():
    s = [read(d) for d in ["materiality_memo", "credit_agreement", "billing_export_2026_01", "billing_export_2026_02", "billing_export_2026_03", "pos_summary_2026_q1",
                           "contract_northgate", "wellness_other_schedule_2026", "contract_uc_sierra", "wallbuild_costs_2026_03", "utilities_invoices_2026_q1",
                           "accrual_workpaper_2026_03", "ap_invoices_2026_q1", "gym_opex_2026_q1", "payroll_tax_2026", "fy2025_monthly_summary", "fx_rates_2026_03",
                           "kletterwerk_invoice_2026_03", "bank_statement_2026_03"]]
    for g in GY:
        inputs = {f"d{i}": cid(f"billing_export_2026_0{i}", "monthly_dues", m, g) for i, m in enumerate(MONTHS_Q1, start=1)}
        expr = "d1+d2+d3"
        if W.ANNUAL_RELEASE_TRUE[g]:
            inputs.update({f"a{i}": cid(f"billing_export_2026_0{i}", "annual_release", m, g) for i, m in enumerate(MONTHS_Q1, start=1)})
            expr += "+a1+a2+a3"
        s.append(num(f"q1_membership_revenue_{g}", expr, inputs, "2026-Q1", "membership_revenue", desc=f"Q1 membership revenue, {W.GYM_NAMES[g]} (dues + annual prepaid release)"))
    rel = {f"a{g}": cid("billing_export_2026_03", "annual_release", "2026-03", g) for g in GY if W.ANNUAL_RELEASE_TRUE[g]}
    s.append(num("q1_deferred_release_2026_03", "+".join(rel.keys()), rel, "2026-03", "deferred_revenue_release", desc="March annual-prepaid deferred revenue release, all gyms"))
    s.append(sent("memo_q1_deferred_revenue", "March released $236,000 of annual-prepaid deferred revenue across five gyms, consistent with the February migration of members to annual plans, and it is recognized in March.",
                  list(rel.values()), "2026-03", "deferred_revenue_release", ["q1_deferred_release_2026_03"]))
    s.append(num("q1_membership_revenue", "+".join(f"m{i}" for i in range(6)), {f"m{i}": f"q1_membership_revenue_{g}" for i, g in enumerate(GY)}, "2026-Q1", "membership_revenue", desc="Q1 membership revenue, all gyms"))
    s.append(num("q1_daypass_retail_revenue", "+".join(f"p{i}" for i in range(6)), {f"p{i}": cid("pos_summary_2026_q1", "daypass_retail_revenue", "2026-Q1", g) for i, g in enumerate(GY)}, "2026-Q1", "daypass_revenue", desc="Q1 day pass and retail revenue"))
    wi = {f"n{i}": cid("contract_northgate", "wellness_revenue", m, "Northgate Biotech") for i, m in enumerate(MONTHS_Q1)}
    wi.update({f"o{i}": cid("wellness_other_schedule_2026", "wellness_revenue", m, "Other wellness") for i, m in enumerate(MONTHS_Q1)})
    s.append(num("q1_wellness_revenue", "n0+n1+n2+o0+o1+o2", wi, "2026-Q1", "wellness_revenue", desc="Q1 corporate wellness revenue (ratable)"))
    s.append(num("uc_sierra_progress_pct", "incurred/est_cost*100", {"incurred": cid("wallbuild_costs_2026_03", "cost_incurred_to_date", "2026-03-31", "UC Sierra"), "est_cost": cid("contract_uc_sierra", "estimated_total_cost", None, "UC Sierra")},
                 "2026-Q1", "wallbuild_progress", {"display_decimals": 1}, "UC Sierra percent complete (cost-to-cost) at March 31"))
    s.append(num("q1_wallbuild_revenue", "price*pct/100", {"price": cid("contract_uc_sierra", "contract_price", None, "UC Sierra"), "pct": "uc_sierra_progress_pct"}, "2026-Q1", "wallbuild_revenue", desc="Q1 Wall Build revenue recognized over time"))
    s.append(num("q1_wallbuild_cost", "m+l", {"m": cid("wallbuild_costs_2026_03", "cost_materials", "2026-Q1", "UC Sierra"), "l": cid("wallbuild_costs_2026_03", "cost_labor", "2026-Q1", "UC Sierra")}, "2026-Q1", "wallbuild_cost", desc="Q1 Wall Build cost of revenue (materials + labor)"))
    s.append(num("q1_revenue_total", "m+d+w+b", {"m": "q1_membership_revenue", "d": "q1_daypass_retail_revenue", "w": "q1_wellness_revenue", "b": "q1_wallbuild_revenue"}, "2026-Q1", "revenue", desc="Q1 total revenue"))
    ui = {}
    for g in GY:
        for i, m in enumerate(MONTHS_Q1):
            src = "accrual_workpaper_2026_03" if (g == "G3" and m == "2026-03") else "utilities_invoices_2026_q1"
            ui[f"u{g}{i}"] = cid(src, "utilities", m, g)
    s.append(num("q1_utilities_expense", "+".join(ui.keys()), ui, "2026-Q1", "utilities", desc="Q1 utilities (17 invoices + the G3 March accrual)"))
    for g in GY:
        inputs = {"m": f"q1_membership_revenue_{g}", "dp": cid("pos_summary_2026_q1", "daypass_retail_revenue", "2026-Q1", g), "ox": cid("gym_opex_2026_q1", "gym_opex_ex_utilities", "2026-Q1", g)}
        inputs.update({f"u{i}": ui[f"u{g}{i}"] for i in range(3)})
        s.append(num(f"q1_gym_ebitda_{g}", "m+dp-ox-u0-u1-u2", inputs, "2026-Q1", "gym_ebitda", desc=f"Q1 gym EBITDA, {W.GYM_NAMES[g]}"))
    s.append(num("q1_route_setting_expense", "r0+r1+r2", {f"r{i}": cid("ap_invoices_2026_q1", "route_setting", m) for i, m in enumerate(MONTHS_Q1)}, "2026-Q1", "route_setting", desc="Q1 route-setting contract labor"))
    s.append(num("q1_legal_expense", "l0+l1+l2", {f"l{i}": cid("ap_invoices_2026_q1", "legal", m) for i, m in enumerate(MONTHS_Q1)}, "2026-Q1", "legal", desc="Q1 professional fees, legal"))
    s.append(num("q1_payroll_tax_expense", "p0+p1+p2", {f"p{i}": cid("payroll_tax_2026", "payroll_tax", m) for i, m in enumerate(MONTHS_Q1)}, "2026-Q1", "payroll_tax", desc="Q1 payroll taxes"))
    s.append(num("q1_corporate_costs", "r+l+cp+ga", {"r": "q1_route_setting_expense", "l": "q1_legal_expense", "cp": cid("ap_invoices_2026_q1", "corporate_payroll", "2026-Q1"), "ga": cid("ap_invoices_2026_q1", "corporate_ga", "2026-Q1")}, "2026-Q1", "corporate_costs", desc="Q1 corporate costs"))
    s.append(num("q1_ebitda", "+".join(f"g{i}" for i in range(6)) + "+w+br-bc-cc", {**{f"g{i}": f"q1_gym_ebitda_{g}" for i, g in enumerate(GY)}, "w": "q1_wellness_revenue", "br": "q1_wallbuild_revenue", "bc": "q1_wallbuild_cost", "cc": "q1_corporate_costs"},
                 "2026-Q1", "ebitda", desc="Q1 EBITDA"))
    s.append(num("q1_pretax", "e-dep-int-fx", {"e": "q1_ebitda", "dep": cid("gym_opex_2026_q1", "depreciation", "2026-Q1"), "int": cid("gym_opex_2026_q1", "interest_expense", "2026-Q1"), "fx": cid("gym_opex_2026_q1", "realized_fx", "2026-Q1")}, "2026-Q1", "pretax", desc="Q1 pretax income"))
    s.append(num("ttm_adj_ebitda_2026_q1", "q1+p2+p3+p4", {"q1": "q1_ebitda", "p2": cid("fy2025_monthly_summary", "ebitda", "2025-Q2"), "p3": cid("fy2025_monthly_summary", "ebitda", "2025-Q3"), "p4": cid("fy2025_monthly_summary", "ebitda", "2025-Q4")},
                 "2026-Q1", "ttm_ebitda", desc="TTM Adjusted EBITDA at March 31, 2026 (credit agreement definition)"))
    s.append(num("capex_holds_2026_03", "eur*rate", {"eur": cid("kletterwerk_invoice_2026_03", "invoice_amount_eur", "2026-03-20", "Kletterwerk GmbH", "EUR"), "rate": cid("fx_rates_2026_03", "eurusd", "2026-03-20", unit="rate")}, "2026-03", "capex", desc="Climbing holds capitalized (Kletterwerk KW-5520) in USD"))
    s.append(num("depreciation_schedule_holds_2026", "c/life", {"c": "capex_holds_2026_03", "life": cid("kletterwerk_invoice_2026_03", "useful_life_months", None, "Kletterwerk GmbH", "months")}, "2026", "depreciation_schedule", desc="Monthly depreciation, Kletterwerk holds"))
    s.append(sent("memo_q1_utilities_accrual", "Sacramento March utilities were accrued at $48,000 on the basis of the March 2025 invoice and January-February 2026 usage; the Bayline invoice had not arrived at close.",
                  [cid("accrual_workpaper_2026_03", "utilities", "2026-03", "G3"), cid("accrual_workpaper_2026_03", "accrual_basis", None, "G3")], "2026-03", "utilities"))
    s.append(sent("memo_q1_wallbuild", "UC Sierra is 40% complete on a cost-to-cost basis ($240,000 of $600,000), so $360,000 of the $900,000 contract price is recognized in Q1.",
                  [cid("wallbuild_costs_2026_03", "cost_incurred_to_date", "2026-03-31", "UC Sierra"), cid("contract_uc_sierra", "estimated_total_cost", None, "UC Sierra"), cid("contract_uc_sierra", "contract_price", None, "UC Sierra")],
                  "2026-Q1", "wallbuild_revenue", ["uc_sierra_progress_pct", "q1_wallbuild_revenue"]))
    s.append(je("je_q1_utilities_accrual_G3", [L("6100", W.G3_MARCH_ACCRUAL * 100, "G3"), L("2100", -W.G3_MARCH_ACCRUAL * 100, "G3")], "2026-03", "March utilities accrual, Bayline Power (Sacramento), estimate",
                supporters=[cid("accrual_workpaper_2026_03", "utilities", "2026-03", "G3")]))
    s.append(je("je_q1_wallbuild_revenue", [L("1310", 36_000_000), L("4300", -36_000_000)], "2026-03", "UC Sierra revenue recognized over time, 40% complete", supporters=["q1_wallbuild_revenue"]))
    s.append(finish("Q1 close drafted: revenue $10.42M, EBITDA $1.40M, TTM $5.60M; two entries for the Controller."))
    return {"run_id": "R1_q1_close", "agent": "close_accountant", "pinned_at": "2026-04-10T17:00:00-07:00",
            "task": "Run the Q1 2026 hard close: membership revenue per gym from the billing exports, day pass/retail, wellness, Wall Build over time, utilities incl. the Sacramento accrual, gym EBITDA, corporate costs, EBITDA, pretax, TTM Adjusted EBITDA, the holds capex, and the two closing entries.", "steps": s}


# ---------------------------------------------------------------- R2: Q1 board deck
def r2_q1_board_deck():
    s = [read(d) for d in ["materiality_memo", "credit_agreement", "fy2026_budget", "fy2025_monthly_summary", "bank_statement_2026_03", "payroll_tax_2026"]]
    s += [num("tile_q1_revenue", "x", {"x": "q1_revenue_total"}, "2026-Q1", "revenue", {"display_rounding": 100_000}, "KPI tile: Q1 revenue ($0.1M)"),
          num("tile_q1_ebitda", "x", {"x": "q1_ebitda"}, "2026-Q1", "ebitda", {"display_rounding": 100_000}, "KPI tile: Q1 EBITDA ($0.1M)"),
          num("tile_q1_ebitda_margin", "e/r*100", {"e": "q1_ebitda", "r": "q1_revenue_total"}, "2026-Q1", "margin", {"display_decimals": 1}, "KPI tile: EBITDA margin %"),
          num("tile_q1_membership_revenue", "x", {"x": "q1_membership_revenue"}, "2026-Q1", "membership_revenue", {"display_rounding": 10_000}, "KPI tile: membership revenue ($0.01M)"),
          num("tile_q1_cash_collected", "x", {"x": cid("bank_statement_2026_03", "cash_collected", "2026-Q1")}, "2026-Q1", "cash_kpi", {"display_rounding": 100_000}, "KPI tile: Q1 cash collected"),
          num("tile_q1_net_leverage", "lev", {"lev": "leverage_2026_q1"}, "2026-Q1", "leverage", {"covenant_max": W.COVENANT_MAX}, "KPI tile: net leverage vs 3.00x covenant (from the Covenant agent's calculation)"),
          num("kpi_q1_revenue_growth_yoy", "(r-p)/p*100", {"r": "q1_revenue_total", "p": cid("fy2025_monthly_summary", "revenue", "2025-Q1")}, "2026-Q1", "growth", {"sign": "up"}, "Q1 revenue growth vs Q1 2025, %"),
          num("kpi_q1_route_setting_qoq", "(q-p)/p*100", {"q": "q1_route_setting_expense", "p": cid("fy2025_monthly_summary", "route_setting", "2025-Q4")}, "2026-Q1", "route_setting_growth", {"sign": "down", "display_decimals": 0}, "Route-setting cost change vs Q4 2025, %"),
          num("bva_q1_revenue", "a-b", {"a": "q1_revenue_total", "b": cid("fy2026_budget", "budget_revenue", "2026-Q1")}, "2026-Q1", "bva_revenue", desc="BvA: revenue vs budget"),
          num("bva_q1_membership", "a-b", {"a": "q1_membership_revenue", "b": cid("fy2026_budget", "budget_membership_revenue", "2026-Q1")}, "2026-Q1", "bva_membership", desc="BvA: membership revenue vs budget"),
          num("bva_q1_utilities", "a-b", {"a": "q1_utilities_expense", "b": cid("fy2026_budget", "budget_utilities", "2026-Q1")}, "2026-Q1", "bva_utilities", desc="BvA: utilities vs budget"),
          num("bva_q1_route_setting", "a-b", {"a": "q1_route_setting_expense", "b": cid("fy2026_budget", "budget_route_setting", "2026-Q1")}, "2026-Q1", "bva_route_setting", desc="BvA: route setting vs budget"),
          num("bva_q1_legal", "a-b", {"a": "q1_legal_expense", "b": cid("fy2026_budget", "budget_legal", "2026-Q1")}, "2026-Q1", "bva_legal", desc="BvA: legal vs budget"),
          num("bva_q1_payroll_tax", "a-b", {"a": "q1_payroll_tax_expense", "b": cid("fy2026_budget", "budget_payroll_tax", "2026-Q1")}, "2026-Q1", "bva_payroll_tax", desc="BvA: payroll tax vs budget"),
          num("bva_q1_ebitda", "a-b", {"a": "q1_ebitda", "b": cid("fy2026_budget", "budget_ebitda", "2026-Q1")}, "2026-Q1", "bva_ebitda", desc="BvA: EBITDA vs budget"),
          num("comp_fy2025_revenue", "x", {"x": cid("fy2025_monthly_summary", "revenue", "2025")}, "2025", "revenue", {"display_rounding": 100_000}, "Comparative: FY2025 revenue"),
          num("comp_fy2025_ebitda", "x", {"x": cid("fy2025_monthly_summary", "ebitda", "2025")}, "2025", "ebitda", {"display_rounding": 10_000}, "Comparative: FY2025 EBITDA"),
          num("kpi_fy2025_ebitda_margin", "e/r*100", {"e": "comp_fy2025_ebitda", "r": "comp_fy2025_revenue"}, "2025", "margin", {"display_decimals": 1}, "Comparative: FY2025 EBITDA margin %"),
          sent("deck_s_revenue_growth", "Q1 revenue grew year over year, led by memberships.", [cid("fy2025_monthly_summary", "revenue", "2025-Q1")], "2026-Q1", "revenue", ["q1_revenue_total", "kpi_q1_revenue_growth_yoy"], {"sign": "up"}),
          sent("deck_s_membership_flux", "Membership revenue was $7.42M in Q1, 0.9% above the $7.35M budget, reflecting the February migration to annual prepaid plans.", [cid("fy2026_budget", "budget_membership_revenue", "2026-Q1")], "2026-Q1", "membership_revenue", ["tile_q1_membership_revenue", "bva_q1_membership"]),
          sent("deck_s_route_setting", "Route-setting costs fell 18% quarter over quarter as the in-house crew replaced contractors.", [cid("fy2025_monthly_summary", "route_setting", "2025-Q4")], "2026-Q1", "route_setting", ["kpi_q1_route_setting_qoq", "q1_route_setting_expense"], {"sign": "down"}),
          sent("deck_s_utilities", "Utilities ran 2% over budget on winter rates at Sacramento.", [cid("fy2026_budget", "budget_utilities", "2026-Q1")], "2026-Q1", "utilities", ["bva_q1_utilities", "q1_utilities_expense"]),
          sent("deck_s_wallbuild", "Wall Build is 40% complete on UC Sierra with $360,000 recognized in Q1.", [], "2026-Q1", "wallbuild_revenue", ["uc_sierra_progress_pct", "q1_wallbuild_revenue"]),
          sent("deck_s_ebitda_margin", "EBITDA margin was 13.4%, 90 bps below the 14.3% full-year budget run-rate.", [cid("fy2026_budget", "budget_ebitda", "2026"), cid("fy2026_budget", "budget_revenue", "2026")], "2026-Q1", "margin", ["tile_q1_ebitda_margin"]),
          sent("deck_s_covenant", "We remain within our 3.00x covenant: net leverage was 2.95x, with about $100k of EBITDA headroom.", [cid("credit_agreement", "covenant_max_leverage", unit="x")], "2026-Q1", "leverage", ["tile_q1_net_leverage", "covenant_headroom_2026_q1"], {"covenant_max": W.COVENANT_MAX}),
          sent("deck_s_cash", "Cash collections were $9.9M in Q1, 95% of billings, and cash closed at $1.5M.", [cid("bank_statement_2026_03", "cash_balance", "2026-03-31")], "2026-Q1", "cash_kpi", ["tile_q1_cash_collected"]),
          sent("deck_s_fy2025_comp", "FY2025 revenue was $39.1M with EBITDA of $5.55M (14.2% margin), the comparative base for 2026.", [], "2025", "ebitda", ["comp_fy2025_revenue", "comp_fy2025_ebitda", "kpi_fy2025_ebitda_margin"]),
          sent("deck_s_payroll_tax", "Payroll taxes were 5% under budget in Q1 at the 3.4% UI rate.", [cid("payroll_tax_2026", "sui_rate", "2026", unit="ratio")], "2026-Q1", "payroll_tax", ["bva_q1_payroll_tax"])]
    tiles = ["tile_q1_revenue", "tile_q1_ebitda", "tile_q1_ebitda_margin", "tile_q1_membership_revenue", "tile_q1_cash_collected", "tile_q1_net_leverage"]
    sents = ["deck_s_revenue_growth", "deck_s_membership_flux", "deck_s_route_setting", "deck_s_utilities", "deck_s_wallbuild", "deck_s_ebitda_margin", "deck_s_covenant", "deck_s_cash", "deck_s_fy2025_comp", "deck_s_payroll_tax"]
    s.append(act("deck_publish_q1_2026", "deck_publish", {"summary": "Q1 2026 board deck published to the board portal", "recipients": "Board of Directors"}, tiles + sents, "controller", "2026-Q1", "deck"))
    s.append(finish("Q1 board deck: 6 tiles, 7 BvA lines, 10 sentences; publish action for the Controller."))
    return {"run_id": "R2_q1_board_deck", "agent": "reporting_analyst", "pinned_at": "2026-04-24T15:00:00-07:00",
            "task": "Build the Q1 2026 board deck: KPI tiles, budget-versus-actuals lines, flux commentary and FY2025 comparatives, then propose publishing it.", "steps": s}


# ---------------------------------------------------------------- R3a: Q1 covenant computation (Covenant agent, April 22; the deck consumes it)
def r3a_q1_covenant_calc():
    s = [read("credit_agreement"), read("bank_statement_2026_03"),
         num("net_debt_2026_q1", "loan-cash", {"loan": cid("credit_agreement", "term_loan_principal"), "cash": cid("bank_statement_2026_03", "cash_balance", "2026-03-31")}, "2026-Q1", "net_debt", desc="Net debt at March 31, 2026"),
         num("leverage_2026_q1", "nd/ttm", {"nd": "net_debt_2026_q1", "ttm": "ttm_adj_ebitda_2026_q1"}, "2026-Q1", "leverage", {"covenant_max": W.COVENANT_MAX}, "Net Leverage Ratio, Q1 2026 (Section 7.11 test)"),
         num("covenant_headroom_2026_q1", "ttm-nd/cmax", {"ttm": "ttm_adj_ebitda_2026_q1", "nd": "net_debt_2026_q1", "cmax": cid("credit_agreement", "covenant_max_leverage", unit="x")}, "2026-Q1", "headroom", {"sign": "up"}, "EBITDA headroom before the covenant breaks"),
         finish("Q1 covenant computed: 2.95x, compliant.")]
    return {"run_id": "R3a_q1_covenant_calc", "agent": "covenant_comp", "pinned_at": "2026-04-22T10:00:00-07:00",
            "task": "Compute net debt and the Net Leverage Ratio at March 31, 2026 from the credit agreement's definition and the Close Accountant's TTM Adjusted EBITDA, so the board deck and the certificate can rest on it.", "steps": s}


# ---------------------------------------------------------------- R3: Q1 compliance certificate (consumes the covenant calc)
def r3_q1_cert():
    s = [read("credit_agreement"),
         sent("cert_s_compliance", "As of March 31, 2026 the Net Leverage Ratio was 2.95x, within the 3.00x maximum under Section 7.11.", [cid("credit_agreement", "covenant_max_leverage", unit="x")], "2026-Q1", "leverage", ["leverage_2026_q1"], {"covenant_max": W.COVENANT_MAX}),
         act("cert_send_q1_2026", "certificate_send", {"summary": "Q1 2026 compliance certificate to Redwood Commercial Credit (CFO signature)", "recipient": "Redwood Commercial Credit", "period": "2026-Q1", "value_from": "leverage_2026_q1", "conclusions": {"covenant_max": W.COVENANT_MAX}},
             ["leverage_2026_q1", "cert_s_compliance", "net_debt_2026_q1", "covenant_headroom_2026_q1"], "cfo", "2026-Q1", "certificate"),
         finish("Q1 certificate: 2.95x, compliant; sent to the CFO for signature.")]
    return {"run_id": "R3_q1_covenant_cert", "agent": "covenant_comp", "pinned_at": "2026-05-15T10:00:00-07:00",
            "task": "Compute net debt and the Net Leverage Ratio at March 31, 2026 from the credit agreement's definition, and draft the Q1 compliance certificate for the CFO to sign.", "steps": s}


# ---------------------------------------------------------------- R4: GM bonuses
def r4_gm_bonus():
    s = [read("comp_plan")]
    for g in GY:
        s.append(num(f"gm_bonus_q1_{g}", "max(0,(e-t)*r)", {"e": f"q1_gym_ebitda_{g}", "t": cid("comp_plan", "gym_ebitda_target", "2026-Q1", g), "r": cid("comp_plan", "gm_bonus_rate", unit="ratio")},
                     "2026-Q1", "bonus_payout", {"tiers": [1]}, f"Q1 GM bonus, {W.GYM_NAMES[g]}: 4% of gym EBITDA above target"))
    s.append(num("gm_bonus_q1_total", "+".join(f"b{i}" for i in range(6)), {f"b{i}": f"gm_bonus_q1_{g}" for i, g in enumerate(GY)}, "2026-Q1", "bonus_payout", desc="Q1 GM bonuses, total"))
    s.append(act("bonus_payout_q1_2026", "bonus_payout", {"summary": "Q1 2026 GM bonus payout via payroll May 31", "per_gym": {g: f"gm_bonus_q1_{g}" for g in GY}}, [f"gm_bonus_q1_{g}" for g in GY] + ["gm_bonus_q1_total"], "hr", "2026-Q1", "bonus_payout"))
    s.append(finish("GM bonuses computed: Oakland $2,000, San Jose $800, Fresno $2,000, others $0."))
    return {"run_id": "R4_q1_gm_bonus", "agent": "covenant_comp", "pinned_at": "2026-05-29T09:00:00-07:00",
            "task": "Compute the Q1 2026 GM bonuses from the comp plan (4% of gym EBITDA above target) and propose the payout for HR and the Controller.", "steps": s}


# ---------------------------------------------------------------- R5: cash refresh June 2
def r5_cash_refresh_0602():
    s = [read(d) for d in ["materiality_memo", "bank_statement_2026_05", "gl_cash_2026_05", "ach_batch_2026_06_01", "billing_export_2026_06", "billing_export_2026_03", "bank_feed_2026_06_w1", "ar_invoices_2026_05", "fy2026_budget"]]
    s += [num("cash_opening_2026_w23", "x", {"x": cid("bank_statement_2026_05", "cash_balance", "2026-05-31")}, "2026-W23", "cash_forecast", desc="13-week forecast opening balance (May 31 bank balance)"),
          num("kpi_may_cash_collected", "x", {"x": cid("bank_statement_2026_05", "cash_collected", "2026-05")}, "2026-05", "cash_kpi", {"display_rounding": 10_000}, "KPI: May cash collected"),
          num("recon_cash_2026_05", "bank-book", {"bank": cid("bank_statement_2026_05", "cash_balance", "2026-05-31"), "book": cid("gl_cash_2026_05", "book_cash_balance", "2026-05-31")}, "2026-05", "cash_recon", desc="May bank reconciliation: unreconciled difference (the unidentified $40k wire applied to Northgate)"),
          num("ar_northgate_2026_05_31", "ar-wire", {"ar": cid("ar_invoices_2026_05", "ar_balance", "2026-05-31", "Northgate Biotech"), "wire": cid("bank_statement_2026_05", "wire_credit", "2026-05-30", "Northgate Biotech")}, "2026-05", "ar_balance", {"max": 24_000}, "Northgate AR after applying the May 30 wire (over-60-days test: max two months billing)"),
          num("recon_bank_fee_2026_06_w1", "f", {"f": cid("bank_feed_2026_06_w1", "bank_fee", "2026-06-02")}, "2026-06", "cash_recon", desc="Recon line: bank fee June 2"),
          num("cf_2026_w23_actual_collections", "c", {"c": cid("ach_batch_2026_06_01", "collected", "2026-06-01")}, "2026-W23", "cash_actual", desc="Week 23 actual collections (June 1 ACH batch)"),
          num("ar_member_dues_2026_06", "+".join(f"b{i}" for i in range(6)) + "-c", {**{f"b{i}": cid("billing_export_2026_06", "monthly_dues", "2026-06", g) for i, g in enumerate(GY)}, "c": cid("ach_batch_2026_06_01", "collected", "2026-06-01")}, "2026-06", "member_ar", desc="Member dues AR after the June 1 batch")]
    dues = {f"b{i}": cid("billing_export_2026_06", "monthly_dues", "2026-06", g) for i, g in enumerate(GY)}
    dues.update({f"m{i}": cid("billing_export_2026_03", "monthly_dues", "2026-03", g) for i, g in enumerate(GY)})
    s.append(num("cf_2026_weekly_dues", "(" + "+".join(dues) + ")/2/4.33", dues, "2026-H2", "cash_forecast", desc="Weekly dues run-rate (average of the March and June monthly dues billings)"))
    prev = "cash_opening_2026_w23"
    for w in range(23, 36):
        inputs = {"p": prev, "d": "cf_2026_weekly_dues" if w != 23 else "cf_2026_w23_actual_collections", "o": cid("fy2026_budget", "weekly_opex_cash", "2026")}
        s.append(num(f"cf_2026_w{w}", "p+d-o", inputs, f"2026-W{w}", "cash_forecast", {"min_buffer": 500_000}, f"13-week cash forecast: ending balance week {w}"))
        prev = f"cf_2026_w{w}"
    s.append(sent("cash_s_may", "May collections were $3.31M and cash closed at $1.62M, with the forecast staying above the $500k buffer through August.", [], "2026-05", "cash_kpi", ["kpi_may_cash_collected", "cash_opening_2026_w23", "cf_2026_w35"]))
    s.append(finish("Cash refresh: opening $1.62M, 13 weekly cells, May KPI, AR lines."))
    return {"run_id": "R5_cash_refresh_0602", "agent": "reporting_analyst", "pinned_at": "2026-06-02T09:00:00-07:00",
            "task": "Refresh the 13-week cash forecast (weeks 23-35) from the May bank statement, the June 1 ACH batch and the June billing; produce the May cash KPI, the May bank reconciliation line and the AR lines.", "steps": s}


# ---------------------------------------------------------------- R6: H2 forecast June 5
def r6_h2_forecast():
    s = [read(d) for d in ["contract_northgate", "wellness_other_schedule_2026", "wellness_billing_2026_05", "member_stats_2026", "fy2026_budget"]]
    cells = []
    for m in range(6, 13):
        per = f"2026-{m:02d}"
        s.append(num(f"fc_wellness_{per}", "n+o", {"n": cid("contract_northgate", "wellness_revenue", per, "Northgate Biotech"), "o": cid("wellness_other_schedule_2026", "wellness_revenue", per, "Other wellness")}, per, "wellness_forecast", desc=f"Wellness revenue forecast {per}"))
        cells.append(f"fc_wellness_{per}")
    s.append(num("fc_wellness_h2_total", "+".join(f"c{i}" for i in range(7)), {f"c{i}": c for i, c in enumerate(cells)}, "2026-H2", "wellness_forecast", desc="H2 wellness revenue forecast"))
    ytd = {f"n{m}": cid("contract_northgate", "wellness_revenue", f"2026-{m:02d}", "Northgate Biotech") for m in range(1, 6)}
    ytd.update({f"o{m}": cid("wellness_other_schedule_2026", "wellness_revenue", f"2026-{m:02d}", "Other wellness") for m in range(1, 6)})
    ytd["cr"] = cid("wellness_billing_2026_05", "sla_credit", "2026-05", "Northgate Biotech")
    s.append(num("wellness_revenue_ytd_may", "+".join(k for k in ytd if k != "cr") + "+cr", ytd, "2026-05", "wellness_revenue", desc="Wellness revenue January-May actual (net of credits)"))
    s.append(num("fc_membership_h2", "members*dues*6", {"members": cid("member_stats_2026", "active_members", "2026-06", unit="count"), "dues": cid("fy2026_budget", "avg_monthly_dues", "2026")}, "2026-H2", "membership_forecast", desc="H2 membership revenue forecast (members x average dues x 6)"))
    s.append(num("fc_revenue_h2_total", "m+w", {"m": "fc_membership_h2", "w": "fc_wellness_h2_total"}, "2026-H2", "revenue_forecast", {"display_rounding": 100_000}, "H2 revenue forecast"))
    s.append(sent("fc_s_h2", "H2 revenue is forecast at $6.1M, with corporate wellness contributing $224,000 on the current contract base.", [], "2026-H2", "revenue_forecast", ["fc_revenue_h2_total", "fc_wellness_h2_total"]))
    s.append(finish("H2 forecast: wellness cells June-December, membership run-rate, total."))
    return {"run_id": "R6_h2_forecast", "agent": "reporting_analyst", "pinned_at": "2026-06-05T10:00:00-07:00",
            "task": "Build the H2 2026 revenue forecast: wellness revenue per month from the contract schedules, the membership run-rate, the YTD wellness actual, and a summary sentence.", "steps": s}


# ---------------------------------------------------------------- R7: AP payment run June 12
def r7_ap_run(pin="2026-06-12T09:00:00-07:00", suffix=""):
    pay = {"i1": cid("ap_aging_2026_06_12", "payable", "2026-06-12", "Summit Mats Supply INV-2231"), "i2": cid("ap_aging_2026_06_12", "payable", "2026-06-12", "Summit Mats Supply 2231"),
           "i3": cid("ap_aging_2026_06_12", "payable", "2026-06-12", "Bayline Power BP-33840"), "i4": cid("ap_aging_2026_06_12", "payable", "2026-06-12", "Holdfast Route Setting RS-118")}
    s = [read("ap_aging_2026_06_12"), read("bank_statement_2026_05"), read("vendor_master"),
         num(f"ap_run_0612_total{suffix}", "i1+i2+i3+i4", pay, "2026-06", "payment", desc="June 12 payment run total"),
         num(f"ap_run_0612_cash_after{suffix}", "cash-t", {"cash": cid("bank_statement_2026_05", "cash_balance", "2026-05-31"), "t": f"ap_run_0612_total{suffix}"}, "2026-06", "cash_floor", {"min_buffer": 500_000}, "Cash after the run vs the $500k floor"),
         act(f"payment_run_0612{suffix}", "payment_run", {"summary": "AP payment run June 12, 2026", "invoices": list(pay.values())}, [f"ap_run_0612_total{suffix}", f"ap_run_0612_cash_after{suffix}"] + list(pay.values()), "ap", "2026-06", "payment"),
         finish("Payment run prepared for AP release.")]
    return {"run_id": f"R7_ap_run_0612{suffix}", "agent": "close_accountant", "pinned_at": pin,
            "task": "Prepare the June 12 AP payment run from the AP aging; check the cash floor; propose the run for AP release.", "steps": s}


# ---------------------------------------------------------------- R8: Q2 estimated tax June 15
def r8_q2_tax():
    s = [read("company_policies"), read("fy2026_budget"),
         num("q2_estimated_tax_2026", "pretax*rate", {"pretax": "q1_pretax", "rate": cid("fy2026_budget", "federal_tax_rate", "2026", unit="ratio")}, "2026-Q2", "tax_payment", desc="Q2 federal estimated payment: 21% of the latest Q1 pretax (annualized method, company policy)"),
         act("tax_payment_q2_2026", "tax_payment", {"summary": "Q2 2026 federal estimated tax payment (EFTPS) June 15", "payee": "US Treasury"}, ["q2_estimated_tax_2026", cid("company_policies", "tax_overpayment_policy")], "controller", "2026-Q2", "tax_payment"),
         finish("Q2 estimated tax computed from the current Q1 pretax.")]
    return {"run_id": "R8_q2_est_tax", "agent": "covenant_comp", "pinned_at": "2026-06-15T10:00:00-07:00",
            "task": "Compute the Q2 2026 federal estimated tax payment from the current Q1 pretax income and propose the payment.", "steps": s}


# ---------------------------------------------------------------- R5b: cash refresh June 16 (AR past due, dunning)
def r5b_cash_refresh_0616():
    inv = cid("ar_invoices_2026_05", "invoice_amount", "2026-05-16", "Pacific Lumen Labs")
    age = cid("ar_invoices_2026_05", "invoice_age_days", "2026-06-16", "Pacific Lumen Labs", "days")
    terms = cid("customer_master", "payment_terms_days", None, "Pacific Lumen Labs", "days")
    s = [read("customer_master"), read("ar_invoices_2026_05"),
         num("ar_pacific_lumen_days_past_due_0616", "age-terms", {"age": age, "terms": terms}, "2026-06", "ar_aging", {"sign": "up"}, "Pacific Lumen invoice: days past due (positive = past due)"),
         num("cf_0616_collections_w25", "inv*(1 if age-terms>=0 else 0)", {"inv": inv, "age": age, "terms": terms}, "2026-W25", "cash_forecast", desc="Expected Pacific Lumen collection, week 25"),
         num("cf_0616_collections_w27", "inv*(1 if age-terms<0 else 0)", {"inv": inv, "age": age, "terms": terms}, "2026-W27", "cash_forecast", desc="Expected Pacific Lumen collection, week 27"),
         act("dunning_email_pacific_lumen_0616", "dunning_email", {"summary": "Past-due reminder to Pacific Lumen Labs for invoice of May 16 ($18,000)", "customer": "Pacific Lumen Labs", "amount": 18_000}, ["ar_pacific_lumen_days_past_due_0616", inv, terms], "ap", "2026-06", "collections"),
         finish("AR aging refreshed; one dunning email proposed.")]
    return {"run_id": "R5b_cash_refresh_0616", "agent": "reporting_analyst", "pinned_at": "2026-06-16T09:00:00-07:00",
            "task": "Weekly AR aging refresh: compute days past due for corporate invoices from the customer master terms, re-time expected collections, and propose dunning where past due.", "steps": s}


# ---------------------------------------------------------------- R9: June commissions
def r9_commissions():
    s = [read("comp_plan"), read("order_form_northgate_amendment"),
         num("commission_northgate_amendment", "seats*price*term*rate", {"seats": cid("order_form_northgate_amendment", "seats", None, "Northgate Biotech", "count"), "price": cid("order_form_northgate_amendment", "seat_price", None, "Northgate Biotech", "USD/seat"),
                                                                       "term": cid("order_form_northgate_amendment", "term_months", None, "Northgate Biotech", "months"), "rate": cid("comp_plan", "commission_rate", unit="ratio")},
             "2026-06", "commission_payout", desc="Commission on the Northgate amendment: 8% of first-year contract value"),
         act("commission_payout_0620", "commission_payout", {"summary": "June payroll commission, rep A. Reyes (Northgate amendment)", "rep": "A. Reyes"}, ["commission_northgate_amendment"], "vp_sales", "2026-06", "commission_payout"),
         finish("Commission computed from the order form.")]
    return {"run_id": "R9_june_commissions", "agent": "covenant_comp", "pinned_at": "2026-06-19T09:00:00-07:00",
            "task": "Compute the June sales commission on the Northgate amendment from the order form and the comp plan; propose the payout.", "steps": s}


# ---------------------------------------------------------------- R10: June close (in progress at 'now')
def r10_june_close():
    s = [read(d) for d in ["materiality_memo", "company_policies", "accrual_workpaper_2026_03", "utilities_invoices_2026_q2", "fy2026_budget", "payroll_tax_2026", "ach_batch_2026_06_01",
                           "wellness_billing_2026_05", "remittance_pacific_lumen_2026_07_06", "norm_pacific_lumen_short_pay", "bayline_history"]]
    apr = {f"u{i}": cid("utilities_invoices_2026_q2", "utilities", "2026-04", g) for i, g in enumerate(GY)}
    apr["tu"] = cid("accrual_workpaper_2026_03", "utilities_trueup", "2026-04", "G3")
    apr["b"] = cid("fy2026_budget", "budget_utilities", "2026-04")
    s += [num("bva_2026_04_utilities", "+".join(k for k in apr if k.startswith("u")) + "+tu-b", apr, "2026-04", "bva_utilities", desc="April BvA: utilities (incl. the Sacramento March true-up)"),
          num("h1_payroll_tax_bva", "+".join(f"p{m}" for m in range(1, 7)) + "-b", {**{f"p{m}": cid("payroll_tax_2026", "payroll_tax", f"2026-{m:02d}") for m in range(1, 7)}, "b": cid("fy2026_budget", "budget_payroll_tax", "2026-H1")}, "2026-H1", "bva_payroll_tax", desc="H1 BvA: payroll taxes (revised UI rate)"),
          num("june_utilities_accrual_G3", "may", {"may": cid("utilities_invoices_2026_q2", "utilities", "2026-05", "G3")}, "2026-06", "utilities", desc="June utilities accrual, Sacramento (May invoice basis; June is not a winter month, factor 1.00)"),
          je("je_june_utilities_accrual_G3", [L("6100", 3_840_000, "G3"), L("2100", -3_840_000, "G3")], "2026-06", "June utilities accrual, Bayline Power (Sacramento)", supporters=["june_utilities_accrual_G3"]),
          num("pl_short_pay_0706", "inv-rec", {"inv": cid("remittance_pacific_lumen_2026_07_06", "invoice_amount", "2026-06-30", "Pacific Lumen Labs"), "rec": cid("remittance_pacific_lumen_2026_07_06", "cash_received", "2026-07-06", "Pacific Lumen Labs")}, "2026-07", "ar_balance", desc="Pacific Lumen short-pay on the June 30 invoice"),
          num("pl_auto_clear_0706", "min(sp, fee)", {"sp": "pl_short_pay_0706", "fee": cid("norm_pacific_lumen_short_pay", "typical_wire_fee", None, "Pacific Lumen Labs")}, "2026-07", "bank_fee", desc="Portion auto-cleared to bank fees under norm N2"),
          num("pl_dispute_0706", "sp-ac", {"sp": "pl_short_pay_0706", "ac": "pl_auto_clear_0706"}, "2026-07", "ar_balance", desc="Remaining short-pay routed to a person (likely dispute)"),
          je("je_pl_bank_fee_0706", [L("6400", 3_500), L("1200", -3_500)], "2026-07", "Pacific Lumen wire fee auto-cleared under approved norm N2 ($35)", supporters=["pl_auto_clear_0706"]),
          route("Pacific Lumen short-paid $1,035: $35 matches the intermediary-bank fee pattern; the remaining $1,000 does not and looks like a dispute", ["pl_dispute_0706"], "ap"),
          num("june_sales_credits", "0-cr", {"cr": cid("wellness_billing_2026_05", "sla_credit", "2026-05", "Northgate Biotech")}, "2026-06", "sales_credits", desc="SLA credit to Northgate (May closure) booked in June to 4900"),
          je("je_sla_credit_northgate_0618", [L("4900", 650_000), L("1200", -650_000)], "2026-06", "Northgate SLA credit for the San Jose flood closure May 10-24; May omission logged", supporters=["june_sales_credits"]),
          je("je_r01_reversal_0603", [L("1210", 231_000), L("1015", -231_000)], "2026-06", "Reverse 14 R01 returns ($2,310) from the June 1 batch; restore member AR; retry once per policy T-4", supporters=[cid("ach_batch_2026_06_01", "returns_r01", "2026-06-01")]),
          je("je_r10_reversal_0707", [L("1210", 18_900), L("1015", -18_900)], "2026-07", "Reverse R10 return ($189), member M-48812; suspend debits; open Member Services case; never re-present without new authorization", supporters=[cid("ach_batch_2026_06_01", "returns_r10", "2026-06-01")]),
          act("member_case_m48812", "member_services_case", {"summary": "R10 unauthorized-debit case: suspend ACH, never re-present without new authorization", "member": "M-48812", "suspend_debits": True, "never_represent": True}, [cid("ach_batch_2026_06_01", "returns_r10", "2026-06-01"), cid("company_policies", "r10_policy")], "controller", "2026-07", "collections"),
          sent("close_s_june_status", "June close is in progress: the Sacramento accrual is drafted at the May invoice level, the R01 and R10 returns are reversed, and the Pacific Lumen short-pay is split per the approved norm.", [cid("company_policies", "r10_policy")], "2026-06", "close_status", ["june_utilities_accrual_G3", "pl_auto_clear_0706", "pl_dispute_0706"]),
          finish("June close in progress: accruals, reversals, short-pay split, SLA credit.")]
    return {"run_id": "R10_june_close", "agent": "close_accountant", "pinned_at": "2026-07-08T08:00:00-07:00",
            "task": "June 2026 close (in progress): April utilities BvA with the March true-up, H1 payroll-tax BvA, June accruals, the Pacific Lumen short-pay under the approved norm, the Northgate SLA credit, and the R01/R10 reversals.", "steps": s}


# ---------------------------------------------------------------- E11 correction runs (live)
def r12_e11_first_draft():
    lines = [L("4000", W.E11_DUP[g] * 100, g) for g in GY if W.E11_DUP[g]] + [L("2300", -W.E11_DUP[g] * 100, g) for g in GY if W.E11_DUP[g]]
    s = [read("billing_export_2026_03"), read("company_policies"), read("materiality_memo"),
         je("je_e11_dedupe_v1", lines, "2026-03", "Reverse the duplicated March annual-prepaid release ($118,000): book the correction to the period it belongs to",
            supporters=[cid("billing_export_2026_03", "annual_release", "2026-03", g) for g in GY if W.E11_DUP[g]], correction_id="E11", approver="agent:close_accountant"),
         finish("Correcting entry drafted into March.")]
    return {"run_id": "R12_e11_draft1", "agent": "close_accountant", "pinned_at": "2026-07-08T09:10:00-07:00",
            "task": "Trackback reports E11: the March billing export double-counted the annual-prepaid release ($118,000). Draft the correcting entry and book the correction to the period it belongs to.", "steps": s}


def r13_e11_redraft():
    lines = [L("4000", W.E11_DUP[g] * 100, g) for g in GY if W.E11_DUP[g]] + [L("2300", -W.E11_DUP[g] * 100, g) for g in GY if W.E11_DUP[g]]
    s = [read("billing_export_2026_03"), read("company_policies"), read("materiality_memo"), read("credit_agreement"),
         je("je_e11_dedupe_v2", lines, "2026-03", "OUT-OF-PERIOD (orig 2026-03, E11): reverse the duplicated March annual-prepaid release $118,000; Q1 locked, booked in June per policy C-1; lender package restated separately",
            posting="2026-06", supporters=[cid("billing_export_2026_03", "annual_release", "2026-03", g) for g in GY if W.E11_DUP[g]], correction_id="E11"),
         act("lender_notice_e11", "certificate_send", {"summary": "Corrected Q1 2026 compliance certificate (3.03x, breach), lender notice and waiver request under Section 6.02(f)", "recipient": "Redwood Commercial Credit", "correction_id": "E11"},
             [cid("credit_agreement", "corrected_certificate_clause"), cid("billing_export_2026_03", "annual_release", "2026-03", "G4")], "cfo", "2026-Q1", "certificate"),
         act("control_dedupe_billing_release", "control_proposal", {"summary": "New control: billing-export release batches are checked for duplicate batch ids per gym and month before the deferred-revenue release is booked", "correction_id": "E11"},
             [cid("billing_export_2026_03", "annual_release", "2026-03", "G4")], "controller", "2026-07", "control"),
         finish("Re-drafted in June with an out-of-period tag; lender notice to the CFO; dedupe control proposed.")]
    return {"run_id": "R13_e11_redraft", "agent": "close_accountant", "pinned_at": "2026-07-08T09:15:00-07:00",
            "task": "The Controller rejected the March-dated draft: 'Q1 locked; book in Q2 with OOP tag; restate the lender package separately.' Re-draft accordingly, draft the corrected certificate and lender notice for the CFO, and propose a dedupe control.", "steps": s}


def r12_q2_accrual_estimate_0630():
    """X1 setup: the Close Accountant's pre-close estimate of the June utilities accrual (budget basis) and its method note."""
    s = [read("fy2026_budget"),
         num("q2_utilities_accrual_est_G3", "b", {"b": cid("fy2026_budget", "budget_utilities", "2026-06", "G3")}, "2026-06", "utilities", desc="June utilities accrual estimate, Sacramento (budget basis, pre-close)"),
         sent("q2_accrual_method_note", "The June Sacramento utilities accrual is estimated on the budget basis pending the Bayline invoice; no seasonal factor is applied.", [cid("fy2026_budget", "budget_utilities", "2026-06", "G3")], "2026-06", "utilities", ["q2_utilities_accrual_est_G3"]),
         finish("Pre-close June accrual estimate on the budget basis.")]
    return {"run_id": "R12_q2_accrual_est", "agent": "close_accountant", "pinned_at": "2026-06-30T10:00:00-07:00",
            "task": "Estimate the June Sacramento utilities accrual ahead of the close and document the method.", "steps": s}


def r5d_cash_preview_0701():
    """X1 consumer: the Reporting Analyst's June BvA preview and cash cell rest on the Close Accountant's estimate."""
    s = [read("fy2026_budget"),
         num("bva_2026_06_utilities_prelim", "e-b", {"e": "q2_utilities_accrual_est_G3", "b": cid("fy2026_budget", "budget_utilities", "2026-06", "G3")}, "2026-06", "bva_utilities", desc="June BvA preview: Sacramento utilities (estimate vs budget)"),
         num("cf_0701_w27_utilities", "e", {"e": "q2_utilities_accrual_est_G3"}, "2026-W27", "cash_forecast", desc="Week-27 cash outflow for the Sacramento utilities accrual"),
         sent("cash_s_june_preview", "June utilities at Sacramento are previewed at $52,000, in line with budget, with the outflow landing in week 27.", [cid("fy2026_budget", "budget_utilities", "2026-06", "G3")], "2026-06", "bva_utilities", ["q2_utilities_accrual_est_G3", "bva_2026_06_utilities_prelim"]),
         finish("June preview built on the Close Accountant's estimate.")]
    return {"run_id": "R5d_cash_preview_0701", "agent": "reporting_analyst", "pinned_at": "2026-07-01T09:00:00-07:00",
            "task": "Preview the June utilities budget-versus-actual and the week-27 cash outflow from the Close Accountant's accrual estimate.", "steps": s}


def r5c_cash_refresh_0708():
    s = [read("bank_statement_2026_05"), read("fy2026_budget"),
         num("cf_0708_june_accrued_outflow", "acc", {"acc": "june_utilities_accrual_G3"}, "2026-W28", "cash_forecast", desc="Week-28 expected utilities outflow from the Close Accountant's June accrual"),
         num("cf_0708_w28", "p-o", {"p": "cf_2026_w28", "o": "cf_0708_june_accrued_outflow"}, "2026-W28", "cash_forecast", {"min_buffer": 500_000}, "13-week forecast refresh: week 28 ending balance after the June accrual"),
         finish("Cash refresh: June accrual folded into week 28.")]
    return {"run_id": "R5c_cash_refresh_0708", "agent": "reporting_analyst", "pinned_at": "2026-07-08T08:45:00-07:00",
            "task": "Refresh the cash forecast with the Close Accountant's June accruals.", "steps": s}


HISTORY_RUNS = [r0_q4_2025_cert, r1_q1_close, r3a_q1_covenant_calc, r2_q1_board_deck, r3_q1_cert, r4_gm_bonus, r5_cash_refresh_0602, r6_h2_forecast, r7_ap_run, r8_q2_tax, r5b_cash_refresh_0616, r9_commissions, r12_q2_accrual_estimate_0630, r5d_cash_preview_0701, r10_june_close, r5c_cash_refresh_0708]


def prior_artifacts(order: dict) -> list[str]:
    produced_here = {st["args"]["name"] for st in order["steps"] if "name" in st["args"]}
    prior: list[str] = []
    for st in order["steps"]:
        a = st["args"]
        refs = list((a.get("inputs") or {}).values()) + list(a.get("artifact_ids") or []) + list(a.get("supporters") or []) + ([a["params"]["value_from"]] if isinstance(a.get("params"), dict) and a["params"].get("value_from") else [])
        for r in refs:
            if not r.startswith("c_") and r not in produced_here and r not in prior:
                prior.append(r)
    return prior


def with_handoffs(order: dict) -> dict:
    """Prepend a get_artifact read for every earlier-run artifact the order builds on, so the scripted provider leaves the same
    consumption receipts the real model does (the receipt is the only road a ping may travel)."""
    prior = prior_artifacts(order)
    if not prior:
        return order
    first_write = next((i for i, st in enumerate(order["steps"]) if st["tool"] not in ("get_document", "search_claims", "get_claim", "get_artifact")), len(order["steps"]))
    reads = [{"tool": "get_artifact", "args": {"artifact_id": r}, "parallel": True} for r in prior]
    return {**order, "steps": order["steps"][:first_write] + reads + order["steps"][first_write:]}


def _label(ref: str) -> str:
    """Human label for a claim id (document, line item, entity, period) or an artifact name."""
    if ref.startswith("c_"):
        from .. import graph
        i = graph.claim_info(ref) or {}
        if i:
            per = (i.get("period_start") or "")[:10]
            per_end = (i.get("period_end") or "")[:10]
            span = f" {per}..{per_end}" if per and per_end and per != per_end else (f" {per}" if per else "")
            return f"claim '{i.get('line_item')}'{(' for ' + i['entity']) if i.get('entity') else ''}{span} in document `{i.get('source_id')}`"
        return f"claim {ref}"
    return f"artifact `{ref}`"


def required_outputs_text(order: dict) -> str:
    """The work order as the real model sees it: documents to read, then every required output with its formula and inputs.
    The model still has to read the documents itself (every input must come from its own reads) and cannot type numbers."""
    docs = [st["args"]["doc_id"] for st in order["steps"] if st["tool"] == "get_document"]
    prior = prior_artifacts(order)
    lines = ["Documents to read first (these ids exist; nothing else does):", "  " + ", ".join(f"`{d}`" for d in docs), ""]
    if prior:
        lines += ["Artifacts produced by earlier runs (other agents or your own) that you build on. Read each with get_artifact first (it records what you consumed), then use it by name as an emit_number input, artifact_id or supporter:",
                  "  " + ", ".join(f"`{r}`" for r in prior), ""]
    lines += [
             "Required outputs, in order (use these exact names, formulas and inputs; inputs refer to claims you will have read, by their document/line item/entity/period, or to artifacts you produced):"]
    for st in order["steps"]:
        t, a = st["tool"], st["args"]
        if t == "emit_number":
            ins = "; ".join(f"{k} = {_label(v)}" for k, v in a["inputs"].items())
            concl = f" Conclusions: {a['conclusions']}." if a.get("conclusions") else ""
            lines.append(f"- emit_number `{a['name']}` (line_item {a['line_item']}, period {a['period']}): {a.get('description', '')}. Formula: `{a['formula']}` with {ins}.{concl}")
        elif t == "emit_sentence":
            cl = "; ".join(_label(c) for c in a["claim_ids"]) or "none"
            arts = ", ".join(f"`{x}`" for x in a.get("artifact_ids") or []) or "none"
            concl = f" Conclusions: {a['conclusions']}." if a.get("conclusions") else ""
            lines.append(f"- emit_sentence `{a['name']}` (line_item {a['line_item']}, period {a['period']}): text_request: \"{a['text_request']}\"; claim_ids: {cl}; artifact_ids: {arts}.{concl}")
        elif t == "propose_journal_entry":
            ls = "; ".join(f"{l['account']} {l.get('gym') or ''} {l['amount_cents']} cents" for l in a["lines"])
            sup = ", ".join(_label(x) for x in a.get("supporters") or []) or "none"
            extra = (f" posting_period {a['posting_period']};" if a.get("posting_period") else "") + (f" correction_id {a['correction_id']};" if a.get("correction_id") else "") + (f" approver '{a['approver']}';" if a.get("approver") else "")
            lines.append(f"- propose_journal_entry `{a['name']}`: lines [{ls}]; orig_period {a['orig_period']};{extra} memo: \"{a['memo']}\"; supporters: {sup}.")
        elif t == "propose_action":
            sup = ", ".join(_label(x) for x in a["supporters"])
            lines.append(f"- propose_action `{a['name']}` (kind {a['kind']}, approver_role {a['approver_role']}{', period ' + a['period'] if a.get('period') else ''}{', line_item ' + a['line_item'] if a.get('line_item') else ''}): params {a['params']}; supporters: {sup}.")
        elif t == "route_to_human":
            lines.append(f"- route_to_human (to {a.get('to_role', 'controller')}): reason \"{a['reason']}\"; artifact_ids {a['artifact_ids']}.")
    lines.append("")
    lines.append("Call finish only after every required output above exists. Do not invent document ids; if a read is refused, say so in the finish summary and continue with the rest.")
    return "\n".join(lines)


# ---------------------------------------------------------------- follow-up runs after history corrections (the agent books the fix)
def fu_e01():
    s = [read("accrual_workpaper_2026_03"), read("materiality_memo"),
         num("utilities_trueup_G3_2026_04", "t", {"t": cid("accrual_workpaper_2026_03", "utilities_trueup", "2026-04", "G3")}, "2026-04", "utilities", desc="Bayline March true-up booked in April (estimate change, ASC 250)"),
         je("je_e01_utilities_trueup", [L("6100", 390_000, "G3"), L("2100", -390_000, "G3")], "2026-04", "Bayline Power March invoice $51,900 vs $48,000 accrual: +$3,900 true-up booked in April (estimate change; March not reopened)", supporters=["utilities_trueup_G3_2026_04"], correction_id="E01"),
         finish("E01 true-up drafted in April.")]
    return {"run_id": "FU_E01", "agent": "close_accountant", "pinned_at": "2026-04-12T10:00:00-07:00", "task": "Book the Bayline invoice true-up (E01) as an estimate change in April.", "steps": s}


def fu_e07():
    s = [read("contract_uc_sierra"), read("wallbuild_costs_2026_03"),
         num("uc_sierra_progress_pct_0420", "incurred/est_cost*100", {"incurred": cid("wallbuild_costs_2026_03", "cost_incurred_to_date", "2026-03-31", "UC Sierra"), "est_cost": cid("contract_uc_sierra", "estimated_total_cost", None, "UC Sierra")}, "2026-04", "wallbuild_progress", {"display_decimals": 2}, "UC Sierra percent complete after Change Order 1 (240/660)"),
         num("uc_sierra_cumulative_revenue_0420", "price*pct/100", {"price": cid("contract_uc_sierra", "contract_price", None, "UC Sierra"), "pct": "uc_sierra_progress_pct_0420"}, "2026-04", "wallbuild_revenue", desc="Cumulative revenue that should be recognized after the change order"),
         num("uc_sierra_catchup_0420", "cum-q1", {"cum": "uc_sierra_cumulative_revenue_0420", "q1": "q1_wallbuild_revenue"}, "2026-04", "wallbuild_revenue", desc="ASC 606 cumulative catch-up booked in April"),
         je("je_e07_catchup", [L("1310", 2_181_800), L("4300", -2_181_800)], "2026-04", "UC Sierra Change Order 1: cumulative catch-up +$21,818 (progress 36.36% of $1,050,000 less $360,000 recognized in Q1)", supporters=["uc_sierra_catchup_0420"], correction_id="E07"),
         finish("E07 catch-up drafted in April; Q1 untouched.")]
    return {"run_id": "FU_E07", "agent": "close_accountant", "pinned_at": "2026-04-20T12:00:00-07:00", "task": "Book the UC Sierra change order (E07) as a cumulative catch-up in April.", "steps": s}


def fu_e10():
    s = [read("ap_invoices_2026_q1"), read("company_policies"),
         je("je_e10_legal_oop", [L("6300", 1_400_000), L("2120", -1_400_000)], "2026-03", "OUT-OF-PERIOD (orig 2026-03, E10): March employment-counsel invoice $14,000 found un-accrued; booked in May per policy C-1; misstatement log", posting="2026-05",
            supporters=[cid("ap_invoices_2026_q1", "legal", "2026-03")], correction_id="E10"),
         finish("E10 booked out of period in May.")]
    return {"run_id": "FU_E10", "agent": "close_accountant", "pinned_at": "2026-05-20T15:00:00-07:00", "task": "Book the un-accrued March legal invoice (E10) as an out-of-period entry in May.", "steps": s}


def fu_e02():
    s = [read("ap_invoices_2026_q1"), read("company_policies"),
         je("je_e02_route_setting_oop", [L("6200", 2_250_000), L("2110", -2_250_000)], "2026-03", "OUT-OF-PERIOD (orig 2026-03, E02): March route-setting invoice $22,500 (timesheets existed at close); booked in May per policy C-1; misstatement log", posting="2026-05",
            supporters=[cid("ap_invoices_2026_q1", "route_setting", "2026-03")], correction_id="E02"),
         finish("E02 booked out of period in May.")]
    return {"run_id": "FU_E02", "agent": "close_accountant", "pinned_at": "2026-05-27T11:00:00-07:00", "task": "Book the late March route-setting invoice (E02) as an out-of-period entry in May.", "steps": s}


def fu_e05():
    s = [read("bank_statement_2026_05"), read("ar_invoices_2026_05"),
         je("je_e05_wire_reversal", [L("1200", 4_000_000, None), L("1010", -4_000_000, None)], "2026-05", "Reverse the misdirected $40,000 wire applied to Northgate AR on May 30 (bank correction E05); May locked, booked June 1 referencing May; reinstate AR, start collections",
            posting="2026-06", supporters=[cid("bank_statement_2026_05", "wire_credit", "2026-05-30", "Northgate Biotech")], correction_id="E05"),
         act("collections_northgate_0616", "collections_task", {"summary": "Northgate Biotech AR $48,000 now over 60 days: start collections, check the reserve", "customer": "Northgate Biotech", "amount": 48_000},
             [cid("ar_invoices_2026_05", "ar_balance", "2026-05-31", "Northgate Biotech")], "ap", "2026-06", "collections"),
         finish("E05 reversal drafted; collections task proposed.")]
    return {"run_id": "FU_E05", "agent": "close_accountant", "pinned_at": "2026-06-16T15:00:00-07:00", "task": "Reverse the misdirected wire (E05) in June referencing May and start collections on Northgate.", "steps": s}


def fu_e09():
    s = [read("fx_rates_2026_03"), read("kletterwerk_invoice_2026_03"),
         num("capex_holds_2026_03_corrected", "eur*rate", {"eur": cid("kletterwerk_invoice_2026_03", "invoice_amount_eur", "2026-03-20", "Kletterwerk GmbH", "EUR"), "rate": cid("fx_rates_2026_03", "eurusd", "2026-03-20", unit="rate")}, "2026-07", "capex", desc="Kletterwerk holds at the corrected fixing 1.0820"),
         je("je_e09_fx_capex", [L("1500", 459_000), L("7100", -459_000)], "2026-07", "Kletterwerk KW-5520: EUR/USD fixing corrected 1.0280 -> 1.0820; adjust asset 1500 +$4,590, reclassify from realized FX; depreciation true-up trivial", supporters=["capex_holds_2026_03_corrected"], correction_id="E09"),
         finish("E09 asset adjustment drafted in July.")]
    return {"run_id": "FU_E09", "agent": "close_accountant", "pinned_at": "2026-07-02T11:00:00-07:00", "task": "Adjust the holds asset for the corrected FX fixing (E09) in the open period.", "steps": s}


FOLLOWUPS = {"E01": fu_e01, "E07": fu_e07, "E10": fu_e10, "E02": fu_e02, "E05": fu_e05, "E09": fu_e09}


# ---------------------------------------------------------------- Scenario B (E20) follow-ups: the trap and the re-draft
def fu_e20_trap():
    s = [read("fy2025_monthly_summary"), read("company_policies"),
         je("je_e20_oop_q2", [L("4000", 9_500_000), L("2300", -9_500_000)], "2025-12", "Reverse $95,000 of December 2025 annual-membership revenue that belongs to 2026 (E20); booked in June as an out-of-period entry",
            posting="2026-06", supporters=[cid("fy2025_monthly_summary", "membership_revenue", "2025-12")], correction_id="E20"),
         finish("E20 drafted as a Q2 out-of-period entry.")]
    return {"run_id": "FU_E20_draft1", "agent": "close_accountant", "pinned_at": "2026-07-08T09:32:00-07:00",
            "task": "Trackback reports E20: $95,000 of December 2025 annual memberships for 2026 service were recognized in 2025. Draft the correction.", "steps": s}


def fu_e20_redraft():
    s = [read("fy2025_monthly_summary"), read("company_policies"), read("credit_agreement"),
         je("je_e20_opening_re", [L("3900", 9_500_000), L("2300", -9_500_000)], "2025-12", "LITTLE r (E20): revise FY2025 comparatives; adjust opening retained earnings (3900) and deferred revenue (2300) by $95,000 as of January 1, 2026; 2026 revenue recognized ratably from the deferred balance; disclose in the lender package",
            posting="2026-06", supporters=[cid("fy2025_monthly_summary", "membership_revenue", "2025-12"), cid("fy2025_monthly_summary", "deferred_revenue_memberships", "2025-12-31")], correction_id="E20"),
         act("lender_package_fy2025_revised", "certificate_send", {"summary": "Revised FY2025 comparatives in the lender package (little r) and re-test of the Q4 2025 certificate (2.915x, compliant)", "recipient": "Redwood Commercial Credit", "correction_id": "E20"},
             [cid("credit_agreement", "corrected_certificate_clause"), cid("fy2025_monthly_summary", "ebitda", "2025-Q4")], "cfo", "2025-Q4", "certificate"),
         finish("Re-drafted as a prior-period revision through opening retained earnings; lender package revision to the CFO.")]
    return {"run_id": "FU_E20_redraft", "agent": "close_accountant", "pinned_at": "2026-07-08T09:36:00-07:00",
            "task": "The Controller rejected the Q2 out-of-period draft: 'This is a prior-year error. Revise the FY2025 comparatives, adjust opening retained earnings and deferred revenue, disclose. Do not run it through Q2.' Re-draft accordingly.", "steps": s}
