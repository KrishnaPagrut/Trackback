"""The case library (SPEC.md Section 12): the six Tidewall exceptions plus generated variants on the same world, each with expected labels
written from the generator's own rules and the reference arithmetic (world/refcalc.py), never from the engines being graded.

Families: duplicate imports of different sizes and regions (some flip the covenant, some don't, some only hit R6); unaccrued invoices
received before the close (errors) and after (changes in estimate); accrual true-ups (estimate changes; the trap is restating);
misclassifications with no income effect; FX corrections on capex (outside Adjusted EBITDA); prior-year items (rollover and iron curtain
with opposite signs); trivial items below $25k; pure noise (expected: zero new exceptions). Each case is train or held-out, stratified by
family, for the learning experiment.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable

from .. import config as C
from ..world.refcalc import Ref, reach

CLOSE = C.KEY_DATES["q1_close"]
P1_LOG = {"rollover": -228_000.0, "iron_curtain": 228_000.0}


@dataclass
class Case:
    id: str
    family: str
    split: str
    stage: str                     # detect (recon runs on a variant of the inputs) | evaluate (the exception is given)
    title: str
    expected: dict
    mutate: Callable[[dict], None] | None = None
    exception: dict | None = None
    expected_kind: str | None = None
    planted: list[str] = field(default_factory=list)     # which v1 weaknesses this case exercises


# ---------------------------------------------------------------------------------------------------- expected labels (the rules)
def expect(lines: list[dict], entries: list[dict], targets: dict, *, classification: str, kind: str, amount: float) -> dict:
    """The generator's rules: SAB 108 sizes, aggregation with the logged P1, qualitative tests via the reference arithmetic, treatment, approvers."""
    if classification == "estimate_change":
        return {"classification": classification, "material": False, "treatment": "no_action_or_prospective", "approvers": {}, "lender": False}
    roll = sum(l["amount_cents"] for l in lines if C.ACCOUNTS[l["account"]][1] in ("revenue", "expense") and l["orig_period"] >= "2026-01") / 100
    iron = -sum(l["amount_cents"] for l in lines if C.ACCOUNTS[l["account"]][1] in ("asset", "liability")) / 100
    trivial = max(abs(roll), abs(iron), abs(amount)) < C.MATERIALITY_V3["clearly_trivial"]
    before, after = Ref(entries, CLOSE), Ref(entries, CLOSE, lines)
    flips = before.status("2026Q1") != after.status("2026Q1")
    bonus = []
    for r in C.REGIONS:
        b = round(max(0.0, before.ebitda("2026Q1", r) - targets[r] / 100) * C.BONUS_RATE, 2)
        a = round(max(0.0, after.ebitda("2026Q1", r) - targets[r] / 100) * C.BONUS_RATE, 2)
        if abs(a - b) > 0.005:
            bonus.append(r)
    delivered = flips or any(reach(m, lines)[0] and abs(_mv(before, m) - _mv(after, m)) > 0.5
                             for m in ("ttm_adj_ebitda@2026Q1", "revenue@2026Q1", "membership_revenue@2026Q1", "net_debt@2026Q1"))
    agg_roll, agg_iron = (0.0, 0.0) if trivial else (roll + P1_LOG["rollover"], iron + P1_LOG["iron_curtain"])
    overall = C.MATERIALITY_V3["overall"]
    qual = flips or bool(bonus) or delivered
    quant = abs(roll) > overall or abs(iron) > overall
    agg_fail = abs(agg_roll) > overall or abs(agg_iron) > overall
    material = (not trivial) and (quant or qual or agg_fail and max(abs(roll), abs(iron)) > C.MATERIALITY_V3["performance"])
    orig = max(l["orig_period"] for l in lines)
    locked = orig in C.LOCKED_PERIODS
    approvers = {"journal_entry": "dana"}
    if flips:
        approvers["lender_document"] = "sam"
    if bonus:
        approvers["comp_offset"] = "lena"
    if kind == "duplicate_vendor_invoice":
        approvers = {"vendor_credit": "marco", "vendor_hold": "marco"}
    return {"classification": classification, "rollover": round(roll, 2), "iron_curtain": round(iron, 2), "trivial": trivial, "material": material, "covenant_flip": flips,
            "bonus_regions": bonus, "posting_period": C.OPEN_PERIOD if locked else orig, "orig_period": orig, "approvers": approvers, "lender": flips,
            "leverage_after": round(after.leverage("2026Q1"), 4)}


def _mv(ref: Ref, m: str) -> float:
    name, q = m.split("@")
    return {"ttm_adj_ebitda": ref.ttm_ebitda, "revenue": ref.revenue, "membership_revenue": ref.membership, "net_debt": ref.net_debt}[name](q)


# ---------------------------------------------------------------------------------------------------- mutations (detect-stage variants)
def dup_import(batch: str, period: str, members: list[dict], posted_at: str) -> tuple[Callable, list[dict], float, dict]:
    rel: dict[str, int] = {}
    for m in members:
        if m["batch"] == batch:
            rel[m["gym_id"]] = rel.get(m["gym_id"], 0) + m["release_cents"]
    imp = f"IMP-{period.replace('-', '')}-{batch}-2"
    gl_lines = []
    for g in sorted(rel):
        gl_lines += [{"entry_id": f"{imp}-{g}-a", "txn_id": imp, "posted_at": posted_at, "eff_date": f"{period}-28", "period": period, "orig_period": period, "entity": g, "account": "2300",
                      "amount_cents": rel[g], "memo": f"Annual plan release import {batch} ({period})", "source_ref": "", "import_id": imp, "correction_id": None},
                     {"entry_id": f"{imp}-{g}-b", "txn_id": imp, "posted_at": posted_at, "eff_date": f"{period}-28", "period": period, "orig_period": period, "entity": g, "account": "4010",
                      "amount_cents": -rel[g], "memo": f"Annual plan release import {batch} ({period})", "source_ref": "", "import_id": imp, "correction_id": None}]
    total = sum(rel.values()) / 100

    def mut(inp: dict) -> None:
        inp["gl"].extend(gl_lines)
        inp["import_log"].append({"import_id": imp, "batch": batch, "period": period, "posted_at": posted_at, "status": "ok (retry after timeout)", "lines": str(len(gl_lines)), "total": f"{total:.2f}"})
    lines = [{"entity": l["entity"], "account": l["account"], "amount_cents": -l["amount_cents"], "orig_period": period} for l in gl_lines]
    by_region: dict[str, float] = {}
    for g, c in rel.items():
        by_region[C.GYM_REGION[g]] = by_region.get(C.GYM_REGION[g], 0) + c / 100
    return mut, lines, total, by_region


def ap_invoice(vendor_id: str, vendor: str, no: str, amount: float, received: str, service: str, status: str = "unprocessed", accrual: float | None = None, booked: str = "") -> Callable:
    def mut(inp: dict) -> None:
        inp["ap"].append({"invoice_id": f"AP9{len(inp['ap']):03d}", "vendor_id": vendor_id, "vendor": vendor, "invoice_no": no, "amount": f"{amount:.2f}", "received_at": received,
                          "service_period": service, "status": status, "assigned_to": "marco", "po": "", "paid_on": "", "booked_period": booked})
        if accrual is not None:
            inp["accruals"].append({"accrual_id": f"ACR-{no}", "vendor_id": vendor_id, "vendor": vendor, "period": service, "account": "6700", "amount": f"{accrual:.2f}",
                                    "posted_at": CLOSE, "reversed_in": booked})
    return mut


def build(entries: list[dict], members: list[dict], targets: dict) -> list[Case]:
    cases: list[Case] = []

    def split(i: int) -> str:
        return "train" if i % 2 == 0 else "heldout"

    # --- the six Tidewall exceptions themselves (detected on the real inputs)
    base = {"X1": ("duplicate_import", "error"), "X2": ("unaccrued_invoice", "error"), "X3": ("accrual_true_up", "estimate_change"), "X4": ("duplicate_vendor_invoice", "error"),
            "X5": ("ach_return", "fact_update"), "X6": ("unbooked_bank_fee", "fact_update")}
    for i, (cid, (kind, cls)) in enumerate(base.items()):
        cases.append(Case(id=f"TW-{cid}", family="tidewall", split="train" if cid in ("X1", "X3", "X4") else "heldout", stage="real", title=f"Tidewall {cid}", expected={"classification": cls},
                          expected_kind=kind, planted=["materiality", "routing", "posting"] if cid == "X1" else (["classification"] if cid == "X3" else [])))
    # --- duplicate imports: sizes and regions
    dups = [("B07", "2026-01", "2026-02-03T05:30:00-07:00"), ("B03", "2026-02", "2026-03-03T05:30:00-07:00"), ("B05", "2026-03", "2026-04-04T23:10:00-07:00"),
            ("B01", "2026-01", "2026-02-04T02:00:00-07:00"), ("B07", "2026-02", "2026-03-05T01:00:00-07:00"), ("B08", "2026-03", "2026-04-05T03:00:00-07:00"),
            ("B02", "2026-05", "2026-06-04T05:30:00-07:00"), ("B06", "2026-06", "2026-07-04T05:30:00-07:00")]
    for i, (b, p, ts) in enumerate(dups):
        mut, lines, total, by_region = dup_import(b, p, members, ts)
        exp = expect(lines, entries, targets, classification="error", kind="duplicate_import", amount=total)
        cases.append(Case(id=f"DUP-{b}-{p}", family="duplicate_import", split=split(i), stage="detect", title=f"Batch {b} {p} imported twice (${total:,.0f})", expected=exp, mutate=mut,
                          expected_kind="duplicate_import", planted=["materiality"] + (["routing"] if exp["lender"] else []) + (["posting"] if exp["orig_period"] in C.LOCKED_PERIODS else [])))
    # --- an R6-only duplicate (built directly: a desert-southwest batch slice)
    r6 = [m for m in members if m["region"] == "R6" and m["batch"] == "B04"]
    mut, lines, total, by_region = dup_import("B04", "2026-02", r6, "2026-03-03T23:00:00-07:00")
    exp = expect(lines, entries, targets, classification="error", kind="duplicate_import", amount=total)
    cases.append(Case(id="DUP-R6-B04-2026-02", family="duplicate_import", split="heldout", stage="evaluate", title=f"R6-only duplicate release (${total:,.0f})", expected=exp,
                      exception={"kind": "duplicate_import", "title": f"Batch B04 R6 slice 2026-02 imported twice", "amount": total, "batch": "B04", "period": "2026-02", "by_region": by_region,
                                 "duplicate_import": "IMP-202602-B04-2", "evidence": [{"what": "GL import", "import_id": "IMP-202602-B04-2", "posted_at": "2026-03-03T23:00:00-07:00"}],
                                 "correction": {"lines": lines, "orig_period": "2026-02"}, "recon": "billing_to_gl", "system_of_record": "billing_release_lines",
                                 "trust": {"trusted": "billing", "over": "GL", "why": "summary feed duplicated"}, "knowable": {"at": "2026-03-03T23:00:00-07:00", "fact": "posted twice"}},
                      expected_kind="duplicate_import", planted=["materiality"]))
    # --- unaccrued invoices: before the close (errors) and after (changes in estimate)
    unacc = [("V05", "Ridgeway Facilities", "RF-0331", 96_000.0, "2026-04-06T10:00:00-07:00", "2026-03", "error"),
             ("V09", "Crestline Insurance Brokers", "CIB-2203", 310_000.0, "2026-03-25T09:00:00-07:00", "2026-02", "error"),
             ("V07", "Holdfast Climbing Holds", "HCH-7714", 64_000.0, "2026-05-28T14:00:00-07:00", "2026-03", "estimate_change"),
             ("V06", "Pacific Chalk Co.", "PCC-0418", 44_500.0, "2026-06-18T11:00:00-07:00", "2026-03", "estimate_change"),
             ("V08", "Northbay Janitorial", "NBJ-3121", 182_000.0, "2026-04-09T16:00:00-07:00", "2026-03", "error"),
             ("V04", "Brightline Kessler LLP", "BRK-26-0228", 210_000.0, "2026-04-29T09:00:00-07:00", "2026-02", "estimate_change")]
    acct = {"V05": "6700", "V09": "6700", "V07": "6700", "V06": "6700", "V08": "6700", "V04": "6400"}
    for i, (vid, vn, no, amt, rec, svc, cls) in enumerate(unacc):
        lines = [{"entity": "HQ", "account": acct[vid], "amount_cents": int(amt * 100), "orig_period": svc}, {"entity": "HQ", "account": "2010", "amount_cents": -int(amt * 100), "orig_period": svc}]
        exp = expect(lines, entries, targets, classification=cls, kind="unaccrued_invoice", amount=amt)
        cases.append(Case(id=f"UNACC-{no}", family="unaccrued_" + ("before" if cls == "error" else "after"), split=split(i), stage="detect",
                          title=f"{vn} {no} (${amt:,.0f}, {svc} service) received {rec[:10]}", expected=exp, mutate=ap_invoice(vid, vn, no, amt, rec, svc), expected_kind="unaccrued_invoice",
                          planted=["classification"] if cls == "estimate_change" else (["materiality", "posting"])))
    # --- accrual true-ups (estimate changes; trap: restating)
    tus = [("V05", "Ridgeway Facilities", "RF-TU1", 150_000.0, 171_000.0, "2026-05-12T09:00:00-07:00", "2026-03", "2026-05"),
           ("V09", "Crestline Insurance Brokers", "CIB-TU2", 90_000.0, 76_500.0, "2026-04-22T09:00:00-07:00", "2026-03", "2026-04"),
           ("V08", "Northbay Janitorial", "NBJ-TU3", 60_000.0, 92_000.0, "2026-06-02T09:00:00-07:00", "2026-03", "2026-06")]
    for i, (vid, vn, no, accrued, inv, rec, svc, booked) in enumerate(tus):
        def mut(inp, vid=vid, vn=vn, no=no, accrued=accrued, inv=inv, rec=rec, svc=svc, booked=booked):
            inp["ap"].append({"invoice_id": f"AP8{len(inp['ap']):03d}", "vendor_id": vid, "vendor": vn, "invoice_no": no, "amount": f"{inv:.2f}", "received_at": rec, "service_period": svc,
                              "status": "paid", "assigned_to": "marco", "po": "", "paid_on": booked + "-28", "booked_period": booked})
            inp["accruals"].append({"accrual_id": f"ACR-{no}", "vendor_id": vid, "vendor": vn, "period": svc, "account": "6700", "amount": f"{accrued:.2f}", "posted_at": CLOSE, "reversed_in": booked})
        cases.append(Case(id=f"TRUEUP-{no}", family="accrual_true_up", split=split(i), stage="detect", title=f"{vn} true-up ${inv - accrued:+,.0f}", expected={"classification": "estimate_change", "material": False,
                          "treatment": "no_action_or_prospective", "approvers": {}}, mutate=mut, expected_kind="accrual_true_up", planted=["classification"]))
    # --- misclassification with no income effect; FX on capex; prior-year recognition (evaluate-stage)
    evals = [("MISCLASS-1", "misclassification", "Utilities booked to other opex (HQ, March)", [("HQ", "6200", 85_000), ("HQ", "6700", -85_000)], "2026-03"),
             ("MISCLASS-2", "misclassification", "Route setting booked to payroll (gyms, February)", [("G03", "6300", 42_000), ("G03", "6000", -42_000)], "2026-02"),
             ("FX-CAPEX-1", "fx_error", "FX on the Kletterwerk wall-holds purchase (capex)", [("HQ", "7100", 120_000), ("HQ", "1500", -120_000)], "2026-03"),
             ("FX-CAPEX-2", "fx_error", "FX revaluation of a EUR equipment payable", [("HQ", "7100", 38_000), ("HQ", "2010", -38_000)], "2026-02"),
             ("PRIOR-1", "prior_year_recognition", "December 2025 corporate wellness prepaid recognized at billing", [("HQ", "4200", 300_000, "2025-12"), ("HQ", "2300", -150_000, "2026-03"), ("HQ", "4200", -150_000, "2026-03")], None),
             ("PRIOR-2", "prior_year_recognition", "November 2025 wall build revenue recognized early", [("WALL", "4300", 180_000, "2025-11"), ("HQ", "2300", -90_000, "2026-02"), ("WALL", "4300", -90_000, "2026-02")], None)]
    for i, (cid, kind, title, ls, per) in enumerate(evals):
        lines = [{"entity": l[0], "account": l[1], "amount_cents": l[2] * 100, "orig_period": (l[3] if len(l) > 3 else per)} for l in ls]
        amt = max(abs(l["amount_cents"]) for l in lines) / 100
        exp = expect(lines, entries, targets, classification="error", kind=kind, amount=amt)
        cases.append(Case(id=cid, family=kind, split=split(i), stage="evaluate", title=title, expected=exp, expected_kind=kind,
                          exception={"kind": kind, "title": title, "amount": amt, "correction": {"lines": lines, "orig_period": max(l["orig_period"] for l in lines)}, "recon": "given", "evidence": [],
                                     "system_of_record": "gl", "trust": {"trusted": "source documents", "over": "GL", "why": "the posting does not match the document"},
                                     "knowable": {"at": "2026-07-08T08:00:00-07:00", "fact": "found in review"}}, planted=["posting"] if max(l["orig_period"] for l in lines) in C.LOCKED_PERIODS else []))
    # --- trivial items (below $25k: excluded from aggregation)
    trivs = [("TRIV-DUPINV", "V06", "Pacific Chalk Co.", "PCC-5510", 4_380.0), ("TRIV-UNACC", "V08", "Northbay Janitorial", "NBJ-0390", 9_250.0)]
    for i, (cid, vid, vn, no, amt) in enumerate(trivs):
        if cid == "TRIV-DUPINV":
            def mut(inp, vid=vid, vn=vn, no=no, amt=amt):
                for k, n in enumerate((no, no.replace("PCC-", ""))):
                    inp["ap"].append({"invoice_id": f"AP7{k}{len(inp['ap']):03d}", "vendor_id": vid, "vendor": vn, "invoice_no": n, "amount": f"{amt:.2f}", "received_at": "2026-06-08T09:00:00-07:00",
                                      "service_period": "2026-06", "status": "paid", "assigned_to": "marco", "po": "4512", "paid_on": "2026-06-12", "booked_period": "2026-06"})
            kind = "duplicate_vendor_invoice"
            lines = [{"entity": "HQ", "account": "2010", "amount_cents": int(amt * 100), "orig_period": "2026-06"}, {"entity": "HQ", "account": "6700", "amount_cents": -int(amt * 100), "orig_period": "2026-06"}]
        else:
            mut = ap_invoice(vid, vn, no, amt, "2026-04-03T09:00:00-07:00", "2026-03")
            kind = "unaccrued_invoice"
            lines = [{"entity": "HQ", "account": "6700", "amount_cents": int(amt * 100), "orig_period": "2026-03"}, {"entity": "HQ", "account": "2010", "amount_cents": -int(amt * 100), "orig_period": "2026-03"}]
        exp = expect(lines, entries, targets, classification="error", kind=kind, amount=amt)
        cases.append(Case(id=cid, family="trivial", split=split(i), stage="detect", title=f"{vn} {no} (${amt:,.0f})", expected=exp, mutate=mut, expected_kind=kind))
    # --- pure noise: timing, rounding, aliases, bundled payments (expected: zero new exceptions)
    def noise_timing(inp):
        inp["book"].append({"book_id": "CB9001", "date": "2026-06-30", "description": "Card batch Rockies 2026-06-30 (late batch)", "amount": "61234.56", "ref": "CARD-R4-30b"})

    def noise_rounding(inp):
        inp["open_invoices"].append({"invoice_no": "INV-W29002", "customer_id": "C004", "customer": "Alpenfels Klettern AG", "issue_date": "2026-06-01", "due_date": "2026-06-30", "amount": "18340.21", "currency": "EUR"})
        inp["book"].append({"book_id": "CB9002", "date": "2026-06-22", "description": "Customer receipt Alpenfels Klettern AG", "amount": "18340.21", "ref": "AR-ALP2"})
        inp["bank"].append({"bank_id": "BK9002", "date": "2026-06-22", "description": "WIRE IN ALPENFELS KLETTERN AG EUR 16,800.00", "amount": "18340.23", "trace": "9990002"})

    def noise_alias(inp):
        inp["open_invoices"].append({"invoice_no": "INV-W29001", "customer_id": "C007", "customer": "Mission Ridge Credit Union", "issue_date": "2026-06-01", "due_date": "2026-06-30", "amount": "14200.00", "currency": "USD"})
        inp["bank"].append({"bank_id": "BK9003", "date": "2026-06-24", "description": "WIRE IN MRCU OPERATIONS", "amount": "14200.00", "trace": "9990003"})
        inp["book"].append({"book_id": "CB9003", "date": "2026-06-24", "description": "Customer receipt Mission Ridge Credit Union", "amount": "14200.00", "ref": "AR-MRCU"})

    def noise_bundle(inp):
        for k, a in enumerate(("21000.00", "17500.00")):
            inp["open_invoices"].append({"invoice_no": f"INV-W2910{k}", "customer_id": "C005", "customer": "Bayshore Health Partners", "issue_date": "2026-06-03", "due_date": "2026-07-03", "amount": a, "currency": "USD"})
        inp["bank"].append({"bank_id": "BK9004", "date": "2026-06-26", "description": "WIRE IN BAYSHORE HEALTH PARTNERS", "amount": "38500.00", "trace": "9990004"})
        inp["book"].append({"book_id": "CB9004", "date": "2026-06-26", "description": "Customer receipt Bayshore Health Partners", "amount": "38500.00", "ref": "AR-BAY2"})

    for i, (cid, fn, title) in enumerate([("NOISE-TIMING", noise_timing, "A late card batch in transit"), ("NOISE-ROUNDING", noise_rounding, "A second euro wire, 2 cents off"),
                                          ("NOISE-ALIAS", noise_alias, "Mission Ridge pays as MRCU OPERATIONS"), ("NOISE-BUNDLE", noise_bundle, "Bayshore pays two invoices with one wire")]):
        cases.append(Case(id=cid, family="noise", split=split(i), stage="detect", title=title, expected={"exceptions": 0}, mutate=fn, expected_kind=None))
    return cases


def apply(inp: dict, case: Case) -> dict:
    out = {k: (copy.copy(v) if isinstance(v, list) else v) for k, v in inp.items()}
    for k in ("gl", "import_log", "ap", "accruals", "bank", "book", "open_invoices"):
        out[k] = list(inp[k])
    if case.mutate:
        case.mutate(out)
    return out
