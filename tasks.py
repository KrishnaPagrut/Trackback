"""Cross-platform task runner (Windows and macOS): python tasks.py <target>. The Makefile wraps the same targets.

setup    venv (Python 3.11) + backend deps + frontend deps, copies .env.example to .env
world    generate Tidewall and Lyft, run the agents through history, write the canonical snapshot
test     pytest
eval     scorecard over every case, both worlds -> data/eval/latest.json (replay mode)
check    offline demo check: replay forced, outside networking refused, every Stage beat
web      build the frontend into web/ (committed, so demo needs no npm)
demo     restore the snapshot and serve http://localhost:8000 in replay mode
reset    restore the canonical snapshot
serve    dev server with reload
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
VENV = BACKEND / ".venv"
PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
DEPS = ["-r", str(BACKEND / "requirements.txt"), "pytest", "playwright"]


def run(cmd: list[str], env: dict | None = None, cwd: Path = ROOT) -> None:
    e = {**os.environ, "PYTHONPATH": str(BACKEND), "PYTHONUTF8": "1", **(env or {})}
    print("+", " ".join(str(c) for c in cmd), flush=True)
    r = subprocess.run([str(c) for c in cmd], env=e, cwd=str(cwd))
    if r.returncode:
        sys.exit(r.returncode)


def npm() -> str:
    return shutil.which("npm.cmd" if os.name == "nt" else "npm") or "npm"


def world_mode() -> str:
    m = os.environ.get("TRACKBACK_LLM_MODE", "")
    return m if m in ("record", "scripted") else "scripted"   # building a world needs a writer; replay only reads


def main(target: str) -> None:
    if target == "setup":
        if not PY.exists():
            base = ["py", "-3.11"] if os.name == "nt" else [shutil.which("python3.11") or "python3"]
            run([*base, "-m", "venv", str(VENV)])
        run([PY, "-m", "pip", "install", "-q", "--upgrade", "pip"])
        run([PY, "-m", "pip", "install", "-q", *DEPS])
        run([npm(), "install", "--silent"], cwd=ROOT / "frontend")
        if not (ROOT / ".env").exists():
            shutil.copy(ROOT / ".env.example", ROOT / ".env")
        print("setup ok")
    elif target == "world":
        run([PY, "-m", "trackback.cli", "world"], env={"TRACKBACK_LLM_MODE": world_mode()})
    elif target == "test":
        run([PY, "-m", "pytest", "-q"], cwd=BACKEND)
    elif target == "eval":
        run([PY, "-m", "trackback.cli", "eval"], env={"TRACKBACK_LLM_MODE": "replay"})
    elif target == "check":
        run([PY, "-m", "trackback.cli", "check"], env={"TRACKBACK_LLM_MODE": "replay"})
    elif target == "web":
        run([npm(), "run", "build", "--silent"], cwd=ROOT / "frontend")
    elif target == "demo":
        run([PY, "-m", "trackback.cli", "reset"])
        run([PY, "-m", "uvicorn", "trackback.main:app", "--app-dir", "backend", "--host", "127.0.0.1", "--port", "8000"], env={"TRACKBACK_LLM_MODE": "replay"})
    elif target == "reset":
        run([PY, "-m", "trackback.cli", "reset"])
    elif target == "serve":
        run([PY, "-m", "uvicorn", "trackback.main:app", "--app-dir", "backend", "--host", "127.0.0.1", "--port", "8000", "--reload"])
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "help")
