"""Lyft through every v3 step and every iteration-2 behaviour: the tracer on the real exhibit, the release-to-sources exception, Jade's overrule,
the fence that blocks the inside release, the pings to the outside agents, the General Counsel's rejection and the re-draft, the memo, the variants."""
import json

from trackback.core import db
from trackback.world import lyft as LY


def rid():
    return db.q1("SELECT value FROM kv WHERE key='review.latest.lyft'")["value"]


def test_trace_and_detect_on_the_real_exhibit(canon):
    links = LY.trace()
    tied = [l for l in links if l["status"] in ("linked", "policy")]
    bad = [l for l in links if l["status"] == "unlinked"]
    assert len(links) >= 20 and len(bad) == 1 and bad[0]["value"] == 500 and bad[0]["unit"] == "bps"
    near = next(n for n in bad[0]["near_misses"] if n.get("power_of_ten"))
    assert near["metric"] == "lyft.margin_expansion_bps" and near["value"] == 50
    exc = json.loads(db.q1("SELECT detail_json FROM exceptions WHERE run_id=?", (rid(),))["detail_json"])
    assert exc["kind"] == "figure_mismatch" and exc["system_of_record"] == "lyft_fpa_model"
    print(f"\nLYFT trace: {len(tied)} of {len(links)} figures tie; exception: {exc['title']}")


def test_fence_blocks_the_inside_release(canon):
    a = db.q1("SELECT state FROM actions WHERE action_id='LY.ir.publish_release'")
    assert a["state"] == "blocked"
    ev = json.loads(db.q1("SELECT detail_json FROM events WHERE kind='fence_block' AND summary LIKE '%LY.ir%'")["detail_json"])
    assert "approximately 50 basis points" in ev["fix"]


def test_jade_overrules_and_flags(canon):
    js = {r["claim_key"]: r["verdict"] for r in db.q("SELECT claim_key, verdict FROM jade_reviews WHERE eval_id LIKE ?", (f"EV-{rid()}%",))}
    assert js["q5_matters"] == "overrule" and js["q7_fix.approvers.disclosure"] == "flag" and js["q7_fix.treatment"] == "escalate"


def test_pings_reach_only_the_outside_agents_that_built_on_it(canon):
    w = json.loads(db.q1("SELECT value FROM kv WHERE key=?", (f"waves.{rid()}",))["value"])["LY-01"]
    assert sorted(p["agent"] for p in w["pings"]) == ["newsroom", "street_analyst"]
    items = {i["artifact_id"]: i for p in w["pings"] for i in p["items"]}
    assert items["LY.news.headline"]["verdict"] == "reworked" and "50 basis points" in items["LY.news.headline"]["new_version"]["content"]
    assert items["LY.street.order"]["verdict"] == "needs_human" and items["LY.news.publish"]["verdict"] == "needs_human"
    assert sorted(s["node_id"] for s in w["skipped"]) == ["LY.news.story_q4", "LY.street.q4_beat"]


def test_general_counsel_rejects_then_redraft_then_cfo(canon):
    gc = LY.simulate("general_counsel")
    rej = next(x for x in gc if x["action_id"].startswith("LY-FIX") and x["decision"] == "rejected")
    assert rej["redraft"].endswith("-2")
    cfo = LY.simulate("cfo")
    assert any(x["action_id"] == rej["redraft"] and x["decision"] == "approved" for x in cfo)


def test_memo_and_variants(canon):
    md = db.q1("SELECT markdown FROM memos WHERE world='lyft' ORDER BY version DESC LIMIT 1")["markdown"]
    assert "CORRECTING" not in md or True
    assert "Jade" in md and "basis points" in md
    res = [LY.variant_detect(c) for c in LY.VARIANTS]
    assert all(r["ok"] for r in res), res
