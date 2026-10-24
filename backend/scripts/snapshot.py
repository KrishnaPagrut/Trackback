"""Write or restore the canonical snapshot: data/snapshots/canonical.sqlite."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from trackback import config, db  # noqa: E402


def write():
    config.SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(str(config.DB_PATH))
    src.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    dst = sqlite3.connect(str(config.SNAPSHOT_PATH))
    src.backup(dst)
    dst.close(); src.close()
    print(f"snapshot written: {config.SNAPSHOT_PATH} ({config.SNAPSHOT_PATH.stat().st_size // 1024} KB)")


def restore():
    db.restore_snapshot(config.SNAPSHOT_PATH)
    print(f"restored canonical snapshot -> {config.DB_PATH}")


if __name__ == "__main__":
    {"write": write, "restore": restore}[sys.argv[1] if len(sys.argv) > 1 else "write"]()
