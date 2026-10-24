"""Iteration-2 protocol endpoints: discovery, versions/retractions, pings (202 + Location), responses, challenges, waves, SSE events."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from . import config
from .core import db, pings as P, waves as W

router = APIRouter()


@router.get("/.well-known/trackback")
def well_known():
    return P.well_known()


class VersionReq(BaseModel):
    agent_id: str
    content: str | None = None
    value_num: float | None = None
    conclusions: dict | None = None
    reason: str = ""
    approved_by: str | None = None


@router.post("/artifacts/{artifact_id}/versions")
def publish_version(artifact_id: str, req: VersionReq):
    try:
        return W.publish_version(artifact_id, agent_id=req.agent_id, content=req.content, value_num=req.value_num, conclusions=req.conclusions, reason=req.reason, ts=config.DEMO_NOW, approved_by=req.approved_by)
    except KeyError:
        raise HTTPException(404, "no such artifact")


@router.post("/artifacts/{artifact_id}/retract")
def retract(artifact_id: str, req: VersionReq):
    try:
        return W.publish_version(artifact_id, agent_id=req.agent_id, content=None, value_num=None, conclusions=None, reason=req.reason, ts=config.DEMO_NOW, retract=True)
    except KeyError:
        raise HTTPException(404, "no such artifact")


@router.post("/agents/{agent_id}/trackback", status_code=202)
def deliver_ping(agent_id: str, envelope: dict, response: Response):
    """Deliver a ping. 202 + Location. Duplicate idempotency key returns 202 with the existing Location. Refusals are 400-class with a code."""
    if not isinstance(envelope, dict) or envelope.get("type") != P.PING_TYPE or "data" not in envelope:
        return JSONResponse({"refused": "malformed"}, status_code=400)
    if envelope.get("subject", "").split("/")[-1] != agent_id:
        return JSONResponse({"refused": "malformed", "detail": "subject does not match the endpoint"}, status_code=400)
    rec = P.enqueue(envelope, config.DEMO_NOW)
    if rec.get("refusal"):
        return JSONResponse({"refused": rec["refusal"], "ping_id": rec["ping_id"]}, status_code=400)
    if not rec.get("duplicate"):
        P.deliver(rec["ping_id"], config.DEMO_NOW)
    response.headers["Location"] = rec["location"]
    return {"ping_id": rec["ping_id"], "state": "acknowledged" if not rec["duplicate"] else rec["state"], "duplicate": rec["duplicate"]}


@router.get("/pings/{ping_id}")
def ping_status(ping_id: str):
    try:
        return P.status(ping_id)
    except KeyError:
        raise HTTPException(404, "no such ping")


class PingResponse(BaseModel):
    items: list[dict]


@router.post("/pings/{ping_id}/response")
def ping_response(ping_id: str, body: PingResponse):
    try:
        return P.respond(ping_id, body.items, config.DEMO_NOW)
    except KeyError:
        raise HTTPException(404, "no such ping")


@router.get("/pings")
def list_pings(correction: str | None = None):
    rows = db.q("SELECT * FROM pings WHERE (?1 IS NULL OR correction_id=?1) ORDER BY created_at, ping_id", (correction,))
    out = []
    for r in rows:
        d = dict(r); d.pop("payload_json", None); d["causal_chain"] = json.loads(d.pop("causal_chain_json") or "[]")
        resp = db.q1("SELECT * FROM ping_responses WHERE ping_id=? ORDER BY responded_at DESC LIMIT 1", (r["ping_id"],))
        d["response"] = dict(resp) if resp else None
        if d["response"]:
            d["response"]["items"] = json.loads(d["response"].pop("items_json") or "[]")
        nodes = json.loads(r["payload_json"])["data"]["your_nodes"]
        d["n_items"] = len(nodes)
        d["items"] = [{"artifact_id": n.get("artifact_id"), "kind": n.get("kind"), "line_item": n.get("line_item"), "prior_output_excerpt": n.get("prior_output_excerpt"),
                       "conclusions": n.get("conclusions"), "changed_fields": n.get("changed_fields") or []} for n in nodes]
        out.append(d)
    return {"pings": out, "waves": [dict(w) for w in db.q("SELECT * FROM waves WHERE (?1 IS NULL OR correction_id=?1) ORDER BY started_at", (correction,))]}


class ChallengeReq(BaseModel):
    from_agent_id: str
    target_artifact_id: str
    reason: str


@router.post("/challenges")
def challenge(req: ChallengeReq):
    return W.file_challenge(req.from_agent_id, req.target_artifact_id, req.reason, config.DEMO_NOW)


@router.get("/challenges")
def challenges():
    return {"challenges": [dict(r) for r in db.q("SELECT * FROM upstream_challenges ORDER BY created_at")]}


@router.get("/corrections/{correction_id}/graph")
def correction_graph(correction_id: str):
    from .api import graph_view
    return graph_view(correction=correction_id)


@router.get("/events")
async def events(after: int = 0):
    """Server-sent events fed from the outbox (the durable record; SSE is only the doorbell)."""
    async def gen():
        last = after
        for _ in range(600):  # ~5 minutes per connection; the UI reconnects with ?after=
            rows = db.q("SELECT * FROM outbox WHERE event_id>? ORDER BY event_id LIMIT 100", (last,))
            for r in rows:
                last = r["event_id"]
                yield f"id: {r['event_id']}\nevent: {r['kind']}\ndata: {r['payload_json']}\n\n"
            await asyncio.sleep(0.5)
    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/outbox")
def outbox(after: int = 0, limit: int = 200):
    rows = db.q("SELECT * FROM outbox WHERE event_id>? ORDER BY event_id LIMIT ?", (after, limit))
    return {"events": [{**dict(r), "payload": json.loads(r["payload_json"])} for r in rows]}
