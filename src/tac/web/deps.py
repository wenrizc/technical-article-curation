from __future__ import annotations

import sqlite3
from collections.abc import Iterator

from fastapi import Request

from tac.application.jobs import JobManager
from tac.infrastructure.db import store as db
from tac.settings import Settings


def settings_from_request(request: Request) -> Settings:
    return request.app.state.settings


def job_manager_from_request(request: Request) -> JobManager:
    return request.app.state.job_manager


def db_conn(request: Request) -> Iterator[sqlite3.Connection]:
    settings = settings_from_request(request)
    conn = db.connect(settings.state_db, busy_timeout_ms=settings.db_busy_timeout_ms)
    try:
        yield conn
    finally:
        conn.close()
