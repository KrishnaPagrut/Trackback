"""M1 acceptance: TimeMap lists versions; TimeGate 302s; post-pin 403; pre-existence 404;
missing Accept-Datetime in a pinned session resolves to the pin; append-only and sum-to-zero invariants."""
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from trackback import config, db


def seed(conn):
    db.insert("sources", {"source_id": "billing_export_2026_03", "uri_r": "/r/billing_export_2026_03", "system": "billing", "kind": "billing_export", "title": "Billing export March"})
    for vid, tx, body in [("v1", "2026-04-09T14:02:00-07:00", {"rows": [1, 1]}), ("v2", "2026-07-08T09:05:00-07:00", {"rows": [1]})]:
        db.insert("source_versions", {"version_id": vid, "source_id": "billing_export_2026_03", "body": json.dumps(body), "content_hash": vid,
                                      "document_date": "2026-03-31", "tx_from": db.norm_ts(tx), "tx_to": config.TX_CURRENT, "supersedes": None, "correction_id": None})
    db.insert("sources", {"source_id": "late_doc", "uri_r": "/r/late_doc", "system": "ap", "kind": "invoice", "title": "late"})
    db.insert("source_versions", {"version_id": "l1", "source_id": "late_doc", "body": "{}", "content_hash": "l1", "document_date": "2026-03-01",
                                  "tx_from": db.norm_ts("2026-05-20T10:00:00-07:00"), "tx_to": config.TX_CURRENT, "supersedes": None, "correction_id": None})
    db.insert("runs", {"run_id": "run_q1", "agent": "close", "task": "q1", "pinned_at": db.norm_ts("2026-04-10T17:00:00-07:00"), "mode": "scripted", "status": "done",
                       "started_at": None, "finished_at": None, "turns": 0, "note": None})
    conn.commit()


@pytest.fixture()
def client(fresh_db):
    seed(fresh_db)
    from trackback.main import app
    return TestClient(app)


def test_timemap_lists_versions(client):
    r = client.get("/tm/billing_export_2026_03")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/link-format")
    assert r.text.count('rel="first memento"') == 1 and r.text.count('rel="last memento"') == 1


def test_timegate_302(client):
    r = client.get("/tg/billing_export_2026_03", headers={"Accept-Datetime": "Fri, 10 Apr 2026 23:00:00 GMT"}, follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/20260409210200")
    assert r.headers["Vary"].lower() == "accept-datetime"
    m = client.get(r.headers["Location"])
    assert m.status_code == 200 and m.headers["Memento-Datetime"] == "Thu, 09 Apr 2026 21:02:00 GMT"


def test_timegate_bad_datetime_400(client):
    assert client.get("/tg/billing_export_2026_03", headers={"Accept-Datetime": "yesterday"}).status_code == 400


def test_post_pin_fetch_403(client):
    r = client.get("/m/billing_export_2026_03/20260708160500", headers={"X-Trackback-Run": "run_q1"})
    assert r.status_code == 403
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["type"] == config.PROBLEM_TYPE and body["pinned_at"] and body["first_memento_datetime"]
    assert r.headers[config.PIN_HEADER]
    rows = db.q("SELECT * FROM reads WHERE run_id='run_q1' AND http_status=403")
    assert len(rows) == 1


def test_pre_existence_404(client):
    r = client.get("/tg/late_doc", headers={"X-Trackback-Run": "run_q1"}, follow_redirects=False)
    assert r.status_code == 404 and r.json()["type"] == config.PROBLEM_TYPE
    r2 = client.get("/m/late_doc/20260520170000", headers={"X-Trackback-Run": "run_q1"})
    assert r2.status_code == 404


def test_missing_accept_datetime_resolves_to_pin(client):
    r = client.get("/tg/billing_export_2026_03", headers={"X-Trackback-Run": "run_q1"}, follow_redirects=False)
    assert r.status_code == 302 and r.headers["Location"].endswith("/20260409210200")
    r = client.get("/r/billing_export_2026_03", headers={"X-Trackback-Run": "run_q1"})
    assert r.json()["version_id"] == "v1"
    r = client.get("/tg/billing_export_2026_03", headers={"X-Trackback-Run": "run_q1", "Accept-Datetime": "Wed, 08 Jul 2026 20:00:00 GMT"}, follow_redirects=False)
    assert r.status_code == 403


def test_unpinned_timegate_returns_latest_per_rfc(client):
    r = client.get("/tg/billing_export_2026_03", follow_redirects=False)
    assert r.headers["Location"].endswith("/20260708160500")


def test_pinned_timemap_hides_future(client):
    r = client.get("/tm/billing_export_2026_03", headers={"X-Trackback-Run": "run_q1"})
    assert "20260708160500" not in r.text and "20260409210200" in r.text


def test_append_only(fresh_db):
    seed(fresh_db)
    with pytest.raises(sqlite3.IntegrityError):
        fresh_db.execute("DELETE FROM source_versions WHERE version_id='v1'")
    with pytest.raises(sqlite3.IntegrityError):
        fresh_db.execute("UPDATE source_versions SET body='x' WHERE version_id='v1'")
    fresh_db.execute("UPDATE source_versions SET tx_to='2026-07-08T16:05:00+00:00' WHERE version_id='v1'")  # allowed
    assert fresh_db.execute("SELECT tx_to FROM source_versions WHERE version_id='v1'").fetchone()[0].startswith("2026-07-08")


def test_sum_to_zero_and_sod(fresh_db):
    from trackback import ledger
    tx_id = ledger.post_entry([("6100", 390000, "G3"), ("2100", -390000, "G3")], period="2026-04", orig_period="2026-03", memo="t", ts="2026-04-12")
    assert ledger.balanced(tx_id)
    with pytest.raises(ValueError):
        ledger.post_entry([("6100", 100, None)], period="2026-04", orig_period="2026-04", memo="bad", ts="2026-04-12")
    with pytest.raises(sqlite3.IntegrityError):
        db.insert("approvals", {"approval_id": "a1", "action_id": "x", "proposer": "agent:close", "approver": "agent:close", "decision": "approved", "reason": "", "ts": "t"})
