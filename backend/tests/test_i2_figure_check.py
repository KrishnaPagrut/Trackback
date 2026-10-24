"""The extra-zero check: a sentence that cites a number must show it; same digits at another magnitude is a mismatch."""
from trackback.core import db, fence, graph


def _sentence(fresh_db, content, cited_value, aid="n1", sid="s1"):
    graph.new_artifact(artifact_id=aid, kind="number", run_id="t", pinned_at="2026-07-08T09:00:00-07:00", period="2024", line_item="margin_expansion_bps",
                       content=None, value_num=cited_value, formula=None, conclusions=None)
    v = graph.new_artifact(artifact_id=sid, kind="sentence", run_id="t", pinned_at="2026-07-08T09:00:00-07:00", period="2024", line_item="margin_expansion_bps",
                           content=content, value_num=None, formula=None, conclusions=None, fields={"artifacts": [aid]})
    return db.q1("SELECT * FROM artifacts WHERE artifact_id=? AND version=?", (sid, v))


def test_extra_zero_is_flagged(fresh_db):
    row = _sentence(fresh_db, "Margin expansion of approximately 500 basis points year-over-year.", 50.0)
    fm = fence.figure_mismatch(row)
    assert fm and fm["stated"] == 500 and fm["cited_value"] == 50


def test_correct_figure_passes(fresh_db):
    row = _sentence(fresh_db, "Margin expansion of approximately 50 basis points year-over-year.", 50.0, aid="n2", sid="s2")
    assert fence.figure_mismatch(row) is None


def test_rounded_display_and_small_values_do_not_trip(fresh_db):
    row = _sentence(fresh_db, "Membership revenue was $7.42M in Q1.", 7_420_000.0, aid="n3", sid="s3")
    assert fence.figure_mismatch(row) is None
    row = _sentence(fresh_db, "Net income more than doubled (9%).", 0.9, aid="n4", sid="s4")  # ratios under 10 are never checked
    assert fence.figure_mismatch(row) is None
