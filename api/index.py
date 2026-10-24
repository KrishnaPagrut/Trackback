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


# ------------------------------------------------------------------ cross-instance consistency
# Serverless hosts run several copies of this function, each with its own /tmp database. The browser sends the journal of every
# state-changing call it made (header x-tb-journal); a copy that is behind replays the missing calls through the app before
# answering, and a copy that holds work the browser has since undone or reset restores the snapshot first. Replays are
# deterministic: the world is rebuilt from the snapshot and the same calls in the same order.
import asyncio  # noqa: E402
import json  # noqa: E402

import httpx  # noqa: E402
from starlette.requests import Request  # noqa: E402

APPLIED: set[str] = set()
_SYNC = asyncio.Lock()   # one replay at a time per instance: concurrent page loads must not interleave half-applied worlds


async def _replay(entries: list[dict]) -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://replay", timeout=120) as c:
        for e in entries:
            try:
                await c.post(e["path"], json=e.get("body"), headers={"x-tb-replaying": "1"})
            except Exception:  # noqa: BLE001  (an already-applied correction answers 4xx; the state is what matters)
                pass
            APPLIED.add(e["id"])


@app.middleware("http")
async def journal_sync(request: Request, call_next):
    if request.headers.get("x-tb-replaying"):
        return await call_next(request)
    raw = request.headers.get("x-tb-journal")
    try:
        entries = json.loads(raw) if raw else []
    except ValueError:
        entries = []
    ids = {e.get("id") for e in entries}
    async with _SYNC:
        if APPLIED - ids:                  # this copy is ahead of the browser (reset or undo happened elsewhere): start over
            _restore()
            APPLIED.clear()
        missing = [e for e in entries if e.get("id") and e["id"] not in APPLIED]
        if missing:
            await _replay(missing)
    response = await call_next(request)
    op = request.headers.get("x-tb-op")
    if op and request.method == "POST" and response.status_code < 400:
        APPLIED.add(op)
    return response
