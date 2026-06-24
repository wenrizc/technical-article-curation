from __future__ import annotations

import sqlite3

from tac.domain.models import TagCandidateStatus, TagStatus
from tac.infrastructure.db.store import normalize_tag_name, tag_slug
from tac.shared.utils import utc_now_iso


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, object] | None:
    return dict(row) if row else None


def list_tags(
    conn: sqlite3.Connection,
    *,
    status: str | None = None,
    q: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> dict[str, object]:
    where: list[str] = []
    params: list[object] = []
    if status:
        where.append("status = ?")
        params.append(status)
    if q:
        where.append("(name LIKE ? OR description LIKE ?)")
        pattern = f"%{q.strip()}%"
        params.extend([pattern, pattern])
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    total = conn.execute(f"SELECT COUNT(*) FROM tag_vocabulary {where_sql}", params).fetchone()[0]
    rows = conn.execute(
        f"""
        SELECT
            tv.*,
            (
                SELECT COUNT(*) FROM article_tags at
                WHERE at.tag_id = tv.id
            ) AS article_count
        FROM tag_vocabulary tv
        {where_sql}
        ORDER BY tv.status ASC, tv.name COLLATE NOCASE ASC
        LIMIT ? OFFSET ?
        """,
        [*params, limit, offset],
    ).fetchall()
    return {
        "items": [dict(row) for row in rows],
        "total": int(total),
        "limit": limit,
        "offset": offset,
    }


def create_tag(
    conn: sqlite3.Connection,
    *,
    name: str,
    description: str = "",
    status: TagStatus = TagStatus.active,
) -> dict[str, object]:
    normalized = normalize_tag_name(name)
    if not normalized:
        raise ValueError("tag name must not be empty")
    now = utc_now_iso()
    cur = conn.execute(
        """
        INSERT INTO tag_vocabulary(name, normalized_name, slug, description, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (name.strip(), normalized, tag_slug(name), description.strip(), status.value, now, now),
    )
    conn.commit()
    return get_tag(conn, int(cur.lastrowid)) or {}


def get_tag(conn: sqlite3.Connection, tag_id: int) -> dict[str, object] | None:
    return _row_to_dict(
        conn.execute("SELECT * FROM tag_vocabulary WHERE id = ?", (tag_id,)).fetchone()
    )


def update_tag(
    conn: sqlite3.Connection,
    tag_id: int,
    *,
    name: str | None = None,
    description: str | None = None,
    status: TagStatus | None = None,
) -> dict[str, object] | None:
    existing = get_tag(conn, tag_id)
    if existing is None:
        return None
    fields: list[str] = []
    params: list[object] = []
    if name is not None:
        normalized = normalize_tag_name(name)
        if not normalized:
            raise ValueError("tag name must not be empty")
        fields.extend(["name = ?", "normalized_name = ?", "slug = ?"])
        params.extend([name.strip(), normalized, tag_slug(name)])
    if description is not None:
        fields.append("description = ?")
        params.append(description.strip())
    if status is not None:
        fields.append("status = ?")
        params.append(status.value)
    if not fields:
        return existing
    fields.append("updated_at = ?")
    params.append(utc_now_iso())
    params.append(tag_id)
    conn.execute(
        f"""
        UPDATE tag_vocabulary
        SET {", ".join(fields)}
        WHERE id = ?
        """,
        params,
    )
    conn.commit()
    return get_tag(conn, tag_id)


def list_tag_candidates(
    conn: sqlite3.Connection,
    *,
    status: str | None = TagCandidateStatus.pending.value,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, object]:
    where = []
    params: list[object] = []
    if status:
        where.append("tc.status = ?")
        params.append(status)
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    total = conn.execute(
        f"SELECT COUNT(*) FROM tag_candidates tc {where_sql}",
        params,
    ).fetchone()[0]
    rows = conn.execute(
        f"""
        SELECT
            tc.*,
            a.title AS article_title,
            a.url AS article_url,
            a.status AS article_status
        FROM tag_candidates tc
        JOIN articles a ON a.id = tc.article_id
        {where_sql}
        ORDER BY tc.created_at DESC, tc.id DESC
        LIMIT ? OFFSET ?
        """,
        [*params, limit, offset],
    ).fetchall()
    return {
        "items": [dict(row) for row in rows],
        "total": int(total),
        "limit": limit,
        "offset": offset,
    }


def approve_candidate(
    conn: sqlite3.Connection,
    candidate_id: int,
    *,
    tag_id: int | None = None,
    name: str | None = None,
) -> dict[str, object] | None:
    candidate = _candidate(conn, candidate_id)
    if candidate is None:
        return None
    if tag_id is None:
        tag = _get_or_create_tag_by_name(conn, name or candidate["suggested_tag"])
        tag_id = int(tag["id"])
    elif get_tag(conn, tag_id) is None:
        raise ValueError("tag not found")
    now = utc_now_iso()
    conn.execute(
        """
        INSERT OR IGNORE INTO article_tags(article_id, tag_id, evaluation_id, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (candidate["article_id"], tag_id, candidate["evaluation_id"], now),
    )
    conn.execute(
        """
        UPDATE tag_candidates
        SET status = ?, reviewed_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (TagCandidateStatus.approved.value, now, now, candidate_id),
    )
    conn.commit()
    return dict(_candidate(conn, candidate_id))


def reject_candidate(conn: sqlite3.Connection, candidate_id: int) -> dict[str, object] | None:
    candidate = _candidate(conn, candidate_id)
    if candidate is None:
        return None
    now = utc_now_iso()
    conn.execute(
        """
        UPDATE tag_candidates
        SET status = ?, reviewed_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (TagCandidateStatus.rejected.value, now, now, candidate_id),
    )
    conn.commit()
    return dict(_candidate(conn, candidate_id))


def _candidate(conn: sqlite3.Connection, candidate_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM tag_candidates WHERE id = ?", (candidate_id,)).fetchone()


def _get_or_create_tag_by_name(conn: sqlite3.Connection, name: str) -> dict[str, object]:
    normalized = normalize_tag_name(name)
    if not normalized:
        raise ValueError("tag name must not be empty")
    existing = conn.execute(
        "SELECT * FROM tag_vocabulary WHERE normalized_name = ?",
        (normalized,),
    ).fetchone()
    if existing:
        if existing["status"] != TagStatus.active.value:
            update_tag(conn, int(existing["id"]), status=TagStatus.active)
        return dict(get_tag(conn, int(existing["id"])) or existing)
    return create_tag(conn, name=name, description="由 AI 标签候选审核通过创建")
