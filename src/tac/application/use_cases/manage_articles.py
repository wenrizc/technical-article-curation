from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Literal

from tac.domain.models import ArticleStatus
from tac.shared.dates import parse_datetime
from tac.shared.utils import utc_now_iso

SortField = Literal["updated_at", "created_at", "collected_at", "published_at", "retry_count"]
SortOrder = Literal["asc", "desc"]

SORT_COLUMNS: dict[str, str] = {
    "updated_at": "a.updated_at",
    "created_at": "a.created_at",
    "collected_at": "a.collected_at",
    "published_at": "a.published_at",
    "retry_count": "a.retry_count",
}

PUBLIC_TAGS_SQL = """
            COALESCE((
                SELECT json_group_array(name)
                FROM (
                    SELECT tv.name AS name
                    FROM article_tags at
                    JOIN tag_vocabulary tv ON tv.id = at.tag_id
                    WHERE at.article_id = a.id
                      AND tv.status = 'active'
                    ORDER BY tv.name COLLATE NOCASE
                )
            ), '[]')
"""


@dataclass(frozen=True)
class Page:
    items: list[dict[str, object]]
    total: int
    page: int
    page_size: int

    @property
    def has_next(self) -> bool:
        return self.page * self.page_size < self.total

    def as_dict(self) -> dict[str, object]:
        return {
            "items": self.items,
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
            "has_next": self.has_next,
        }


def _article(conn: sqlite3.Connection, article_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()


def set_article_status(
    conn: sqlite3.Connection, article_id: int, status: ArticleStatus
) -> sqlite3.Row | None:
    article = _article(conn, article_id)
    if not article:
        return None
    now = utc_now_iso()
    conn.execute(
        "UPDATE articles SET status = ?, updated_at = ? WHERE id = ?",
        (status.value, now, article_id),
    )
    conn.commit()
    return _article(conn, article_id)


def article_row_to_dict(row: sqlite3.Row) -> dict[str, object]:
    result = dict(row)
    if "source_tags" in result and isinstance(result["source_tags"], str):
        result["source_tags"] = json.loads(result["source_tags"])
    if "tags" in result and isinstance(result["tags"], str) and result["tags"]:
        result["tags"] = json.loads(result["tags"])
    if "crawler_metadata" in result and isinstance(result["crawler_metadata"], str):
        result["crawler_metadata"] = json.loads(result["crawler_metadata"] or "{}")
    if "source_content_metadata" in result and isinstance(result["source_content_metadata"], str):
        result["source_content_metadata"] = json.loads(result["source_content_metadata"] or "{}")
    return result


def _page_values(page: int, page_size: int, *, max_page_size: int = 200) -> tuple[int, int]:
    page = max(1, page)
    page_size = min(max(1, page_size), max_page_size)
    return page, page_size


def _article_filters(
    *,
    status: str | None,
    source: str | None,
    q: str | None,
    failed_only: bool,
    since: str | None = None,
    until: str | None = None,
) -> tuple[list[str], list[object]]:
    where: list[str] = []
    params: list[object] = []
    if status:
        if status == "unaccepted":
            where.append("a.status != ?")
            params.append(ArticleStatus.accepted.value)
        elif status != "all":
            where.append("a.status = ?")
            params.append(status)
    if source:
        where.append("a.source_name = ?")
        params.append(source)
    if q:
        pattern = f"%{q.strip()}%"
        where.append("(a.title LIKE ? OR a.url LIKE ? OR a.source_name LIKE ?)")
        params.extend([pattern, pattern, pattern])
    if parsed_since := parse_datetime(since):
        where.append("a.published_at >= ?")
        params.append(parsed_since)
    if parsed_until := parse_datetime(until, date_as_end=True):
        where.append("a.published_at < ?")
        params.append(parsed_until)
    if failed_only:
        where.append(
            """
            (
              (
                SELECT f.status FROM fetches f
                WHERE f.article_id = a.id
                ORDER BY f.id DESC
                LIMIT 1
              ) = 'failed'
              OR (
                NOT EXISTS (SELECT 1 FROM evaluations e WHERE e.article_id = a.id)
                AND EXISTS (SELECT 1 FROM evaluation_failures ef WHERE ef.article_id = a.id)
              )
            )
            """
        )
    return where, params


def list_admin_articles(
    conn: sqlite3.Connection,
    *,
    page: int = 1,
    page_size: int = 50,
    status: str | None = None,
    source: str | None = None,
    q: str | None = None,
    failed_only: bool = False,
    since: str | None = None,
    until: str | None = None,
    sort: str = "updated_at",
    order: str = "desc",
) -> Page:
    page, page_size = _page_values(page, page_size)
    sort_column = SORT_COLUMNS.get(sort, "a.updated_at")
    order_sql = "ASC" if order.lower() == "asc" else "DESC"
    where, params = _article_filters(
        status=status,
        source=source,
        q=q,
        failed_only=failed_only,
        since=since,
        until=until,
    )
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    total = conn.execute(
        f"SELECT COUNT(*) FROM articles a {where_sql}",
        params,
    ).fetchone()[0]
    offset = (page - 1) * page_size
    rows = conn.execute(
        f"""
        SELECT
            a.id,
            a.title,
            a.url,
            a.source_name,
            a.status,
            a.retry_count,
            a.published_at,
            a.created_at,
            a.updated_at,
            a.collected_at,
            (
                SELECT q.status FROM article_queue q
                WHERE q.article_id = a.id AND q.stage = 'fetch'
                ORDER BY q.id DESC
                LIMIT 1
            ) AS fetch_queue_status,
            (
                SELECT q.status FROM article_queue q
                WHERE q.article_id = a.id AND q.stage = 'evaluate'
                ORDER BY q.id DESC
                LIMIT 1
            ) AS evaluate_queue_status,
            (
                SELECT f.status FROM fetches f
                WHERE f.article_id = a.id
                ORDER BY f.id DESC
                LIMIT 1
            ) AS fetch_status,
            (
                SELECT f.error FROM fetches f
                WHERE f.article_id = a.id
                ORDER BY f.id DESC
                LIMIT 1
            ) AS fetch_error,
            (
                SELECT e.decision FROM evaluations e
                WHERE e.article_id = a.id
                ORDER BY e.id DESC
                LIMIT 1
            ) AS evaluation_status,
            (
                SELECT ef.error FROM evaluation_failures ef
                WHERE ef.article_id = a.id
                ORDER BY ef.id DESC
                LIMIT 1
            ) AS evaluation_error
        FROM articles a
        {where_sql}
        ORDER BY {sort_column} {order_sql}, a.id {order_sql}
        LIMIT ? OFFSET ?
        """,
        [*params, page_size, offset],
    ).fetchall()
    return Page([dict(row) for row in rows], int(total), page, page_size)


def list_public_articles(
    conn: sqlite3.Connection,
    *,
    page: int = 1,
    page_size: int = 50,
    q: str | None = None,
) -> Page:
    page, page_size = _page_values(page, page_size)
    where, params = _article_filters(
        status=ArticleStatus.accepted.value,
        source=None,
        q=q,
        failed_only=False,
    )
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    total = conn.execute(f"SELECT COUNT(*) FROM articles a {where_sql}", params).fetchone()[0]
    offset = (page - 1) * page_size
    rows = conn.execute(
        f"""
        SELECT
            a.id,
            a.slug,
            a.title,
            a.url,
            a.source_name AS source,
            a.status,
            a.published_at,
            a.collected_at,
            a.created_at,
            a.updated_at,
            (
                SELECT e.summary FROM evaluations e
                WHERE e.article_id = a.id
                ORDER BY e.id DESC
                LIMIT 1
            ) AS summary,
{PUBLIC_TAGS_SQL}
            AS tags,
            (
                SELECT e.content_type FROM evaluations e
                WHERE e.article_id = a.id
                ORDER BY e.id DESC
                LIMIT 1
            ) AS content_type,
            (
                SELECT e.recommendation_reason FROM evaluations e
                WHERE e.article_id = a.id
                ORDER BY e.id DESC
                LIMIT 1
            ) AS recommendation_reason
        FROM articles a
        {where_sql}
        ORDER BY COALESCE(a.published_at, a.collected_at, a.updated_at, a.created_at) DESC, a.id DESC
        LIMIT ? OFFSET ?
        """,
        [*params, page_size, offset],
    ).fetchall()
    return Page([article_row_to_dict(row) for row in rows], int(total), page, page_size)


def list_all_public_articles(
    conn: sqlite3.Connection,
    *,
    q: str | None = None,
) -> list[dict[str, object]]:
    where, params = _article_filters(
        status=ArticleStatus.accepted.value,
        source=None,
        q=q,
        failed_only=False,
    )
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    rows = conn.execute(
        f"""
        SELECT
            a.id,
            a.slug,
            a.title,
            a.url,
            a.source_name AS source,
            a.status,
            a.published_at,
            a.collected_at,
            a.created_at,
            a.updated_at,
            (
                SELECT e.summary FROM evaluations e
                WHERE e.article_id = a.id
                ORDER BY e.id DESC
                LIMIT 1
            ) AS summary,
{PUBLIC_TAGS_SQL}
            AS tags,
            (
                SELECT e.content_type FROM evaluations e
                WHERE e.article_id = a.id
                ORDER BY e.id DESC
                LIMIT 1
            ) AS content_type,
            (
                SELECT e.recommendation_reason FROM evaluations e
                WHERE e.article_id = a.id
                ORDER BY e.id DESC
                LIMIT 1
            ) AS recommendation_reason
        FROM articles a
        {where_sql}
        ORDER BY COALESCE(a.published_at, a.collected_at, a.updated_at, a.created_at) DESC, a.id DESC
        """,
        params,
    ).fetchall()
    return [article_row_to_dict(row) for row in rows]


def get_article_detail(conn: sqlite3.Connection, article_id: int) -> dict[str, object] | None:
    article = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    if not article:
        return None
    latest_fetch = conn.execute(
        """
        SELECT * FROM fetches
        WHERE article_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (article_id,),
    ).fetchone()
    latest_evaluation = conn.execute(
        """
        SELECT * FROM evaluations
        WHERE article_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (article_id,),
    ).fetchone()
    evaluation_failure = conn.execute(
        """
        SELECT * FROM evaluation_failures
        WHERE article_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (article_id,),
    ).fetchone()
    latest_queue = conn.execute(
        """
        SELECT * FROM article_queue
        WHERE article_id = ?
        ORDER BY id DESC
        LIMIT 10
        """,
        (article_id,),
    ).fetchall()
    return {
        "article": article_row_to_dict(article),
        "latest_fetch": article_row_to_dict(latest_fetch) if latest_fetch else None,
        "latest_evaluation": article_row_to_dict(latest_evaluation) if latest_evaluation else None,
        "latest_evaluation_failure": dict(evaluation_failure) if evaluation_failure else None,
        "queue": [dict(row) for row in latest_queue],
    }


def get_public_article_detail(conn: sqlite3.Connection, slug: str) -> dict[str, object] | None:
    article = conn.execute(
        f"""
        SELECT
            a.*,
            f.content_markdown,
            f.fetched_at,
            e.summary,
            e.content_type,
{PUBLIC_TAGS_SQL}
            AS tags,
            e.recommendation_reason
        FROM articles a
        LEFT JOIN fetches f ON f.article_id = a.id
          AND f.id = (
              SELECT MAX(id) FROM fetches
              WHERE article_id = a.id AND status = 'success'
          )
        LEFT JOIN evaluations e ON e.article_id = a.id
          AND e.id = (
              SELECT MAX(id) FROM evaluations
              WHERE article_id = a.id
          )
        WHERE a.slug = ?
          AND a.status = ?
        """,
        (slug, ArticleStatus.accepted.value),
    ).fetchone()
    if not article:
        return None
    result = article_row_to_dict(article)
    result.pop("source_content_markdown", None)
    result.pop("source_content_metadata", None)
    return result


def source_names(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT source_name FROM articles ORDER BY source_name ASC"
    ).fetchall()
    return [row["source_name"] for row in rows]


def summary(conn: sqlite3.Connection) -> dict[str, int]:
    status_counts = {
        status.value: 0
        for status in (
            ArticleStatus.candidate,
            ArticleStatus.accepted,
            ArticleStatus.rejected,
            ArticleStatus.low_confidence,
            ArticleStatus.skipped_out_of_range,
        )
    }
    rows = conn.execute("SELECT status, COUNT(*) AS count FROM articles GROUP BY status").fetchall()
    for row in rows:
        status_counts[row["status"]] = int(row["count"])
    fetch_failed = conn.execute(
        """
        SELECT COUNT(*) FROM fetches f
        WHERE f.status = 'failed'
          AND f.id = (
              SELECT MAX(f2.id) FROM fetches f2
              WHERE f2.article_id = f.article_id
          )
        """
    ).fetchone()[0]
    evaluation_failed = conn.execute(
        """
        SELECT COUNT(*) FROM evaluation_failures ef
        WHERE NOT EXISTS (
            SELECT 1 FROM evaluations e
            WHERE e.article_id = ef.article_id
        )
          AND ef.id = (
              SELECT MAX(ef2.id) FROM evaluation_failures ef2
              WHERE ef2.article_id = ef.article_id
          )
        """
    ).fetchone()[0]
    return {
        "total": sum(status_counts.values()),
        **status_counts,
        "fetch_failed": int(fetch_failed),
        "evaluation_failed": int(evaluation_failed),
    }
