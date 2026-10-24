"""The review agent (SPEC.md Section 7): one Error Evaluation per exception, seven questions, every claim carrying the evidence it rests on.
Decisions come from the playbook; the LLM writes root_cause and the explanation strings; numbers come from the engines."""
from __future__ import annotations

from .. import config as C
from ..engine import materiality as MAT, replay as R
from . import llm
from .playbook import ROLE_PERSON

CLOSE = C.KEY_DATES["q1_close"]


def knowable(exc: dict) -> dict:
    """When did the fact first exist in any system, by Replay? (the estimate-versus-error question)."""
    k = exc["kind"]
    if k == "duplicate_import":
        posted = next(e["posted_at"] for e in exc["evidence"] if e.get("import_id") == exc["duplicate_import"])
        caps = [v for v in R.timemap("billing_release_lines") if v["captured_at"] >= _utc(posted)]
        first = caps[0] if caps else None
        return {"at": first["captured_at"] if first else _utc(posted), "evidence": f"replay:{first['version_id']}" if first else f"gl_import_log:{exc['duplicate_import']}",
                "fact": f"the duplicate import {exc['duplicate_import']} posted {_pt(posted)}; the billing line export captured {_pt(first['captured_at']) if first else '?'} already showed batch {exc['batch']} once, before the Q1 close"}
    if k in ("unaccrued_invoice", "accrual_true_up", "duplicate_vendor_invoice"):
        at = exc["knowable"]["at"]
        return {"at": _utc(at), "evidence": "replay:ap_invoices", "fact": exc["knowable"]["fact"]}
    return {"at": _utc(exc["knowable"]["at"]), "evidence": f"replay:{exc.get('system_of_record')}", "fact": exc["knowable"]["fact"]}


def _pt(ts: str) -> str:
    from datetime import datetime, timedelta, timezone
    d = datetime.fromisoformat(_utc(ts)).astimezone(timezone(timedelta(hours=-7)))
    return f"{d:%b} {d.day} {d:%H:%M} PT"


def _utc(ts: str) -> str:
    from ..core import db
    return db.norm_ts(ts)


def classify(exc: dict, pb: dict, kn: dict) -> dict:
    k = exc["kind"]
    made = _utc(CLOSE)
    if k in ("ach_return", "unbooked_bank_fee"):
        return {"value": "fact_update", "rule": "a new bank fact in the open period", "knowable_at": kn["at"], "original_made_at": None}
    if k == "duplicate_vendor_invoice":
        return {"value": "error", "rule": "one invoice keyed twice and paid twice", "knowable_at": kn["at"], "original_made_at": kn["at"]}
    if k in ("duplicate_import", "misclassification", "fx_error", "prior_year_recognition"):
        return {"value": "error", "rule": "the books recorded something that never happened as recorded: an error whenever it is found", "knowable_at": kn["at"], "original_made_at": made}
    if k in ("accrual_true_up", "unaccrued_invoice") and not pb["classification"]["by_knowable_at"]:
        if pb["classification"]["closed_period_invoice"] == "estimate_change":
            return {"value": "estimate_change", "rule": "invoice for a closed period's service (treated as a change in estimate)", "knowable_at": kn["at"], "original_made_at": made}
        # weakness 2: any invoice for a closed period's service is an error, without asking when it arrived
        return {"value": "error", "rule": "invoice for a closed period's service (v1: treated as an error)", "knowable_at": kn["at"], "original_made_at": made}
    value = "error" if kn["at"] <= made else "estimate_change"
    rule = ("the fact existed before the close: an error" if value == "error" else
            "the information arrived after the close: a change in estimate (ASC 250), booked when it arrived")
    return {"value": value, "rule": rule, "knowable_at": kn["at"], "original_made_at": made}


def evaluate(exc: dict, ripple: dict | None, mat: dict, pb: dict, pin: str) -> dict:
    """One Error Evaluation. `mat` is the full materiality framework output (the agent uses only what its playbook allows)."""
    eid = exc["exception_id"]
    kn = knowable(exc)
    cls = classify(exc, pb, kn)
    corr = exc.get("correction") or {}
    lines = corr.get("lines") or []
    size = MAT.sizes(lines) if lines else {"rollover": 0.0, "iron_curtain": 0.0}
    if exc["kind"] == "accrual_true_up":
        size = {"rollover": 0.0, "iron_curtain": 0.0}
    # q1: what happened (root cause in words: the LLM, or a template)
    rc_facts = {"kind": exc["kind"], "title": exc["title"], "amount": f"${exc['amount']:,.2f}", "evidence": [str(e)[:220] for e in exc.get("evidence", [])][:3],
                "batch": exc.get("batch", ""), "period": exc.get("period", ""), "dup": exc.get("duplicate_import", ""), "kept": exc.get("kept_import", "")}
    rc_tpl = {"duplicate_import": "The March import of annual-plan batch {batch} ran twice: {kept} posted, the job timed out, and the retry {dup} posted the same {amount} again. Billing released the batch once.",
              "unaccrued_invoice": "{title}. It sat unprocessed in the AP inbox, so the close had no entry for it.",
              "accrual_true_up": "{title}. The final invoice came in above the close estimate.",
              "duplicate_vendor_invoice": "{title}: the same invoice was keyed twice with different numbering.",
              "ach_return": "{title}: returned debits the cash book still shows as collected.",
              "unbooked_bank_fee": "{title}: a bank charge nobody booked."}.get(exc["kind"], "{title}.")
    rc = llm.write(f"root_cause:{eid}", "Write the root cause in one sentence for the error memo.", rc_facts, rc_tpl, pin)
    q1 = {"kind": exc["kind"], "root_cause": rc["text"], "root_cause_model": rc["model"], "evidence": [f"recon:{exc['recon']}:{eid}"] + [e.get("import_id") or e.get("invoice_no") or e.get("bank_id") or "" for e in exc.get("evidence", []) if isinstance(e, dict)][:4]}
    q2 = {"trusted": (exc.get("trust") or {}).get("trusted"), "over": (exc.get("trust") or {}).get("over"), "why": (exc.get("trust") or {}).get("why"), "system_of_record": exc.get("system_of_record"),
          "evidence": [f"source:{exc.get('system_of_record')}"]}
    q3 = {**cls, "evidence": kn["evidence"], "fact": kn["fact"]}
    q4 = {"amount": exc["amount"], **size, "by_region": exc.get("by_region") or {}, "evidence": [f"correction:{eid}"]}
    # q5: does it matter (the playbook decides which tests the agent runs)
    full = mat["per_item"].get(eid)
    naive = MAT.naive_five_percent(exc)
    if cls["value"] == "estimate_change":
        q5 = {"material": False, "method": "n/a", "tests": [], "triggers": [], "why": "a change in estimate is not a misstatement"}
    elif pb["materiality"]["rule"] == "five_percent_pretax":
        q5 = {"material": naive["material"], "method": naive["rule"], "tests": [{"test": "5% of budgeted annual pretax", "value": naive["pct"], "threshold": 5.0, "fails": naive["material"]}],
              "triggers": [], "why": f"{naive['pct']:.2f}% of budgeted pretax income, under 5%: immaterial" if not naive["material"] else f"{naive['pct']:.2f}% of budgeted pretax: material"}
    else:
        q5 = {"material": bool(full and full["material"]), "method": "SAB 108 both methods + SAB 99 qualitative + aggregation", "triggers": (full or {}).get("triggers", []),
              "qualitative": (full or {}).get("qualitative", []), "tests": [t for t in mat["tests"] if t["subject"] in (eid, "aggregate")],
              "why": _mat_why(full, mat)}
    q5["evidence"] = ["materiality_memo", f"ripple:{eid}"] + (["misstatement_log"] if pb["materiality"]["aggregate"] else [])
    # q6: what it touched (the ripple)
    if ripple:
        q6 = {"invalidated": [i for i, v in ripple["items"].items() if v["verdict"] == "invalidated"], "still_valid": {i: v["reason"] for i, v in ripple["items"].items() if v["verdict"] == "still_valid"},
              "actions": {i: {"verdict": v["verdict"], "reason": v["reason"], "compensation": v.get("compensation")} for i, v in ripple["actions"].items()},
              "agent_work": {i: v["verdict"] for i, v in ripple.get("agent_nodes", {}).items()}, "counts": ripple["counts"], "evidence": [f"ripple:{eid}"]}
    else:
        q6 = {"invalidated": [], "still_valid": {}, "actions": {}, "counts": {}, "evidence": []}
    # q7: the fix (entries, posting period, documents, compensations, approvers)
    q7 = _fix(exc, cls, q5, q6, lines, pb)
    needs = [i for i, v in (ripple or {}).get("items", {}).items() if v["verdict"] == "needs_review"]
    conf = {"q1_what": 0.95, "q2_trust": 0.9, "q3_classification": 0.9 if cls["value"] != "estimate_change" else 0.85, "q4_size": 0.99, "q5_matters": 0.8 if pb["materiality"]["qualitative"] else 0.7,
            "q6_touched": 0.95 if not needs else 0.7, "q7_fix": 0.85}
    return {"exception_id": eid, "title": exc["title"], "kind": exc["kind"], "playbook_version": pb["version"], "q1_what": q1, "q2_trust": q2, "q3_classification": q3, "q4_size": q4,
            "q5_matters": q5, "q6_touched": q6, "q7_fix": q7, "confidence": {"overall": round(min(conf.values()), 2), "per_claim": conf, "needs_human": needs}}


def _mat_why(full: dict | None, mat: dict) -> str:
    if not full:
        return "not assessed"
    agg = mat["aggregate"]
    parts = []
    if full["trivial"]:
        return "below clearly trivial; not accumulated"
    parts.append(f"aggregate rollover ${agg['rollover']:,.0f} {'passes' if agg['rollover_passes'] else 'fails'}, iron curtain ${agg['iron_curtain']:,.0f} {'fails' if agg['iron_curtain_fails'] else 'passes'} against ${mat['thresholds']['overall']:,.0f}")
    for q in full["qualitative"]:
        parts.append(q["label"].lower() + (f" ({q['detail']})" if q.get("detail") else ""))
    return ("Material: " if full["material"] else "Immaterial: ") + "; ".join(parts)


def _fix(exc: dict, cls: dict, q5: dict, q6: dict, lines: list[dict], pb: dict) -> dict:
    eid, k = exc["exception_id"], exc["kind"]
    orig = (exc.get("correction") or {}).get("orig_period")
    route = pb["routing"]
    if cls["value"] == "estimate_change":
        booked = exc.get("booked_in") or []
        return {"entries": [], "treatment": "no_action", "posting_period": None, "why": f"already trued up in {', '.join(booked)} as a change in estimate" if booked else "book prospectively",
                "documents_to_reissue": [], "compensations": [], "approvers": {}, "evidence": ["accruals", "ap_invoices"]}
    if k == "accrual_true_up":   # v1's mistake: treats the true-up as an error and restates Q1
        return {"entries": [{"entity": "HQ", "account": "6300", "amount_cents": int(round(exc["amount"] * 100)), "orig_period": orig}, {"entity": "HQ", "account": "2100", "amount_cents": -int(round(exc["amount"] * 100)), "orig_period": orig}],
                "treatment": "restate_q1", "posting_period": orig, "why": "restate Q1 for the March route-setting invoice", "documents_to_reissue": ["Q1 financial statements"], "compensations": [],
                "approvers": {"journal_entry": ROLE_PERSON[route["journal_entry"]]}, "evidence": ["ap_invoices", "accruals"]}
    posting = orig if pb["posting"]["period"] == "original" else (C.OPEN_PERIOD if orig in C.LOCKED_PERIODS else orig)
    entries = [{**l, "period": posting} for l in lines]
    docs: list[str] = []
    inval = q6.get("invalidated", [])
    if any(i.startswith("CERT.") for i in inval):
        docs.append("Compliance_Certificate_Q1-26_signed.pdf")
    if any(i.startswith("DECK.") for i in inval):
        docs.append("Board_Deck_Q1-26.pptx")
    if any(i.startswith("WB.") for i in inval):
        docs.append("Covenant_Q1-26_PN.xlsx")
    comps = [{"action_id": a, **v["compensation"]} for a, v in q6.get("actions", {}).items() if v.get("compensation")]
    approvers = {"journal_entry": ROLE_PERSON[route["journal_entry"]]}
    if any(c["kind"] == "corrected_certificate_and_lender_notice" for c in comps):
        approvers["lender_document"] = ROLE_PERSON[route["lender_document"]]      # weakness 4 in v1: the controller
    if any(c["kind"] == "offset_next_bonus" for c in comps):
        approvers["comp_offset"] = ROLE_PERSON[route["comp_offset"]]
    if any(c["kind"] == "reduce_next_installment" for c in comps):
        approvers["tax_offset"] = ROLE_PERSON[route["tax_offset"]]
    if k == "duplicate_vendor_invoice":
        approvers = {"vendor_credit": ROLE_PERSON[route["vendor_credit"]], "vendor_hold": ROLE_PERSON[route["vendor_credit"]]}
    treat = MAT.treatment({**exc, "classification": cls["value"], "correction": {"orig_period": orig}}, {"material": q5.get("material")}, prior_package_issued=bool(docs), locked=set(C.LOCKED_PERIODS))
    out = {"entries": entries, "posting_period": posting, "orig_period": orig, "treatment": treat["treatment"] if pb["posting"]["period"] != "original" else "correct_in_original_period",
           "why": treat["why"], "documents_to_reissue": docs, "compensations": comps, "approvers": approvers, "memo": (exc.get("correction") or {}).get("memo"), "evidence": [f"correction:{eid}"]}
    if k == "ach_return":
        out["policy"] = exc.get("policy")
    if k == "duplicate_vendor_invoice":
        out["holds"] = [{"target": f"next payment to {exc.get('vendor')}", "until": "vendor credit received"}]
    if comps and any(c["kind"] == "offset_next_bonus" for c in comps):
        out["holds"] = [{"target": f"Jul 15 bonus run, {c['action_id'].split('-')[-1]}", "until": "offset approved"} for c in comps if c["kind"] == "offset_next_bonus"]
    return out
