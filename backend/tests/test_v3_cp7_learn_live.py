"""CP7 live: the shipped review proposes its own lessons; the gate refuses the over-general one; after Dana approves the four that pass,
the agent (v2) gets X1 right on its own and Jade has nothing left to correct."""
from trackback import lessons, review
from trackback.core import db


def test_lessons_gate_approve_and_rerun(canon):
    ids = {r["mistake_kind"]: r["lesson_id"] for r in db.q("SELECT * FROM lessons WHERE world='tidewall'")}
    assert set(ids) == {"materiality_framework", "classify_by_knowable_at", "post_in_open_period", "lender_documents_to_cfo", "closed_period_invoices_are_estimates"}
    bad = lessons.gate_live(ids["closed_period_invoices_are_estimates"])
    assert bad["result"] == "fail" and any("TW-X2" in b for b in bad["broke"])
    for k in ("classify_by_knowable_at", "lender_documents_to_cfo", "materiality_framework", "post_in_open_period"):
        g = lessons.gate_live(ids[k])
        assert g["result"] == "pass" and not g["broke"], k
        assert lessons.approve(ids[k], "dana", "2026-07-08T09:30:00-07:00")["approved"]
    now = review.evaluate_only()
    assert now["playbook"] == "v2"
    x1 = next(v for v in now["exceptions"].values() if "imported twice" in v["title"])
    assert x1["material"] and x1["posting"] == "2026-06" and x1["approvers"]["lender_document"] == "sam" and not x1["jade"]
    assert all(not v["jade"] or all(j["verdict"] == "approve" for j in v["jade"]) for v in now["exceptions"].values())
    print("\nLEARN: v2 after four approved lessons; Jade has nothing to correct")
