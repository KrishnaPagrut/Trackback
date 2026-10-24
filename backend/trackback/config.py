"""Central configuration. Nothing in the app reads the real wall clock except logs."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

# Demo clock, pinned (Section 2, rule 14).
DEMO_NOW = "2026-07-08T09:00:00-07:00"
TZ_OFFSET = "-07:00"

# Models (Section 2, rule 6)
AGENT_MODEL = os.environ.get("TRACKBACK_AGENT_MODEL", "claude-sonnet-5-5")
JUDGE_MODEL = os.environ.get("TRACKBACK_JUDGE_MODEL", "claude-opus-5-5")
MUSE_MODEL = "muse-spark-1.1"

# LLM gateway mode: record | replay | scripted
LLM_MODE = os.environ.get("TRACKBACK_LLM_MODE", "replay")
MAX_TOOL_TURNS = 25

# Paths
DATA_DIR = ROOT / "data"
DB_PATH = Path(os.environ.get("TRACKBACK_DB", str(DATA_DIR / "trackback.sqlite")))
PUBLIC_DIR = DATA_DIR / "public"
GENERATED_DIR = DATA_DIR / "generated"
ANSWER_KEY_PATH = DATA_DIR / "answer_key" / "answer_key.yaml"
SNAPSHOT_PATH = Path(os.environ.get("TRACKBACK_SNAPSHOT", str(DATA_DIR / "snapshots" / "canonical.sqlite")))
EVAL_PATH = DATA_DIR / "eval" / "latest.json"
LLM_CACHE_EXPORT = DATA_DIR / "llm_cache" / "cache.jsonl"
FRONTEND_DIST = ROOT / "frontend" / "dist"

# Materiality memo defaults (Section 5.2). The live values come from the memo claim.
MATERIALITY_DEFAULTS = {
    "annual": 160_000.0,
    "quarterly_performance": 60_000.0,
    "clearly_trivial": 8_000.0,
    "flux_pct": 0.10,
    "flux_abs": 25_000.0,
}

# Memento profile
PIN_HEADER = "Trackback-Pinned-At"
PROBLEM_TYPE = "https://trackback.local/problems/temporal-pin-violation"
TX_CURRENT = "9999-12-31T00:00:00+00:00"

# Company
COMPANY = "Tidewall Climbing Co."
GYMS = {
    "G1": "Oakland", "G2": "San Jose", "G3": "Sacramento",
    "G4": "Fresno", "G5": "Santa Cruz", "G6": "Berkeley",
}
PEOPLE = {
    "controller": "Dana Ortiz",
    "cfo": "Sam Whitfield",
    "ap": "Priya Nair",
    "vp_sales": "Leo Brandt",
    "hr": "Mei Tanaka",
}

# Packs the core can load by name (the core never imports one directly; see core/domain.py)
PACK_MODULES = {"finance": "trackback.domains.finance"}
