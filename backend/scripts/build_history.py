"""Run the agents at their historical pinned times in timeline order, apply the pre-July-8 corrections through the engine,
record the human approvals and executions, mine the norms. Mode comes from TRACKBACK_LLM_MODE (record | replay | scripted)."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from trackback import approvals, config, corrections, db, ledger, norms  # noqa: E402
from trackback.agents import base, workorders as wo  # noqa: E402
from trackback.engine import fence  # noqa: E402
from trackback.llm import gateway  # noqa: E402

P = config.PEOPLE
CONTROLLER, CFO, AP, VP, HR = P["controller"], P["cfo"], P["ap"], P["vp_sales"], P["hr"]
LOG: list[dict] = []


def say(msg: str) -> None:
    print(msg, flush=True); LOG.append({"t": time.time(), "msg": msg})


def run(order_fn, **over):
    o = wo.with_handoffs(order_fn(**over) if over else order_fn())
    r = base.run_agent(run_id=o["run_id"], agent=o["agent"], task=o["task"], pinned_at=o["pinned_at"], required_outputs=wo.required_outputs_text(o), script=o["steps"])
    errs = [x for x in r["results"] if "error" in x["result"]]
    say(f"run {o['run_id']:<24} {o['pinned_at'][:16]} turns={r['turns']:>2} produced={len(r['produced']):>3} refusals={len(r['refusals'])} errors={len(errs)}")
    for e in errs:
        say(f"   ERROR {e['tool']} {e['args'].get('name')}: {e['result']}")
    return r


def approve_and_execute(action_id: str, approver: str, ts: str, reason: str = "approved", second: str | None = None) -> None:
    if db.q1("SELECT 1 FROM actions WHERE action_id=?", (action_id,)) is None:
        say(f"   MISSING {action_id}: the agent did not propose it (see STATUS.md); skipped")
        return
    approvals.decide(action_id, approver, "approved", reason, ts)
    if second:
        approvals.decide(action_id, second, "approved", reason, ts)
    res = corrections.execute_action(action_id, ts)
    say(f"   {action_id}: approved by {approver}{(' + ' + second) if second else ''}; executed={res['executed']}" + (f" blocked={len(res['blocked'])}" if not res["executed"] else ""))


def approve_pending_jes(run_id: str, ts: str) -> None:
    for a in db.q("SELECT action_id FROM actions WHERE run_id=? AND kind='journal_entry' AND state='proposed'", (run_id,)):
        approve_and_execute(a["action_id"], CONTROLLER, ts)


def correct(cid: str) -> dict:
    r = corrections.apply_correction(cid)
    c = r["counts"]
    say(f"corr {cid:<4} {r['tx_time'][:16]} naive={r['naive_count']:>3} invalidated={c['invalidated']:>2} cleared={c['unaffected']:>2} review={c['needs_review']} unprovable={c['unprovable']} verdict={r['materiality_verdict']}")
    comps = [f.get("compensation") for f in r["findings"] if f.get("compensation")]
    for cp in comps:
        say(f"   compensation: {cp.get('kind')} ({cp.get('action_id')})")
    return r


def approve_compensations(correction_id: str, ts: str, approver_map: dict[str, str]) -> None:
    for a in db.q("SELECT * FROM actions WHERE run_id=? AND state='proposed'", (f"correction:{correction_id}",)):
        role = a["approver_role"].split("+")[0]
        approver = approver_map.get(role, CONTROLLER)
        second = approver_map.get(a["approver_role"].split("+")[1]) if "+" in a["approver_role"] else None
        approve_and_execute(a["action_id"], approver, ts, f"compensation for {correction_id}", second=second)


def main() -> None:
    mode = gateway.mode()
    say(f"== build_history in {mode} mode")
    roles = {"controller": CONTROLLER, "cfo": CFO, "ap": AP, "vp_sales": VP, "hr": HR}
    # ---- Lyft real-world scenario first (Feb 2024 predates the Tidewall runs, so the pinned corpora stay stable)
    from trackback.realworld import lyft
    say(lyft.build(mode))
    # ---- Q4 2025 certificate (fixture)
    run(wo.r0_q4_2025_cert); approve_and_execute("ACT-cert_send_q4_2025", CFO, "2026-02-13T14:00:00-08:00", "signed")
    # ---- Q1 close and lock
    run(wo.r1_q1_close); approve_pending_jes("R1_q1_close", "2026-04-10T17:30:00-07:00")
    for p in ("2026-01", "2026-02", "2026-03"):
        ledger.lock_period(p, "2026-04-10T18:00:00-07:00", CONTROLLER)
    say("   Q1 locked (2026-01..03) by the Controller")
    # ---- E01, E07 (estimate changes, April)
    correct("E01"); run(wo.fu_e01); approve_pending_jes("FU_E01", "2026-04-12T11:00:00-07:00")
    correct("E07"); run(wo.fu_e07); approve_pending_jes("FU_E07", "2026-04-20T13:00:00-07:00")
    # ---- covenant calc, board deck, certificate
    run(wo.r3a_q1_covenant_calc)
    run(wo.r2_q1_board_deck); approve_and_execute("ACT-deck_publish_q1_2026", CONTROLLER, "2026-04-24T16:00:00-07:00", "published")
    run(wo.r3_q1_cert); approve_and_execute("ACT-cert_send_q1_2026", CFO, "2026-05-15T11:00:00-07:00", "signed and sent")
    # ---- E10, E02 (errors, OOP)
    correct("E10"); run(wo.fu_e10); approve_pending_jes("FU_E10", "2026-05-20T16:00:00-07:00"); approve_compensations("E10", "2026-05-20T16:30:00-07:00", roles)
    correct("E02"); run(wo.fu_e02); approve_pending_jes("FU_E02", "2026-05-27T12:00:00-07:00"); approve_compensations("E02", "2026-05-27T12:30:00-07:00", roles)
    # ---- bonuses
    run(wo.r4_gm_bonus); approve_and_execute("ACT-bonus_payout_q1_2026", HR, "2026-05-31T09:00:00-07:00", "payroll", second=CONTROLLER)
    # ---- June
    run(wo.r5_cash_refresh_0602)
    correct("E03")
    rx = corrections.apply_corrections(["E17", "E18"])  # X2: both arrive June 4 within the debounce window -> one wave
    say(f"corr E17+E18 (coalesced, X2) naive={rx['naive_count']} invalidated={rx['counts']['invalidated']} cleared={rx['counts']['unaffected']} pings={[p['agent'] for p in rx['pings']]}")
    run(wo.r6_h2_forecast)
    correct("E06")
    v = corrections.verify_vendor_change("email_kletterwerk_iban_2026_06_10", "2026-06-10T09:30:00-07:00")
    corrections.refuse_correction("E15", "vendor_master", "email_kletterwerk_iban_2026_06_10", v["reason"], "2026-06-10T09:35:00-07:00", {"sender": v["sender"]})
    say(f"E15  refused: {v['reason'][:90]}")
    run(wo.r7_ap_run)
    correct("E14")
    if db.q1("SELECT 1 FROM actions WHERE action_id='ACT-payment_run_0612'"):
        ok, stale = fence.guard_execute("ACT-payment_run_0612", "2026-06-12T09:30:00-07:00")
        say(f"   fence on ACT-payment_run_0612: {'passed' if ok else 'BLOCKED'} ({len(stale)} stale supporters)")
    else:
        say("   MISSING ACT-payment_run_0612: fence check skipped")
    run(wo.r7_ap_run, pin="2026-06-12T09:35:00-07:00", suffix="_v2"); approve_and_execute("ACT-payment_run_0612_v2", AP, "2026-06-12T10:00:00-07:00", "released once, duplicate held")
    run(wo.r8_q2_tax); approve_and_execute("ACT-tax_payment_q2_2026", CONTROLLER, "2026-06-15T11:00:00-07:00", "EFTPS")
    run(wo.r5b_cash_refresh_0616); approve_and_execute("ACT-dunning_email_pacific_lumen_0616", AP, "2026-06-16T10:00:00-07:00", "sent")
    correct("E05"); run(wo.fu_e05); approve_pending_jes("FU_E05", "2026-06-16T16:00:00-07:00"); approve_compensations("E05", "2026-06-16T16:30:00-07:00", roles)
    for a in db.q("SELECT action_id FROM actions WHERE run_id='FU_E05' AND state='proposed'"):
        approve_and_execute(a["action_id"], AP, "2026-06-16T16:40:00-07:00", "collections started")
    correct("E08")
    run(wo.r9_commissions); approve_and_execute("ACT-commission_payout_0620", VP, "2026-06-20T09:00:00-07:00", "June payroll", second=CONTROLLER)
    correct("E16"); approve_compensations("E16", "2026-06-22T11:00:00-07:00", roles)
    correct("E13"); approve_compensations("E13", "2026-06-24T11:00:00-07:00", roles)
    # ---- norms mined June 30: N2 (Pacific Lumen) approved; N1 (Bayline winter factor) proposed, approved July 1
    m2 = norms.mine_short_pay("pacific_lumen_history", "Pacific Lumen Labs")
    norms.propose("pacific_lumen_short_pay", m2, "2026-06-30T08:30:00-07:00")
    norms.approve("pacific_lumen_short_pay", CONTROLLER, "2026-06-30T09:00:00-07:00")
    say(f"norm N2 approved: {m2['summary']}")
    m1 = norms.mine_vendor_accrual_bias("bayline_history", "G3", lambda p: int(p[5:7]) in (11, 12, 1, 2, 3))
    norms.propose("bayline_winter_accrual", m1, "2026-06-30T08:30:00-07:00")
    say(f"norm N1 proposed: {m1['summary']}")
    # ---- X1: the Close Accountant's pre-close estimate, the Reporting Analyst's preview on top of it, the norm approval, then the self-revision
    run(wo.r12_q2_accrual_estimate_0630)
    run(wo.r5d_cash_preview_0701)
    norms.approve("bayline_winter_accrual", CONTROLLER, "2026-07-01T10:00:00-07:00")
    say("norm N1 approved by the Controller (valid from July 1, prospective)")
    from trackback.core import waves as WV
    may_g3 = db.q1("SELECT cv.value_num FROM claims c JOIN claim_versions cv ON cv.claim_id=c.claim_id WHERE c.source_id='utilities_invoices_2026_q2' AND c.entity='G3' AND c.period_start='2026-05-01' AND cv.tx_to=?", (config.TX_CURRENT,))["value_num"]
    rx1 = WV.publish_version("q2_utilities_accrual_est_G3", agent_id="close_accountant", content="June utilities accrual estimate, Sacramento: revised to the invoice basis (May invoice, factor 1.00: June is not a winter month) after the Controller approved the Bayline accrual norm",
                             value_num=may_g3, conclusions=None, reason="X1: method change after the Bayline norm approval (ASC 250 estimate change, prospective)", ts="2026-07-02T10:00:00-07:00", approved_by=CONTROLLER)
    WV.publish_version("q2_accrual_method_note", agent_id="close_accountant", content="The June Sacramento utilities accrual is estimated on the invoice basis (May invoice, factor 1.00; the approved 1.08 winter factor applies November to March).",
                       value_num=None, conclusions=None, reason="X1: method note revised with the approved norm", ts="2026-07-02T10:05:00-07:00")
    say(f"X1 self-revision: {rx1['correction_id']} naive={rx1['naive_count']} invalidated={rx1['counts']['invalidated']} cleared={rx1['counts']['unaffected']} pings={[p['agent'] for p in rx1['pings']]}")
    correct("E09"); run(wo.fu_e09); approve_pending_jes("FU_E09", "2026-07-02T12:00:00-07:00")
    correct("E24"); correct("E25")
    correct("E04")
    # ---- June close in progress, norm N1 proposed
    run(wo.r10_june_close)
    run(wo.r5c_cash_refresh_0708)
    from trackback import live
    say(f"primed the replay cache with the live flows: {live.prime_cache_from_scratch()} rows")
    n_art = db.q1("SELECT COUNT(DISTINCT artifact_id) n FROM artifacts")["n"]; n_edges = db.q1("SELECT COUNT(*) n FROM justifications")["n"]
    n_find = db.q1("SELECT COUNT(*) n FROM impact_findings")["n"]; n_cache = db.q1("SELECT COUNT(*) n FROM llm_cache")["n"]
    unbalanced = ledger.all_balanced()
    say(f"== history built: {n_art} artifacts, {n_edges} edges, {n_find} findings, {n_cache} cached LLM responses, unbalanced entries: {unbalanced}")
    gateway.export_cache()
    (config.DATA_DIR / "eval").mkdir(exist_ok=True)
    (config.DATA_DIR / "eval" / "build_history_log.json").write_text(json.dumps(LOG, indent=1))


if __name__ == "__main__":
    main()
