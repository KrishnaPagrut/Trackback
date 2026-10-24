"""Trackback CLI: python -m trackback.cli <world|reset|review|eval|check|snapshot>."""
from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

from . import config as C
from .core import db

BUILD_DB = C.DATA_DIR / "build" / "world.sqlite"


def _use_db(path: Path) -> None:
    C.DB_PATH = path
    os.environ["TRACKBACK_DB"] = str(path)
    db.reset_connection()


def world() -> None:
    """Generate both worlds, run history (agents' past work), run the review, write the canonical snapshot."""
    t0 = time.time()
    from .world import build as WB
    BUILD_DB.parent.mkdir(parents=True, exist_ok=True)
    for p in (BUILD_DB, Path(str(BUILD_DB) + "-wal"), Path(str(BUILD_DB) + "-shm")):
        if p.exists():
            p.unlink()
    _use_db(BUILD_DB)
    gen = WB.generate()
    WB.load(gen)
    from .core.llm import gateway
    n = gateway.import_cache()
    print(f"loaded ledger and sources; {n} recorded model responses seeded from {C.LLM_CACHE_EXPORT.name}")
    import importlib.util
    if importlib.util.find_spec("trackback.world.history"):
        from .world import history
        history.run_all()
    if importlib.util.find_spec("trackback.review"):
        from . import review
        review.run_all()
    snapshot_write()
    print(f"world built in {time.time() - t0:.1f}s")


def snapshot_write() -> None:
    import sqlite3
    conn = db.get_conn()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    C.SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = C.SNAPSHOT_PATH.with_suffix(".tmp")
    if tmp.exists():
        tmp.unlink()
    src = sqlite3.connect(str(C.DB_PATH)); dst = sqlite3.connect(str(tmp))
    src.backup(dst); dst.close(); src.close()
    if C.SNAPSHOT_PATH.exists():
        C.SNAPSHOT_PATH.unlink()
    tmp.rename(C.SNAPSHOT_PATH)
    try:
        from .core.llm import gateway
        gateway.merge_export([C.DB_PATH])
    except Exception as e:  # pragma: no cover
        print("cache export skipped:", e)
    print(f"snapshot written: {C.SNAPSHOT_PATH} ({C.SNAPSHOT_PATH.stat().st_size / 1e6:.1f} MB)")


def reset() -> None:
    if not C.SNAPSHOT_PATH.exists():
        sys.exit("no canonical snapshot: run `python tasks.py world` first")
    db.restore_snapshot(C.SNAPSHOT_PATH)
    undo = C.DATA_DIR / "snapshots" / "undo"
    if undo.exists():
        shutil.rmtree(undo)
    print(f"restored {C.SNAPSHOT_PATH.name} -> {C.DB_PATH}")


def main(argv: list[str]) -> None:
    cmd = argv[0] if argv else "help"
    if cmd == "world":
        world()
    elif cmd == "reset":
        reset()
    elif cmd == "snapshot":
        snapshot_write()
    elif cmd == "review":
        from . import review
        review.run_all()
    elif cmd == "eval":
        from .eval import scorecard
        scorecard.main()
    elif cmd == "check":
        from . import check
        check.main()
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
