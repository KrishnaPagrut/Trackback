"""CP6 and CP7: the scorecard writes every metric from real runs; the four lessons pass the regression gate and the over-general one fails;
v2 beats v1 on held-out cases; Jade catches the planted mistakes; Replay leaks nothing."""
import json

import pytest

from trackback import config as C


@pytest.fixture(scope="module")
def card(canon):
    from trackback.cli import snapshot_write
    from trackback.eval import scorecard
    snap = C.SNAPSHOT_PATH
    C.SNAPSHOT_PATH = C.DATA_DIR / "build" / "test_snapshot.sqlite"
    try:
        snapshot_write()
        return scorecard.main()
    finally:
        C.SNAPSHOT_PATH = snap


def test_scorecard_headline(card):
    h = card["headline"]
    assert h["exceptions_found"] == "6/6" and h["noise_false_alarms"] == 0 and h["replay_leaks"] == 0
    assert (h["x1_invalidated"], h["x1_still_valid"], h["x1_compensations"]) == (40, 23, 5)
    assert h["materiality_v1_jade"] == 1.0 and h["materiality_naive"] < 0.8
    assert h["jade_catch_rate"] == 1.0 and h["jade_false_overrule_rate"] == 0.0
    print("\nSCORECARD", json.dumps(h))


def test_lessons_and_gate(card):
    les = {l["lesson"]: l for l in card["learning"]["lessons"]}
    for k in ("materiality_framework", "classify_by_knowable_at", "post_in_open_period", "lender_documents_to_cfo"):
        assert les[k]["gate"] == "pass", k
    assert les["closed_period_invoices_are_estimates"]["gate"] == "fail" and les["closed_period_invoices_are_estimates"]["broke"]
    print("\nGATE", [(l["lesson"], l["gate"]) for l in card["learning"]["lessons"]])


def test_v2_beats_v1_on_heldout(card):
    ho = card["learning"]["heldout"]
    assert ho["v2"]["cases"]["pass_rate"] > ho["v1"]["cases"]["pass_rate"]
    print(f"\nHELD-OUT v1 {ho['v1']['cases']['pass_rate']} -> v2 {ho['v2']['cases']['pass_rate']}")


def test_lineage_and_replay(card):
    assert card["lineage"]["correct"] == card["lineage"]["truths"] == 55
    assert card["replay"]["leaked"] == 0 and card["replay"]["refused"] > 0
