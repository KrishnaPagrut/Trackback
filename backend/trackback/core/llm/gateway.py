"""LLM gateway: record | replay | scripted. Replay and the cache are the same mechanism.

cache_key = sha256(model, system, messages, tools, params, pinned_at, corpus_snapshot_id).
Record: live call, write cache. Replay: cache only, loud failure on a miss. Scripted: deterministic in-process
provider (no network) that drives the same tools; its responses are cached too so replay works identically.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Callable

from ... import config
from .. import db


class CacheMiss(RuntimeError):
    pass


def corpus_snapshot_id(pinned_at: str) -> str:
    """The corpus as of the pin: a hash of the version ids visible at that time (later versions never change it)."""
    ids = [r["version_id"] for r in db.q("SELECT version_id FROM source_versions WHERE tx_from<=? ORDER BY version_id", (db.norm_ts(pinned_at),))]
    return hashlib.sha256("|".join(ids).encode()).hexdigest()[:16]


def cache_key(model: str, system: str, messages: list, tools: list | None, params: dict, pinned_at: str) -> str:
    payload = db.dumps({"model": model, "system": system, "messages": messages, "tools": tools or [], "params": params,
                        "pinned_at": pinned_at, "corpus": corpus_snapshot_id(pinned_at)})
    return hashlib.sha256(payload.encode()).hexdigest()


def mode() -> str:
    return os.environ.get("TRACKBACK_LLM_MODE", config.LLM_MODE)


def _lookup(key: str) -> dict | None:
    row = db.q1("SELECT response_json, model FROM llm_cache WHERE cache_key=?", (key,))
    if row is None:
        return None
    if mode() == "record" and (row["model"].startswith("scripted:") or row["model"].startswith("fallback:")):
        return None  # record mode never reuses a stand-in response; it re-records with the real model
    return json.loads(row["response_json"])


def _store(key: str, request: dict, response: dict, model: str) -> None:
    existing = db.q1("SELECT model FROM llm_cache WHERE cache_key=?", (key,))
    if existing is not None:
        if existing["model"].startswith(("scripted:", "fallback:")) and not model.startswith(("scripted:", "fallback:")):
            db.get_conn().execute("UPDATE llm_cache SET request_json=?, response_json=?, model=?, ts=? WHERE cache_key=?", (db.dumps(request), db.dumps(response), model, config.DEMO_NOW, key))
            db.commit()
        return
    db.insert("llm_cache", {"cache_key": key, "request_json": db.dumps(request), "response_json": db.dumps(response), "model": model, "ts": config.DEMO_NOW})
    db.commit()


def complete(*, model: str, system: str, messages: list, tools: list | None, params: dict | None, pinned_at: str,
             scripted: Callable[[dict], dict] | None = None, purpose: str = "agent", allow_fallback: bool = False) -> tuple[dict, str, bool]:
    """Return (response_dict, cache_key, hit). response_dict mirrors the Messages API shape (content blocks, stop_reason).
    allow_fallback: in replay mode, a miss uses the deterministic `scripted` provider instead of failing (judge and prose for
    a judge's own live edit); agent runs never fall back, so replay fidelity stays honest."""
    params = params or {}
    key = cache_key(model, system, messages, tools, params, pinned_at)
    cached = _lookup(key)
    if cached is not None:
        return cached, key, True
    m = mode()
    request = {"model": model, "system": system, "messages": messages, "tools": tools, "params": params, "pinned_at": pinned_at, "purpose": purpose}
    if m == "replay":
        if allow_fallback and scripted is not None:
            response = scripted(request)
            response["model"] = f"fallback:heuristic ({model} not available offline)"
            _store(key, {**request, "fallback": True}, response, f"fallback:{model}")
            return response, key, False
        raise CacheMiss(f"replay mode: no cached response for {purpose} ({key[:12]})")
    if m == "record":
        from . import anthropic_provider
        response = anthropic_provider.call(model=model, system=system, messages=messages, tools=tools, params=params)
        _store(key, request, response, model)
        return response, key, False
    if m == "scripted":
        if scripted is None:
            raise CacheMiss(f"scripted mode: no script for {purpose}")
        response = scripted(request)
        _store(key, request, response, f"scripted:{model}")
        return response, key, False
    raise ValueError(f"unknown TRACKBACK_LLM_MODE {m}")


def export_cache(path=None) -> int:
    path = path or config.LLM_CACHE_EXPORT
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = db.q("SELECT * FROM llm_cache ORDER BY ts")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(db.dumps(dict(r)) + "\n")
    return len(rows)


def import_cache(path=None, *, real_only: bool = True) -> int:
    """Seed the cache from a jsonl export (data/llm_cache/cache.jsonl). Real-model rows only by default, so a fresh world
    (make world) re-uses every recorded response whose key still matches and record mode only pays for new turns."""
    path = path or config.LLM_CACHE_EXPORT
    if not path.exists():
        return 0
    n = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if real_only and str(r.get("model", "")).startswith(("scripted:", "fallback:")):
                continue
            if db.q1("SELECT 1 FROM llm_cache WHERE cache_key=?", (r["cache_key"],)) is None:
                db.insert("llm_cache", {"cache_key": r["cache_key"], "request_json": r["request_json"], "response_json": r["response_json"], "model": r["model"], "ts": r["ts"]})
                n += 1
    return n


def merge_export(extra_db_paths: list, path=None) -> int:
    """Merge real-model rows from other databases into the jsonl export (keeps paid responses across rebuilds)."""
    import sqlite3
    path = path or config.LLM_CACHE_EXPORT
    rows: dict[str, dict] = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line); rows[r["cache_key"]] = r
    for p in extra_db_paths:
        c = sqlite3.connect(str(p)); c.row_factory = sqlite3.Row
        for r in c.execute("SELECT * FROM llm_cache"):
            r = dict(r)
            if str(r["model"]).startswith(("scripted:", "fallback:")):
                continue
            rows.setdefault(r["cache_key"], r)
        c.close()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in sorted(rows.values(), key=lambda r: (r["ts"], r["cache_key"])):
            f.write(json.dumps(r, sort_keys=True) + "\n")
    return len(rows)

