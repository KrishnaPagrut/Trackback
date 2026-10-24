"""SQLite access, append-only helpers and as-of (bitemporal) query helpers."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any, Iterable

from .. import config

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schema.sql"
_local = threading.local()
_generation = 0  # bumped by reset_connection(all_threads=True); every thread reopens its connection on the next call


def _connect(path: Path | None = None) -> sqlite3.Connection:
    p = Path(path) if path else config.DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p), check_same_thread=False, timeout=30, isolation_level=None)  # autocommit; explicit BEGIN in db.tx()
    conn.row_factory = sqlite3.Row
    _migrate(conn)
    conn.executescript(SCHEMA_PATH.read_text())
    return conn


# Columns added in iteration 2. Existing databases (snapshots recorded earlier) get them via ALTER TABLE; new ones via CREATE TABLE.
_ADDED_COLUMNS = {
    "artifacts": ["agent_id TEXT", "node_kind TEXT", "origin TEXT", "supersedes_version INT", "content_hash TEXT", "reason TEXT", "approved_by TEXT", "metric TEXT", "fields_json TEXT"],
    "runs": ["trigger TEXT", "ping_id TEXT", "goal TEXT", "deliverables_json TEXT", "model TEXT", "prompt_version TEXT"],
}


def _migrate(conn: sqlite3.Connection) -> None:
    for table, cols in _ADDED_COLUMNS.items():
        if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is None:
            continue
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for col in cols:
            name = col.split()[0]
            if name not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col}")


def get_conn() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None or getattr(_local, "path", None) != str(config.DB_PATH) or getattr(_local, "gen", None) != _generation:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        conn = _connect()
        _local.conn = conn
        _local.path = str(config.DB_PATH)
        _local.gen = _generation
    return conn


def reset_connection(all_threads: bool = True) -> None:
    """Close this thread's connection; optionally make other threads reopen on
    their next call. Used when switching databases in builders and tests;
    live reset/undo keeps connections valid through restore_snapshot()."""
    global _generation
    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
    _local.conn = None
    if all_threads:
        _generation += 1


def restore_snapshot(snapshot: Path) -> None:
    """Restore through SQLite so open readers keep a valid database and WAL.

    Unlinking a live database leaves worker connections on the old inode and
    lets them reuse the new database's journal files. SQLite's backup API
    replaces the contents under its own locks without replacing the file.
    """
    snapshot = Path(snapshot).resolve()
    if snapshot == config.DB_PATH.resolve():
        raise ValueError("snapshot and live database must be different files")
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(snapshot.as_uri() + "?mode=ro", uri=True)) as source:
        with closing(sqlite3.connect(str(config.DB_PATH), timeout=30)) as target:
            source.backup(target)


@contextmanager
def tx():
    conn = get_conn()
    try:
        conn.execute("BEGIN")
        yield conn
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def commit() -> None:
    """Autocommit mode: statements commit themselves. Inside an explicit transaction (db.tx / dry runs) this is a no-op."""
    conn = get_conn()
    if not conn.in_transaction:
        conn.commit()


def q(sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    return list(get_conn().execute(sql, tuple(params)).fetchall())


def q1(sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
    return get_conn().execute(sql, tuple(params)).fetchone()


def insert(table: str, row: dict[str, Any]) -> None:
    cols = ",".join(row.keys())
    ph = ",".join("?" for _ in row)
    get_conn().execute(f"INSERT INTO {table}({cols}) VALUES({ph})", tuple(row.values()))


def close_tx(table: str, key_col: str, key: str, at: str, extra_where: str = "", extra_params: tuple = ()) -> None:
    """The one allowed update: close a current row's transaction-time interval."""
    get_conn().execute(
        f"UPDATE {table} SET tx_to=? WHERE {key_col}=? AND tx_to=? {extra_where}",
        (at, key, config.TX_CURRENT, *extra_params),
    )


def hid(*parts: Any, n: int = 12) -> str:
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return h[:n]


def lot_code(artifact_id: str, version: int | str) -> str:
    return hashlib.sha256(f"{artifact_id}#{version}".encode()).hexdigest()[:4].upper()


def dumps(o: Any) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), default=str)


# ---- as-of helpers -----------------------------------------------------------

def norm_ts(ts: str) -> str:
    """Normalise ISO timestamps to a sortable UTC string (YYYY-MM-DDTHH:MM:SS+00:00)."""
    from datetime import datetime, timezone
    if ts == config.TX_CURRENT:
        return ts
    s = ts.strip().replace("Z", "+00:00")
    if len(s) == 10:
        s += "T00:00:00-07:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def source_version_as_of(source_id: str, at: str) -> sqlite3.Row | None:
    """Latest version of a source whose tx_from <= at (transaction-time axis)."""
    at = norm_ts(at)
    return q1(
        "SELECT * FROM source_versions WHERE source_id=? AND tx_from<=? ORDER BY tx_from DESC LIMIT 1",
        (source_id, at),
    )


def source_versions_all(source_id: str) -> list[sqlite3.Row]:
    return q("SELECT * FROM source_versions WHERE source_id=? ORDER BY tx_from ASC", (source_id,))


def claim_version_as_of(claim_id: str, at: str) -> sqlite3.Row | None:
    at = norm_ts(at)
    return q1(
        "SELECT * FROM claim_versions WHERE claim_id=? AND tx_from<=? ORDER BY tx_from DESC LIMIT 1",
        (claim_id, at),
    )


def claim_version_current(claim_id: str) -> sqlite3.Row | None:
    return q1(
        "SELECT * FROM claim_versions WHERE claim_id=? AND tx_to=? ORDER BY tx_from DESC LIMIT 1",
        (claim_id, config.TX_CURRENT),
    )


def artifact_current(artifact_id: str) -> sqlite3.Row | None:
    return q1("SELECT * FROM artifacts WHERE artifact_id=? ORDER BY version DESC LIMIT 1", (artifact_id,))


def artifacts_as_of(at: str) -> list[sqlite3.Row]:
    at = norm_ts(at)
    return q("SELECT * FROM artifacts WHERE tx_from<=? AND tx_to>? ORDER BY tx_from", (at, at))


def log_event(kind: str, summary: str, actor: str = "trackback", detail: Any = None,
              ts: str | None = None, correction_id: str | None = None, run_id: str | None = None) -> None:
    insert("events", {
        "ts": ts or config.DEMO_NOW, "kind": kind, "actor": actor, "summary": summary,
        "detail_json": dumps(detail) if detail is not None else None,
        "correction_id": correction_id, "run_id": run_id,
    })
