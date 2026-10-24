"""The files people (and two agents) made by hand, outside the books (SPEC.md Section 5.6), plus the lineage truth for every number
in them. Numbers are typed from the reference arithmetic at the time each file was made; nobody linked them to the books.

- Covenant_Q1-26_PN.xlsx (Priya, May 12): hardcodes and formulas written WITHOUT cached values; the tracer must evaluate them.
- Board_Deck_Q1-26.pptx (Apr 24): slide 2 typed by the CFO's office (the TTM line from the Apr 9 draft: H1, stale); slides 3 and 4
  written by the Reporting Analyst agent.
- Compliance_Certificate_Q1-26_signed.pdf (May 15): drafted by the Covenant and Comp agent, signed by Sam Whitfield.
- Billing_to_GL_rec_Mar26_PN_INCOMPLETE.xlsx: Priya's half-finished handoff.
"""
from __future__ import annotations

from pathlib import Path

from .. import config as C
from .refcalc import Ref, metric_value

DECK_REGION_LABEL = {r: f"{name} ({r})" for r, name in C.REGIONS.items()}


def _m(v: float) -> str:
    return f"${v / 1e6:.1f}M"


def build_items(entries: list[dict], targets: dict) -> tuple[list[dict], dict]:
    """The lineage truth: one dict per number or claim in the files. Returns (items, values used)."""
    close = Ref(entries, C.KEY_DATES["q1_close"])
    draft = Ref(entries, C.KEY_DATES["draft_tb"])
    v = lambda m, ref=close: metric_value(ref, m, targets)  # noqa: E731
    items: list[dict] = []

    def add(**kw):
        kw.setdefault("tolerance", 0.005)
        kw.setdefault("exact", True)
        kw.setdefault("stale", False)
        kw.setdefault("snapshot", "close")
        items.append(kw)

    wb, own_wb = "Covenant_Q1-26_PN.xlsx", "priya"
    add(id="WB.Covenant.B6", file=wb, locator="Covenant!B6", label="Revenue, trailing four quarters", kind="hardcode", link="metric", metric="ttm_revenue@2026Q1",
        value=round(v("ttm_revenue@2026Q1"), 2), owner=own_wb)
    add(id="WB.Covenant.B7", file=wb, locator="Covenant!B7", label="Adjusted EBITDA, trailing four quarters", kind="hardcode", link="metric", metric="ttm_adj_ebitda@2026Q1",
        value=round(v("ttm_adj_ebitda@2026Q1"), 2), owner=own_wb)
    add(id="WB.Covenant.B9", file=wb, locator="Covenant!B9", label="Term loan outstanding, March 31", kind="hardcode", link="metric", metric="term_loan@2026Q1",
        value=round(v("term_loan@2026Q1"), 2), owner=own_wb)
    add(id="WB.Covenant.B10", file=wb, locator="Covenant!B10", label="Cash, March 31", kind="hardcode", link="metric", metric="cash@2026Q1", value=round(v("cash@2026Q1"), 2), owner=own_wb)
    add(id="WB.Covenant.B11", file=wb, locator="Covenant!B11", label="Net debt", kind="formula", link="metric", metric="net_debt@2026Q1", value=round(v("net_debt@2026Q1"), 2), owner=own_wb)
    add(id="WB.Covenant.B12", file=wb, locator="Covenant!B12", label="Net leverage", kind="formula", link="metric", metric="leverage@2026Q1", value=v("leverage@2026Q1"), owner=own_wb, tolerance=0.0005)
    add(id="WB.Covenant.B13", file=wb, locator="Covenant!B13", label="Maximum leverage (Section 7.1)", kind="hardcode", link="policy", metric="policy.max_leverage", value=3.0, owner=own_wb)
    add(id="WB.Covenant.B14", file=wb, locator="Covenant!B14", label="Covenant status", kind="formula", link="metric", metric="covenant_status@2026Q1", value=v("covenant_status@2026Q1"), owner=own_wb)
    add(id="WB.Covenant.B15", file=wb, locator="Covenant!B15", label="Headroom (EBITDA cushion)", kind="formula", link="metric", metric="covenant_headroom@2026Q1",
        value=round(v("covenant_headroom@2026Q1"), 2), owner=own_wb)
    for i, r in enumerate(C.REGIONS):
        row = i + 2
        add(id=f"WB.Bonus.B{row}", file=wb, locator=f"Bonus!B{row}", label=f"{C.REGIONS[r]} ({r}) Q1 EBITDA", kind="hardcode", link="metric", metric=f"ebitda.{r}@2026Q1",
            value=round(v(f"ebitda.{r}@2026Q1"), 2), owner=own_wb)
        add(id=f"WB.Bonus.C{row}", file=wb, locator=f"Bonus!C{row}", label=f"{C.REGIONS[r]} ({r}) Target", kind="hardcode", link="policy", metric=f"policy.bonus_target.{r}",
            value=targets[r] / 100, owner=own_wb)
        add(id=f"WB.Bonus.D{row}", file=wb, locator=f"Bonus!D{row}", label=f"{C.REGIONS[r]} ({r}) Excess", kind="formula", link="derived", metric=None,
            value=round(max(0.0, v(f"ebitda.{r}@2026Q1") - targets[r] / 100), 2), owner=own_wb, refs=[f"WB.Bonus.B{row}", f"WB.Bonus.C{row}"])
        add(id=f"WB.Bonus.E{row}", file=wb, locator=f"Bonus!E{row}", label=f"{C.REGIONS[r]} ({r}) Bonus", kind="formula", link="metric", metric=f"bonus.{r}@2026Q1",
            value=round(v(f"bonus.{r}@2026Q1"), 2), owner=own_wb)
    add(id="WB.Tax.B1", file=wb, locator="Tax!B1", label="Q1 2026 pretax income", kind="hardcode", link="metric", metric="pretax@2026Q1", value=round(v("pretax@2026Q1"), 2), owner=own_wb)
    add(id="WB.Tax.B2", file=wb, locator="Tax!B2", label="Estimated tax rate", kind="hardcode", link="policy", metric="policy.tax_rate", value=C.TAX_RATE, owner=own_wb)
    add(id="WB.Tax.B3", file=wb, locator="Tax!B3", label="Q2 estimated payment", kind="formula", link="metric", metric="tax_installment@2026Q2", value=round(v("tax_installment@2026Q2"), 2), owner=own_wb)

    dk = "Board_Deck_Q1-26.pptx"
    gym = "sum:acct.4000@2026Q1+acct.4010@2026Q1+acct.4100@2026Q1"
    add(id="DECK.s2.l1", file=dk, locator="slide 2, line 1", label="Revenue (Q1)", kind="typed", link="metric", metric="revenue@2026Q1", value=v("revenue@2026Q1"), owner="sam",
        exact=False, tolerance=50_000, display=_m(v("revenue@2026Q1")))
    add(id="DECK.s2.l2", file=dk, locator="slide 2, line 2", label="Adj. EBITDA (TTM)", kind="typed", link="metric", metric="ttm_adj_ebitda@2026Q1", value=v("ttm_adj_ebitda@2026Q1", draft),
        owner="sam", exact=False, tolerance=50_000, stale=True, snapshot="draft", display=_m(v("ttm_adj_ebitda@2026Q1", draft)))
    add(id="DECK.s2.l3.a", file=dk, locator="slide 2, line 3", label="Membership revenue (Q1)", kind="typed", link="metric", metric="membership_revenue@2026Q1",
        value=v("membership_revenue@2026Q1"), owner="sam", exact=False, tolerance=50_000, display=_m(v("membership_revenue@2026Q1")))
    add(id="DECK.s2.l3.b", file=dk, locator="slide 2, line 3", label="Membership revenue growth vs Q4", kind="typed", link="metric", metric="membership_growth@2026Q1",
        value=v("membership_growth@2026Q1"), owner="sam", exact=False, tolerance=0.05, display=f"{v('membership_growth@2026Q1'):.1f}%")
    add(id="DECK.s2.l4.a", file=dk, locator="slide 2, line 4", label="Net leverage", kind="typed", link="metric", metric="leverage@2026Q1", value=v("leverage@2026Q1"), owner="sam",
        exact=False, tolerance=0.005, display=f"{v('leverage@2026Q1'):.2f}x")
    add(id="DECK.s2.l4.b", file=dk, locator="slide 2, line 4", label="Covenant max leverage", kind="typed", link="policy", metric="policy.max_leverage", value=3.0, owner="sam",
        exact=False, tolerance=0.005, display="3.00x")
    add(id="DECK.s2.l5", file=dk, locator="slide 2, line 5", label="Gym revenue (Q1, dues plus day passes)", kind="typed", link="sum", metric=gym, value=v(gym), owner="sam",
        exact=False, tolerance=50_000, display=_m(v(gym)))
    add(id="DECK.s3.l1", file=dk, locator="slide 3, line 1", label="Covenant compliance statement", kind="status", link="metric", metric="covenant_status@2026Q1",
        value=v("covenant_status@2026Q1"), owner="reporting_analyst", exact=False)
    for i, r in enumerate(C.REGIONS):
        add(id=f"DECK.s4.l{i + 1}", file=dk, locator=f"slide 4, line {i + 1}", label=f"Q1 EBITDA, {C.REGIONS[r]} ({r})", kind="typed", link="metric", metric=f"ebitda.{r}@2026Q1",
            value=v(f"ebitda.{r}@2026Q1"), owner="reporting_analyst", exact=False, tolerance=500, display=f"${v(f'ebitda.{r}@2026Q1') / 1000:,.0f}K")

    ct = "Compliance_Certificate_Q1-26_signed.pdf"
    add(id="CERT.l1", file=ct, locator="line 1", label="Adjusted EBITDA, four quarters ended March 31, 2026", kind="typed", link="metric", metric="ttm_adj_ebitda@2026Q1",
        value=round(v("ttm_adj_ebitda@2026Q1")), owner="covenant_comp", exact=False, tolerance=0.5)
    add(id="CERT.l2", file=ct, locator="line 2", label="Net Debt as of March 31, 2026", kind="typed", link="metric", metric="net_debt@2026Q1", value=round(v("net_debt@2026Q1")),
        owner="covenant_comp", exact=False, tolerance=0.5)
    add(id="CERT.l3", file=ct, locator="line 3", label="Net Leverage Ratio", kind="typed", link="metric", metric="leverage@2026Q1", value=round(v("leverage@2026Q1"), 2),
        owner="covenant_comp", exact=False, tolerance=0.005)
    add(id="CERT.l4", file=ct, locator="line 4", label="Maximum permitted Net Leverage Ratio", kind="typed", link="policy", metric="policy.max_leverage", value=3.0,
        owner="covenant_comp", exact=False, tolerance=0.005)
    add(id="CERT.l5", file=ct, locator="line 5", label="Compliance statement", kind="status", link="metric", metric="covenant_status@2026Q1", value=v("covenant_status@2026Q1"),
        owner="covenant_comp", exact=False)
    return items, {}


ACTIONS = [
    {"id": "ACT-cert-q1", "kind": "certificate_sent", "label": "Q1 compliance certificate sent to Redwood (May 15)", "metric": "covenant_status@2026Q1", "executed_at": C.KEY_DATES["certificate_sent"],
     "owner": "covenant_comp", "approver": "sam", "compensation": "corrected_certificate_and_lender_notice", "comp_approver": "sam"},
    *[{"id": f"ACT-bonus-{r}", "kind": "bonus_paid", "label": f"Q1 GM bonus paid, {C.REGIONS[r]} ({r}) (May 31)", "metric": f"bonus.{r}@2026Q1", "executed_at": C.KEY_DATES["bonuses_paid"],
       "owner": "covenant_comp", "approver": "lena", "compensation": "offset_next_bonus", "comp_approver": "lena", "region": r} for r in C.REGIONS],
    {"id": "ACT-tax-q2", "kind": "tax_paid", "label": "Q2 estimated tax paid (Jun 15)", "metric": "tax_installment@2026Q2", "executed_at": C.KEY_DATES["tax_paid"],
     "owner": "covenant_comp", "approver": "dana", "compensation": "reduce_next_installment", "comp_approver": "dana"},
]


# ------------------------------------------------------------------------------------------------------------------------ writers
def write_workbook(path: Path, items: list[dict], targets: dict) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font
    by = {it["id"]: it for it in items}
    wb = Workbook()
    ws = wb.active
    ws.title = "Covenant"
    ws["A1"] = "Tidewall Climbing Co. - Q1 2026 covenant calculation"
    ws["A1"].font = Font(bold=True)
    ws["A2"] = "Prepared by PN 5/12/2026 from the Q1 close. Synthetic company."
    ws["A4"] = "Item"
    ws["B4"] = "Amount"
    rows = {6: "B6", 7: "B7", 9: "B9", 10: "B10"}
    for r, cell in rows.items():
        it = by[f"WB.Covenant.{cell}"]
        ws[f"A{r}"] = it["label"]
        ws[cell] = it["value"]
    ws["A11"] = by["WB.Covenant.B11"]["label"]; ws["B11"] = "=B9-B10"
    ws["A12"] = by["WB.Covenant.B12"]["label"]; ws["B12"] = "=B11/B7"
    ws["A13"] = by["WB.Covenant.B13"]["label"]; ws["B13"] = 3.00
    ws["A14"] = by["WB.Covenant.B14"]["label"]; ws["B14"] = '=IF(B12<=B13,"Compliant","BREACH")'
    ws["A15"] = by["WB.Covenant.B15"]["label"]; ws["B15"] = "=B7-B11/B13"
    ws.column_dimensions["A"].width = 44
    ws.column_dimensions["B"].width = 20
    b = wb.create_sheet("Bonus")
    for col, h in zip("ABCDE", ["Region", "Q1 EBITDA", "Target", "Excess", "Bonus"]):
        b[f"{col}1"] = h
    for i, r in enumerate(C.REGIONS):
        row = i + 2
        b[f"A{row}"] = f"{C.REGIONS[r]} ({r})"
        b[f"B{row}"] = by[f"WB.Bonus.B{row}"]["value"]
        b[f"C{row}"] = targets[r] / 100
        b[f"D{row}"] = f"=MAX(0,B{row}-C{row})"
        b[f"E{row}"] = f"=D{row}*0.04"
    b["A8"] = "Total"
    b["B8"] = "=SUM(B2:B7)"
    b["E8"] = "=SUM(E2:E7)"
    b.column_dimensions["A"].width = 28
    t = wb.create_sheet("Tax")
    t["A1"] = by["WB.Tax.B1"]["label"]; t["B1"] = by["WB.Tax.B1"]["value"]
    t["A2"] = by["WB.Tax.B2"]["label"]; t["B2"] = C.TAX_RATE
    t["A3"] = by["WB.Tax.B3"]["label"]; t["B3"] = "=B1*B2"
    t.column_dimensions["A"].width = 30
    wb.properties.creator = "Priya Nair"
    wb.save(path)


def write_deck(path: Path, items: list[dict]) -> None:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    by = {it["id"]: it for it in items}
    prs = Presentation()
    blank = prs.slide_layouts[6]

    def slide(title: str, lines: list[str]):
        s = prs.slides.add_slide(blank)
        tb = s.shapes.add_textbox(Inches(0.6), Inches(0.4), Inches(9), Inches(1))
        tb.text_frame.text = title
        tb.text_frame.paragraphs[0].runs[0].font.size = Pt(32)
        body = s.shapes.add_textbox(Inches(0.6), Inches(1.5), Inches(9), Inches(5))
        tf = body.text_frame
        tf.word_wrap = True
        for i, ln in enumerate(lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = ln
            p.runs[0].font.size = Pt(20)

    slide("Tidewall Climbing Co.", ["Q1 2026 board update", "April 24, 2026", "Synthetic company"])
    slide("Q1 2026 at a glance", [
        f"Revenue (Q1): {by['DECK.s2.l1']['display']}",
        f"Adj. EBITDA (TTM): {by['DECK.s2.l2']['display']}",
        f"Membership revenue (Q1): {by['DECK.s2.l3.a']['display']}, up {by['DECK.s2.l3.b']['display']} vs Q4",
        f"Net leverage: {by['DECK.s2.l4.a']['display']} (covenant max 3.00x)",
        f"Gym revenue (Q1, dues plus day passes): {by['DECK.s2.l5']['display']}",
    ])
    slide("Covenant", [f"We remain within our 3.00x net leverage covenant at {by['DECK.s2.l4.a']['display']}.",
                       "Membership revenue grew quarter over quarter.", "All six regions were profitable in Q1."])
    slide("Q1 EBITDA by region ($K)", [f"{DECK_REGION_LABEL[r]}: {by[f'DECK.s4.l{i + 1}']['display']}" for i, r in enumerate(C.REGIONS)])
    prs.core_properties.author = "Tidewall finance (slide 2: CFO office; slides 3-4: Reporting Analyst agent)"
    prs.save(path)


def write_certificate(path: Path, items: list[dict]) -> None:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    by = {it["id"]: it for it in items}
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setTitle("Compliance Certificate Q1 2026 (synthetic)")
    y = 740
    for ln in ["COMPLIANCE CERTIFICATE", "Tidewall Climbing Co. (synthetic) to Redwood Commercial Bank, as Administrative Agent",
               "Fiscal quarter ended March 31, 2026. Delivered May 15, 2026.", ""]:
        c.drawString(72, y, ln); y -= 20
    lines = [
        f"1. Adjusted EBITDA for the four fiscal quarters ended March 31, 2026: ${by['CERT.l1']['value']:,.0f}",
        f"2. Net Debt as of March 31, 2026: ${by['CERT.l2']['value']:,.0f}",
        f"3. Net Leverage Ratio: {by['CERT.l3']['value']:.2f} to 1.00",
        "4. Maximum permitted Net Leverage Ratio under Section 7.1: 3.00 to 1.00",
        "5. The Borrower is in compliance with Section 7.1.",
    ]
    for ln in lines:
        c.drawString(72, y, ln); y -= 22
    y -= 30
    for ln in ["/s/ Sam Whitfield", "Sam Whitfield, Chief Financial Officer", "Prepared by the Covenant and Comp agent; signed by the CFO."]:
        c.drawString(72, y, ln); y -= 18
    c.save()


def write_incomplete_rec(path: Path, batch_totals: dict) -> None:
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Mar26"
    for col, h in zip("ABCDE", ["Batch", "Billing release", "GL 4010 import", "Difference", "Status"]):
        ws[f"{col}1"] = h
    for i, b in enumerate(["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B09"]):
        row = i + 2
        ws[f"A{row}"] = b
        if i < 6:
            ws[f"B{row}"] = batch_totals[b]
            ws[f"C{row}"] = batch_totals[b]
            ws[f"D{row}"] = f"=B{row}-C{row}"
            ws[f"E{row}"] = "Tied"
    ws["A13"] = "Note"
    ws["B13"] = "Out of office 6/20 to 7/13. Batches 7 to 9 still to tie. B07 is the February migration cohort. PN"
    wb.properties.creator = "Priya Nair"
    wb.save(path)
