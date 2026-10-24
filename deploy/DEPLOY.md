# Deploying Trackback

The demo is one container: FastAPI + the Memento service + the built frontend, serving the canonical snapshot in replay mode. It needs no API key, no network egress and no database service. Everything a judge can click (drop E11, Scenario B, approvals, undo, reset, the Lyft tab) runs against the SQLite working copy inside the container; `R` or `make reset` restores the snapshot.

## What the image contains

- `backend/` (the app), `data/snapshots/canonical.sqlite` (the world, ~12 MB), `data/answer_key/`, `data/eval/latest*.json` (proof page), `data/public/` (the Lyft exhibit), `data/llm_cache/` (recorded model responses), `frontend/dist` (built in a Node 22 stage).
- Not in the image: `.env`, the dev venv, screenshots, the iteration-1 record snapshot.

## Local check (needs Docker)

```bash
docker build -t trackback .
docker run --rm -p 8000:8000 trackback
# open http://localhost:8000 ; curl http://localhost:8000/api/health
```

`make docker-build` and `make docker-run` do the same.

## Fly.io (recommended: one command, free tier is enough)

```bash
brew install flyctl && fly auth login
fly launch --no-deploy        # accept the Dockerfile; app name of your choice; region sjc; no Postgres, no Redis
fly deploy
fly open
```

`fly.toml` in the repo root sets the internal port (8000), forces HTTPS, keeps one machine running, and points the health check at `/api/health`. If `fly launch` offers to overwrite `fly.toml`, keep ours.

## Render (alternative, also free tier)

New Web Service → connect the GitHub repo → Runtime: Docker → leave the start command empty (the Dockerfile's entrypoint is used) → Health check path `/api/health` → Create. Render sets `PORT`; the entrypoint reads it.

## Any VM with Docker (Railway, a DigitalOcean droplet, a laptop on the venue Wi-Fi)

```bash
git clone <repo> && cd trackback && docker build -t trackback . && docker run -d --restart unless-stopped -p 80:8000 trackback
```

## Things to know

- **One world per instance.** Every visitor shares the same working database. A judge who drops E11 changes what the next judge sees. For a public link that is fine for a hackathon (press `R`); for several judges at once, run one instance per table or ask them to reset first. A per-session copy is the next step if you need it.
- **Replay is forced.** The container sets `TRACKBACK_LLM_MODE=replay` and ignores any key. To refresh the world with a real-model run, do it on your laptop (`TRACKBACK_LLM_MODE=record make world && make eval`), commit the new snapshot and eval files, and redeploy.
- **The snapshot is in git.** `data/snapshots/canonical.sqlite` is tracked on purpose: the image builds from the repo alone. Keep it under ~50 MB.
- **Offline at the venue.** The same image runs on a laptop with Wi-Fi off; `make demo` without Docker does too.
- **Updating.** `git push` then `fly deploy` (or Render auto-deploys on push). The build takes about two minutes (Node stage plus Python stage).
