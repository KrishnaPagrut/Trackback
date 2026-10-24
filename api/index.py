"""Vercel entry point: the whole demo (API, time-pinned document service, built frontend) as one Python function in replay mode.
The working database lives in /tmp (the only writable path); it is restored from the committed snapshot on a cold start."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("TRACKBACK_LLM_MODE", "replay")
os.environ.setdefault("TRACKBACK_DB", "/tmp/trackback/trackback.sqlite")
os.environ.setdefault("TRACKBACK_WEB", str(ROOT / "web"))
os.environ.pop("ANTHROPIC_API_KEY", None)

from trackback import api as _api, config, db  # noqa: E402

_api.UNDO_DIR = Path("/tmp/trackback/undo")
if not config.DB_PATH.exists():
    db.restore_snapshot(config.SNAPSHOT_PATH)

from trackback.main import app  # noqa: E402,F401
