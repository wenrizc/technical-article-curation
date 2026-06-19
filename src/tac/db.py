from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from .models import ArticleStatus, EvaluationResult
from .utils import normalize_title, normalize_url, source_title_slug, utc_now_iso


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate(conn: sqlite3.Connection, migrations_dir: Path = Path("migrations")) -> list[str]:
    applied: list[str] = []
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    migrations = sorted(migrations_dir.glob("*.sql"))
    for path in migrations:
        version = path.stem
        exists = conn.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?", (version,)
        ).fetchone()
        if exists:
            continue
        sql = path.read_text(encoding="utf-8")
        conn.executescript(sql)
        conn.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (version, utc_now_iso()),
        )
        applied.append(version)
    conn.commit()
    return applied


def latest_schema_versions(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
    return [row["version"] for row in rows]


def find_existing(
    conn: sqlite3.Connection, normalized_url: str, normalized_title: str
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT * FROM articles
        WHERE normalized_url = ? OR normalized_title = ?
        ORDER BY
            CASE WHEN status = 'accepted' THEN 0 ELSE 1 END,
            id ASC
        LIMIT 1
        """,
        (normalized_url, normalized_title),
    ).fetchone()


def slug_exists(conn: sqlite3.Connection, slug: str) -> bool:
    return (
        conn.execute("SELECT 1 FROM articles WHERE slug = ?", (slug,)).fetchone()
        is not None
    )


def add_candidate(
    conn: sqlite3.Connection,
    *,
    title: str,
    url: str,
    source_name: str,
    source_tags: Iterable[str] = (),
) -> tuple[int, ArticleStatus, bool]:
    normalized_url = normalize_url(url)
    normalized_title = normalize_title(title or url)
    now = utc_now_iso()
    existing = find_existing(conn, normalized_url, normalized_title)
    if existing and existing["normalized_url"] == normalized_url:
        return int(existing["id"]), ArticleStatus(existing["status"]), False

    duplicate_of = int(existing["id"]) if existing else None
    status = ArticleStatus.duplicate if duplicate_of else ArticleStatus.candidate
    slug = source_title_slug(source_name, title or url, normalized_url, exists=False)
    if slug_exists(conn, slug):
        slug = source_title_slug(source_name, title or url, normalized_url, exists=True)

    cur = conn.execute(
        """
        INSERT INTO articles(
            source_name, title, url, normalized_url, normalized_title, slug,
            status, retry_count, duplicate_of, created_at, updated_at, source_tags
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
        """,
        (
            source_name,
            title or url,
            url,
            normalized_url,
            normalized_title,
            slug,
            status.value,
            duplicate_of,
            now,
            now,
            json.dumps(list(source_tags), ensure_ascii=False),
        ),
    )
    conn.commit()
    return int(cur.lastrowid), status, True


def articles_ready_for_fetch(conn: sqlite3.Connection, max_retry: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT * FROM articles
        WHERE status IN ('candidate', 'failed')
          AND retry_count < ?
          AND NOT EXISTS (
              SELECT 1 FROM fetches
              WHERE fetches.article_id = articles.id
                AND fetches.status = 'success'
          )
        ORDER BY id ASC
        """,
        (max_retry,),
    ).fetchall()


def latest_successful_fetch(conn: sqlite3.Connection, article_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT * FROM fetches
        WHERE article_id = ? AND status = 'success'
        ORDER BY id DESC
        LIMIT 1
        """,
        (article_id,),
    ).fetchone()


def articles_ready_for_evaluation(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT a.* FROM articles a
        WHERE a.status = 'candidate'
          AND EXISTS (
              SELECT 1 FROM fetches f
              WHERE f.article_id = a.id AND f.status = 'success'
          )
          AND NOT EXISTS (
              SELECT 1 FROM evaluations e
              WHERE e.article_id = a.id
          )
        ORDER BY a.id ASC
        """
    ).fetchall()


def record_fetch_success(
    conn: sqlite3.Connection,
    article_id: int,
    content_markdown: str,
    metadata: dict,
) -> None:
    now = utc_now_iso()
    conn.execute(
        """
        INSERT INTO fetches(article_id, fetched_at, status, content_markdown, crawler_metadata)
        VALUES (?, ?, 'success', ?, ?)
        """,
        (article_id, now, content_markdown, json.dumps(metadata, ensure_ascii=False)),
    )
    conn.execute(
        "UPDATE articles SET updated_at = ?, error = NULL WHERE id = ?",
        (now, article_id),
    )
    conn.commit()


def record_failure(conn: sqlite3.Connection, article_id: int, error: str) -> None:
    now = utc_now_iso()
    conn.execute(
        """
        INSERT INTO fetches(article_id, fetched_at, status, error)
        VALUES (?, ?, 'failed', ?)
        """,
        (article_id, now, error),
    )
    conn.execute(
        """
        UPDATE articles
        SET status = 'failed', retry_count = retry_count + 1, updated_at = ?, error = ?
        WHERE id = ?
        """,
        (now, error, article_id),
    )
    conn.commit()


def record_evaluation(
    conn: sqlite3.Connection,
    article_id: int,
    result: EvaluationResult,
    model_name: str,
    raw_json: str,
) -> None:
    now = utc_now_iso()
    conn.execute(
        """
        INSERT INTO evaluations(
            article_id, evaluated_at, decision, confidence, dimensions, summary,
            tags, recommendation_reason, full_reasoning, model_name, raw_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            article_id,
            now,
            result.decision.value,
            result.confidence.value,
            result.dimensions.model_dump_json(by_alias=True),
            result.summary,
            json.dumps(result.tags, ensure_ascii=False),
            result.recommendation_reason,
            result.full_reasoning,
            model_name,
            raw_json,
        ),
    )
    if result.decision.value == "accept" and result.confidence.value == "high":
        status = ArticleStatus.accepted.value
        collected_at = now
    elif result.decision.value == "reject":
        status = ArticleStatus.rejected.value
        collected_at = None
    else:
        status = ArticleStatus.low_confidence.value
        collected_at = None
    conn.execute(
        """
        UPDATE articles
        SET status = ?, collected_at = COALESCE(?, collected_at), updated_at = ?, error = NULL
        WHERE id = ?
        """,
        (status, collected_at, now, article_id),
    )
    conn.commit()


def accepted_articles_for_publish(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
            a.*,
            f.content_markdown,
            f.fetched_at,
            e.summary,
            e.tags,
            e.recommendation_reason,
            e.dimensions
        FROM articles a
        JOIN fetches f ON f.article_id = a.id
        JOIN evaluations e ON e.article_id = a.id
        WHERE a.status = 'accepted'
          AND f.id = (
              SELECT MAX(id) FROM fetches
              WHERE article_id = a.id AND status = 'success'
          )
          AND e.id = (
              SELECT MAX(id) FROM evaluations
              WHERE article_id = a.id
          )
        ORDER BY a.collected_at DESC, a.id DESC
        """
    ).fetchall()
