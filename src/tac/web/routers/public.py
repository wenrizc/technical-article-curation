from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from tac.application.use_cases import manage_articles as articles
from tac.application.use_cases.generate_feed import generate_public_feed, is_not_modified
from tac.web.deps import db_conn, settings_from_request

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/articles")
def list_articles(
    conn: Annotated[sqlite3.Connection, Depends(db_conn)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    q: str | None = None,
) -> dict[str, object]:
    return articles.list_public_articles(
        conn,
        page=page,
        page_size=page_size,
        q=q,
    ).as_dict()


@router.get("/articles/{slug}")
def article_detail(
    slug: str, conn: Annotated[sqlite3.Connection, Depends(db_conn)]
) -> dict[str, object]:
    detail = articles.get_public_article_detail(conn, slug)
    if detail is None:
        raise HTTPException(status_code=404, detail="article not found")
    return detail


@router.get("/index.json")
def index(conn: Annotated[sqlite3.Connection, Depends(db_conn)]) -> list[dict[str, object]]:
    return articles.list_all_public_articles(conn)


def public_feed_response(
    request: Request,
    conn: sqlite3.Connection,
    *,
    limit: int = 50,
) -> Response:
    settings = settings_from_request(request)
    feed = generate_public_feed(settings, conn, limit=limit)
    headers = {
        "Cache-Control": f"public, max-age={settings.public_feed_ttl_minutes * 60}",
        "ETag": feed.etag,
    }
    if feed.last_modified:
        headers["Last-Modified"] = feed.last_modified
    if is_not_modified(
        feed,
        if_none_match=request.headers.get("if-none-match"),
        if_modified_since=request.headers.get("if-modified-since"),
    ):
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    return Response(content=feed.content, media_type="application/rss+xml", headers=headers)


@router.get("/feed.xml")
def feed_xml(
    request: Request,
    conn: Annotated[sqlite3.Connection, Depends(db_conn)],
    limit: int = Query(50, ge=1, le=200),
) -> Response:
    return public_feed_response(request, conn, limit=limit)
