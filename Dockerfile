# Trackback demo image: API, Replay endpoints and the built frontend (web/, committed) in one process, replay mode, offline.
# Build:  docker build -t trackback .
# Run:    docker run -p 8000:8000 trackback          (then open http://localhost:8000)
# No API key is needed or read: the image ships the canonical snapshot and every recorded model response.
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PYTHONUTF8=1 \
    TRACKBACK_LLM_MODE=replay PORT=8000
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -q -r backend/requirements.txt
COPY backend/ backend/
COPY data/snapshots/canonical.sqlite data/snapshots/canonical.sqlite
COPY data/world/ data/world/
COPY data/public/ data/public/
COPY data/eval/latest.json data/eval/latest.json
COPY data/llm_cache/ data/llm_cache/
COPY web/ web/
COPY deploy/entrypoint.sh deploy/entrypoint.sh
RUN chmod +x deploy/entrypoint.sh && mkdir -p data/snapshots/undo data/build
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/health')"
ENTRYPOINT ["deploy/entrypoint.sh"]
