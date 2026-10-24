"""CP4: Jade overrules X1's materiality and X3's classification and flags the lender routing; aggregate $662k / $1.118M."""
import pytest

from trackback import config as C
from trackback import review as RV


@pytest.fixture(scope="module")
def judged(tw):
    pin = C.KEY_DATES["now"]
    excs = [e for r in RV.detect(pin, store=False) for e in r["exceptions"]]
    links = RV.trace(pin, store=False)
    ripples = {e["exception_id"]: RV.ripple_for(e, links, pin, store=False) for e in excs if (e.get("correction") or {}).get("lines")}
    j = RV.judge(excs, ripples, pin, None, store=False)
    j["by_kind"] = {e["kind"]: e["exception_id"] for e in excs}
    return j


def jade_of(j, kind):
    return {f["claim_key"]: f for f in j["jade"][j["by_kind"][kind]]}


def test_aggregate(judged):
    a = judged["materiality"]["aggregate"]
    assert a["rollover"] == pytest.approx(662_000) and a["iron_curtain"] == pytest.approx(1_118_000)
    assert a["rollover_passes"] and a["iron_curtain_fails"]
    x1 = judged["materiality"]["per_item"][judged["by_kind"]["duplicate_import"]]
    assert x1["material"] and x1["above_performance"] and x1["pct_budgeted_pretax"] == 4.69
    assert {"covenant_flip", "compensation"} <= set(x1["triggers"])
    print(f"\nMATERIALITY aggregate rollover {a['rollover']:,.0f} (passes), iron curtain {a['iron_curtain']:,.0f} (fails); X1 triggers {x1['triggers']}")


def test_v1_agent_calls_x1_immaterial_and_jade_overrules(judged):
    eid = judged["by_kind"]["duplicate_import"]
    assert judged["evaluations"][eid]["q5_matters"]["material"] is False
    f = jade_of(judged, "duplicate_import")["q5_matters"]
    assert f["verdict"] == "overrule" and f["corrected"]["material"] is True
    assert "1,118,000" in f["why"] and "3.0208" in f["why"]
    assert judged["final"][eid]["q5_matters"]["material"] is True
    print("\nJADE X1:", f["why"])


def test_jade_overrules_x3_classification(judged):
    eid = judged["by_kind"]["accrual_true_up"]
    assert judged["evaluations"][eid]["q3_classification"]["value"] == "error"
    f = jade_of(judged, "accrual_true_up")["q3_classification"]
    assert f["verdict"] == "overrule" and f["corrected"]["value"] == "estimate_change"
    assert judged["final"][eid]["q7_fix"]["treatment"] == "no_action"
    print("\nJADE X3:", f["why"])


def test_jade_flags_lender_routing(judged):
    f = jade_of(judged, "duplicate_import")["q7_fix.approvers.lender_document"]
    assert f["verdict"] == "flag" and f["agent_value"] == "dana" and f["corrected"]["approver"] == "sam"
    assert judged["final"][judged["by_kind"]["duplicate_import"]]["q7_fix"]["approvers"]["lender_document"] == "sam"
    print("\nJADE routing:", f["why"])


def test_locked_period_is_left_to_dana(judged):
    f = jade_of(judged, "duplicate_import")["q7_fix.posting"]
    assert f["verdict"] == "escalate" and "Dana" in f["why"]
    assert judged["final"][judged["by_kind"]["duplicate_import"]]["q7_fix"]["posting_period"] == "2026-03"


def test_trivial_items_stay_immaterial(judged):
    for k in ("duplicate_vendor_invoice", "ach_return", "unbooked_bank_fee"):
        assert judged["final"][judged["by_kind"][k]]["q5_matters"]["material"] is False
        assert jade_of(judged, k)["q5_matters"]["verdict"] == "approve"
