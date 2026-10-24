"""One process for the demo: API + Memento + built frontend on http://localhost:8000."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config, db, memento


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.get_conn()
    yield


app = FastAPI(title="Trackback", version="0.1.0", lifespan=lifespan)
app.include_router(memento.router)

try:  # api is imported lazily so M1 tests run before the API exists
    from . import api, api_pings  # noqa: E402
    app.include_router(api.router, prefix="/api")
    app.include_router(api_pings.router)
except ImportError:  # pragma: no cover
    pass


if config.FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=config.FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        candidate = config.FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(config.FRONTEND_DIST / "index.html", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
