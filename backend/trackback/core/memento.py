"""RFC 7089 Memento (Pattern 2.1) plus Trackback's time-pinning profile.

Resources: /r/{doc_id} (original), /tg/{doc_id} (TimeGate, 302), /m/{doc_id}/{ts} (memento), /tm/{doc_id} (TimeMap).

Profile deviations from plain RFC 7089 (all four are listed in README.md):
 1. The pin is server-side, bound to the run (header X-Trackback-Run). Accept-Datetime is never the authority.
 2. If the first memento postdates the pin, 404 (not the RFC's "first memento").
 3. A direct fetch of a memento whose Memento-Datetime is after the pin is refused (403).
 4. A missing Accept-Datetime in a pinned session resolves to pinned_at, never to "latest".
Refusals are 403/404 with an RFC 9457 application/problem+json body; never 425 on the wire.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from .. import config
from . import db

router = APIRouter()


# ---- datetime helpers ----------------------------------------------------------

def to_dt(ts: str) -> datetime:
    return datetime.fromisoformat(db.norm_ts(ts))


def http_date(ts: str) -> str:
    return format_datetime(to_dt(ts).astimezone(timezone.utc), usegmt=True)


def ts14(ts: str) -> str:
    return to_dt(ts).astimezone(timezone.utc).strftime("%Y%m%d%H%M%S")


def parse_accept_datetime(raw: str) -> datetime | None:
    raw = raw.strip()
    try:
        return parsedate_to_datetime(raw).astimezone(timezone.utc)
    except Exception:
        pass
    try:
        return to_dt(raw)
    except Exception:
        return None


def parse_ts14(s: str) -> datetime | None:
    try:
        return datetime.strptime(s, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


# ---- pin resolution -------------------------------------------------------------

def run_pin(request: Request) -> tuple[str | None, str | None]:
    """Return (run_id, pinned_at ISO) for a pinned session, or (None, None)."""
    run_id = request.headers.get("X-Trackback-Run")
    if not run_id:
        pin = request.headers.get("X-Trackback-Pin")  # UI scrubber sessions: an explicit pin without a run
        return (None, db.norm_ts(pin)) if pin else (None, None)
    row = db.q1("SELECT pinned_at FROM runs WHERE run_id=?", (run_id,))
    if row is None:
        return run_id, None
    return run_id, db.norm_ts(row["pinned_at"])


def problem(status: int, detail: str, *, pinned_at: str | None, requested: str | None,
            first_memento: str | None, memento: str | None = None, instance: str = "") -> JSONResponse:
    body = {
        "type": config.PROBLEM_TYPE,
        "title": "Temporal pin violation" if status == 403 else "Not knowable as of the pin",
        "status": status,
        "detail": detail,
        "instance": instance,
        "pinned_at": pinned_at,
        "requested_datetime": requested,
        "first_memento_datetime": first_memento,
        "memento_datetime": memento,
    }
    headers = {config.PIN_HEADER: http_date(pinned_at) if pinned_at else ""}
    return JSONResponse(body, status_code=status, media_type="application/problem+json", headers=headers)


def log_read(request: Request, run_id: str | None, pinned_at: str | None, uri: str,
             version: sqlite3.Row | None, status: int) -> None:
    if not run_id:
        return
    db.insert("reads", {
        "read_id": uuid.uuid4().hex[:16],
        "run_id": run_id,
        "tool_call_id": request.headers.get("X-Trackback-Tool-Call"),
        "uri_m": uri,
        "source_version_id": version["version_id"] if version is not None else None,
        "memento_datetime": version["tx_from"] if version is not None else None,
        "pinned_at": pinned_at,
        "http_status": status,
        "ts": pinned_at or config.DEMO_NOW,
    })
    db.commit()


def link_header(doc_id: str, versions: list[sqlite3.Row], current: sqlite3.Row | None = None) -> str:
    parts = [f'</r/{doc_id}>; rel="original"', f'</tg/{doc_id}>; rel="timegate"',
             f'</tm/{doc_id}>; rel="timemap"; type="application/link-format"']
    if versions:
        first, last = versions[0], versions[-1]
        parts.append(f'</m/{doc_id}/{ts14(first["tx_from"])}>; rel="first memento"; datetime="{http_date(first["tx_from"])}"')
        if last["version_id"] != first["version_id"]:
            parts.append(f'</m/{doc_id}/{ts14(last["tx_from"])}>; rel="last memento"; datetime="{http_date(last["tx_from"])}"')
    if current is not None:
        idx = [v["version_id"] for v in versions].index(current["version_id"])
        if idx > 0:
            p = versions[idx - 1]
            parts.append(f'</m/{doc_id}/{ts14(p["tx_from"])}>; rel="prev memento"; datetime="{http_date(p["tx_from"])}"')
        if idx < len(versions) - 1:
            n = versions[idx + 1]
            parts.append(f'</m/{doc_id}/{ts14(n["tx_from"])}>; rel="next memento"; datetime="{http_date(n["tx_from"])}"')
    return ", ".join(parts)


def visible_versions(doc_id: str, pinned_at: str | None) -> list[sqlite3.Row]:
    versions = db.source_versions_all(doc_id)
    if pinned_at:
        versions = [v for v in versions if db.norm_ts(v["tx_from"]) <= pinned_at]
    return versions


def memento_response(doc_id: str, version: sqlite3.Row, versions: list[sqlite3.Row]) -> Response:
    claims = db.q("SELECT claim_version_id, claim_id, value_num, value_text, valid_from, valid_to FROM claim_versions WHERE source_version_id=?",
                  (version["version_id"],))
    try:
        body = json.loads(version["body"])
    except Exception:
        body = {"text": version["body"]}
    payload = {
        "doc_id": doc_id,
        "version_id": version["version_id"],
        "memento_datetime": version["tx_from"],
        "document_date": version["document_date"],
        "content_hash": version["content_hash"],
        "supersedes": version["supersedes"],
        "correction_id": version["correction_id"],
        "body": body,
        "claims": [dict(c) for c in claims],
    }
    headers = {
        "Memento-Datetime": http_date(version["tx_from"]),
        "Link": link_header(doc_id, versions, version),
        "Trackback-Version-Id": version["version_id"],
        "Cache-Control": "immutable, max-age=31536000",
    }
    return JSONResponse(payload, headers=headers)


# ---- endpoints --------------------------------------------------------------------

@router.get("/r/{doc_id}")
def original(doc_id: str, request: Request):
    run_id, pinned_at = run_pin(request)
    all_versions = db.source_versions_all(doc_id)
    if not all_versions:
        return JSONResponse({"type": "about:blank", "title": "Not Found", "status": 404, "detail": f"no source {doc_id}"},
                            status_code=404, media_type="application/problem+json")
    if pinned_at:
        # In a pinned session the "original" is the version as of the pin (deviation 4).
        versions = visible_versions(doc_id, pinned_at)
        if not versions:
            resp = problem(404, f"{doc_id} did not exist as of the pin", pinned_at=pinned_at, requested=None,
                           first_memento=all_versions[0]["tx_from"], instance=f"/r/{doc_id}")
            log_read(request, run_id, pinned_at, f"/r/{doc_id}", None, 404)
            return resp
        resp = memento_response(doc_id, versions[-1], versions)
        resp.headers[config.PIN_HEADER] = http_date(pinned_at)
        log_read(request, run_id, pinned_at, f"/r/{doc_id}", versions[-1], 200)
        return resp
    resp = memento_response(doc_id, all_versions[-1], all_versions)
    resp.headers["Link"] = link_header(doc_id, all_versions)
    del resp.headers["Memento-Datetime"]  # the original resource is not itself a memento
    return resp


@router.get("/tg/{doc_id}")
def timegate(doc_id: str, request: Request):
    run_id, pinned_at = run_pin(request)
    all_versions = db.source_versions_all(doc_id)
    if not all_versions:
        return JSONResponse({"type": "about:blank", "title": "Not Found", "status": 404, "detail": f"no source {doc_id}"},
                            status_code=404, media_type="application/problem+json")
    raw = request.headers.get("Accept-Datetime")
    requested: datetime | None
    if raw:
        requested = parse_accept_datetime(raw)
        if requested is None:
            return JSONResponse({"type": "about:blank", "title": "Bad Request", "status": 400,
                                 "detail": "malformed Accept-Datetime"}, status_code=400, media_type="application/problem+json")
    elif pinned_at:
        requested = to_dt(pinned_at)  # deviation 4
    else:
        requested = None  # plain RFC: latest
    req_iso = requested.isoformat() if requested else None
    if pinned_at and requested and requested.isoformat() > pinned_at:
        resp = problem(403, "requested datetime is after the run's pin", pinned_at=pinned_at, requested=req_iso,
                       first_memento=all_versions[0]["tx_from"], instance=f"/tg/{doc_id}")
        log_read(request, run_id, pinned_at, f"/tg/{doc_id}@{req_iso}", None, 403)
        return resp
    versions = visible_versions(doc_id, pinned_at)
    if pinned_at and not versions:
        resp = problem(404, f"{doc_id} did not exist as of the pin", pinned_at=pinned_at, requested=req_iso,
                       first_memento=all_versions[0]["tx_from"], instance=f"/tg/{doc_id}")
        log_read(request, run_id, pinned_at, f"/tg/{doc_id}@{req_iso}", None, 404)
        return resp
    if requested is None:
        chosen = versions[-1]
    else:
        before = [v for v in versions if to_dt(v["tx_from"]) <= requested]
        chosen = before[-1] if before else versions[0]  # RFC: before first -> first memento (unpinned only)
        if pinned_at and not before:
            resp = problem(404, f"{doc_id} did not exist at the requested datetime", pinned_at=pinned_at, requested=req_iso,
                           first_memento=all_versions[0]["tx_from"], instance=f"/tg/{doc_id}")
            log_read(request, run_id, pinned_at, f"/tg/{doc_id}@{req_iso}", None, 404)
            return resp
    location = f"/m/{doc_id}/{ts14(chosen['tx_from'])}"
    headers = {"Location": location, "Vary": "accept-datetime", "Link": link_header(doc_id, versions)}
    if pinned_at:
        headers[config.PIN_HEADER] = http_date(pinned_at)
    return Response(status_code=302, headers=headers)


@router.get("/m/{doc_id}/{ts}")
def memento(doc_id: str, ts: str, request: Request):
    run_id, pinned_at = run_pin(request)
    all_versions = db.source_versions_all(doc_id)
    if not all_versions:
        return JSONResponse({"type": "about:blank", "title": "Not Found", "status": 404, "detail": f"no source {doc_id}"},
                            status_code=404, media_type="application/problem+json")
    when = parse_ts14(ts)
    if when is None:
        return JSONResponse({"type": "about:blank", "title": "Bad Request", "status": 400, "detail": "malformed memento datetime"},
                            status_code=400, media_type="application/problem+json")
    match = [v for v in all_versions if ts14(v["tx_from"]) == ts]
    if not match:
        return JSONResponse({"type": "about:blank", "title": "Not Found", "status": 404, "detail": "no memento at that datetime"},
                            status_code=404, media_type="application/problem+json")
    version = match[0]
    if pinned_at and db.norm_ts(version["tx_from"]) > pinned_at:
        first = all_versions[0]["tx_from"]
        status = 403 if db.norm_ts(first) <= pinned_at else 404  # deviation 2 vs 3
        detail = (f"this version was published {http_date(version['tx_from'])}; decision time was {http_date(pinned_at)}"
                  if status == 403 else f"{doc_id} did not exist as of the pin")
        resp = problem(status, detail, pinned_at=pinned_at, requested=when.isoformat(), first_memento=first,
                       memento=version["tx_from"], instance=f"/m/{doc_id}/{ts}")
        log_read(request, run_id, pinned_at, f"/m/{doc_id}/{ts}", version, status)
        return resp
    versions = visible_versions(doc_id, pinned_at)
    resp = memento_response(doc_id, version, versions)
    if pinned_at:
        resp.headers[config.PIN_HEADER] = http_date(pinned_at)
    log_read(request, run_id, pinned_at, f"/m/{doc_id}/{ts}", version, 200)
    return resp


@router.get("/tm/{doc_id}")
def timemap(doc_id: str, request: Request):
    run_id, pinned_at = run_pin(request)
    all_versions = db.source_versions_all(doc_id)
    if not all_versions:
        return JSONResponse({"type": "about:blank", "title": "Not Found", "status": 404, "detail": f"no source {doc_id}"},
                            status_code=404, media_type="application/problem+json")
    versions = visible_versions(doc_id, pinned_at)
    lines = [f'</r/{doc_id}>; rel="original"',
             f'</tm/{doc_id}>; rel="self"; type="application/link-format"',
             f'</tg/{doc_id}>; rel="timegate"']
    for i, v in enumerate(versions):
        rel = "memento"
        if len(versions) == 1:
            rel = "first last memento"
        elif i == 0:
            rel = "first memento"
        elif i == len(versions) - 1:
            rel = "last memento"
        lines.append(f'</m/{doc_id}/{ts14(v["tx_from"])}>; rel="{rel}"; datetime="{http_date(v["tx_from"])}"')
    headers = {}
    if pinned_at:
        headers[config.PIN_HEADER] = http_date(pinned_at)
    return Response(",\n".join(lines) + "\n", media_type="application/link-format", headers=headers)
