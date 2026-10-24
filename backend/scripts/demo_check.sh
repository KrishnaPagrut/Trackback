#!/usr/bin/env bash
# Airplane-mode readiness check. Forces the LLM gateway to replay and refuses every outside network connection in-process,
# then runs each demo beat against a scratch copy of the canonical snapshot (backend/scripts/demo_offline_check.py).
set -u
cd "$(dirname "$0")/../.."
export TRACKBACK_LLM_MODE=replay
fail=0
echo "== Trackback demo check (replay mode, networking off)"
[ -f data/snapshots/canonical.sqlite ] && echo "ok   canonical snapshot present" || { echo "FAIL canonical snapshot missing (make world)"; fail=1; }
[ -f frontend/dist/index.html ] && echo "ok   frontend built" || { echo "FAIL frontend not built (make build-frontend)"; fail=1; }
[ -f data/eval/latest.json ] && echo "ok   eval output present" || { echo "FAIL data/eval/latest.json missing (make eval)"; fail=1; }
if grep -rq "domains" backend/trackback/core; then echo "FAIL core mentions a pack"; fail=1; else echo "ok   core never names a pack (grep -r domains backend/trackback/core is empty)"; fi
if grep -rIlE "https?://(cdn|fonts\.googleapis|fonts\.gstatic|unpkg|jsdelivr)" frontend/dist 2>/dev/null | grep -q .; then echo "FAIL CDN reference in frontend/dist"; fail=1; else echo "ok   fonts and libraries bundled (no CDN references in dist)"; fi
n=$(backend/.venv/bin/python -c "import sqlite3;print(sqlite3.connect('data/snapshots/canonical.sqlite').execute('select count(*) from llm_cache').fetchone()[0])")
echo "ok   recorded model responses in the snapshot: $n"
PYTHONPATH=backend backend/.venv/bin/python backend/scripts/demo_offline_check.py || fail=1
[ $fail -eq 0 ] && echo "== PASS" || { echo "== FAIL"; exit 1; }
