"""Restoring a demo must keep existing readers attached to the live database."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier

import pytest

from trackback import api, config
from trackback.core import db


@pytest.fixture()
def saved_world(tmp_path, monkeypatch, fresh_db):
    snapshot = tmp_path / "canonical.sqlite"
    undo_dir = tmp_path / "undo"
    monkeypatch.setattr(config, "SNAPSHOT_PATH", snapshot)
    monkeypatch.setattr(api, "UNDO_DIR", undo_dir)
    db.insert("sources", {"source_id": "baseline", "title": "Baseline"})
    with closing(sqlite3.connect(snapshot)) as target:
        fresh_db.backup(target)
    db.insert("sources", {"source_id": "later", "title": "Later change"})
    return snapshot, undo_dir


@pytest.mark.parametrize("operation", ["reset", "undo"])
def test_restore_updates_an_already_open_reader(saved_world, operation):
    snapshot, undo_dir = saved_world
    if operation == "undo":
        undo_dir.mkdir()
        with closing(sqlite3.connect(snapshot)) as source:
            with closing(sqlite3.connect(undo_dir / "undo_000.sqlite")) as target:
                source.backup(target)
    with closing(sqlite3.connect(config.DB_PATH)) as reader:
        assert reader.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 2
        getattr(api, operation)()
        assert reader.execute("SELECT source_id FROM sources").fetchall() == [("baseline",)]
        assert reader.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_reset_during_parallel_reads(saved_world):
    api.reset()
    ready = Barrier(5)

    def read_repeatedly():
        try:
            db.get_conn()
            ready.wait(timeout=10)
            for _ in range(100):
                assert db.q1("SELECT COUNT(*) n FROM sources")["n"] == 1
        finally:
            db.reset_connection(all_threads=False)

    with ThreadPoolExecutor(max_workers=4) as pool:
        readers = [pool.submit(read_repeatedly) for _ in range(4)]
        ready.wait(timeout=10)
        for _ in range(20):
            api.reset()
        for reader in readers:
            reader.result(timeout=30)
    assert db.q1("PRAGMA integrity_check")[0] == "ok"
