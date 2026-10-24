PY=backend/.venv/bin/python
# Use the same Node runtime for npm and the frontend tools it launches.
NODE_BIN := $(shell ls -d $$HOME/.nvm/versions/node/v22*/bin 2>/dev/null | tail -1)
ifneq ($(NODE_BIN),)
export PATH := $(NODE_BIN):$(PATH)
endif
NPM=npm
PIP=backend/.venv/bin/pip
export PYTHONPATH=backend

.PHONY: setup world test eval eval-v2 demo docker-build docker-run reset serve build-frontend history generate snapshot check

setup:
	test -d backend/.venv || /usr/local/bin/python3.11 -m venv backend/.venv || python3 -m venv backend/.venv
	$(PIP) install -q --upgrade pip
	$(PIP) install -q fastapi 'uvicorn[standard]' anthropic pyyaml pytest httpx pydantic python-dotenv
	cd frontend && $(NPM) install --silent
	test -f .env || cp .env.example .env
	@echo "setup ok"

generate:
	$(PY) backend/scripts/generate_tidewall.py

# building a world needs a writer: record (real model, needs a key) or scripted (deterministic stand-in). Replay only reads,
# so a plain `make world` builds scripted and reuses every recorded response in data/llm_cache/cache.jsonl.
WORLD_MODE = $(if $(filter record scripted,$(TRACKBACK_LLM_MODE)),$(TRACKBACK_LLM_MODE),scripted)

history:
	TRACKBACK_LLM_MODE=$(WORLD_MODE) $(PY) backend/scripts/build_history.py

world: generate history snapshot
	@echo "world built"

snapshot:
	$(PY) backend/scripts/snapshot.py write

test:
	cd backend && .venv/bin/python -m pytest -q

eval:
	TRACKBACK_LLM_MODE=replay $(PY) backend/scripts/eval.py
	TRACKBACK_LLM_MODE=replay $(PY) backend/scripts/eval_v2.py
	TRACKBACK_LLM_MODE=replay $(PY) backend/scripts/eval_learning.py

eval-v2:
	$(PY) backend/scripts/eval_v2.py

build-frontend:
	cd frontend && $(NPM) run build --silent
	rm -rf web && cp -R frontend/dist web

demo: build-frontend
	$(PY) backend/scripts/snapshot.py restore
	TRACKBACK_LLM_MODE=replay $(PY) -m uvicorn trackback.main:app --app-dir backend --host 127.0.0.1 --port 8000

serve:
	$(PY) -m uvicorn trackback.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload

reset:
	$(PY) backend/scripts/snapshot.py restore

check:
	bash backend/scripts/demo_check.sh

docker-build:
	docker build -t trackback .

docker-run:
	docker run --rm -p 8000:8000 trackback
