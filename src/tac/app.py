from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .api import admin, public
from .config import Settings, get_settings
from .jobs import JobManager
from .security import guard_request, new_csrf_token

ADMIN_STATIC_DIR = Path(__file__).parent / "admin_static"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if settings.auto_migrate:
            conn = db.connect(settings.state_db, busy_timeout_ms=settings.db_busy_timeout_ms)
            try:
                db.migrate(conn)
            finally:
                conn.close()
        yield

    app = FastAPI(title="Technical Article Curation", lifespan=lifespan)
    app.state.settings = settings
    app.state.job_manager = JobManager(settings)
    app.state.csrf_token = new_csrf_token()
    app.state.http_semaphore = asyncio.Semaphore(settings.http_max_concurrency)

    app.middleware("http")(guard_request)
    app.include_router(admin.router)
    app.include_router(public.router)
    app.mount("/admin/static", StaticFiles(directory=ADMIN_STATIC_DIR), name="admin-static")

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse("/admin")

    @app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
    def admin_page() -> str:
        html = (ADMIN_STATIC_DIR / "admin.html").read_text(encoding="utf-8")
        return html.replace("__CSRF_TOKEN__", app.state.csrf_token)

    return app


app = create_app()
