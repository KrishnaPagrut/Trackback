import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture()
def fresh_db(tmp_path, monkeypatch):
    from trackback import config, db
    p = tmp_path / "t.sqlite"
    monkeypatch.setattr(config, "DB_PATH", p)
    db.reset_connection()
    yield db.get_conn()
    db.reset_connection()


@pytest.fixture(scope="session")
def tw(tmp_path_factory):
    """The v3 Tidewall world, generated once per test session into its own database."""
    import time
    from trackback import config
    from trackback.core import db
    from trackback.world import build as WB
    p = tmp_path_factory.mktemp("v3") / "world.sqlite"
    old = config.DB_PATH
    config.DB_PATH = p
    db.reset_connection()
    t0 = time.time()
    gen = WB.generate()
    WB.load(gen)
    gen["seconds"] = time.time() - t0
    gen["entries"] = WB.load_entries()
    yield gen
    config.DB_PATH = old
    db.reset_connection()


@pytest.fixture(scope="module")
def canon(tmp_path_factory):
    """The canonical state (world + the agents' history + the review run, as shipped in the snapshot), in its own database."""
    from trackback import config, review
    from trackback.core import db
    from trackback.world import build as WB, history
    p = tmp_path_factory.mktemp("canon") / "canon.sqlite"
    old = config.DB_PATH
    config.DB_PATH = p
    db.reset_connection()
    gen = WB.generate()
    WB.load(gen)
    history.run_all()
    out = review.run_all()
    from trackback.world import lyft
    out["lyft"] = lyft.build_all()
    out["key"] = gen["key"]
    yield out
    config.DB_PATH = old
    db.reset_connection()
