"""Four reconciliations (SPEC.md Section 6.3). Each runs at the pinned time and returns matched items, cleared items (each with a
reason and detail) and exceptions (each with evidence, the system of record and why, when it became knowable, and a proposed
correction as balanced adjusting entries).

1. billing_to_gl      annual-plan release lines vs GL 4010 imports, by (period, batch); Priya's half-finished handoff re-checked
2. bank_to_book       June bank statement vs cash book; lags learned from unambiguous pairs; Hungarian assignment
3. cash_application   incoming wires vs open invoices; names, aliases, acronyms; subset-sum; learned short-pay habits
4. ap_review          duplicate vendor invoices; unaccrued invoices for closed periods; accrual true-ups

All four are pure functions over data (so the case library can run them on variants); `load_inputs(pin)` reads the real sources
through Replay at the pin.
"""
from __future__ import annotations

import itertools
import re
from collections import defaultdict
from datetime import date

import numpy as np
from scipy.optimize import linear_sum_assignment

from .. import config as C
from . import replay as R

STOP = {"WIRE", "IN", "INC", "INC.", "LLC", "CO", "CO.", "AG", "THE", "AND", "OF", "REF", "ACH", "CREDIT", "DEBIT", "TIDEWALL", "PAYMENT", "CUSTOMER", "RECEIPT", "&"}


def toks(s: str) -> set[str]:
    return {t for t in re.split(r"[^A-Za-z0-9]+", (s or "").upper()) if t and t not in STOP and not t.isdigit()}


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if (a or b) else 0.0


def cents(x) -> int:
    return int(round(float(x) * 100))


def d(s: str) -> date:
    return date.fromisoformat(s[:10])


# ======================================================================================================================== inputs
def load_inputs(pin: str, run_id: str | None = None) -> dict:
    from ..world.build import load_entries
    entries = [e for e in load_entries() if e["posted_at"] <= pin]
    inc = None
    try:
        v = R.timegate("billing_rec_incomplete", pin, run_id)
        inc = _read_incomplete_rec(R.file_path(v))
    except R.Refusal:
        pass
    return {
        "pin": pin,
        "billing": R.rows("billing_release_lines", pin, run_id),
        "import_log": R.rows("gl_import_log", pin, run_id),
        "gl": entries,
        "misstatement_log": R.rows("misstatement_log", pin, run_id),
        "bank": R.rows("bank_statement_2026_06", pin, run_id),
        "book": R.rows("cash_book_2026_06", pin, run_id),
        "open_invoices": R.rows("ar_open_invoices_2026_06", pin, run_id),
        "customers": R.rows("customers", pin, run_id),
        "pay_history": R.rows("ar_payment_history", pin, run_id),
        "ap": R.rows("ap_invoices", pin, run_id),
        "accruals": R.rows("accruals", pin, run_id),
        "vendors": R.rows("vendors", pin, run_id),
        "incomplete_rec": inc,
        "locked": set(C.LOCKED_PERIODS),
    }


def _read_incomplete_rec(path) -> dict:
    from openpyxl import load_workbook
    ws = load_workbook(path, data_only=False).active
    rows, note = {}, ""
    for r in range(2, 11):
        b = ws[f"A{r}"].value
        if b:
            rows[b] = {"status": ws[f"E{r}"].value, "billing": ws[f"B{r}"].value, "gl": ws[f"C{r}"].value}
    note = ws["B13"].value or ""
    return {"rows": rows, "note": note, "file": path.name}


def _exc(recon: str, kind: str, title: str, amount: float, **kw) -> dict:
    return {"recon": recon, "kind": kind, "title": title, "amount": round(amount, 2), **kw}


# ======================================================================================================================== 1
def billing_to_gl(inp: dict) -> dict:
    out = {"recon": "billing_to_gl", "title": "Billing to GL: annual-plan releases vs 4010 imports", "matched": [], "cleared": [], "exceptions": []}
    bill: dict[tuple, int] = defaultdict(int)
    bill_gym: dict[tuple, dict] = defaultdict(lambda: defaultdict(int))
    for r in inp["billing"]:
        k = (r["period"], r["batch"])
        c = cents(r["release_amount"])
        bill[k] += c
        bill_gym[k][r["gym_id"]] += c
    imports: dict[tuple, dict[str, dict]] = defaultdict(dict)        # (period, batch) -> import_id -> {gym: cents}
    lines_by_import: dict[str, list[dict]] = defaultdict(list)
    for e in inp["gl"]:
        if e["account"] == "4010" and e.get("import_id"):
            m = re.match(r"IMP-(\d{4})(\d{2})-(B\d+)-(\d+)", e["import_id"])
            if not m:
                continue
            k = (f"{m.group(1)}-{m.group(2)}", m.group(3))
            imports[k].setdefault(e["import_id"], defaultdict(int))[e["entity"]] += -e["amount_cents"]
        if e.get("import_id"):
            lines_by_import[e["import_id"]].append(e)
    logs = {r["import_id"]: r for r in inp["import_log"]}
    known = {r.get("billing_batch"): r for r in inp["misstatement_log"] if r.get("billing_batch")}
    for k in sorted(bill):
        period, batch = k
        b = bill[k]
        imps = imports.get(k, {})
        totals = {i: sum(g.values()) for i, g in imps.items()}
        if len(imps) == 1:
            i, t = next(iter(totals.items()))
            if t == b:
                out["matched"].append({"period": period, "batch": batch, "amount": b / 100, "import_id": i})
            elif abs(t - b) <= 100:
                out["cleared"].append({"reason": "rounding", "amount": (t - b) / 100, "detail": {"period": period, "batch": batch, "billing": b / 100, "gl": t / 100}})
            else:
                out["exceptions"].append(_exc("billing_to_gl", "import_mismatch", f"Batch {batch} {period}: GL import differs from billing", (t - b) / 100,
                                              evidence=[{"billing": b / 100, "gl": t / 100, "import_id": i}]))
        elif len(imps) > 1:
            equal = [i for i, t in totals.items() if t == b]
            extra = [i for i in sorted(imps) if i not in equal[:1]]
            same = equal and all(dict(imps[x]) == dict(imps[equal[0]]) for x in extra)
            if equal and same:
                keep = equal[0]
                dup = extra[-1]
                corr = [{"entity": l["entity"], "account": l["account"], "amount_cents": -l["amount_cents"], "orig_period": period} for l in lines_by_import[dup]]
                lg = logs.get(dup, {})
                by_region: dict[str, float] = defaultdict(float)
                for g, c in imps[dup].items():
                    by_region[C.GYM_REGION.get(g, "HQ")] += c / 100
                out["exceptions"].append(_exc(
                    "billing_to_gl", "duplicate_import", f"Annual-plan batch {batch} ({period}) imported twice into 4010", sum(imps[dup].values()) / 100,
                    period=period, batch=batch, duplicate_import=dup, kept_import=keep, by_region=dict(sorted(by_region.items())),
                    evidence=[{"what": "billing line-level export", "source": "billing_release_lines", "batch": batch, "period": period, "release": b / 100, "members": sum(1 for r in inp["billing"] if r["period"] == period and r["batch"] == batch)},
                              {"what": "GL import", "import_id": keep, "posted_at": logs.get(keep, {}).get("posted_at"), "status": logs.get(keep, {}).get("status"), "amount": totals[keep] / 100},
                              {"what": "GL import", "import_id": dup, "posted_at": lg.get("posted_at"), "status": lg.get("status"), "amount": totals[dup] / 100}],
                    system_of_record="billing_release_lines",
                    trust={"trusted": "Billing system line-level export (member by member)", "over": "GL 4010 batch imports",
                           "why": f"The billing system releases each member's plan once; the GL import is a summary feed. {dup} posted {lg.get('posted_at', '')[:16].replace('T', ' ')} with status '{lg.get('status', '')}', and is identical gym by gym to {keep}."},
                    knowable={"source": "billing_release_lines", "first_capture": None, "fact": f"{dup} posted {lg.get('posted_at')}"},
                    correction={"lines": corr, "orig_period": period, "memo": f"Reverse duplicate import {dup} (batch {batch}, {period})"}))
            else:
                out["exceptions"].append(_exc("billing_to_gl", "import_mismatch", f"Batch {batch} {period}: {len(imps)} imports that do not tie", (sum(totals.values()) - b) / 100))
        else:
            if batch in known:
                ml = known[batch]
                out["cleared"].append({"reason": "known_item", "amount": b / 100, "detail": {"period": period, "batch": batch, "misstatement_log": ml["entry_id"], "note": ml["description"]}})
            else:
                out["exceptions"].append(_exc("billing_to_gl", "missing_import", f"Batch {batch} {period}: released in billing, never imported", b / 100))
    # Priya's handoff: re-check every batch she marked Tied (March), and finish the rest
    inc = inp.get("incomplete_rec")
    if inc:
        confirmed, finished = [], []
        for bt, row in inc["rows"].items():
            k = ("2026-03", bt)
            ok = any(m["period"] == "2026-03" and m["batch"] == bt for m in out["matched"])
            if row.get("status") == "Tied":
                confirmed.append({"batch": bt, "confirmed": ok})
            else:
                res = "matched" if ok else next((e["kind"] for e in out["exceptions"] if e.get("period") == "2026-03" and e.get("batch") == bt),
                                                next((c["reason"] for c in out["cleared"] if c["detail"].get("period") == "2026-03" and c["detail"].get("batch") == bt), "not in billing"))
                finished.append({"batch": bt, "result": res})
        out["handoff"] = {"file": inc["file"], "from": "Priya Nair", "note": inc["note"], "confirmed": confirmed, "finished": finished,
                          "summary": f"Confirmed her batches {confirmed[0]['batch'][1:].lstrip('0')} to {confirmed[-1]['batch'][1:].lstrip('0')}; finished {finished[0]['batch'][1:].lstrip('0')} to {finished[-1]['batch'][1:].lstrip('0')}."
                          if confirmed and finished else ""}
    return out


# ======================================================================================================================== 2
CATS = [("card", ("MERCHANT", "CARD")), ("ach_dues", ("ACH CREDIT DUES", "ACH DUES")), ("return", ("RETURN R0", "RETURN R1")), ("payroll", ("PAYROLL",)),
        ("wire", ("WIRE IN", "CUSTOMER RECEIPT")), ("check", ("CHECK",)), ("fee", ("SERVICE CHARGE", "ANALYSIS")), ("tax", ("TAX", "EFTPS")), ("interest", ("INTEREST",)),
        ("ach_debit", ("ACH DEBIT", "AP RUN", "RENT"))]


def category(desc: str) -> str:
    u = desc.upper()
    for c, keys in CATS:
        if any(k in u for k in keys):
            return c
    return "other"


def bank_to_book(inp: dict) -> dict:
    out = {"recon": "bank_to_book", "title": "Bank to cash book, June 2026", "matched": [], "cleared": [], "exceptions": []}
    book = [{**r, "cat": category(r["description"]), "c": cents(r["amount"]), "d": d(r["date"])} for r in inp["book"]]
    bank = [{**r, "cat": category(r["description"]), "c": cents(r["amount"]), "d": d(r["date"])} for r in inp["bank"]]
    # pass 1: learn the settlement lag per category from unambiguous exact-amount pairs
    by_amt_bank: dict[tuple, list] = defaultdict(list)
    by_amt_book: dict[tuple, list] = defaultdict(list)
    for b in bank:
        by_amt_bank[(b["cat"], b["c"])].append(b)
    for b in book:
        by_amt_book[(b["cat"], b["c"])].append(b)
    lags: dict[str, list[int]] = defaultdict(list)
    for k, bk in by_amt_book.items():
        if len(bk) == 1 and len(by_amt_bank.get(k, [])) == 1:
            lags[k[0]].append((by_amt_bank[k][0]["d"] - bk[0]["d"]).days)
    window = {c: (min(v), max(v)) for c, v in lags.items()}
    out["learned_lags"] = {c: {"min": w[0], "max": w[1], "pairs": len(lags[c])} for c, w in window.items()}
    # pass 2: candidates, scores, Hungarian assignment
    n, m = len(book), len(bank)
    cost = np.full((n, m), 1e6)
    bank_by_c: dict[int, list[int]] = defaultdict(list)
    for j, bn in enumerate(bank):
        bank_by_c[bn["c"]].append(j)
    for i, bk in enumerate(book):
        for j in (j for dc in range(-5, 6) for j in bank_by_c.get(bk["c"] + dc, ())):
            bn = bank[j]
            diff = abs(bk["c"] - bn["c"])
            w = window.get(bk["cat"]) or window.get(bn["cat"]) or (0, 3)
            lag = (bn["d"] - bk["d"]).days
            if w[0] <= lag <= w[1]:
                ds = 1.0
            elif w[0] - 1 <= lag <= w[1] + 1:
                ds = 0.6
            else:
                continue
            am = 1.0 if diff == 0 else 0.7
            tx = jaccard(toks(bk["description"]), toks(bn["description"]))
            if bk["cat"] == bn["cat"]:
                tx = max(tx, 0.3)
            cost[i, j] = 3.0 - (am + ds + tx)
    ri, ci = linear_sum_assignment(cost)
    used_book, used_bank = set(), set()
    for i, j in zip(ri, ci):
        if cost[i, j] >= 1e5:
            continue
        bk, bn = book[i], bank[j]
        used_book.add(i); used_bank.add(j)
        pair = {"book_id": bk["book_id"], "bank_id": bn["bank_id"], "amount": bk["c"] / 100, "book_date": bk["date"], "bank_date": bn["date"], "category": bk["cat"], "score": round(3 - cost[i, j], 2)}
        if bk["c"] != bn["c"]:
            out["cleared"].append({"reason": "fx_rounding", "amount": (bn["c"] - bk["c"]) / 100, "detail": {**pair, "bank_amount": bn["c"] / 100, "book_desc": bk["description"], "bank_desc": bn["description"]}})
        else:
            out["matched"].append(pair)
    month_end = max(b["d"] for b in book)
    for i, bk in enumerate(book):
        if i in used_book:
            continue
        if bk["cat"] == "card" and (month_end - bk["d"]).days <= 2:
            out["cleared"].append({"reason": "deposit_in_transit", "amount": bk["c"] / 100, "detail": {"book_id": bk["book_id"], "date": bk["date"], "description": bk["description"],
                                   "why": f"card batches settle {window.get('card', (2, 2))[0]} days later (learned from {len(lags.get('card', []))} pairs); lands in July"}})
        elif bk["cat"] == "check":
            out["cleared"].append({"reason": "outstanding_check", "amount": bk["c"] / 100, "detail": {"book_id": bk["book_id"], "date": bk["date"], "description": bk["description"]}})
        else:
            out["exceptions"].append(_exc("bank_to_book", "unmatched_book_item", f"Cash book item with no bank line: {bk['description']}", bk["c"] / 100, evidence=[bk]))
    for j, bn in enumerate(bank):
        if j in used_bank:
            continue
        desc = bn["description"].upper()
        if "RETURN R01" in desc:
            amt = -bn["c"]
            out["exceptions"].append(_exc(
                "bank_to_book", "ach_return", "R01 returns from the June 1 dues batch, not in the cash book", amt / 100,
                evidence=[{"what": "bank line", "bank_id": bn["bank_id"], "date": bn["date"], "description": bn["description"], "amount": bn["c"] / 100}],
                system_of_record="bank_statement_2026_06", trust={"trusted": "Bank statement", "over": "Cash book", "why": "Returns are a bank fact; the cash book still shows the full June 1 batch as collected."},
                knowable={"fact": f"bank posted the return {bn['date']}", "at": f"{bn['date']}T00:00:00-07:00"}, return_code="R01",
                policy={"re_present": "R01 may be re-presented once (company policy); R05, R07 and R10 never"},
                correction={"lines": [{"entity": "HQ", "account": "1210", "amount_cents": amt, "orig_period": "2026-06"}, {"entity": "HQ", "account": "1010", "amount_cents": -amt, "orig_period": "2026-06"}],
                            "orig_period": "2026-06", "memo": "Reverse R01-returned dues receipts; reinstate member receivables"}))
        elif "SERVICE CHARGE" in desc or "ANALYSIS" in desc:
            amt = -bn["c"]
            out["exceptions"].append(_exc(
                "bank_to_book", "unbooked_bank_fee", "Bank analysis fee not in the cash book", amt / 100,
                evidence=[{"what": "bank line", "bank_id": bn["bank_id"], "date": bn["date"], "description": bn["description"], "amount": bn["c"] / 100}],
                system_of_record="bank_statement_2026_06", trust={"trusted": "Bank statement", "over": "Cash book", "why": "The bank charged it; nobody booked it."},
                knowable={"fact": f"bank charged the fee {bn['date']}", "at": f"{bn['date']}T00:00:00-07:00"},
                correction={"lines": [{"entity": "HQ", "account": "6500", "amount_cents": amt, "orig_period": "2026-06"}, {"entity": "HQ", "account": "1010", "amount_cents": -amt, "orig_period": "2026-06"}],
                            "orig_period": "2026-06", "memo": "Book June account analysis fee"}))
        else:
            out["exceptions"].append(_exc("bank_to_book", "unmatched_bank_item", f"Bank item with no cash book line: {bn['description']}", bn["c"] / 100, evidence=[bn]))
    return out


# ======================================================================================================================== 3
def _acronym(name: str) -> str:
    return "".join(w[0] for w in re.split(r"\s+", name) if w and w[0].isalpha() and w.upper() not in STOP)


def cash_application(inp: dict) -> dict:
    out = {"recon": "cash_application", "title": "Cash application: incoming wires vs open invoices", "matched": [], "cleared": [], "exceptions": []}
    custs = inp["customers"]
    by_cust_inv: dict[str, list] = defaultdict(list)
    for r in inp["open_invoices"]:
        by_cust_inv[r["customer_id"]].append({**r, "c": cents(r["amount"])})
    habits: dict[str, list[int]] = defaultdict(list)
    for r in inp["pay_history"]:
        s = cents(r["short"])
        if s > 0:
            habits[r["customer_id"]].append(s)
    out["learned_habits"] = {c: {"short_pays": len(v), "min": min(v) / 100, "max": max(v) / 100} for c, v in habits.items() if len(v) >= 6}
    wires = [b for b in inp["bank"] if category(b["description"]) == "wire" and cents(b["amount"]) > 0]
    for w in wires:
        c = cents(w["amount"])
        wt = toks(w["description"])
        best, score, how = None, 0.0, None
        for cu in custs:
            names = [cu["legal_name"]] + [a for a in cu["aliases"].split(";") if a]
            s = max(jaccard(wt, toks(n)) for n in names)
            if s > score:
                best, score, how = cu, s, "name"
        if score < 0.5:
            acr = [cu for cu in custs if _acronym(cu["legal_name"]) in wt]
            hit = [cu for cu in acr if any(i["c"] == c for i in by_cust_inv[cu["customer_id"]])]
            if hit:
                best, score, how = hit[0], 0.9, "acronym+amount"
            else:
                out["exceptions"].append(_exc("cash_application", "unidentified_payer", f"Wire with no customer: {w['description']}", c / 100, evidence=[w]))
                continue
        inv = by_cust_inv[best["customer_id"]]
        rec = {"bank_id": w["bank_id"], "date": w["date"], "payer": w["description"], "customer": best["legal_name"], "identified_by": how, "name_score": round(score, 2), "amount": c / 100}
        exact = [i for i in inv if abs(i["c"] - c) <= (5 if i.get("currency") == "EUR" else 0)]
        if exact:
            i = exact[0]
            rec.update(invoices=[i["invoice_no"]], rule="exact" if i["c"] == c else "exact_within_fx_rounding")
            if how == "acronym+amount":
                rec["suggest_alias"] = w["description"].replace("WIRE IN ", "").strip()
                out["cleared"].append({"reason": "alias", "amount": c / 100, "detail": {**rec, "why": f"'{rec['suggest_alias']}' is not on the customer master; identified as {best['legal_name']} by its acronym and the exact invoice amount. Suggest adding the alias."}})
            else:
                out["matched"].append(rec)
            continue
        found = None
        for k in range(2, 6):
            for combo in itertools.combinations(inv, k):
                if sum(x["c"] for x in combo) == c:
                    found = combo
                    break
            if found:
                break
        if found:
            out["cleared"].append({"reason": "subset_sum", "amount": c / 100, "detail": {**rec, "invoices": [x["invoice_no"] for x in found], "parts": [x["c"] / 100 for x in found],
                                   "why": f"one wire pays {len(found)} invoices: " + " + ".join(f"${x['c'] / 100:,.2f}" for x in found)}})
            continue
        nearest = min(inv, key=lambda x: abs(x["c"] - c)) if inv else None
        short = nearest["c"] - c if nearest else None
        h = habits.get(best["customer_id"], [])
        if nearest and short and short > 0 and len(h) >= 6 and min(h) <= short <= max(h) + 500:
            out["cleared"].append({"reason": "known_short_pay", "amount": short / 100, "detail": {**rec, "invoices": [nearest["invoice_no"]], "invoice_amount": nearest["c"] / 100, "short": short / 100,
                                   "habit": f"short-paid {len(h)} of 12 wires by ${min(h) / 100:,.0f} to ${max(h) / 100:,.0f} (intermediary fees)", "post_to": "6500"}})
        else:
            out["exceptions"].append(_exc("cash_application", "short_payment", f"{best['legal_name']} paid ${c / 100:,.2f} against ${nearest['c'] / 100:,.2f}" if nearest else "no open invoice",
                                          (short or c) / 100, evidence=[rec], route="possible dispute: ask the customer"))
    return out


# ======================================================================================================================== 4
def _digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def ap_review(inp: dict) -> dict:
    out = {"recon": "ap_review", "title": "AP review: duplicates, unaccrued invoices, accrual true-ups", "matched": [], "cleared": [], "exceptions": []}
    ap = inp["ap"]
    acct = {v["vendor_id"]: v.get("account", "6700") for v in inp["vendors"]}
    groups: dict[tuple, list] = defaultdict(list)
    for r in ap:
        groups[(r["vendor_id"], _digits(r["invoice_no"]), cents(r["amount"]), r.get("po") or "")].append(r)
    dup_ids = set()
    for k, rs in groups.items():
        paid = [r for r in rs if r["status"] == "paid"]
        if len(paid) >= 2:
            amt = k[2]
            dup_ids |= {r["invoice_id"] for r in paid[1:]}
            out["exceptions"].append(_exc(
                "ap_review", "duplicate_vendor_invoice", f"{paid[0]['vendor']}: '{paid[0]['invoice_no']}' and '{paid[1]['invoice_no']}' paid twice", amt * (len(paid) - 1) / 100,
                vendor=paid[0]["vendor"], vendor_id=k[0], evidence=[{k2: r[k2] for k2 in ("invoice_id", "invoice_no", "amount", "po", "received_at", "paid_on")} for r in paid],
                system_of_record="ap_invoices", trust={"trusted": "AP invoice register and PO", "over": "the second payment", "why": f"Same vendor, same digits ({k[1]}), same amount, same PO {k[3]}: one invoice keyed twice."},
                knowable={"fact": f"second copy received {paid[1]['received_at']}", "at": paid[1]["received_at"]},
                correction={"lines": [{"entity": "HQ", "account": "2010", "amount_cents": amt, "orig_period": max(r["booked_period"] for r in paid)},
                                      {"entity": "HQ", "account": acct.get(k[0], "6700"), "amount_cents": -amt, "orig_period": max(r["booked_period"] for r in paid)}],
                            "orig_period": max(r["booked_period"] for r in paid), "memo": f"Vendor credit due from {paid[0]['vendor']} (duplicate payment)"}))
    acc = {(a["vendor_id"], a["period"]): a for a in inp["accruals"]}
    for r in ap:
        if r["status"] == "unprocessed":
            if r["service_period"] in inp["locked"] and (r["vendor_id"], r["service_period"]) not in acc:
                amt = cents(r["amount"])
                out["exceptions"].append(_exc(
                    "ap_review", "unaccrued_invoice", f"{r['vendor']} {r['invoice_no']}: {r['service_period']} service, never processed, no accrual", amt / 100,
                    vendor=r["vendor"], vendor_id=r["vendor_id"], invoice_no=r["invoice_no"], assigned_to=r["assigned_to"], service_period=r["service_period"],
                    evidence=[{k2: r[k2] for k2 in ("invoice_id", "invoice_no", "amount", "received_at", "service_period", "status", "assigned_to")}],
                    system_of_record="ap_invoices", trust={"trusted": "AP inbox (the invoice itself)", "over": "the ledger (no entry)", "why": f"The invoice is for {r['service_period']} service and sat unprocessed in the AP inbox."},
                    knowable={"fact": f"invoice received {r['received_at']}", "at": r["received_at"]},
                    correction={"lines": [{"entity": "HQ", "account": acct.get(r["vendor_id"], "6700"), "amount_cents": amt, "orig_period": r["service_period"]},
                                          {"entity": "HQ", "account": "2010", "amount_cents": -amt, "orig_period": r["service_period"]}],
                                "orig_period": r["service_period"], "memo": f"Record {r['vendor']} {r['invoice_no']} ({r['service_period']} service)"}))
            else:
                out["cleared"].append({"reason": "open_period_unprocessed", "amount": cents(r["amount"]) / 100, "detail": {"invoice_no": r["invoice_no"], "vendor": r["vendor"], "service_period": r["service_period"]}})
        elif r["invoice_id"] not in dup_ids:
            out["matched"].append({"invoice_no": r["invoice_no"], "vendor": r["vendor"], "amount": cents(r["amount"]) / 100, "status": r["status"]})
    for (vid, period), a in acc.items():
        invs = [r for r in ap if r["vendor_id"] == vid and r["service_period"] == period]
        total = sum(cents(r["amount"]) for r in invs)
        delta = total - cents(a["amount"])
        received = max((r["received_at"] for r in invs), default=None)
        booked = sorted({r["booked_period"] for r in invs if r.get("booked_period")})
        info = {"accrual_id": a["accrual_id"], "vendor": a["vendor"], "period": period, "accrued": cents(a["amount"]) / 100, "invoiced": total / 100, "delta": delta / 100,
                "received_at": received, "accrual_posted_at": a["posted_at"], "booked_in": booked, "invoices": [r["invoice_no"] for r in invs]}
        if delta == 0:
            out["cleared"].append({"reason": "true_up_zero", "amount": 0.0, "detail": info})
        else:
            out["exceptions"].append(_exc(
                "ap_review", "accrual_true_up", f"{a['vendor']} {period}: invoiced ${total / 100:,.0f} vs ${cents(a['amount']) / 100:,.0f} accrued", delta / 100,
                **info, evidence=[info], system_of_record="ap_invoices",
                trust={"trusted": "The vendor's invoice", "over": "the close accrual", "why": "The invoice is the final amount; the accrual was the estimate at the close."},
                knowable={"fact": f"invoice received {received}", "at": received},
                already_booked=bool(booked) and booked[-1] > period, correction={"lines": [], "orig_period": period, "memo": f"Already trued up in {', '.join(booked)}" if booked else ""}))
    return out


# ======================================================================================================================== all
def run_all(inp: dict) -> list[dict]:
    res = [billing_to_gl(inp), bank_to_book(inp), cash_application(inp), ap_review(inp)]
    for r in res:
        r["counts"] = {"matched": len(r["matched"]), "cleared": len(r["cleared"]), "exceptions": len(r["exceptions"])}
        by = defaultdict(int)
        for c in r["cleared"]:
            by[c["reason"]] += 1
        r["cleared_by_reason"] = dict(by)
    return res
