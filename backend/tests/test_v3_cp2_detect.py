"""CP2: exactly six exceptions (X1 to X6), P1 recognized as known, all noise cleared with the right reasons."""
from trackback import config as C
from trackback.engine import recon as R


def run(tw):
    return {r["recon"]: r for r in R.run_all(R.load_inputs(C.KEY_DATES["now"]))}


def test_exactly_six_exceptions(tw):
    res = run(tw)
    kinds = sorted((e["recon"], e["kind"], e["amount"]) for r in res.values() for e in r["exceptions"])
    assert kinds == sorted([("billing_to_gl", "duplicate_import", 750000.0), ("ap_review", "unaccrued_invoice", 140000.0), ("ap_review", "accrual_true_up", 58000.0),
                            ("ap_review", "duplicate_vendor_invoice", 18750.0), ("bank_to_book", "ach_return", 2310.0), ("bank_to_book", "unbooked_bank_fee", 312.4)])
    print("\nEXCEPTIONS", [(k[1], k[2]) for k in kinds])


def test_p1_known_and_noise_cleared(tw):
    res = run(tw)
    assert res["billing_to_gl"]["cleared_by_reason"] == {"known_item": 6}
    assert res["bank_to_book"]["cleared_by_reason"] == {"deposit_in_transit": 12, "outstanding_check": 3, "fx_rounding": 1}
    assert res["cash_application"]["cleared_by_reason"] == {"subset_sum": 1, "known_short_pay": 1, "alias": 1}
    ss = next(c for c in res["cash_application"]["cleared"] if c["reason"] == "subset_sum")
    assert sorted(ss["detail"]["parts"]) == [50000.0, 62000.0, 74400.0]
    sp = next(c for c in res["cash_application"]["cleared"] if c["reason"] == "known_short_pay")
    assert sp["detail"]["short"] == 25.0 and sp["detail"]["customer"] == "Pacific Lumen Labs"
    al = next(c for c in res["cash_application"]["cleared"] if c["reason"] == "alias")
    assert al["detail"]["suggest_alias"] == "SSU FOUNDATION ACCTS PAYABLE"
    assert res["bank_to_book"]["learned_lags"]["card"]["min"] == 2 == res["bank_to_book"]["learned_lags"]["card"]["max"]
    print("\nCLEARED", {k: v["cleared_by_reason"] for k, v in res.items()})


def test_duplicate_correction_reverses_the_extra_import(tw):
    x1 = next(e for e in run(tw)["billing_to_gl"]["exceptions"])
    assert x1["duplicate_import"] == "IMP-202603-B07-2"
    lines = x1["correction"]["lines"]
    assert sum(l["amount_cents"] for l in lines) == 0
    assert sum(l["amount_cents"] for l in lines if l["account"] == "4010") == 750_000_00
    assert x1["by_region"] == {"R1": 210000.0, "R2": 180000.0, "R3": 150000.0, "R4": 120000.0, "R5": 90000.0}


def test_priya_handoff(tw):
    h = run(tw)["billing_to_gl"]["handoff"]
    assert all(c["confirmed"] for c in h["confirmed"]) and [c["batch"] for c in h["confirmed"]] == ["B01", "B02", "B03", "B04", "B05", "B06"]
    assert {f["batch"]: f["result"] for f in h["finished"]} == {"B07": "duplicate_import", "B08": "matched", "B09": "known_item"}
    print("\nHANDOFF", h["summary"])
