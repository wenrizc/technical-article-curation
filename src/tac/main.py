from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from requests import RequestException, get

from .application.jobs import JobManager
from .application.scheduler import SchedulerService
from .infrastructure.db import store as db
from .settings import Settings, get_settings
from .web.routers import admin, public
from .web.security import guard_request, new_csrf_token

ADMIN_STATIC_DIR = Path(__file__).parent / "web" / "static"
logger = logging.getLogger(__name__)


def _check_rsshub(settings: Settings) -> None:
    if not settings.rsshub_startup_check:
        return
    try:
        response = get(
            settings.rsshub_instance.rstrip("/") + "/",
            timeout=(5, settings.rsshub_timeout_seconds),
        )
        response.raise_for_status()
    except RequestException as exc:
        message = f"rsshub startup check failed: {exc}"
        if settings.rsshub_strict_startup:
            raise RuntimeError(message) from exc
        logger.warning(message)


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
        _check_rsshub(settings)
        app.state.job_manager.recover_interrupted_jobs()
        scheduler = SchedulerService(settings, app.state.job_manager)
        app.state.scheduler = scheduler
        scheduler.start()
        try:
            yield
        finally:
            await scheduler.stop()

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

    @app.get("/feed.xml", include_in_schema=False)
    def root_feed(request: Request, limit: int = Query(50, ge=1, le=200)) -> Response:
        conn = db.connect(settings.state_db, busy_timeout_ms=settings.db_busy_timeout_ms)
        try:
            return public.public_feed_response(request, conn, limit=limit)
        finally:
            conn.close()

    return app


app = create_app()
