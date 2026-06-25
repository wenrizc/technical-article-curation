from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path

from tac.domain.models import ArticleStatus, EvaluationResult, TagCandidateStatus, TagStatus
from tac.shared.dates import parse_datetime
from tac.shared.utils import normalize_url, source_title_slug, utc_now_iso


def connect(db_path: Path, *, busy_timeout_ms: int = 5000) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute(f"PRAGMA busy_timeout = {busy_timeout_ms}")
    return conn


def normalize_tag_name(value: str) -> str:
    return " ".join(value.strip().lower().split())


def tag_slug(value: str) -> str:
    normalized = normalize_tag_name(value)
    return normalized.replace(" ", "-")


def active_tag_names(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        """
        SELECT name
        FROM tag_vocabulary
        WHERE status = ?
        ORDER BY name COLLATE NOCASE ASC
        """,
        (TagStatus.active.value,),
    ).fetchall()
    return [str(row["name"]) for row in rows]


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
        try:
            conn.executescript(sql)
        except sqlite3.OperationalError as exc:
            if (
                version == "010_feed_entry_content"
                and "duplicate column name" in str(exc).lower()
                and _has_columns(
                    conn, "articles", {"source_content_markdown", "source_content_metadata"}
                )
            ):
                pass
            else:
                raise
        conn.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (version, utc_now_iso()),
        )
        applied.append(version)
    conn.commit()
    return applied


def _has_columns(conn: sqlite3.Connection, table: str, columns: set[str]) -> bool:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    return columns.issubset(existing)


def create_job_run(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    kind: str,
    status: str,
    trigger: str,
    schedule_id: str | None = None,
    target_article_id: int | None = None,
    created_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO job_runs(
            job_id, kind, status, trigger, schedule_id, target_article_id, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (job_id, kind, status, trigger, schedule_id, target_article_id, created_at),
    )
    conn.commit()


def mark_job_started(conn: sqlite3.Connection, job_id: str, *, started_at: str) -> None:
    conn.execute(
        """
        UPDATE job_runs
        SET status = 'running', started_at = ?
        WHERE job_id = ?
        """,
        (started_at, job_id),
    )
    conn.commit()


def finish_job_run(
    conn: sqlite3.Connection,
    job_id: str,
    *,
    status: str,
    finished_at: str,
    result: object = None,
    error: str | None = None,
) -> None:
    result_json = None if result is None else json.dumps(result, ensure_ascii=False)
    conn.execute(
        """
        UPDATE job_runs
        SET status = ?, finished_at = ?, result_json = ?, error = ?
        WHERE job_id = ?
        """,
        (status, finished_at, result_json, error, job_id),
    )
    conn.commit()


def mark_interrupted_job_runs(conn: sqlite3.Connection, *, finished_at: str) -> int:
    cur = conn.execute(
        """
        UPDATE job_runs
        SET status = 'failed',
            finished_at = COALESCE(finished_at, ?),
            error = 'job interrupted by service restart'
        WHERE status IN ('queued', 'running')
        """,
        (finished_at,),
    )
    conn.commit()
    return int(cur.rowcount)


def recover_article_queue(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        """
        UPDATE article_queue
        SET status = 'queued',
            job_id = NULL,
            started_at = NULL,
            error = NULL
        WHERE status = 'running'
        """
    )
    conn.commit()
    return int(cur.rowcount)


def enqueue_article(
    conn: sqlite3.Connection,
    *,
    article_id: int,
    stage: str,
    range_since: str | None = None,
    range_until: str | None = None,
    job_id: str | None = None,
) -> tuple[int, bool]:
    existing = conn.execute(
        """
        SELECT id FROM article_queue
        WHERE article_id = ?
          AND stage = ?
          AND status IN ('queued', 'running')
        ORDER BY id ASC
        LIMIT 1
        """,
        (article_id, stage),
    ).fetchone()
    if existing:
        return int(existing["id"]), False
    now = utc_now_iso()
    cur = conn.execute(
        """
        INSERT INTO article_queue(
            article_id, stage, status, job_id, range_since, range_until, created_at
        )
        VALUES (?, ?, 'queued', ?, ?, ?, ?)
        """,
        (article_id, stage, job_id, range_since, range_until, now),
    )
    conn.commit()
    return int(cur.lastrowid), True


def queued_article_items(
    conn: sqlite3.Connection,
    *,
    stage: str,
    limit: int | None = None,
) -> list[sqlite3.Row]:
    limit_sql = "" if limit is None else "LIMIT ?"
    params: list[object] = [stage]
    if limit is not None:
        params.append(limit)
    return conn.execute(
        f"""
        SELECT
            q.id AS queue_id,
            q.stage AS queue_stage,
            q.status AS queue_status,
            q.range_since,
            q.range_until,
            a.*
        FROM article_queue q
        JOIN articles a ON a.id = q.article_id
        WHERE q.stage = ?
          AND q.status = 'queued'
        ORDER BY q.id ASC
        {limit_sql}
        """,
        params,
    ).fetchall()


def mark_queue_running(
    conn: sqlite3.Connection,
    queue_id: int,
    *,
    job_id: str | None = None,
) -> bool:
    cur = conn.execute(
        """
        UPDATE article_queue
        SET status = 'running', job_id = ?, started_at = ?, error = NULL
        WHERE id = ? AND status = 'queued'
        """,
        (job_id, utc_now_iso(), queue_id),
    )
    conn.commit()
    return int(cur.rowcount) == 1


def finish_queue_item(
    conn: sqlite3.Connection,
    queue_id: int,
    *,
    status: str,
    error: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE article_queue
        SET status = ?, finished_at = ?, error = ?
        WHERE id = ?
        """,
        (status, utc_now_iso(), error, queue_id),
    )
    conn.commit()


def get_job_run(conn: sqlite3.Connection, job_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM job_runs WHERE job_id = ?",
        (job_id,),
    ).fetchone()


def list_job_runs(conn: sqlite3.Connection, *, limit: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT * FROM job_runs
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def latest_schedule_job_run(conn: sqlite3.Connection, schedule_id: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT * FROM job_runs
        WHERE schedule_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (schedule_id,),
    ).fetchone()


def get_source_state(conn: sqlite3.Connection, source_name: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM source_state WHERE source_name = ?",
        (source_name,),
    ).fetchone()


def record_source_state(
    conn: sqlite3.Connection,
    *,
    source_name: str,
    etag: str | None,
    modified: str | None,
    last_status: str,
    last_error: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO source_state(
            source_name, etag, modified, last_status, last_error, checked_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_name) DO UPDATE SET
            etag = excluded.etag,
            modified = excluded.modified,
            last_status = excluded.last_status,
            last_error = excluded.last_error,
            checked_at = excluded.checked_at
        """,
        (source_name, etag, modified, last_status, last_error, utc_now_iso()),
    )
    conn.commit()


def find_existing(conn: sqlite3.Connection, normalized_url: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM articles WHERE normalized_url = ? ORDER BY id ASC LIMIT 1",
        (normalized_url,),
    ).fetchone()


def get_article(conn: sqlite3.Connection, article_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()


def slug_exists(conn: sqlite3.Connection, slug: str) -> bool:
    return conn.execute("SELECT 1 FROM articles WHERE slug = ?", (slug,)).fetchone() is not None


def _update_existing_candidate(
    conn: sqlite3.Connection,
    existing: sqlite3.Row,
    *,
    parsed_published_at: str | None,
    cleaned_source_content: str | None,
    source_content_metadata_json: str,
    now: str,
) -> tuple[int, ArticleStatus, bool]:
    updates: list[str] = []
    params: list[object] = []
    if parsed_published_at and not existing["published_at"]:
        updates.append("published_at = ?")
        params.append(parsed_published_at)
    if cleaned_source_content and not _row_value(existing, "source_content_markdown"):
        updates.append("source_content_markdown = ?")
        params.append(cleaned_source_content)
        updates.append("source_content_metadata = ?")
        params.append(source_content_metadata_json)
    if updates:
        updates.append("updated_at = ?")
        params.append(now)
        params.append(existing["id"])
        conn.execute(
            f"UPDATE articles SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        conn.commit()
    return int(existing["id"]), ArticleStatus(existing["status"]), False


def add_candidate(
    conn: sqlite3.Connection,
    *,
    title: str,
    url: str,
    source_name: str,
    published_at: str | None = None,
    source_tags: Iterable[str] = (),
    source_content_markdown: str | None = None,
    source_content_metadata: dict[str, object] | None = None,
) -> tuple[int, ArticleStatus, bool]:
    normalized_url = normalize_url(url)
    now = utc_now_iso()
    parsed_published_at = parse_datetime(published_at)
    cleaned_source_content = (
        source_content_markdown.strip() if source_content_markdown is not None else None
    )
    if cleaned_source_content == "":
        cleaned_source_content = None
    source_content_metadata_json = json.dumps(source_content_metadata or {}, ensure_ascii=False)
    existing = find_existing(conn, normalized_url)
    if existing:
        return _update_existing_candidate(
            conn,
            existing,
            parsed_published_at=parsed_published_at,
            cleaned_source_content=cleaned_source_content,
            source_content_metadata_json=source_content_metadata_json,
            now=now,
        )

    status = ArticleStatus.candidate
    slug = source_title_slug(source_name, title or url, normalized_url, exists=False)
    if slug_exists(conn, slug):
        slug = source_title_slug(source_name, title or url, normalized_url, exists=True)

    try:
        cur = conn.execute(
            """
            INSERT INTO articles(
                source_name, title, url, normalized_url, slug,
                status, retry_count, published_at, created_at, updated_at, source_tags,
                source_content_markdown, source_content_metadata
            )
            VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_name,
                title or url,
                url,
                normalized_url,
                slug,
                status.value,
                parsed_published_at,
                now,
                now,
                json.dumps(list(source_tags), ensure_ascii=False),
                cleaned_source_content,
                source_content_metadata_json,
            ),
        )
    except sqlite3.IntegrityError:
        existing = find_existing(conn, normalized_url)
        if existing is None:
            raise
        return _update_existing_candidate(
            conn,
            existing,
            parsed_published_at=parsed_published_at,
            cleaned_source_content=cleaned_source_content,
            source_content_metadata_json=source_content_metadata_json,
            now=now,
        )
    conn.commit()
    return int(cur.lastrowid), status, True


def _row_value(row: sqlite3.Row, key: str) -> object | None:
    try:
        return row[key]
    except (IndexError, KeyError):
        return None


def articles_ready_for_fetch(conn: sqlite3.Connection, max_retry: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT * FROM articles
        WHERE status = 'candidate'
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
    metadata: dict[str, object],
    published_at: str | None = None,
) -> bool:
    article = get_article(conn, article_id)
    if not article:
        return False
    now = utc_now_iso()
    conn.execute(
        """
        INSERT INTO fetches(article_id, fetched_at, status, content_markdown, crawler_metadata)
        VALUES (?, ?, 'success', ?, ?)
        """,
        (article_id, now, content_markdown, json.dumps(metadata, ensure_ascii=False)),
    )
    parsed_published_at = parse_datetime(published_at)
    if parsed_published_at and not article["published_at"]:
        conn.execute(
            "UPDATE articles SET published_at = ?, updated_at = ?, error = NULL WHERE id = ?",
            (parsed_published_at, now, article_id),
        )
    else:
        conn.execute(
            "UPDATE articles SET updated_at = ?, error = NULL WHERE id = ?",
            (now, article_id),
        )
    conn.commit()
    return True


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
        SET retry_count = retry_count + 1, updated_at = ?, error = ?
        WHERE id = ?
        """,
        (now, error, article_id),
    )
    conn.commit()


def mark_article_skipped_out_of_range(
    conn: sqlite3.Connection, article_id: int, error: str
) -> None:
    now = utc_now_iso()
    conn.execute(
        """
        UPDATE articles
        SET status = ?, updated_at = ?, error = ?
        WHERE id = ?
        """,
        (ArticleStatus.skipped_out_of_range.value, now, error, article_id),
    )
    conn.commit()


def record_evaluation_failure(
    conn: sqlite3.Connection,
    article_id: int,
    *,
    error: str,
    attempts: int,
    raw_response: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO evaluation_failures(article_id, failed_at, error, attempts, raw_response)
        VALUES (?, ?, ?, ?, ?)
        """,
        (article_id, utc_now_iso(), error, attempts, raw_response),
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
    article = get_article(conn, article_id)
    cur = conn.execute(
        """
        INSERT INTO evaluations(
            article_id, evaluated_at, decision, content_type, summary,
            tags, recommendation_reason, model_name, raw_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            article_id,
            now,
            result.decision.value,
            result.content_type.value,
            result.summary,
            json.dumps(result.tags, ensure_ascii=False),
            result.recommendation_reason,
            model_name,
            raw_json,
        ),
    )
    evaluation_id = int(cur.lastrowid)
    _sync_evaluation_tags(
        conn,
        article_id,
        evaluation_id,
        result.tags,
        result.suggested_tags,
        now,
    )
    if article:
        if result.decision.value == "accept":
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


def _sync_evaluation_tags(
    conn: sqlite3.Connection,
    article_id: int,
    evaluation_id: int,
    tags: Iterable[str],
    suggested_tags: Iterable[str],
    now: str,
) -> None:
    conn.execute("DELETE FROM article_tags WHERE article_id = ?", (article_id,))
    cleaned = []
    seen: set[str] = set()
    for tag in tags:
        name = str(tag).strip()
        normalized = normalize_tag_name(name)
        if not name or not normalized or normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append((name, normalized))
    for name, normalized in cleaned:
        vocab = conn.execute(
            """
            SELECT id FROM tag_vocabulary
            WHERE normalized_name = ? AND status = ?
            """,
            (normalized, TagStatus.active.value),
        ).fetchone()
        if vocab:
            conn.execute(
                """
                INSERT OR IGNORE INTO article_tags(article_id, tag_id, evaluation_id, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (article_id, int(vocab["id"]), evaluation_id, now),
            )
            continue
        conn.execute(
            """
            INSERT OR IGNORE INTO tag_candidates(
                article_id, evaluation_id, suggested_tag, normalized_name, status,
                reason, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                article_id,
                evaluation_id,
                name,
                normalized,
                TagCandidateStatus.pending.value,
                "AI 评估将词库外标签放入 tags",
                now,
                now,
            ),
        )
    for tag in suggested_tags:
        name = str(tag).strip()
        normalized = normalize_tag_name(name)
        if not name or not normalized:
            continue
        vocab = conn.execute(
            """
            SELECT id FROM tag_vocabulary
            WHERE normalized_name = ? AND status = ?
            """,
            (normalized, TagStatus.active.value),
        ).fetchone()
        if vocab:
            conn.execute(
                """
                INSERT OR IGNORE INTO article_tags(article_id, tag_id, evaluation_id, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (article_id, int(vocab["id"]), evaluation_id, now),
            )
            continue
        conn.execute(
            """
            INSERT OR IGNORE INTO tag_candidates(
                article_id, evaluation_id, suggested_tag, normalized_name, status,
                reason, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                article_id,
                evaluation_id,
                name,
                normalized,
                TagCandidateStatus.pending.value,
                "AI 评估输出 suggested_tags 新标签建议",
                now,
                now,
            ),
        )


def accepted_articles_for_publish(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
            a.*,
            f.content_markdown,
            f.fetched_at,
            e.summary,
            e.content_type,
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
            ), '[]') AS tags,
            e.recommendation_reason
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
        ORDER BY COALESCE(a.published_at, a.collected_at, a.updated_at, a.created_at) DESC, a.id DESC
        """
    ).fetchall()


def failure_report(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
            a.id AS article_id,
            a.title,
            a.url,
            'fetch' AS stage,
            f.error AS error
        FROM fetches f
        JOIN articles a ON a.id = f.article_id
        WHERE f.status = 'failed'
          AND f.id = (
              SELECT MAX(f2.id) FROM fetches f2
              WHERE f2.article_id = f.article_id
          )
        UNION ALL
        SELECT
            a.id AS article_id,
            a.title,
            a.url,
            'evaluation' AS stage,
            ef.error AS error
        FROM evaluation_failures ef
        JOIN articles a ON a.id = ef.article_id
        WHERE NOT EXISTS (
            SELECT 1 FROM evaluations e
            WHERE e.article_id = ef.article_id
        )
          AND ef.id = (
              SELECT MAX(ef2.id) FROM evaluation_failures ef2
              WHERE ef2.article_id = ef.article_id
          )
        ORDER BY article_id ASC, stage ASC
        """
    ).fetchall()
