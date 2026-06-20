from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable

import typer

from . import db
from .config import Settings, get_settings
from .discover import discover_candidates
from .evaluate import evaluate_pending
from .fetch import fetch_pending
from .publish import publish_public

app = typer.Typer(no_args_is_help=True)
report_app = typer.Typer(no_args_is_help=True)
app.add_typer(report_app, name="report")


def _conn() -> tuple[Settings, sqlite3.Connection]:
    settings = get_settings()
    return settings, db.connect(settings.state_db)


def _echo(result: dict) -> None:
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


def _rows(rows: Iterable[sqlite3.Row]) -> list[dict[str, object]]:
    return [dict(row) for row in rows]


@app.command()
def migrate() -> None:
    """Apply SQLite migrations."""
    settings, conn = _conn()
    with conn:
        applied = db.migrate(conn)
        versions = db.latest_schema_versions(conn)
    _echo({"database": str(settings.state_db), "applied": applied, "versions": versions})


@app.command()
def discover() -> None:
    """Discover candidate articles from RSS/Atom feeds and manual URLs."""
    settings, conn = _conn()
    db.migrate(conn)
    result = discover_candidates(settings, conn)
    _echo(result)


@app.command()
def fetch(
    limit: int | None = typer.Option(None, help="Maximum number of articles to fetch."),
) -> None:
    """Fetch and clean candidate article Markdown."""
    settings, conn = _conn()
    db.migrate(conn)
    result = fetch_pending(settings, conn, limit=limit)
    _echo(result)


@app.command()
def evaluate(
    limit: int | None = typer.Option(None, help="Maximum number of articles to evaluate."),
) -> None:
    """Evaluate fetched articles with a strict Pydantic schema."""
    settings, conn = _conn()
    db.migrate(conn)
    result = evaluate_pending(settings, conn, limit=limit)
    _echo(result)


@app.command()
def publish() -> None:
    """Publish accepted articles to public/ JSON and Markdown files."""
    settings, conn = _conn()
    db.migrate(conn)
    result = publish_public(settings, conn)
    _echo(result)


@report_app.command("sources")
def report_sources() -> None:
    """Report latest RSS source check states."""
    _, conn = _conn()
    db.migrate(conn)
    _echo({"sources": _rows(db.source_state_report(conn))})


@report_app.command("failures")
def report_failures() -> None:
    """Report latest fetch and evaluation failures."""
    _, conn = _conn()
    db.migrate(conn)
    _echo({"failures": _rows(db.failure_report(conn))})


@app.command()
def run(
    limit: int | None = typer.Option(
        None, help="Maximum number of articles to fetch/evaluate in this run."
    ),
) -> None:
    """Run migrate, discover, fetch, evaluate, and publish."""
    settings, conn = _conn()
    applied = db.migrate(conn)
    result = {
        "migrate": {"applied": applied},
        "discover": discover_candidates(settings, conn),
        "fetch": fetch_pending(settings, conn, limit=limit),
        "evaluate": evaluate_pending(settings, conn, limit=limit),
        "publish": publish_public(settings, conn),
    }
    _echo(result)


if __name__ == "__main__":
    app()
