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
