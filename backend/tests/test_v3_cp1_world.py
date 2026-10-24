"""CP1: every Section 5.1 calibration target, asserted through the engine's Books and through the independent reference arithmetic."""
import sqlite3

import pytest

from trackback import config as C
from trackback.core import db
from trackback.engine.books import Books, tidewall_library
from trackback.world import answer_key as AK
from trackback.world.refcalc import Ref


def lib(tw):
    return tidewall_library({r: v / 100 for r, v in tw["world"].targets.items()})


def test_ttm_adjusted_ebitda_close_and_draft(tw):
    L = lib(tw)
    close = L.evaluate(Books(tw["entries"], C.KEY_DATES["q1_close"]))
    draft = L.evaluate(Books(tw["entries"], C.KEY_DATES["draft_tb"]))
    assert close["ttm_adj_ebitda@2026Q1"] == pytest.approx(32_000_000.00, abs=0.005)
    assert draft["ttm_adj_ebitda@2026Q1"] == pytest.approx(32_600_000.00, abs=0.005)
    assert Ref(tw["entries"], C.KEY_DATES["q1_close"]).ttm_ebitda("2026Q1") == pytest.approx(32_000_000.00, abs=0.005)
    print(f"\nCALIBRATION ttm_adj_ebitda close={close['ttm_adj_ebitda@2026Q1']:,.2f} draft={draft['ttm_adj_ebitda@2026Q1']:,.2f}")


def test_close_accruals_posted_apr_10(tw):
    acc = [e for e in tw["entries"] if e["posted_at"].startswith("2026-04-10") and e["account"] in ("6300", "6200")]
    assert {(e["account"], e["entity"], e["amount_cents"]) for e in acc} == {("6300", "HQ", 410_000_00), ("6200", "HQ", 190_000_00)}


def test_loan_cash_net_debt_leverage(tw):
    v = lib(tw).evaluate(Books(tw["entries"], C.KEY_DATES["q1_close"]))
    assert v["term_loan@2026Q1"] == pytest.approx(105_000_000)
    assert v["cash@2026Q1"] == pytest.approx(10_600_000)
    assert v["net_debt@2026Q1"] == pytest.approx(94_400_000)
    assert round(v["leverage@2026Q1"], 2) == 2.95
    assert v["covenant_status@2026Q1"] == "Compliant"
    print(f"\nCALIBRATION cash={v['cash@2026Q1']:,.0f} net_debt={v['net_debt@2026Q1']:,.0f} leverage={v['leverage@2026Q1']:.4f}")


def test_x1_effects(tw):
    key = tw["key"]
    x1 = AK.correction_lines("X1", tw["world"].facts)
    assert -sum(l["amount_cents"] for l in x1 if l["account"] == "2300") == 750_000_00
    v = lib(tw).evaluate(Books(tw["entries"], C.KEY_DATES["q1_close"], x1))
    assert v["ttm_adj_ebitda@2026Q1"] == pytest.approx(31_250_000)
    assert round(v["leverage@2026Q1"], 4) == 3.0208
    assert v["covenant_status@2026Q1"] == "BREACH"
    assert key["calibration"]["leverage_after_all"] == 3.0681
    print(f"\nCALIBRATION after X1: ttm={v['ttm_adj_ebitda@2026Q1']:,.0f} leverage={v['leverage@2026Q1']:.4f}; with X2 and P1: {key['calibration']['leverage_after_all']}")


def test_bonuses_and_tax(tw):
    c = tw["key"]["calibration"]
    assert c["bonus_overpaid"] == {"R1": 8400.0, "R2": 7200.0, "R3": 0.0, "R4": 4800.0, "R5": 0.0, "R6": 0.0}
    assert c["tax_overpaid_x1"] == pytest.approx(195_000.0)
    v = lib(tw).evaluate(Books(tw["entries"], C.KEY_DATES["q1_close"]))
    assert v["bonus.R3@2026Q1"] == 0 and v["bonus.R5@2026Q1"] == 0 and v["bonus.R6@2026Q1"] > 0
    print(f"\nCALIBRATION bonus overpaid {c['bonus_overpaid']}; Q2 tax overpaid {c['tax_overpaid_x1']:,.0f}")


def test_aggregate_materiality(tw):
    m = tw["key"]["materiality"]
    assert m["aggregate_rollover"] == pytest.approx(662_000)
    assert m["aggregate_iron_curtain"] == pytest.approx(1_118_000)
    assert m["rollover_passes"] and m["iron_curtain_fails"]
    print(f"\nCALIBRATION aggregate rollover={m['aggregate_rollover']:,.0f} iron curtain={m['aggregate_iron_curtain']:,.0f}")


def test_appendix_a_counts(tw):
    assert tw["key"]["impact"]["X1"]["counts"] == {"invalidated": 40, "still_valid": 23, "compensations": 5}
    assert tw["key"]["impact"]["X4"]["counts"]["invalidated"] == 0
    assert tw["key"]["impact"]["X6"]["counts"]["invalidated"] == 0


def test_engine_matches_reference_on_every_lineage_metric(tw):
    from trackback.world.refcalc import metric_value
    L = lib(tw)
    targets = tw["world"].targets
    for snap in ("draft", "close", "now"):
        v = L.evaluate(Books(tw["entries"], C.SNAPSHOTS[snap]))
        ref = Ref(tw["entries"], C.SNAPSHOTS[snap])
        for it in tw["items"]:
            m = it.get("metric")
            if not m or it["link"] == "derived":
                continue
            ev = sum(v[x] for x in m[4:].split("+")) if m.startswith("sum:") else v[m]
            rv = metric_value(ref, m, targets)
            assert ev == rv if isinstance(rv, str) else ev == pytest.approx(rv, abs=0.01), (snap, m)


def test_ledger_is_append_only(tw):
    with pytest.raises(sqlite3.DatabaseError):
        db.get_conn().execute("UPDATE gl_entries SET amount_cents=0 WHERE entry_id=(SELECT entry_id FROM gl_entries LIMIT 1)")
    with pytest.raises(sqlite3.DatabaseError):
        db.get_conn().execute("DELETE FROM gl_entries")


def test_every_transaction_balances(tw):
    from collections import defaultdict
    s = defaultdict(int)
    for e in tw["entries"]:
        s[e["txn_id"]] += e["amount_cents"]
    assert all(v == 0 for v in s.values())


def test_world_builds_fast(tw):
    assert tw["seconds"] < 30
