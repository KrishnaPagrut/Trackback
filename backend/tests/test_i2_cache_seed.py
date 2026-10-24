"""The cache seed keeps paid model responses across rebuilds: real rows are imported, scripted/fallback rows are not."""
import json

from trackback.core import db
from trackback.core.llm import gateway as g


def test_import_cache_keeps_real_rows_only(tmp_path, fresh_db):
    seed = tmp_path / "cache.jsonl"
    rows = [
        {"cache_key": "k_real", "request_json": "{}", "response_json": json.dumps({"content": []}), "model": "claude-sonnet-5-5", "ts": "2026-07-08T09:00:00-07:00"},
        {"cache_key": "k_scripted", "request_json": "{}", "response_json": json.dumps({"content": []}), "model": "scripted:claude-sonnet-5-5", "ts": "2026-07-08T09:00:00-07:00"},
        {"cache_key": "k_fallback", "request_json": "{}", "response_json": json.dumps({"content": []}), "model": "fallback:claude-opus-5-5", "ts": "2026-07-08T09:00:00-07:00"},
    ]
    seed.write_text("".join(json.dumps(r) + "\n" for r in rows))
    n = g.import_cache(seed)
    assert n == 1
    assert db.q1("SELECT 1 FROM llm_cache WHERE cache_key='k_real'") is not None
    assert db.q1("SELECT 1 FROM llm_cache WHERE cache_key='k_scripted'") is None
    assert g.import_cache(seed) == 0  # idempotent
