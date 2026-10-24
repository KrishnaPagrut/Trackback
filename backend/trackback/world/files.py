"""The source files (SPEC.md Section 5.6) with the ordinary mess left in (Section 5.4's noise list):
12 card deposits in transit, 3 outstanding checks, one euro wire with a $0.01 conversion difference, Northgate paying three invoices
with one wire (subset-sum), Pacific Lumen's habitual $15 to $35 short-pays, SSU paying under its foundation's name, and billing batch 9
(P1) with no GL import. Planted: X1 (duplicate import), X2 (unprocessed Brightline invoice), X3 (Cragline true-up), X4 (Summit Mats
duplicate), X5 (R01 return), X6 (bank analysis fee)."""
from __future__ import annotations

import random
from collections import defaultdict

from .. import config as C
from .generator import World, batch_gym_release

CUSTOMERS = [
    {"customer_id": "C001", "legal_name": "Northgate Biotech Inc.", "aliases": "NORTHGATE BIOTECH;NORTHGATE BIO", "currency": "USD"},
    {"customer_id": "C002", "legal_name": "Pacific Lumen Labs", "aliases": "PAC LUMEN LABS;PACIFIC LUMEN", "currency": "USD"},
    {"customer_id": "C003", "legal_name": "Sierra State University", "aliases": "SIERRA STATE UNIV", "currency": "USD"},
    {"customer_id": "C004", "legal_name": "Alpenfels Klettern AG", "aliases": "ALPENFELS KLETTERN", "currency": "EUR"},
    {"customer_id": "C005", "legal_name": "Bayshore Health Partners", "aliases": "BAYSHORE HEALTH", "currency": "USD"},
    {"customer_id": "C006", "legal_name": "Granite Peak Software", "aliases": "GRANITE PEAK SW", "currency": "USD"},
    {"customer_id": "C007", "legal_name": "Mission Ridge Credit Union", "aliases": "MISSION RIDGE CU", "currency": "USD"},
    {"customer_id": "C008", "legal_name": "Cascade Outfitters Co.", "aliases": "CASCADE OUTFITTERS", "currency": "USD"},
    {"customer_id": "C009", "legal_name": "Redline Logistics LLC", "aliases": "REDLINE LOGISTICS", "currency": "USD"},
    {"customer_id": "C010", "legal_name": "Harbor and Vine Hotels", "aliases": "HARBOR VINE HOTELS", "currency": "USD"},
]
VENDORS = [
    {"vendor_id": "V01", "account": "6300", "name": "Cragline Route Setters"}, {"vendor_id": "V02", "account": "6200", "name": "Bayline Power"}, {"vendor_id": "V03", "account": "6700", "name": "Summit Mats Supply"},
    {"vendor_id": "V04", "account": "6400", "name": "Brightline Kessler LLP"}, {"vendor_id": "V05", "account": "6700", "name": "Ridgeway Facilities"}, {"vendor_id": "V06", "account": "6700", "name": "Pacific Chalk Co."},
    {"vendor_id": "V07", "account": "6700", "name": "Holdfast Climbing Holds"}, {"vendor_id": "V08", "account": "6700", "name": "Northbay Janitorial"}, {"vendor_id": "V09", "account": "6700", "name": "Crestline Insurance Brokers"},
    {"vendor_id": "V10", "account": "1500", "name": "Kletterwerk GmbH"},
]


def _d(day: int, month: int = 6) -> str:
    return f"2026-{month:02d}-{day:02d}"


def build_files(w: World, seed: int = C.SEED) -> dict:
    rng = random.Random(seed + 1)
    f: dict = {}
    _billing(w, f)
    _import_log(w, f)
    _bank_and_book(w, rng, f)
    _ar(rng, f)
    _ap(rng, f)
    _docs(w, f)
    return f


# ------------------------------------------------------------------------------------------------------------------ billing + GL
def _billing(w: World, f: dict) -> None:
    rows = []
    for p in ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]:
        for m in w.members:
            rows.append({"period": p, "member_id": m["member_id"], "gym_id": m["gym_id"], "region": m["region"], "batch": m["batch"],
                         "plan_price": f"{m['plan_price_cents'] / 100:.2f}", "release_amount": f"{m['release_cents'] / 100:.2f}"})
    f["billing_release_lines_2026-04-09.csv"] = [r for r in rows if r["period"] <= "2026-03"]
    f["billing_release_lines_2026-07-08.csv"] = rows
    f["_batch_totals_mar"] = {b: sum(batch_gym_release(w, b).values()) / 100 for b in ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B09"]}


def _import_log(w: World, f: dict) -> None:
    rows = [{**r, "total": f"{r['total']:.2f}"} for r in w.import_log if r["period"] >= "2026-01"]
    f["gl_import_log_2026-04-09.csv"] = [r for r in rows if r["posted_at"] <= C.KEY_DATES["billing_capture_1"]]
    f["gl_import_log_2026-07-08.csv"] = rows
    f["gl_detail_export.csv"] = [{**e, "amount": f"{e['amount_cents'] / 100:.2f}"} for e in w.entries]


# ------------------------------------------------------------------------------------------------------------------ bank + book
def _bank_and_book(w: World, rng: random.Random, f: dict) -> None:
    book, bank = [], []
    bseq, kseq = [0], [0]

    def B(date, desc, amt, ref):
        bseq[0] += 1
        book.append({"book_id": f"CB{bseq[0]:04d}", "date": date, "description": desc, "amount": f"{amt:.2f}", "ref": ref})

    def K(date, desc, amt, trace=None):
        kseq[0] += 1
        bank.append({"bank_id": f"BK{kseq[0]:04d}", "date": date, "description": desc, "amount": f"{amt:.2f}", "trace": trace or f"{rng.randint(10**9, 10**10 - 1)}"})

    # 1. card batches per region per day; the bank settles two days later (Jun 29 and 30 land in July: 12 deposits in transit)
    for d in range(1, 31):
        for r in C.REGIONS:
            amt = round(rng.uniform(52_000, 68_000), 2)
            B(_d(d), f"Card batch {C.REGIONS[r]} {_d(d)}", amt, f"CARD-{r}-{d:02d}")
            if d + 2 <= 30:
                K(_d(d + 2), f"MERCHANT SETTLEMENT TIDEWALL {r} {6:02d}{d:02d}", amt)
    # 2. ACH dues batches (Jun 1 and Jun 15) per region; R01 returns from the Jun 1 batch: $2,310.00 on Jun 3, not in the book (X5)
    for day in (1, 15):
        for r in C.REGIONS:
            amt = round(rng.uniform(38_000, 46_000), 2)
            B(_d(day), f"ACH dues batch {C.REGIONS[r]} {_d(day)}", amt, f"ACH-{r}-{day:02d}")
            K(_d(day + 1), f"ACH CREDIT DUES BATCH {r} {6:02d}{day:02d}", amt)
    K(_d(3), "RETURN R01 INSUFFICIENT FUNDS DUES BATCH 0601 (14 ITEMS)", -2310.00)
    # 3. payroll
    for day in (15, 30):
        amt = round(rng.uniform(3_650_000, 3_720_000), 2)
        B(_d(day), "Payroll funding (gyms and HQ)", -amt, f"PAY-{day}")
        K(_d(day), "ADP PAYROLL FUNDING", -amt)
    # 4. customer wires in (the cash application recon works these against open invoices)
    wires = [("Northgate Biotech Inc.", 186_400.00, 186_400.00, 9, "WIRE IN NORTHGATE BIOTECH INC REF 2026-0609"),
             ("Pacific Lumen Labs", 48_475.00, 48_475.00, 10, "WIRE IN PAC LUMEN LABS INV PL-6612"),
             ("Sierra State University", 74_250.00, 74_250.00, 11, "WIRE IN SSU FOUNDATION ACCTS PAYABLE"),
             ("Alpenfels Klettern AG", 52_130.47, 52_130.48, 16, "WIRE IN ALPENFELS KLETTERN AG EUR 47,850.00"),
             ("Bayshore Health Partners", 61_200.00, 61_200.00, 5, "WIRE IN BAYSHORE HEALTH PARTNERS"),
             ("Granite Peak Software", 38_400.00, 38_400.00, 8, "WIRE IN GRANITE PEAK SOFTWARE"),
             ("Mission Ridge Credit Union", 27_900.00, 27_900.00, 12, "WIRE IN MISSION RIDGE CU"),
             ("Cascade Outfitters Co.", 44_650.00, 44_650.00, 17, "WIRE IN CASCADE OUTFITTERS"),
             ("Redline Logistics LLC", 33_120.00, 33_120.00, 19, "WIRE IN REDLINE LOGISTICS LLC"),
             ("Harbor and Vine Hotels", 52_800.00, 52_800.00, 23, "WIRE IN HARBOR VINE HOTELS")]
    for name, book_amt, bank_amt, day, bdesc in wires:
        B(_d(day), f"Customer receipt {name}", book_amt, f"AR-{name.split()[0].upper()}")
        K(_d(day), bdesc, bank_amt)
    # 5. the Jun 12 AP run (ACH); Summit Mats paid twice (X4) and Cragline's $468,000
    ap_run = [("Cragline Route Setters", 468_000.00), ("Summit Mats Supply INV-2231", 18_750.00), ("Summit Mats Supply 2231", 18_750.00)]
    for v in VENDORS[4:9]:
        for _ in range(3):
            ap_run.append((v["name"], round(rng.uniform(4_000, 42_000), 2)))
    for name, amt in ap_run:
        B(_d(12), f"AP run 06/12 {name}", -amt, f"APRUN-{name[:12].upper().replace(' ', '')}")
        K(_d(13), f"ACH DEBIT {name.split(' INV')[0].split(' 2231')[0].upper()}", -amt)
    # 6. checks: 15 issued, 3 outstanding at month end
    for i in range(15):
        day = 3 + i
        amt = round(rng.uniform(900, 14_000), 2)
        no = 50410 + i
        v = VENDORS[i % len(VENDORS)]["name"]
        B(_d(min(day, 26)), f"Check {no} {v}", -amt, f"CHK-{no}")
        clear = min(day, 26) + rng.randint(3, 9)
        if i < 12 and clear <= 30:
            K(_d(clear), f"CHECK {no}", -amt)
        elif i < 12:
            K(_d(30), f"CHECK {no}", -amt)
    # 7. rent (48 ACH debits on Jun 1), interest, tax
    for g, info in sorted(w.gyms.items()):
        amt = round(68_000 * info["factor"], 2)
        B(_d(1), f"Rent {info['name']}", -amt, f"RENT-{g}")
        K(_d(1), f"ACH DEBIT LANDLORD {g} {info['city'].upper()}", -amt)
    B(_d(30), "Term loan interest (Redwood)", -612_500.00, "INT-0630"); K(_d(30), "LOAN INTEREST REDWOOD COMMERCIAL", -612_500.00)
    tax = next(e for e in w.entries if e["source_ref"] == "ACT-tax-q2" and e["account"] == "8100")["amount_cents"] / 100
    B(_d(15), "Q2 federal estimated tax (EFTPS)", -tax, "TAX-Q2"); K(_d(15), "IRS USATAXPYMT EFTPS", -tax)
    # 8. bank analysis fee, not in the book (X6)
    K(_d(30), "ACCOUNT ANALYSIS SERVICE CHARGE JUNE", -312.40)
    f["cash_book_2026-06.csv"] = book
    f["bank_statement_2026-06.csv"] = sorted(bank, key=lambda r: (r["date"], r["bank_id"]))
    f["_wires"] = wires


# ------------------------------------------------------------------------------------------------------------------ AR
def _ar(rng: random.Random, f: dict) -> None:
    open_inv = []
    n = [0]

    def inv(cust, amt, issue, ccy="USD", no=None):
        n[0] += 1
        open_inv.append({"invoice_no": no or f"INV-W{26000 + n[0]}", "customer_id": cust["customer_id"], "customer": cust["legal_name"], "issue_date": issue,
                         "due_date": issue.replace("-05-", "-06-") if "-05-" in issue else issue, "amount": f"{amt:.2f}", "currency": ccy})

    by = {c["legal_name"]: c for c in CUSTOMERS}
    inv(by["Northgate Biotech Inc."], 62_000.00, "2026-05-08"); inv(by["Northgate Biotech Inc."], 74_400.00, "2026-05-15"); inv(by["Northgate Biotech Inc."], 50_000.00, "2026-05-22")
    inv(by["Northgate Biotech Inc."], 41_250.00, "2026-06-05")           # a fourth open invoice so the subset-sum has a choice to make
    inv(by["Pacific Lumen Labs"], 48_500.00, "2026-05-10", no="PL-6612")
    inv(by["Sierra State University"], 74_250.00, "2026-05-12"); inv(by["Sierra State University"], 18_600.00, "2026-06-02")
    inv(by["Alpenfels Klettern AG"], 52_130.47, "2026-05-14", ccy="EUR")
    for name, amt, d in [("Bayshore Health Partners", 61_200.00, "2026-05-06"), ("Granite Peak Software", 38_400.00, "2026-05-09"), ("Mission Ridge Credit Union", 27_900.00, "2026-05-13"),
                         ("Cascade Outfitters Co.", 44_650.00, "2026-05-18"), ("Redline Logistics LLC", 33_120.00, "2026-05-20"), ("Harbor and Vine Hotels", 52_800.00, "2026-05-27"),
                         ("Harbor and Vine Hotels", 26_400.00, "2026-06-10"), ("Granite Peak Software", 19_200.00, "2026-06-08")]:
        inv(by[name], amt, d)
    f["ar_open_invoices_2026-06.csv"] = open_inv
    f["customers.csv"] = CUSTOMERS
    hist = []
    for c in CUSTOMERS:
        for k in range(12):
            month = [(2025, m) for m in range(6, 13)] + [(2026, m) for m in range(1, 6)]
            y, mth = month[k]
            amt = round(rng.uniform(25_000, 80_000), 2)
            paid = amt
            if c["customer_id"] == "C002" and k != 5:               # Pacific Lumen short-pays 11 of 12 wires by $15 to $35
                paid = round(amt - rng.randint(15, 35), 2)
            hist.append({"customer_id": c["customer_id"], "customer": c["legal_name"], "month": f"{y}-{mth:02d}", "invoice_amount": f"{amt:.2f}", "paid_amount": f"{paid:.2f}",
                         "short": f"{amt - paid:.2f}"})
    f["ar_payment_history.csv"] = hist


# ------------------------------------------------------------------------------------------------------------------ AP
def _ap(rng: random.Random, f: dict) -> None:
    rows = []
    n = [0]
    vb = {v["name"]: v for v in VENDORS}

    def add(vendor, no, amt, received, service, status, assigned="marco", po="", paid_on="", booked=""):
        n[0] += 1
        rows.append({"invoice_id": f"AP{n[0]:04d}", "vendor_id": vb[vendor]["vendor_id"], "vendor": vendor, "invoice_no": no, "amount": f"{amt:.2f}", "received_at": received,
                     "service_period": service, "status": status, "assigned_to": assigned, "po": po, "paid_on": paid_on, "booked_period": booked})

    for p, rec in [("2026-03", "2026-04-01T09:12:00-07:00"), ("2026-04", "2026-05-01T09:05:00-07:00"), ("2026-05", "2026-06-01T09:20:00-07:00")]:
        add("Brightline Kessler LLP", f"BRK-RET-{p[2:4]}{p[5:]}", 130_000.00, rec, p, "paid", po="", paid_on=f"{p}-28", booked=p)
    # X2: received Apr 2 08:41, March employment-counsel work, never processed, assigned to Priya
    add("Brightline Kessler LLP", "BRK-26-0331", 140_000.00, "2026-04-02T08:41:00-07:00", "2026-03", "unprocessed", assigned="priya")
    # Bayline March utilities: three invoices that sum to the $190,000 accrual (true-up $0)
    for no, amt, d in [("BP-30871", 71_400.00, "2026-04-08T10:02:00-07:00"), ("BP-30872", 63_850.00, "2026-04-09T14:30:00-07:00"), ("BP-30873", 54_750.00, "2026-04-14T08:55:00-07:00")]:
        add("Bayline Power", no, amt, d, "2026-03", "paid", paid_on="2026-05-12", booked="2026-04")
    # X3: Cragline CRX-5521 received May 20 vs the $410,000 March accrual, already handled in May
    add("Cragline Route Setters", "CRX-5521", 468_000.00, "2026-05-20T11:00:00-07:00", "2026-03", "paid", paid_on="2026-06-12", booked="2026-05", po="PO-4402")
    # X4: Summit Mats duplicates, both paid Jun 12
    add("Summit Mats Supply", "INV-2231", 18_750.00, "2026-06-02T09:15:00-07:00", "2026-06", "paid", po="4471", paid_on="2026-06-12", booked="2026-06")
    add("Summit Mats Supply", "2231", 18_750.00, "2026-06-03T16:40:00-07:00", "2026-06", "paid", po="4471", paid_on="2026-06-12", booked="2026-06")
    # ordinary invoices
    for v in VENDORS[4:9] + [VENDORS[2], VENDORS[9]]:
        for k in range(6):
            mth = 3 + k % 4
            amt = round(rng.uniform(1_200, 42_000), 2)
            add(v["name"], f"{v['vendor_id']}-{2600 + k}", amt, f"2026-{mth:02d}-{rng.randint(2, 26):02d}T10:00:00-07:00", f"2026-{mth:02d}", "paid",
                po=f"PO-{4300 + k}", paid_on=f"2026-{mth:02d}-28", booked=f"2026-{mth:02d}")
    # open-period invoices still unprocessed (June service): not exceptions
    add("Ridgeway Facilities", "RF-7781", 12_480.00, "2026-07-02T09:00:00-07:00", "2026-06", "unprocessed")
    add("Pacific Chalk Co.", "PCC-1193", 3_960.00, "2026-07-06T13:10:00-07:00", "2026-06", "unprocessed")
    f["ap_invoices.csv"] = rows
    f["ap_invoices_2026-04-09.csv"] = [r for r in rows if r["received_at"] <= C.KEY_DATES["draft_tb"]]
    f["accruals.csv"] = [
        {"accrual_id": "ACR-0326-CRAG", "vendor_id": "V01", "vendor": "Cragline Route Setters", "period": "2026-03", "account": "6300", "amount": "410000.00", "posted_at": "2026-04-10T16:30:00-07:00", "reversed_in": "2026-05"},
        {"accrual_id": "ACR-0326-BAYL", "vendor_id": "V02", "vendor": "Bayline Power", "period": "2026-03", "account": "6200", "amount": "190000.00", "posted_at": "2026-04-10T16:30:00-07:00", "reversed_in": "2026-04"},
    ]
    f["vendors.csv"] = VENDORS


# ------------------------------------------------------------------------------------------------------------------ documents
def _docs(w: World, f: dict) -> None:
    f["misstatement_log.csv"] = [{"entry_id": "ML-2026-01", "logged_by": "Dana Ortiz", "logged_at": "2026-04-10T17:30:00-07:00", "item": "P1",
                                  "description": "380 December 2025 promo annual plans ($1,200 each, $456,000) recognized at sale instead of over 2026 ($38,000 a month). Billing batch B09.",
                                  "period": "2025-12", "billing_batch": "B09", "rollover": "-228000.00", "iron_curtain": "228000.00", "ttm_ebitda_effect": "342000.00",
                                  "status": "uncorrected (passed as immaterial at the Q1 close)"}]
    f["materiality_memo.json"] = {"title": "FY2026 materiality memo", "author": "Dana Ortiz, Controller", "date": "2026-01-15", "synthetic": True,
                                  "overall": C.MATERIALITY_V3["overall"], "performance": C.MATERIALITY_V3["performance"], "clearly_trivial": C.MATERIALITY_V3["clearly_trivial"],
                                  "flux": {"pct": 0.10, "abs": 250_000}, "basis": C.MATERIALITY_V3["basis"],
                                  "text": "Overall materiality $800,000 (5% of $16.0M budgeted pretax). Performance materiality $250,000. Misstatements below $25,000 are clearly trivial and are not accumulated. Evaluate under both SAB 108 methods and consider qualitative factors (SAB 99), including covenant compliance and management compensation."}
    f["credit_agreement.json"] = {"title": "Term Loan Credit Agreement (synthetic)", "lender": "Redwood Commercial Bank", "borrower": "Tidewall Climbing Co.", "date": "2025-04-01",
                                  "facility": 105_000_000, "section_7_1": "Net Leverage Ratio as of the last day of any fiscal quarter shall not exceed 3.00 to 1.00.",
                                  "definitions": {"Net Debt": "Funded debt less unrestricted cash.", "Adjusted EBITDA": "Net income before interest, taxes, depreciation and amortization, and foreign exchange gains and losses, for the four fiscal quarters then ended."},
                                  "correction_clause": "If any financial statements delivered are materially misstated, the Borrower shall promptly deliver corrected financial statements and a corrected Compliance Certificate.",
                                  "signatory": "Chief Financial Officer"}
    f["comp_plan.json"] = {"title": "FY2026 GM bonus plan", "date": "2026-01-05", "rate": C.BONUS_RATE, "basis": "4% of regional Q1 EBITDA above target, paid May 31",
                           "targets": {r: w.targets[r] / 100 for r in C.REGIONS},
                           "overpayments": "Overpayments are offset against the next bonus. No ad-hoc payroll deductions.", "approver": "HR (Lena Park), Controller informed"}
    f["people.json"] = {k: {kk: vv for kk, vv in v.items()} for k, v in C.PEOPLE_V3.items()}
    f["gyms.csv"] = [{"gym_id": g, "name": i["name"], "city": i["city"], "region": i["region"], "region_name": C.REGIONS[i["region"]], "size_factor": i["factor"]} for g, i in sorted(w.gyms.items())]
