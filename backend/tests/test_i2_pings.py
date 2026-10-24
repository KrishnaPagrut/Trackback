"""I2-3 acceptance: refusal codes, duplicate idempotency key, signature check, discovery."""
import json

import pytest
from fastapi.testclient import TestClient

from trackback import config
from trackback.core import db, graph, pings as P


def seed(conn):
    P.ensure_agents()
    db.insert("runs", {"run_id": "r1", "agent": "close_accountant", "task": "t", "pinned_at": "2026-04-10T17:00:00-07:00", "mode": "scripted", "status": "done", "started_at": None, "finished_at": None, "turns": 0, "note": None})
    graph.new_artifact(artifact_id="q1_ebitda", kind="number", run_id="r1", pinned_at="2026-04-10T17:00:00-07:00", period="2026-Q1", line_item="ebitda", content="Q1 EBITDA", value_num=1_400_000, formula={"expr": "x", "inputs": {}}, conclusions=None, agent_id="close_accountant")
    db.insert("runs", {"run_id": "r2", "agent": "reporting_analyst", "task": "t", "pinned_at": "2026-04-24T15:00:00-07:00", "mode": "scripted", "status": "done", "started_at": None, "finished_at": None, "turns": 0, "note": None})
    graph.new_artifact(artifact_id="tile_q1_ebitda", kind="number", run_id="r2", pinned_at="2026-04-24T15:00:00-07:00", period="2026-Q1", line_item="ebitda", content="tile", value_num=1_400_000, formula={"expr": "x", "inputs": {"x": {"kind": "artifact", "id": "q1_ebitda", "version": "1"}}}, conclusions={"display_rounding": 100000}, agent_id="reporting_analyst")
    graph.add_receipt(consumer_id="tile_q1_ebitda", consumer_version=1, consumed_id="q1_ebitda", consumed_version=1, fields_read=["value"], run_id="r2", agent_id="reporting_analyst", ts="2026-04-24T15:00:00-07:00")
    conn.commit()


def envelope(agent="reporting_analyst", target="tile_q1_ebitda", version=1, consumed=None, hop=1, chain=None, sign=True):
    sha = db.q1("SELECT content_hash FROM artifacts WHERE artifact_id='q1_ebitda' AND version=1")["content_hash"]
    items = [{"artifact_id": target, "node_kind": "calc", "kind": "number", "prior_version": version, "prior_output_excerpt": "", "fields_read": ["value"], "changed_fields": [],
              "consumed": consumed if consumed is not None else {"artifact_id": "q1_ebitda", "version": 1, "sha256": sha}}]
    env = P.build_ping(correction_id="E11", wave_id="w1", wave_no=1, target_agent_id=agent, hop=hop, causal_chain=chain or [], items=items, root_ping_id=None, ts=config.DEMO_NOW)
    if not sign:
        env["data"]["signature"] = "hmac-sha256=deadbeef"
    return env


@pytest.fixture()
def client(fresh_db):
    seed(fresh_db)
    from trackback.main import app
    return TestClient(app)


def test_discovery(client):
    r = client.get("/.well-known/trackback")
    assert r.status_code == 200 and {"close_accountant", "reporting_analyst", "covenant_comp"} <= {a["agent_id"] for a in r.json()["agents"]}  # Tidewall seats (plus the Lyft seats)


def test_accepts_with_location_and_dedups(client):
    env = envelope()
    r = client.post("/agents/reporting_analyst/trackback", json=env)
    assert r.status_code == 202 and r.headers["Location"].startswith("/pings/")
    r2 = client.post("/agents/reporting_analyst/trackback", json=env)
    assert r2.status_code == 202 and r2.json()["duplicate"] is True and r2.headers["Location"] == r.headers["Location"]
    st = client.get(r.headers["Location"]).json()
    assert st["state"] == "acknowledged"
    resp = client.post(r.headers["Location"] + "/response", json={"items": [{"artifact_id": "tile_q1_ebitda", "verdict": "still_valid", "reason": "display unchanged"}]})
    assert resp.json()["state"] == "still_valid"


@pytest.mark.parametrize("mutate,code", [
    (lambda e: e["data"].__setitem__("signature", "hmac-sha256=bad"), "unauthenticated"),
    (lambda e: e["data"]["your_nodes"][0].__setitem__("prior_version", 7), "stale_target"),
    (lambda e: e["data"]["your_nodes"][0].__setitem__("consumed", {"artifact_id": "q1_ebitda", "version": 1, "sha256": "0000"}), "hash_mismatch"),
    (lambda e: e["data"]["your_nodes"][0].__setitem__("consumed", {"artifact_id": "nope", "version": 1, "sha256": "x"}), "not_a_dependent"),
    (lambda e: e["data"].__setitem__("hop", 99), "hop_limit"),
    (lambda e: e["data"]["causal_chain"].append({"node": "tile_q1_ebitda"}), "cycle"),
    (lambda e: e["data"]["your_nodes"][0].__setitem__("consumed", {"artifact_id": "tile_q1_ebitda", "version": 1, "sha256": "x"}), "self_ping"),
])
def test_refusals(client, mutate, code):
    env = envelope()
    mutate(env)
    if code != "unauthenticated":
        env["data"]["signature"] = P.sign(env["data"])  # re-sign the mutated payload so only the intended refusal fires
    r = client.post("/agents/reporting_analyst/trackback", json=env)
    assert r.status_code == 400 and r.json()["refused"] == code


def test_unknown_agent_and_malformed(client):
    env = envelope(agent="nobody")
    r = client.post("/agents/nobody/trackback", json=env)
    assert r.status_code == 400 and r.json()["refused"] == "unknown_target"
    assert client.post("/agents/reporting_analyst/trackback", json={"type": "x"}).status_code == 400
