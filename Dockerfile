# Trackback demo image: API + Memento service + built frontend in one process, replay mode, offline.
# Build:  docker build -t trackback .
# Run:    docker run -p 8000:8000 trackback          (then open http://localhost:8000)
# No API key is needed or read: the image ships the canonical snapshot and every recorded model response.

# ---- frontend (needs Node 22 for vite 7 / rolldown)
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --silent || npm install --silent
COPY frontend/ ./
RUN npm run build --silent

# ---- backend
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    TRACKBACK_LLM_MODE=replay PORT=8000
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -q -r backend/requirements.txt
COPY backend/ backend/
COPY data/snapshots/canonical.sqlite data/snapshots/canonical.sqlite
COPY data/answer_key/ data/answer_key/
COPY data/eval/latest.json data/eval/latest_v2.json data/eval/
COPY data/public/ data/public/
COPY data/llm_cache/ data/llm_cache/
COPY --from=web /web/dist frontend/dist
COPY deploy/entrypoint.sh deploy/entrypoint.sh
RUN chmod +x deploy/entrypoint.sh && mkdir -p data/snapshots/undo
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/health')"
ENTRYPOINT ["deploy/entrypoint.sh"]
