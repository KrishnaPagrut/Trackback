"""Jade and the lessons memory, on a scratch copy of the canonical snapshot (no network, replay mode)."""
import os
import shutil
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SNAP = ROOT / "data" / "snapshots" / "canonical.sqlite"


@pytest.fixture()
def snap_db(tmp_path, monkeypatch):
    if not SNAP.exists():
        pytest.skip("no canonical snapshot")
    from trackback import config, db
    p = tmp_path / "snap.sqlite"
    s = sqlite3.connect(str(SNAP)); d = sqlite3.connect(str(p)); s.backup(d); d.close(); s.close()
    monkeypatch.setenv("TRACKBACK_LLM_MODE", "replay")
    monkeypatch.setattr(config, "DB_PATH", p)
    db.reset_connection()
    conn = db.get_conn()
    conn.execute("DELETE FROM evaluations"); conn.execute("DELETE FROM lessons"); conn.commit()
    yield conn
    db.reset_connection()


def test_playbook_v1_weaknesses_and_jade_overrules(snap_db):
    from trackback import review, lessons
    f = review.case_facts("E01")
    v1 = review.playbook_claims(f, set())
    assert v1["classification"]["value"] == "error"            # closed service period -> error (the weakness)
    assert v1["posting"]["value"] == "2026-03"                  # dated into the locked period
    j = review.jade_review(f, v1)
    assert j["classification"]["verdict"] == "overrule" and j["classification"]["jade"] == "new information"
    assert j["posting"]["verdict"] == "overrule" and j["posting"]["jade"] == "2026-04"
    v2 = review.playbook_claims(f, set(review.CHECKS))
    assert review.jade_review(f, v2)["summary"]["overruled"] == 0
    assert review.playbook_version(set()) == "v1" and review.playbook_version(set(review.CHECKS)) == "v2"


def test_evaluate_stores_and_proposes_lessons(snap_db):
    from trackback import review, lessons, db
    ev = review.evaluate("E01")
    assert ev["playbook_version"] == "v1"
    assert set(ev["jade"]["summary"]["overruled_claims"]) == {"classification", "posting"}
    ls = {l["lesson_id"]: l for l in lessons.all_lessons()}
    assert ls["L-classification"]["status"] == "proposed" and ls["L-classification"]["proposed_by"] == "jade"
    assert "E01" in ls["L-posting"]["cases"]
    assert review.load("E01")["headline"]["verdict"] == "overruled"
    assert db.q1("SELECT 1 FROM events WHERE kind='jade_review' AND correction_id='E01'")


def test_gate_approve_prospective_and_recall(snap_db):
    from trackback import review, lessons, config
    review.evaluate("E01")
    with pytest.raises(PermissionError):
        lessons.approve("L-classification", "agent:close_accountant", "2026-04-14T09:00:00-07:00")
    l = lessons.approve("L-classification", config.PEOPLE["controller"], "2026-04-14T09:00:00-07:00")
    assert l["status"] == "active" and l["gate"]["passed"] and l["gate"]["newly_failing"] == []
    assert lessons.active_checks("2026-04-13T00:00:00-07:00") == set()          # never backwards
    assert "classify_by_knowable_at" in lessons.active_checks("2026-04-14T10:00:00-07:00")
    ev = review.evaluate("E10")                                                  # May 20: the lesson is on
    assert ev["playbook_version"] == "v1+1" and "classification" not in ev["jade"]["summary"]["overruled_claims"]
    ev2 = review.evaluate("E02")
    assert any(r["lesson_id"] == "L-posting" for r in ev2["recalled"])          # E02 looks like E10: closed period, error, same comps


def test_gate_rejects_the_broad_lesson(snap_db):
    from trackback import review, lessons, config
    for cid in ("E01", "E10", "E02", "E09"):
        review.evaluate(cid)
    lessons.signal_rejection("E10", "JE-nonexistent", config.PEOPLE["controller"], "Q1 is locked; book in Q2 with an out-of-period tag", "2026-05-20T16:00:00-07:00")
    out = {l["lesson_id"]: l for l in lessons.approve_pending(config.PEOPLE["controller"], "2026-07-08T09:20:00-07:00")}
    assert out["L-posting"]["status"] == "active"
    bad = out["L-locked-means-estimate"]
    assert bad["status"] == "rejected_by_gate" and {x["case_id"] for x in bad["gate"]["newly_failing"]} >= {"E10", "E02"}
