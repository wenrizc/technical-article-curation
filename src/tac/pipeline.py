from __future__ import annotations

from collections.abc import Callable
from typing import Any

from . import db
from .config import Settings
from .discover import discover_candidates
from .evaluate import evaluate_pending
from .fetch import fetch_pending
from .publish import publish_public


def _with_conn(settings: Settings, fn: Callable[[Any], dict[str, Any] | list[str]]) -> Any:
    conn = db.connect(settings.state_db, busy_timeout_ms=settings.db_busy_timeout_ms)
    try:
        return fn(conn)
    finally:
        conn.close()


def run_migrate(settings: Settings) -> dict[str, object]:
    def _run(conn):
        applied = db.migrate(conn)
        return {"database": str(settings.state_db), "applied": applied}

    return _with_conn(settings, _run)


def run_discover(settings: Settings) -> dict[str, int]:
    def _run(conn):
        db.migrate(conn)
        return discover_candidates(settings, conn)

    return _with_conn(settings, _run)


def run_fetch(
    settings: Settings, *, limit: int | None = None, article_ids: list[int] | None = None
) -> dict[str, int]:
    def _run(conn):
        db.migrate(conn)
        return fetch_pending(settings, conn, limit=limit, article_ids=article_ids)

    return _with_conn(settings, _run)


def run_evaluate(
    settings: Settings, *, limit: int | None = None, article_ids: list[int] | None = None
) -> dict[str, int]:
    def _run(conn):
        db.migrate(conn)
        return evaluate_pending(settings, conn, limit=limit, article_ids=article_ids)

    return _with_conn(settings, _run)


def run_publish(settings: Settings) -> dict[str, int]:
    def _run(conn):
        db.migrate(conn)
        return publish_public(settings, conn)

    return _with_conn(settings, _run)


def run_all(settings: Settings, *, limit: int | None = None) -> dict[str, object]:
    def _run(conn):
        applied = db.migrate(conn)
        return {
            "migrate": {"applied": applied},
            "discover": discover_candidates(settings, conn),
            "fetch": fetch_pending(settings, conn, limit=limit),
            "evaluate": evaluate_pending(settings, conn, limit=limit),
            "publish": publish_public(settings, conn),
        }

    return _with_conn(settings, _run)
