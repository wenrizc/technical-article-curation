from __future__ import annotations

from collections.abc import Callable
from typing import Any

from tac.application.tag_cache import TagVocabularyCache
from tac.application.use_cases.discover_articles import discover_candidates
from tac.application.use_cases.evaluate_articles import evaluate_pending
from tac.application.use_cases.fetch_articles import fetch_pending
from tac.application.use_cases.publish_articles import publish_public
from tac.infrastructure.db import store as db
from tac.settings import Settings


def _with_conn(settings: Settings, fn: Callable[[Any], dict[str, Any] | list[str]]) -> Any:
    conn = db.connect(settings.state_db, busy_timeout_ms=settings.db_busy_timeout_ms)
    try:
        return fn(conn)
    finally:
        conn.close()


def run_discover(
    settings: Settings, *, since: str | None = None, until: str | None = None
) -> dict[str, int]:
    def _run(conn):
        db.migrate(conn, migrations_dir=settings.migrations_dir)
        return discover_candidates(settings, conn, since=since, until=until)

    return _with_conn(settings, _run)


def run_fetch(
    settings: Settings, *, limit: int | None = None, article_ids: list[int] | None = None
) -> dict[str, int]:
    def _run(conn):
        db.migrate(conn, migrations_dir=settings.migrations_dir)
        return fetch_pending(settings, conn, limit=limit, article_ids=article_ids)

    return _with_conn(settings, _run)


def run_evaluate(
    settings: Settings,
    *,
    limit: int | None = None,
    article_ids: list[int] | None = None,
    tag_cache: TagVocabularyCache | None = None,
) -> dict[str, int]:
    def _run(conn):
        db.migrate(conn, migrations_dir=settings.migrations_dir)
        return evaluate_pending(
            settings,
            conn,
            limit=limit,
            article_ids=article_ids,
            tag_cache=tag_cache,
        )

    return _with_conn(settings, _run)


def run_publish(settings: Settings) -> dict[str, int]:
    def _run(conn):
        db.migrate(conn, migrations_dir=settings.migrations_dir)
        return publish_public(settings, conn)

    return _with_conn(settings, _run)


def run_all(
    settings: Settings,
    *,
    limit: int | None = None,
    since: str | None = None,
    until: str | None = None,
    tag_cache: TagVocabularyCache | None = None,
) -> dict[str, object]:
    def _run(conn):
        applied = db.migrate(conn, migrations_dir=settings.migrations_dir)
        return {
            "migrate": {"applied": applied},
            "discover": discover_candidates(settings, conn, since=since, until=until),
            "fetch": fetch_pending(settings, conn, limit=limit),
            "evaluate": evaluate_pending(settings, conn, limit=limit, tag_cache=tag_cache),
            "publish": publish_public(settings, conn),
        }

    return _with_conn(settings, _run)
