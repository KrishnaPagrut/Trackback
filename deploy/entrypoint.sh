#!/bin/sh
# Restore the canonical snapshot into the working database, then serve. Replay mode is forced: the demo never calls the model.
set -e
cd /app
export TRACKBACK_LLM_MODE=replay
export PYTHONPATH=backend
python backend/scripts/snapshot.py restore
exec python -m uvicorn trackback.main:app --app-dir backend --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
