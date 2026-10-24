"""Materiality (SPEC.md Section 6.6): SAB 108's two methods, the memo's thresholds, SAB 99 qualitative factors computed through the graph,
aggregation with the uncorrected misstatement log, and the treatment decision tree.

- rollover = the correction's P&L amounts whose orig_period falls in the current fiscal year (positive: income overstated)
- iron curtain = minus the correction's asset and liability amounts (positive: net assets overstated)
- prior-year items on the log (P1) use their logged values
- items below clearly trivial are excluded from aggregation, and the output says so
- SAB 108: material if material under either method
"""
from __future__ import annotations

from .. import config as C

FY_START = "2026-01"


def sizes(lines: list[dict]) -> dict:
    roll = sum(l["amount_cents"] for l in lines if C.ACCOUNTS[l["account"]][1] in ("revenue", "expense") and (l.get("orig_period") or "") >= FY_START) / 100
    iron = -sum(l["amount_cents"] for l in lines if C.ACCOUNTS[l["account"]][1] in ("asset", "liability")) / 100
    return {"rollover": round(roll, 2), "iron_curtain": round(iron, 2)}


def qualitative(ripple: dict | None) -> list[dict]:
    """SAB 99 factors, read from the ripple (never guessed)."""
    if not ripple:
        return []
    out = []
    items, acts, mets = ripple.get("items", {}), ripple.get("actions", {}), ripple.get("metrics", {})
    flips = [i for i, v in {**items, **acts}.items() if v.get("reason") == "conclusion_flipped" and "covenant_status" in (v.get("metric") or "")]
    if flips:
        lev = next((m for k, m in mets.items() if k.startswith("leverage@2026Q1")), None)
        out.append({"factor": "covenant_flip", "label": "Flips loan covenant compliance", "evidence": flips[:4],
                    "detail": f"net leverage {lev['old']:.2f}x to {lev['new']:.4f}x against {C.COVENANT['max_leverage']:.2f}x" if lev else ""})
    comp = [i for i, v in acts.items() if v.get("kind") == "bonus_paid" and v["verdict"] == "invalidated"]
    if comp:
        out.append({"factor": "compensation", "label": "Changes management compensation", "evidence": comp,
                    "detail": "; ".join(f"{i}: overpaid ${acts[i]['compensation']['amount']:,.0f}" for i in comp)})
    trend = [k for k, m in mets.items() if k.startswith("membership_growth") and m.get("conclusion_old") != m.get("conclusion_new")]
    if trend:
        out.append({"factor": "trend_reversal", "label": "Reverses a trend", "evidence": trend})
    pre = [k for k, m in mets.items() if k.startswith("pretax@") and isinstance(m.get("old"), (int, float)) and (m["old"] > 0) != (m["new"] > 0)]
    if pre:
        out.append({"factor": "loss_to_income", "label": "Turns income into a loss (or back)", "evidence": pre})
    docs = sorted({v["file"] for v in items.values() if v["verdict"] == "invalidated" and (v["file"].startswith("Compliance_Certificate") or v["file"].startswith("Board_Deck"))})
    if docs:
        out.append({"factor": "delivered_document", "label": "Affects a document already delivered to the lender or the board", "evidence": docs})
    return out


def evaluate(exceptions: list[dict], misstatement_log: list[dict], ripples: dict[str, dict], memo: dict | None = None) -> dict:
    """exceptions: [{exception_id, kind, classification, amount, correction:{lines}}]. Estimate changes are not misstatements."""
    m = memo or C.MATERIALITY_V3
    overall, perf, trivial = m["overall"], m["performance"], m["clearly_trivial"]
    rows, excluded = [], []
    for e in exceptions:
        if e.get("classification") == "estimate_change":
            excluded.append({"id": e["exception_id"], "why": "change in estimate: not a misstatement (ASC 250), booked prospectively"})
            continue
        s = sizes((e.get("correction") or {}).get("lines") or [])
        big = max(abs(s["rollover"]), abs(s["iron_curtain"]), abs(e.get("amount", 0)))
        row = {"id": e["exception_id"], "kind": e["kind"], "title": e.get("title"), **s, "amount": e.get("amount"), "source": "this review"}
        if big < trivial:
            row["trivial"] = True
            excluded.append({"id": e["exception_id"], "why": f"below clearly trivial (${trivial:,.0f}): not accumulated"})
        rows.append(row)
    for r in misstatement_log:
        rows.append({"id": r.get("item") or r["entry_id"], "kind": "logged_uncorrected", "title": r["description"], "rollover": float(r["rollover"]), "iron_curtain": float(r["iron_curtain"]),
                     "amount": abs(float(r["iron_curtain"])), "source": f"misstatement log {r['entry_id']} ({r['logged_by']})", "ttm_ebitda_effect": float(r.get("ttm_ebitda_effect") or 0)})
    agg_rows = [r for r in rows if not r.get("trivial")]
    agg_roll = round(sum(r["rollover"] for r in agg_rows), 2)
    agg_iron = round(sum(r["iron_curtain"] for r in agg_rows), 2)
    tests = []
    for r in rows:
        if r.get("trivial"):
            continue
        tests.append({"subject": r["id"], "method": "rollover", "value": r["rollover"], "threshold": overall, "fails": abs(r["rollover"]) > overall})
        tests.append({"subject": r["id"], "method": "iron_curtain", "value": r["iron_curtain"], "threshold": overall, "fails": abs(r["iron_curtain"]) > overall})
        tests.append({"subject": r["id"], "method": "performance", "value": max(abs(r["rollover"]), abs(r["iron_curtain"])), "threshold": perf, "fails": max(abs(r["rollover"]), abs(r["iron_curtain"])) > perf})
    tests.append({"subject": "aggregate", "method": "rollover", "value": agg_roll, "threshold": overall, "fails": abs(agg_roll) > overall})
    tests.append({"subject": "aggregate", "method": "iron_curtain", "value": agg_iron, "threshold": overall, "fails": abs(agg_iron) > overall})
    qual = {eid: qualitative(rp) for eid, rp in ripples.items()}
    if any(r["kind"] == "logged_uncorrected" for r in rows):
        for eid in qual:
            pass
    known_uncorrected = [r["id"] for r in rows if r["kind"] == "logged_uncorrected"]
    per_item = {}
    for r in rows:
        if r["kind"] == "logged_uncorrected":
            continue
        q = qual.get(r["id"], [])
        if known_uncorrected and q:
            q = q + [{"factor": "known_uncorrected", "label": "Known items left uncorrected", "evidence": known_uncorrected}]
        quant = [t for t in tests if t["subject"] == r["id"] and t["fails"] and t["method"] != "performance"]
        agg_fail = [t for t in tests if t["subject"] == "aggregate" and t["fails"]]
        in_agg = not r.get("trivial")
        triggers = [t["method"] for t in quant] + [f"aggregate_{t['method']}" for t in agg_fail if in_agg and (q or quant)] + [x["factor"] for x in q]
        material = bool(quant or (in_agg and agg_fail and (q or abs(r["iron_curtain"]) > perf or abs(r["rollover"]) > perf)) or q)
        per_item[r["id"]] = {"material": material, "triggers": triggers, "qualitative": q,
                             "above_performance": max(abs(r["rollover"]), abs(r["iron_curtain"])) > perf, "trivial": bool(r.get("trivial")),
                             "pct_budgeted_pretax": round(max(abs(r["rollover"]), abs(r["iron_curtain"])) / m.get("budgeted_pretax", 16e6) * 100, 2)}
    return {"thresholds": {"overall": overall, "performance": perf, "clearly_trivial": trivial, "basis": m.get("basis")}, "rows": rows, "excluded": excluded,
            "aggregate": {"rollover": agg_roll, "iron_curtain": agg_iron, "rollover_passes": abs(agg_roll) <= overall, "iron_curtain_fails": abs(agg_iron) > overall,
                          "items": [r["id"] for r in agg_rows], "material_either_method": abs(agg_roll) > overall or abs(agg_iron) > overall},
            "tests": tests, "per_item": per_item}


def naive_five_percent(e: dict, memo: dict | None = None) -> dict:
    """The baseline (and playbook v1's rule): immaterial if under 5% of annual pretax, rollover only, no qualitative tests, no aggregation."""
    m = memo or C.MATERIALITY_V3
    s = sizes((e.get("correction") or {}).get("lines") or [])
    pct = abs(s["rollover"] or e.get("amount", 0)) / m["budgeted_pretax"] * 100
    return {"material": pct >= 5.0, "rule": "5% of annual pretax, rollover only", "pct": round(pct, 2), "rollover": s["rollover"]}


def treatment(e: dict, mat: dict, prior_package_issued: bool, locked: set[str]) -> dict:
    """Decision tree. Material to a previously issued Q1 package: correct in the open period (post in June tagged to March), reissue the Q1
    lender package and certificate (CFO), notify the board. Immaterial to prior periods but material if booked now: revise comparatives.
    Otherwise an out-of-period adjustment. Estimate changes are never restatements."""
    if e.get("classification") == "estimate_change":
        return {"treatment": "no_action" if e.get("already_booked") else "book_prospectively", "why": "change in estimate (ASC 250): no restatement, no Q1 entry"}
    orig = (e.get("correction") or {}).get("orig_period")
    if mat.get("material") and orig in locked and prior_package_issued:
        return {"treatment": "correct_in_open_period", "posting_period": C.OPEN_PERIOD, "orig_period": orig, "reissue": ["Q1 lender package", "Compliance certificate"],
                "notify": ["board"], "why": f"{orig} is locked and the Q1 package was delivered: post in {C.OPEN_PERIOD} tagged to {orig}, reissue the package and certificate, notify the board"}
    if orig in locked:
        return {"treatment": "out_of_period_adjustment", "posting_period": C.OPEN_PERIOD, "orig_period": orig, "why": f"{orig} is locked: post in {C.OPEN_PERIOD} with an out-of-period tag"}
    return {"treatment": "current_period_entry", "posting_period": orig or C.OPEN_PERIOD, "orig_period": orig, "why": "open period: book it now"}
