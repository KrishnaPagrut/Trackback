"""The trackback ping protocol v1: CloudEvents 1.0 envelope, PROV-O names, HMAC-SHA256 signature, Webmention-style delivery
(202 + status URL, idempotent re-sends), synchronous refusals in the 400 class. Only the hub creates pings; agents never do.

Lineage (say so in the README): TrackBack 1.2 (2002/2004, unverified pings, died of spam), Pingback 1.0 (XML-RPC, verification a MAY),
Webmention (W3C 2017: receiver MUST verify the source links to the target, 202 + Location, 410 = delete). Trackback verifies against a
hash-stamped consumption receipt instead of a link, so a ping can only travel along what the hub itself recorded at read time."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from typing import Any

from .. import config
from . import db, graph

PING_TYPE = "dev.trackback.ping.v1"
MAX_HOPS = 6
MAX_WAVES = 2
MAX_LLM_CALLS_PER_EVENT = 12
REFUSALS = ("malformed", "self_ping", "unknown_target", "stale_target", "not_a_dependent", "hash_mismatch", "hop_limit", "cycle", "unauthenticated", "rate_limit")
RESPONSE_STATES = ("acknowledged", "still_valid", "reworked", "needs_human", "refused", "superseded", "failed")


def _secret() -> bytes:
    return os.environ.get("TRACKBACK_PING_SECRET", "trackback-dev-secret").encode()


def canonical(data: dict) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str).encode()


def sign(data: dict) -> str:
    body = {k: v for k, v in data.items() if k != "signature"}
    return "hmac-sha256=" + hmac.new(_secret(), canonical(body), hashlib.sha256).hexdigest()


def verify(data: dict) -> bool:
    sig = data.get("signature") or ""
    return hmac.compare_digest(sig, sign(data))


def idempotency_key(agent_id: str, correction_id: str, wave_no: int, suspect_versions: list[str]) -> str:
    return hashlib.sha256(f"{agent_id}|{correction_id}|wave{wave_no}|{','.join(sorted(suspect_versions))}".encode()).hexdigest()


def agents_registry() -> list[dict]:
    rows = db.q("SELECT * FROM agents ORDER BY agent_id")
    return [dict(r) for r in rows]


def ensure_agents() -> None:
    from ..agents.base import SEATS
    for aid, seat in SEATS.items():
        if db.q1("SELECT 1 FROM agents WHERE agent_id=?", (aid,)) is None:
            db.insert("agents", {"agent_id": aid, "display_name": aid.replace("_", " ").title(), "ping_endpoint": f"/agents/{aid}/trackback",
                                 "model": config.AGENT_MODEL, "prompt_version": "v2", "seat": seat})
    if db.q1("SELECT 1 FROM agents WHERE agent_id='trackback'") is None:
        db.insert("agents", {"agent_id": "trackback", "display_name": "Trackback (engine)", "ping_endpoint": None, "model": None, "prompt_version": None, "seat": "The hub: recomputes every calc node itself and is the only thing that can create pings."})
    db.commit()


def build_ping(*, correction_id: str, wave_id: str, wave_no: int, target_agent_id: str, hop: int, causal_chain: list[dict], items: list[dict],
               root_ping_id: str | None, ts: str) -> dict:
    """Assemble the CloudEvents envelope for one agent's bundle of suspect nodes in this wave."""
    ping_id = "ping_" + uuid.uuid4().hex[:12]
    data = {
        "ping_id": ping_id,
        "idempotency_key": idempotency_key(target_agent_id, correction_id, wave_no, [f"{i['artifact_id']}@{i['prior_version']}" for i in items]),
        "correction_id": correction_id, "wave": wave_no, "root_ping_id": root_ping_id or ping_id, "hop": hop, "max_hops": MAX_HOPS,
        "causal_chain": causal_chain, "your_nodes": items,
        "allowed_responses": ["still_valid", "reworked", "needs_human"],
        "constraints": "Only change content that depends on changed fields. Never compute numbers; numbers come from Trackback.",
        "status_url": f"/pings/{ping_id}",
    }
    data["signature"] = sign(data)
    envelope = {"specversion": "1.0", "type": PING_TYPE, "source": f"trackback://hub/corrections/{correction_id}", "id": ping_id,
                "subject": f"trackback://agent/{target_agent_id}", "time": db.norm_ts(ts), "datacontenttype": "application/json",
                "tbcorrection": correction_id, "tbwave": wave_no, "data": data}
    return envelope


def refusal_check(envelope: dict) -> str | None:
    """Synchronous refusals on delivery. Returns a refusal code or None."""
    try:
        data = envelope["data"]; agent = envelope["subject"].split("/")[-1]
        items = data["your_nodes"]; chain = data["causal_chain"]; hop = int(data["hop"])
    except (KeyError, TypeError, ValueError):
        return "malformed"
    if not verify(data):
        return "unauthenticated"
    if db.q1("SELECT 1 FROM agents WHERE agent_id=?", (agent,)) is None:
        return "unknown_target"
    if hop > data.get("max_hops", MAX_HOPS):
        return "hop_limit"
    chain_nodes = {c.get("node") for c in chain}
    for it in items:
        aid, ver = it["artifact_id"], int(it["prior_version"])
        cur = db.artifact_current(aid)
        if cur is None:
            return "unknown_target"
        if cur["version"] != ver:
            return "stale_target"
        if aid in chain_nodes:
            return "cycle"
        consumed = it.get("consumed") or {}
        if consumed.get("artifact_id") == aid:
            return "self_ping"
        if consumed:
            rc = db.q1("SELECT consumed_sha256 FROM consumption_receipts WHERE consumer_artifact_id=? AND consumer_version=? AND consumed_artifact_id=? AND consumed_version=?",
                       (aid, ver, consumed["artifact_id"], int(consumed["version"])))
            if rc is None:
                return "not_a_dependent"
            if consumed.get("sha256") and rc["consumed_sha256"] and consumed["sha256"] != rc["consumed_sha256"]:
                return "hash_mismatch"
    return None


def enqueue(envelope: dict, ts: str) -> dict:
    """Write the ping and its outbox row in the caller's transaction. Duplicate idempotency key: return the existing ping (Pingback 0x0030)."""
    data = envelope["data"]
    existing = db.q1("SELECT ping_id, state FROM pings WHERE idempotency_key=?", (data["idempotency_key"],))
    if existing:
        return {"ping_id": existing["ping_id"], "state": existing["state"], "duplicate": True, "location": f"/pings/{existing['ping_id']}"}
    refusal = refusal_check(envelope)
    db.insert("pings", {"ping_id": data["ping_id"], "idempotency_key": data["idempotency_key"], "correction_id": data["correction_id"], "wave_id": envelope.get("tbwave_id"),
                        "root_ping_id": data["root_ping_id"], "hop": data["hop"], "causal_chain_json": db.dumps(data["causal_chain"]), "target_agent_id": envelope["subject"].split("/")[-1],
                        "payload_json": db.dumps(envelope), "state": "refused" if refusal else "pending", "refusal_code": refusal, "created_at": db.norm_ts(ts),
                        "delivered_at": None, "responded_at": None, "attempts": 0, "superseded_by": None})
    db.insert("outbox", {"kind": "ping.refused" if refusal else "ping.enqueued", "payload_json": db.dumps({"ping_id": data["ping_id"], "agent": envelope["subject"].split("/")[-1], "refusal": refusal,
                         "n_items": len(data["your_nodes"]), "wave": data["wave"], "correction_id": data["correction_id"]}), "created_at": db.norm_ts(ts), "sent_at": None, "ping_id": data["ping_id"]})
    return {"ping_id": data["ping_id"], "state": "refused" if refusal else "pending", "refusal": refusal, "duplicate": False, "location": f"/pings/{data['ping_id']}"}


def deliver(ping_id: str, ts: str) -> dict:
    """Mark delivered (202 semantics). The in-process dispatcher calls the agent through the same handler the HTTP route wraps."""
    p = db.q1("SELECT * FROM pings WHERE ping_id=?", (ping_id,))
    if p is None:
        raise KeyError(ping_id)
    if p["state"] == "refused":
        return {"ping_id": ping_id, "state": "refused", "refusal": p["refusal_code"]}
    db.get_conn().execute("UPDATE pings SET state='acknowledged', delivered_at=?, attempts=attempts+1 WHERE ping_id=? AND state IN ('pending','acknowledged')", (db.norm_ts(ts), ping_id))
    db.insert("outbox", {"kind": "ping.delivered", "payload_json": db.dumps({"ping_id": ping_id, "agent": p["target_agent_id"]}), "created_at": db.norm_ts(ts), "sent_at": None, "ping_id": ping_id})
    db.commit()
    return {"ping_id": ping_id, "state": "acknowledged", "location": f"/pings/{ping_id}"}


def respond(ping_id: str, items: list[dict], ts: str) -> dict:
    """Record the agent's verdicts. items: [{artifact_id, verdict, reason, new_version?, material_change?, evidence?, compensation_id?}]."""
    p = db.q1("SELECT * FROM pings WHERE ping_id=?", (ping_id,))
    if p is None:
        raise KeyError(ping_id)
    if p["responded_at"]:
        return {"ping_id": ping_id, "state": p["state"], "duplicate": True}
    verdicts = {i["verdict"] for i in items}
    state = "needs_human" if "needs_human" in verdicts else ("reworked" if "reworked" in verdicts else "still_valid")
    db.insert("ping_responses", {"ping_id": ping_id, "state": state, "reason": "; ".join(f"{i['artifact_id']}: {i.get('reason', '')}" for i in items)[:2000],
                                 "evidence_json": db.dumps([i.get("evidence") for i in items]), "new_versions_json": db.dumps([i.get("new_version") for i in items if i.get("new_version")]),
                                 "material_change": 1 if any(i.get("material_change") for i in items) else 0, "responded_at": db.norm_ts(ts), "items_json": db.dumps(items)})
    db.get_conn().execute("UPDATE pings SET state=?, responded_at=? WHERE ping_id=?", (state, db.norm_ts(ts), ping_id))
    db.insert("outbox", {"kind": "ping.responded", "payload_json": db.dumps({"ping_id": ping_id, "agent": p["target_agent_id"], "state": state, "items": [{k: i.get(k) for k in ("artifact_id", "verdict", "reason")} for i in items]}),
                         "created_at": db.norm_ts(ts), "sent_at": None, "ping_id": ping_id})
    db.commit()
    return {"ping_id": ping_id, "state": state}


def status(ping_id: str) -> dict:
    p = db.q1("SELECT * FROM pings WHERE ping_id=?", (ping_id,))
    if p is None:
        raise KeyError(ping_id)
    d = dict(p); d["payload"] = json.loads(d.pop("payload_json")); d["causal_chain"] = json.loads(d.pop("causal_chain_json") or "[]")
    r = db.q1("SELECT * FROM ping_responses WHERE ping_id=? ORDER BY responded_at DESC LIMIT 1", (ping_id,))
    d["response"] = dict(r) if r else None
    if d["response"]:
        d["response"]["items"] = json.loads(d["response"].pop("items_json") or "[]")
    return d


def well_known() -> dict:
    return {"protocol": PING_TYPE, "versions": ["v1"], "hub": "trackback://hub", "agents": [{"agent_id": a["agent_id"], "display_name": a["display_name"], "ping_endpoint": a["ping_endpoint"],
            "model": a["model"], "prompt_version": a["prompt_version"]} for a in agents_registry() if a["ping_endpoint"]],
            "refusal_codes": list(REFUSALS), "response_states": list(RESPONSE_STATES), "limits": {"max_hops": MAX_HOPS, "max_waves": MAX_WAVES, "max_llm_calls_per_event": MAX_LLM_CALLS_PER_EVENT},
            "lineage": {"trackback": "1.2 (2004)", "pingback": "1.0", "webmention": "W3C Recommendation 2017-01-12", "envelope": "CloudEvents 1.0", "provenance": "W3C PROV-O"}}
