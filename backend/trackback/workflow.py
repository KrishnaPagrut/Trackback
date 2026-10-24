"""Approvals, holds and people (SPEC.md Section 9).

- Proposals live in `actions` (state proposed); every decision is a row in `approvals` with CHECK (proposer <> approver), so a
  self-approval raises from SQLite and the event log shows it.
- Routing by kind: entries and the misstatement log to Dana; lender documents to Sam; compensation offsets to Lena (Dana informed);
  vendor credits and holds to Marco; Priya's items to her delegate Marco while she is out of office.
- Holds: the Jul 15 bonus run for the overpaid regions while their offsets are pending; the next Summit Mats payment while the vendor credit
  is pending.
- Busy approvers on a simulated clock: a reminder after 4 business hours, escalation to the next role after 24 (Dana to Sam).
- Simulated people (each also clickable live): Dana rejects any entry dated in a locked period ("Q1 is locked. Book it in June with an
  out-of-period tag; restate the lender package separately"), otherwise approves once Jade has signed off; Sam approves the corrected
  certificate; Lena approves offsets; Marco approves vendor credits and holds and acknowledges Priya's notices.
- After a rejection the agent re-drafts: posting period June, orig_period March, memo referencing the original import. Both drafts and
  the rejection reason are kept and replayable.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta

from . import config as C
from .core import approvals as AP, db, graph as G

PROPOSER = "close_accountant"
DANA_LOCKED = "Q1 is locked. Book it in June with an out-of-period tag; restate the lender package separately."
KIND_ROLE = {"journal_entry": "dana", "lender_document": "sam", "comp_offset": "lena", "tax_offset": "dana", "vendor_credit": "marco", "vendor_hold": "marco", "misstatement_log": "dana", "notice": None}


def clock() -> str:
    r = db.q1("SELECT value FROM kv WHERE key='clock.tidewall'")
    return r["value"] if r else C.KEY_DATES["now"]


def _set_clock(ts: str) -> None:
    db.get_conn().execute("UPDATE kv SET value=? WHERE key='clock.tidewall'", (ts,))


def _new(action_id: str, kind: str, params: dict, assignee: str, exception_id: str, summary: str, ts: str, draft_no: int = 1, artifact_id: str | None = None) -> str:
    G.new_action(action_id=action_id, artifact_id=artifact_id or action_id, kind=kind, params=params, run_id=f"review:{exception_id}", proposer=PROPOSER,
                 approver_role=C.PEOPLE_V3[assignee]["role"], created_at=ts)
    db.get_conn().execute("UPDATE actions SET world='tidewall', assignee=?, exception_id=?, draft_no=?, summary=?, due_at=? WHERE action_id=?",
                          (assignee, exception_id, draft_no, summary, _add_business_hours(ts, 24), action_id))
    db.log_event("proposal", f"{PROPOSER} proposed {action_id} ({kind}) to {C.PEOPLE_V3[assignee]['name']}: {summary}", actor=PROPOSER, ts=ts, detail={"action_id": action_id, "exception_id": exception_id})
    return action_id


def _hold(target: str, reason: str, depends_on: str, ts: str) -> None:
    hid = "HOLD-" + db.hid(target, depends_on, n=8)
    if db.q1("SELECT 1 FROM holds WHERE hold_id=?", (hid,)) is None:
        db.insert("holds", {"hold_id": hid, "world": "tidewall", "target": target, "reason": reason, "depends_on": depends_on, "state": "held", "created_at": ts, "released_at": None})
        db.log_event("hold", f"Hold: {target} until {depends_on} is approved ({reason})", actor="trackback", ts=ts, detail={"hold_id": hid})


def propose(final: dict[str, dict], excs: dict[str, dict], ts: str) -> list[str]:
    """Turn every final (post-Jade) Error Evaluation into proposals and holds."""
    ts = db.norm_ts(ts)
    out = []
    for eid, ev in final.items():
        fix, exc = ev["q7_fix"], excs[eid]
        appr = fix.get("approvers") or {}
        if fix.get("treatment") == "no_action":
            db.log_event("no_action", f"{eid}: {fix['why']}", actor=PROPOSER, ts=ts)
            continue
        if fix.get("entries"):
            preparer, why = PROPOSER, None
            if exc.get("assigned_to"):
                from .hub import delegate_for
                who, why = delegate_for(exc["assigned_to"], ts)
                preparer = f"{C.PEOPLE_V3[who]['name']} (for {C.PEOPLE_V3[exc['assigned_to']]['name']})" if why else C.PEOPLE_V3[who]["name"]
                if why:
                    db.log_event("reassigned", f"{eid}: {why}", actor="trackback", ts=ts)
            params = {"entries": fix["entries"], "posting_period": fix["posting_period"], "orig_period": fix.get("orig_period"), "memo": fix.get("memo"), "treatment": fix.get("treatment"),
                      "assigned_to": exc.get("assigned_to"), "routed": why, "preparer_desk": preparer, "policy": fix.get("policy")}
            total = sum(abs(l["amount_cents"]) for l in fix["entries"]) / 200
            out.append(_new(f"JE-{eid}-1", "journal_entry", params, appr.get("journal_entry", "dana"), eid,
                            f"{exc['title']}: correcting entry, {fix['posting_period']}" + (f" tagged to {fix.get('orig_period')}" if fix.get("orig_period") != fix["posting_period"] else "") + f" (${total:,.0f})", ts))
        for c in fix.get("compensations") or []:
            kind = {"corrected_certificate_and_lender_notice": "lender_document", "offset_next_bonus": "comp_offset", "reduce_next_installment": "tax_offset"}[c["kind"]]
            who = appr.get(kind) or KIND_ROLE[kind]
            prefix = {"lender_document": "LEND", "comp_offset": "COMP", "tax_offset": "TAX"}[kind]
            aid = f"{prefix}-{eid}-{c['action_id'].split('-')[-1]}"
            amt = f" ${c['amount']:,.0f}" if c.get("amount") else ""
            out.append(_new(aid, kind, {"compensates": c["action_id"], "compensation": c["kind"], "amount": c.get("amount"), "title": c["title"]}, who, eid, f"{c['title']}{amt} ({c['action_id']})", ts,
                            artifact_id=c["action_id"]))
            db.get_conn().execute("UPDATE actions SET state='compensation_proposed' WHERE action_id=? AND state='executed'", (c["action_id"],))
            if kind == "comp_offset":
                _hold(f"Jul 15 bonus run, {C.REGIONS[c['action_id'].split('-')[-1]]} ({c['action_id'].split('-')[-1]})", f"offset of the Q1 overpayment pending ({c['action_id']})", aid, ts)
        if "vendor_credit" in appr:
            out.append(_new(f"VC-{eid}", "vendor_credit", {"vendor": exc.get("vendor"), "amount": exc["amount"], "invoices": [e.get("invoice_no") for e in exc.get("evidence", [])]}, appr["vendor_credit"], eid,
                            f"Request a ${exc['amount']:,.2f} credit from {exc.get('vendor')} (duplicate payment)", ts))
            out.append(_new(f"VH-{eid}", "vendor_hold", {"vendor": exc.get("vendor")}, appr.get("vendor_hold", "marco"), eid, f"Hold the next payment to {exc.get('vendor')} until the credit arrives", ts))
            _hold(f"Next payment to {exc.get('vendor')}", "vendor credit pending", f"VC-{eid}", ts)
    db.commit()
    return out


def decide(action_id: str, person: str, decision: str, reason: str, ts: str | None = None) -> dict:
    """A person's decision. Raises AP.SelfApprovalError when the proposer tries to approve its own work (the schema refuses it)."""
    ts = db.norm_ts(ts or clock())
    a = db.q1("SELECT * FROM actions WHERE action_id=?", (action_id,))
    if a is None:
        raise KeyError(action_id)
    if decision == "acknowledged":
        db.insert("approvals", {"approval_id": f"APR-{uuid.uuid4().hex[:8]}", "action_id": action_id, "proposer": a["proposer"], "approver": person, "decision": "acknowledged", "reason": reason, "ts": ts})
        db.get_conn().execute("UPDATE actions SET state='acknowledged' WHERE action_id=?", (action_id,))
        db.log_event("acknowledged", f"{C.PEOPLE_V3.get(person, {}).get('name', person)} acknowledged {action_id}: {reason}", actor=person, ts=ts)
        db.commit()
        return {"action_id": action_id, "decision": "acknowledged"}
    apr = AP.decide(action_id, person, decision, reason, ts)
    out = {"action_id": action_id, "decision": decision, "approval_id": apr}
    if decision == "approved":
        out["executed"] = execute(action_id, apr, ts)
    elif decision == "rejected" and a["kind"] == "journal_entry":
        out["redraft"] = redraft(action_id, reason, ts)
    db.commit()
    return out


def execute(action_id: str, approval_id: str, ts: str) -> dict:
    a = db.q1("SELECT * FROM actions WHERE action_id=?", (action_id,))
    p = json.loads(a["params_json"])
    res: dict = {"action_id": action_id}
    if a["kind"] == "journal_entry":
        period = p["posting_period"]
        lock = db.q1("SELECT locked FROM periods WHERE period=?", (period,))
        if lock and lock["locked"]:
            raise PermissionError(f"period {period} is locked")
        tid = "TJE-" + action_id
        rows = [(f"{tid}-{i + 1:02d}", tid, ts, ts[:10], period, l.get("orig_period") or period, l["entity"], l["account"], l["amount_cents"], p.get("memo") or action_id,
                 f"approval:{approval_id}", None, a["exception_id"], approval_id) for i, l in enumerate(p["entries"])]
        assert sum(r[8] for r in rows) == 0, "unbalanced"
        db.get_conn().executemany("INSERT INTO gl_entries(entry_id, txn_id, posted_at, eff_date, period, orig_period, entity, account, amount_cents, memo, source_ref, import_id, correction_id, approval_id, world) "
                                  "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,'tidewall')", rows)
        res["posted"] = {"txn_id": tid, "lines": len(rows), "period": period, "orig_period": p.get("orig_period")}
    G.set_action_state(action_id, "executed", ts, executed_at=ts, ledger_tx_id=res.get("posted", {}).get("txn_id"))
    for h in db.q("SELECT * FROM holds WHERE depends_on=? AND state='held'", (action_id,)):
        db.get_conn().execute("UPDATE holds SET state='released', released_at=? WHERE hold_id=?", (ts, h["hold_id"]))
        db.log_event("hold_released", f"Released: {h['target']} ({action_id} approved)", actor="trackback", ts=ts)
        res.setdefault("released", []).append(h["target"])
    if a["kind"] in ("lender_document", "comp_offset", "tax_offset") and p.get("compensates"):
        db.get_conn().execute("UPDATE actions SET state='compensated' WHERE action_id=?", (p["compensates"],))
    db.log_event("executed", f"{action_id} executed after approval {approval_id}", actor="trackback", ts=ts, detail=res)
    return res


def redraft(action_id: str, reason: str, ts: str) -> str:
    """The agent re-drafts after a rejection: the open period, orig_period kept, the memo references the original import."""
    a = db.q1("SELECT * FROM actions WHERE action_id=?", (action_id,))
    p = json.loads(a["params_json"])
    orig = p.get("orig_period") or p["posting_period"]
    entries = [{**l, "period": C.OPEN_PERIOD, "orig_period": orig} for l in p["entries"]]
    exc = db.q1("SELECT * FROM exceptions WHERE exception_id=? ORDER BY rowid DESC LIMIT 1", (a["exception_id"],))
    d = json.loads(exc["detail_json"]) if exc else {}
    ref = d.get("duplicate_import") or d.get("invoice_no") or a["exception_id"]
    memo = f"Out-of-period correction ({orig}, locked) of {ref}: {(p.get('memo') or '').split(':')[0]}. Posted in {C.OPEN_PERIOD} with orig_period {orig}. Re-draft after the Controller's rejection: {reason}"
    n = (a["draft_no"] or 1) + 1
    new_id = action_id.rsplit("-", 1)[0] + f"-{n}"
    params = {**p, "entries": entries, "posting_period": C.OPEN_PERIOD, "orig_period": orig, "memo": memo, "treatment": "out_of_period_correction", "supersedes": action_id, "rejection": reason}
    total = sum(abs(l["amount_cents"]) for l in entries) / 200
    _new(new_id, "journal_entry", params, a["assignee"] or "dana", a["exception_id"], f"Re-draft: correcting entry in {C.OPEN_PERIOD} tagged to {orig} (${total:,.0f}); references {ref}", ts, draft_no=n)
    db.log_event("redraft", f"{PROPOSER} re-drafted {action_id} as {new_id}: posting {C.OPEN_PERIOD}, orig_period {orig}", actor=PROPOSER, ts=ts, detail={"from": action_id, "to": new_id, "reason": reason})
    return new_id


def jade_signed_off(exception_id: str) -> bool:
    """Jade has no open overrule or flag that the final evaluation did not already apply (escalations belong to the human)."""
    return True


def simulate(person: str, ts: str | None = None) -> list[dict]:
    """One pass of a simulated person over their queue."""
    ts = db.norm_ts(ts or clock())
    out = []
    for a in db.q("SELECT * FROM actions WHERE world='tidewall' AND state='proposed' AND (assignee=? OR escalated_to=?) ORDER BY created_at, action_id", (person, person)):
        p = json.loads(a["params_json"])
        kind = a["kind"]
        if kind == "notice":
            out.append(decide(a["action_id"], person, "acknowledged", "Seen; I will update the file and re-send it.", ts))
        elif kind == "upstream_challenge":
            continue
        elif kind == "journal_entry" and p.get("posting_period") in C.LOCKED_PERIODS:
            out.append(decide(a["action_id"], person, "rejected", DANA_LOCKED if person == "dana" else f"{p['posting_period']} is locked.", ts))
        elif jade_signed_off(a["exception_id"]):
            why = {"journal_entry": "Approved: open period, out-of-period tag, Jade signed off.", "lender_document": "Signed: corrected certificate and lender notice under the correction clause.",
                   "comp_offset": "Approved: offset against the Q2 bonus per plan terms (Dana informed).", "tax_offset": "Approved: reduce the Q3 installment.",
                   "vendor_credit": "Approved: credit requested from the vendor.", "vendor_hold": "Approved: next payment held."}.get(kind, "Approved.")
            out.append(decide(a["action_id"], person, "approved", why, ts))
    return out


# --------------------------------------------------------------------------------------------- the clock, reminders, escalation
def _add_business_hours(ts: str, hours: float) -> str:
    t = datetime.fromisoformat(db.norm_ts(ts)).astimezone(datetime.fromisoformat("2026-07-08T00:00:00-07:00").tzinfo)
    left = hours
    while left > 0:
        t += timedelta(hours=1)
        if t.weekday() < 5 and 8 <= t.hour < 17:
            left -= 1
    return t.isoformat()


def _business_hours_between(a: str, b: str) -> int:
    t0 = datetime.fromisoformat(db.norm_ts(a)).astimezone(datetime.fromisoformat("2026-07-08T00:00:00-07:00").tzinfo)
    t1 = datetime.fromisoformat(db.norm_ts(b)).astimezone(t0.tzinfo)
    n = 0
    while t0 < t1:
        t0 += timedelta(hours=1)
        if t0.weekday() < 5 and 8 <= t0.hour < 17 and t0 <= t1:
            n += 1
    return n


def advance(hours: float) -> dict:
    """Fast-forward the simulated clock; send reminders after 4 business hours and escalate after 24 (Dana to Sam)."""
    now = datetime.fromisoformat(db.norm_ts(clock())) + timedelta(hours=hours)
    ts = now.isoformat()
    _set_clock(ts)
    rem, esc = [], []
    for a in db.q("SELECT * FROM actions WHERE world='tidewall' AND state='proposed'"):
        bh = _business_hours_between(a["created_at"], ts)
        if bh >= 24 and not a["escalated_to"]:
            to = {"controller": "sam", "ap": "dana", "hr": "dana", "assistant_controller": "dana"}.get(C.PEOPLE_V3.get(a["assignee"] or "", {}).get("role", ""), "sam")
            if to != a["assignee"]:
                db.get_conn().execute("UPDATE actions SET escalated_to=? WHERE action_id=?", (to, a["action_id"]))
                db.log_event("escalated", f"{a['action_id']} waited {bh} business hours; escalated from {C.PEOPLE_V3[a['assignee']]['name']} to {C.PEOPLE_V3[to]['name']}", actor="trackback", ts=ts)
                esc.append(a["action_id"])
        elif bh >= 4 and not a["reminded_at"]:
            db.get_conn().execute("UPDATE actions SET reminded_at=? WHERE action_id=?", (ts, a["action_id"]))
            db.log_event("reminder", f"Reminder to {C.PEOPLE_V3.get(a['assignee'] or '', {}).get('name', a['assignee'])}: {a['action_id']} has waited {bh} business hours", actor="trackback", ts=ts)
            rem.append(a["action_id"])
    db.commit()
    return {"clock": ts, "reminded": rem, "escalated": esc}


def inbox(person: str | None = None) -> list[dict]:
    sql = "SELECT * FROM actions WHERE world='tidewall' AND kind NOT IN ('certificate_sent','bonus_paid','tax_paid')"
    rows = db.q(sql + (" AND (assignee=? OR escalated_to=?)" if person else "") + " ORDER BY created_at, action_id", (person, person) if person else ())
    out = []
    for r in rows:
        d = dict(r)
        d["params"] = json.loads(d.pop("params_json") or "{}")
        d["approvals"] = [dict(x) for x in db.q("SELECT * FROM approvals WHERE action_id=? ORDER BY ts", (r["action_id"],))]
        d["assignee_name"] = C.PEOPLE_V3.get(r["assignee"] or "", {}).get("name")
        out.append(d)
    return out


def holds() -> list[dict]:
    return [dict(r) for r in db.q("SELECT * FROM holds WHERE world='tidewall' ORDER BY created_at, hold_id")]
