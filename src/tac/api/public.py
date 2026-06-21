from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from tac.deps import db_conn
from tac.services import articles

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/articles")
def list_articles(
    conn: Annotated[sqlite3.Connection, Depends(db_conn)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    status: str | None = None,
    q: str | None = None,
) -> dict[str, object]:
    return articles.list_public_articles(
        conn,
        page=page,
        page_size=page_size,
        status=status,
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
    return articles.list_public_articles(conn, page=1, page_size=200).items
