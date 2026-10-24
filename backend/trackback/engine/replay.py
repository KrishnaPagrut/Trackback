"""Replay: the time-pinned view of every source (the RFC 7089 Memento protocol with Trackback's pinning profile, SPEC.md 6.2).

The HTTP endpoints (/r /tg /m /tm) live in core/memento.py. This is the in-process API the engines use:
- timemap(source): every version with its captured_at (Memento-Datetime).
- timegate(source, at): the latest version captured at or before `at`; refuses (404) if the first version postdates the pin. Never the
  nearest later version, never "latest" for a pinned read.
- fetch(version_id, pin): refuses (403) a version captured after the pin, with both timestamps.
- rows(source, pin, run_id): the parsed file as of the pin; every read (refusals too) is logged in `reads`.
"""
from __future__ import annotations

import csv
import json
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .. import config as C
from ..core import db


@dataclass
class Refusal(Exception):
    status: int
    source: str
    pinned_at: str
    requested: str | None
    first_available: str | None
    detail: str

    def problem(self) -> dict:
        return {"type": C.PROBLEM_TYPE, "title": "Temporal pin violation" if self.status == 403 else "Not knowable as of the pin", "status": self.status,
                "detail": self.detail, "source": self.source, "pinned_at": self.pinned_at, "requested": self.requested, "first_available": self.first_available}


def timemap(source: str) -> list[dict]:
    return [{"version_id": r["version_id"], "captured_at": r["tx_from"], "body": json.loads(r["body"]), "content_hash": r["content_hash"]} for r in db.source_versions_all(source)]


def _log(run_id: str | None, uri: str, version: dict | None, pin: str, status: int) -> None:
    if not run_id:
        return
    db.insert("reads", {"read_id": uuid.uuid4().hex[:16], "run_id": run_id, "tool_call_id": None, "uri_m": uri, "source_version_id": version["version_id"] if version else None,
                        "memento_datetime": version["captured_at"] if version else None, "pinned_at": pin, "http_status": status, "ts": pin})


def timegate(source: str, at: str, run_id: str | None = None) -> dict:
    pin = db.norm_ts(at)
    versions = timemap(source)
    if not versions:
        raise KeyError(source)
    before = [v for v in versions if db.norm_ts(v["captured_at"]) <= pin]
    if not before:
        _log(run_id, f"/tg/{source}", None, pin, 404)
        raise Refusal(404, source, pin, pin, versions[0]["captured_at"], f"{source} did not exist as of {pin}")
    _log(run_id, f"/tg/{source}", before[-1], pin, 200)
    return before[-1]


def fetch(version_id: str, pin: str, run_id: str | None = None) -> dict:
    r = db.q1("SELECT * FROM source_versions WHERE version_id=?", (version_id,))
    if r is None:
        raise KeyError(version_id)
    v = {"version_id": r["version_id"], "captured_at": r["tx_from"], "body": json.loads(r["body"]), "content_hash": r["content_hash"], "source": r["source_id"]}
    pin = db.norm_ts(pin)
    if db.norm_ts(v["captured_at"]) > pin:
        first = db.source_versions_all(r["source_id"])[0]["tx_from"]
        status = 403 if db.norm_ts(first) <= pin else 404
        _log(run_id, f"/m/{version_id}", v, pin, status)
        raise Refusal(status, r["source_id"], pin, v["captured_at"], first, f"This version was captured {v['captured_at']}; the decision time was {pin}.")
    _log(run_id, f"/m/{version_id}", v, pin, 200)
    return v


@lru_cache(maxsize=64)
def _read_file(path: str, mtime: float) -> tuple:
    p = Path(path)
    if p.suffix == ".csv":
        with open(p, encoding="utf-8") as fh:
            return tuple(csv.DictReader(fh))
    if p.suffix == ".json":
        return (json.loads(p.read_text(encoding="utf-8")),)
    return ()


def file_path(version: dict) -> Path:
    base = C.DATA_DIR if version["body"].get("world") == "lyft" else C.FILES_DIR
    return base / version["body"]["path"]


def rows(source: str, pin: str, run_id: str | None = None) -> list[dict]:
    v = timegate(source, pin, run_id)
    p = file_path(v)
    data = _read_file(str(p), p.stat().st_mtime)
    return [dict(r) for r in data] if p.suffix == ".csv" else list(data)


def doc(source: str, pin: str, run_id: str | None = None) -> dict:
    return rows(source, pin, run_id)[0]
