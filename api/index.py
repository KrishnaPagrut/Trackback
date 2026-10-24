"""Vercel entry point: the whole demo (API, time-pinned document service, built frontend) as one Python function in replay mode.
The working database lives in /tmp (the only writable path) and is restored from the committed snapshot on every cold start."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("TRACKBACK_LLM_MODE", "replay")
os.environ.setdefault("TRACKBACK_DB", "/tmp/trackback/trackback.sqlite")
os.environ.setdefault("TRACKBACK_WEB", str(ROOT / "web"))
os.environ.pop("ANTHROPIC_API_KEY", None)

# The bundle is read-only and the snapshot is a WAL-mode database, which SQLite cannot even open read-only without creating a
# sidecar file next to it. So the snapshot is copied into /tmp once per cold start and every restore (including /api/reset) reads the copy.
_SNAP_SRC = ROOT / "data" / "snapshots" / "canonical.sqlite"
_SNAP = Path("/tmp/trackback/snapshot.sqlite")
if not _SNAP_SRC.exists():
    raise RuntimeError(f"snapshot missing from the deployment: {_SNAP_SRC}")
_SNAP.parent.mkdir(parents=True, exist_ok=True)
if not _SNAP.exists() or _SNAP.stat().st_size != _SNAP_SRC.stat().st_size:
    import shutil
    shutil.copyfile(_SNAP_SRC, _SNAP)
os.environ["TRACKBACK_SNAPSHOT"] = str(_SNAP)

from trackback import config, db  # noqa: E402


def _restore() -> None:
    db.reset_connection()
    db.restore_snapshot(config.SNAPSHOT_PATH)
    db.reset_connection()


_restore()   # before any module can open the database and create an empty schema

from trackback import api as _api  # noqa: E402
from trackback.main import app  # noqa: E402,F401

_api.UNDO_DIR = Path("/tmp/trackback/undo")
if (db.q1("SELECT COUNT(*) n FROM artifacts") or {"n": 0})["n"] == 0:   # belt and braces: never serve an empty world
    _restore()
