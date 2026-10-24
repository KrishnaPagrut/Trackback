"""CP3: every lineage truth correct, H1 stale, the X1 ripple matches Appendix A (and X2, X4, X6 match the key), Replay refuses future reads."""
import json

import pytest

from trackback import config as C
from trackback import review as RV
from trackback.engine import recon as RC, replay as R


@pytest.fixture(scope="module")
def links(tw):
    return RV.trace(C.KEY_DATES["now"], store=False)


def test_every_lineage_truth(tw, links):
    truth = {t["id"]: t for t in tw["key"]["lineage"]}
    got = {l["item_id"]: l for l in links}
    assert set(got) == set(truth)
    for iid, t in truth.items():
        l = got[iid]
        if t["link"] == "derived":
            assert l["status"] == "derived", iid
        elif t["metric"].startswith("sum:"):
            assert l["status"] == "reconstructed" and sorted(l["metric_id"][4:].split("+")) == sorted(t["metric"][4:].split("+")), iid
        else:
            assert l["metric_id"] == t["metric"], (iid, l["metric_id"], t["metric"])
        assert (l["status"] == "stale") == bool(t.get("stale")), iid
    n_linked = sum(1 for l in links if l["status"] != "derived")
    print(f"\nTRACE {n_linked} of {n_linked} lineage truths correct, {sum(1 for l in links if l['status'] == 'derived')} derived cells; min confidence {min(l['confidence'] for l in links if l['status'] in ('linked', 'policy', 'stale')):.2f}")


def test_h1_deck_ebitda_is_stale(links):
    h1 = next(l for l in links if l["item_id"] == "DECK.s2.l2")
    assert h1["status"] == "stale" and h1["snapshot"] == "draft"
    assert "$32,000,000" in h1["explanation"]
    print("\nH1", h1["explanation"])


@pytest.mark.parametrize("kind,kid", [("duplicate_import", "X1"), ("unaccrued_invoice", "X2"), ("duplicate_vendor_invoice", "X4"), ("unbooked_bank_fee", "X6")])
def test_ripple_matches_the_key(tw, links, kind, kid):
    exc = next(e for r in RV.detect(C.KEY_DATES["now"], store=False) for e in r["exceptions"] if e["kind"] == kind)
    res = RV.ripple_for(exc, links, C.KEY_DATES["now"], store=False)
    exp = tw["key"]["impact"][kid]
    for i, v in res["items"].items():
        assert (v["verdict"], v["reason"]) == (exp["items"][i]["verdict"], exp["items"][i]["reason"]), (kid, i)
    for i, v in res["actions"].items():
        assert (v["verdict"], v["reason"]) == (exp["actions"][i]["verdict"], exp["actions"][i]["reason"]), (kid, i)
        if exp["actions"][i]["amount"]:
            assert v["compensation"]["amount"] == pytest.approx(exp["actions"][i]["amount"])
    if kid == "X1":
        c = res["counts"]
        assert (c["invalidated"], c["still_valid"], c["compensations"]) == (40, 23, 5)
        assert c["seconds"] if False else res["seconds"] < 1.0
        print(f"\nRIPPLE X1: {c['invalidated']} invalidated, {c['still_valid']} still valid, {c['compensations']} compensations; {c['metrics_recomputed']} of {c['metrics_total']} metrics recomputed; naive {c['naive']}; {res['seconds']}s")


def test_replay_refuses_future_reads(tw):
    pin = C.KEY_DATES["q1_close"]
    tm = R.timemap("billing_release_lines")
    assert len(tm) == 2
    assert R.timegate("billing_release_lines", pin)["version_id"] == "billing_release_lines@v1"
    with pytest.raises(R.Refusal) as e:
        R.fetch("billing_release_lines@v2", pin)
    assert e.value.status == 403 and e.value.problem()["type"].endswith("temporal-pin-violation")
    with pytest.raises(R.Refusal) as e2:
        R.timegate("bank_statement_2026_06", pin)
    assert e2.value.status == 404
    print(f"\nREPLAY refused: {e.value.detail}")


def test_x1_was_visible_on_april_9(tw):
    rows = R.rows("billing_release_lines", C.KEY_DATES["draft_tb"])
    b07 = sum(float(r["release_amount"]) for r in rows if r["batch"] == "B07" and r["period"] == "2026-03")
    log = R.rows("gl_import_log", C.KEY_DATES["draft_tb"])
    assert round(b07, 2) == 750000.0 and sum(1 for r in log if r["batch"] == "B07" and r["period"] == "2026-03") == 2
