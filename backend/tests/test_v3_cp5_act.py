"""CP5: Dana rejects the Q1-dated entry, the agent re-drafts in June, self-approval raises, the bonus run is held, the memo renders.
Plus iteration 2: the X1 ripple pings all three agent lanes (still_valid with a reason, reworked, needs_human with compensations), the cash
forecast is skipped, people get notices (Priya's routed to Marco), S1 pings only the Reporting Analyst, S2 coalesces, S3 starts no wave."""
import json

import pytest

from trackback import config as C, hub, memo, workflow
from trackback.core import approvals as AP, db


def x1(canon):
    return next(e["exception_id"] for r in canon["detect"] for e in r["exceptions"] if e["kind"] == "duplicate_import")


def waves(canon):
    return json.loads(db.q1("SELECT value FROM kv WHERE key=?", (f"waves.{canon['run_id']}",))["value"])


def test_x1_wave_crosses_three_lanes(canon):
    w = waves(canon)[x1(canon)]
    by = {p["agent"]: p for p in w["pings"]}
    assert set(by) == {"close_accountant", "covenant_comp", "reporting_analyst"}
    verdicts = {i["artifact_id"]: i["verdict"] for p in w["pings"] for i in p["items"]}
    assert verdicts["CA.q1_close_memo"] == "reworked"
    assert verdicts["DECK.s3.l1"] == "reworked"
    assert verdicts["RA.commentary.membership_growth"] == "still_valid" and verdicts["RA.commentary.regions_profitable"] == "still_valid"
    assert all(verdicts[a] == "needs_human" for a in ("ACT-cert-q1", "ACT-bonus-R1", "ACT-bonus-R2", "ACT-bonus-R4", "ACT-tax-q2"))
    assert "RA.cash_forecast.opening" in {s["node_id"] for s in w["skipped"]}
    notices = {n["owner"]: n for n in w["notices"]}
    assert notices["priya"]["to"] == "marco" and "out of office" in notices["priya"]["routed_because"]
    print("\nWAVE X1:", {a: p["state"] for a, p in by.items()}, "skipped:", [s["node_id"] for s in w["skipped"]])


def test_coalesced_and_challenge(canon):
    w = waves(canon)
    s2 = next(v for k, v in w.items() if "+" in k)
    assert [p["agent"] for p in s2["pings"]] == ["reporting_analyst"]
    assert sorted(s2["solo_pings"].values()) == [0, 1]
    assert w["S3"]["challenge"]["wave_started"] is False and w["S3"]["challenge"]["to"] == "dana"


def test_dana_rejects_then_agent_redrafts_in_june(canon):
    eid = x1(canon)
    je = db.q1("SELECT * FROM actions WHERE action_id=?", (f"JE-{eid}-1",))
    assert json.loads(je["params_json"])["posting_period"] == "2026-03"
    out = workflow.simulate("dana")
    rej = next(o for o in out if o["action_id"] == f"JE-{eid}-1")
    assert rej["decision"] == "rejected" and rej["redraft"] == f"JE-{eid}-2"
    assert "Q1 is locked" in db.q1("SELECT reason FROM approvals WHERE action_id=? AND decision='rejected'", (f"JE-{eid}-1",))["reason"]
    p2 = json.loads(db.q1("SELECT params_json FROM actions WHERE action_id=?", (f"JE-{eid}-2",))["params_json"])
    assert p2["posting_period"] == "2026-06" and p2["orig_period"] == "2026-03" and "IMP-202603-B07-2" in p2["memo"]
    print("\nDANA:", workflow.DANA_LOCKED, "| re-draft:", p2["memo"][:120])


def test_self_approval_raises(canon):
    eid = x1(canon)
    with pytest.raises(AP.SelfApprovalError):
        workflow.decide(f"JE-{eid}-2", "close_accountant", "approved", "approving my own entry")
    assert db.q1("SELECT 1 FROM events WHERE kind='sod_violation'") is not None
    print("\nSoD: self-approval refused by CHECK (proposer <> approver)")


def test_bonus_run_held_until_offsets(canon):
    held = [h["target"] for h in workflow.holds() if h["state"] == "held"]
    assert any("R1" in h for h in held) and any("R2" in h for h in held) and any("R4" in h for h in held)
    assert not any("(R3)" in h or "(R5)" in h or "(R6)" in h for h in held)
    assert any("Summit Mats" in h for h in held)
    workflow.simulate("lena")
    assert not any("bonus run" in h["target"] and h["state"] == "held" for h in workflow.holds())


def test_approved_entry_posts_and_restates_leverage(canon):
    eid = x1(canon)
    out = workflow.decide(f"JE-{eid}-2", "dana", "approved", "Open period, OOP tag")
    assert out["executed"]["posted"]["period"] == "2026-06"
    from trackback import review
    from trackback.engine.books import Books
    cx = review.ctx(C.KEY_DATES["now"])
    v = cx.lib.evaluate(Books(cx.entries))
    assert round(v["leverage@2026Q1"], 4) == 3.0208


def test_lender_document_goes_to_sam(canon):
    eid = x1(canon)
    lend = db.q1("SELECT * FROM actions WHERE action_id LIKE ?", (f"LEND-{eid}-%",))
    assert lend["assignee"] == "sam"
    workflow.simulate("sam")
    assert db.q1("SELECT state FROM actions WHERE action_id=?", (lend["action_id"],))["state"] == "executed"


def test_reminder_and_escalation(canon):
    workflow.advance(30)
    workflow.advance(48)
    assert db.q1("SELECT 1 FROM events WHERE kind='reminder'") is not None
    assert db.q1("SELECT 1 FROM events WHERE kind='escalated'") is not None


def test_memo_renders(canon):
    eid = x1(canon)
    md = db.q1("SELECT markdown FROM memos WHERE exception_id=? ORDER BY version DESC LIMIT 1", (eid,))["markdown"]
    for s in ("## 4. Quantification", "Iron curtain", "1,118,000", "Controls going forward", "Block duplicate import ids", "Jade"):
        assert s in md, s
    h = memo.to_html(md)
    assert "<table>" in h and "<h2>" in h


def test_s1_self_revision_pings_only_reporting_analyst(canon):
    res = hub.revise("CA.june_accrual.utilities", agent="close_accountant", new_value=195_000.0, reason="Bayline's June meter read came in higher", ts="2026-07-08T09:20:00-07:00")
    assert [p["agent"] for p in res["pings"]] == ["reporting_analyst"]
    assert any(n["agent"] == "covenant_comp" and n["reason"] == "different_period" for n in res["not_pinged"])
    assert res["pings"][0]["items"][0]["verdict"] == "reworked"
    print("\nS1:", res["pings"][0]["items"][0]["reason"], "| not pinged:", res["not_pinged"])
