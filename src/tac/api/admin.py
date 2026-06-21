from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from tac import db, pipeline
from tac.deps import db_conn, job_manager_from_request, settings_from_request
from tac.jobs import JobConflict, JobManager, JobNotFound, JobQueueFull
from tac.models import ArticleStatus
from tac.services import articles
from tac.services.sources import (
    SourceConflict,
    SourceValidationError,
    read_sources_yaml,
    save_sources_yaml,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


class StatusUpdate(BaseModel):
    status: ArticleStatus


class SourcesUpdate(BaseModel):
    content: str
    previous_hash: str


def _row_or_404(row):
    if row is None:
        raise HTTPException(status_code=404, detail="not found")
    return articles.article_row_to_dict(row)


def _submit(
    request: Request,
    background_tasks: BackgroundTasks,
    kind: str,
    runner,
    *,
    target_article_id: int | None = None,
) -> dict[str, object]:
    manager: JobManager = job_manager_from_request(request)
    try:
        job = manager.submit_job(kind, runner, target_article_id=target_article_id)
    except JobQueueFull as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except JobConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    background_tasks.add_task(manager.run_job, job.job_id)
    return job.as_dict()


@router.get("/summary")
def summary(conn: Annotated[sqlite3.Connection, Depends(db_conn)]) -> dict[str, int]:
    return articles.summary(conn)


@router.get("/source-names")
def source_names(conn: Annotated[sqlite3.Connection, Depends(db_conn)]) -> dict[str, list[str]]:
    return {"items": articles.source_names(conn)}


@router.get("/articles")
def list_articles(
    conn: Annotated[sqlite3.Connection, Depends(db_conn)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    status: str | None = None,
    source: str | None = None,
    q: str | None = None,
    failed_only: bool = False,
    sort: str = "updated_at",
    order: str = "desc",
) -> dict[str, object]:
    return articles.list_admin_articles(
        conn,
        page=page,
        page_size=page_size,
        status=status,
        source=source,
        q=q,
        failed_only=failed_only,
        sort=sort,
        order=order,
    ).as_dict()


@router.get("/articles/{article_id}")
def article_detail(
    article_id: int, conn: Annotated[sqlite3.Connection, Depends(db_conn)]
) -> dict[str, object]:
    detail = articles.get_article_detail(conn, article_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="article not found")
    return detail


@router.post("/articles/{article_id}/status")
def set_status(
    article_id: int,
    payload: StatusUpdate,
    conn: Annotated[sqlite3.Connection, Depends(db_conn)],
) -> dict[str, object]:
    return _row_or_404(articles.set_article_status(conn, article_id, payload.status))


@router.post("/articles/{article_id}/archive")
def archive(
    article_id: int, conn: Annotated[sqlite3.Connection, Depends(db_conn)]
) -> dict[str, object]:
    return _row_or_404(articles.archive_article(conn, article_id))


@router.post("/articles/{article_id}/unarchive")
def unarchive(
    article_id: int, conn: Annotated[sqlite3.Connection, Depends(db_conn)]
) -> dict[str, object]:
    return _row_or_404(articles.unarchive_article(conn, article_id))


@router.post("/articles/{article_id}/retry-fetch")
def retry_fetch(
    article_id: int, request: Request, background_tasks: BackgroundTasks
) -> dict[str, object]:
    settings = settings_from_request(request)
    return _submit(
        request,
        background_tasks,
        "retry-fetch",
        lambda: pipeline.run_fetch(settings, article_ids=[article_id]),
        target_article_id=article_id,
    )


@router.post("/articles/{article_id}/retry-evaluate")
def retry_evaluate(
    article_id: int, request: Request, background_tasks: BackgroundTasks
) -> dict[str, object]:
    settings = settings_from_request(request)
    return _submit(
        request,
        background_tasks,
        "retry-evaluate",
        lambda: pipeline.run_evaluate(settings, article_ids=[article_id]),
        target_article_id=article_id,
    )


@router.get("/failures")
def failures(
    conn: Annotated[sqlite3.Connection, Depends(db_conn)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    rows = [dict(row) for row in db.failure_report(conn)]
    start = (page - 1) * page_size
    end = start + page_size
    total = len(rows)
    return {
        "items": rows[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": end < total,
    }


@router.get("/sources")
def get_sources(request: Request) -> dict[str, str]:
    settings = settings_from_request(request)
    current = read_sources_yaml(settings.sources_path)
    return {"content": current.content, "content_hash": current.content_hash}


@router.put("/sources")
def update_sources(payload: SourcesUpdate, request: Request) -> dict[str, str]:
    settings = settings_from_request(request)
    try:
        saved = save_sources_yaml(
            settings.sources_path,
            content=payload.content,
            previous_hash=payload.previous_hash,
        )
    except SourceConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SourceValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"content": saved.content, "content_hash": saved.content_hash}


@router.get("/jobs")
def list_jobs(request: Request) -> dict[str, object]:
    manager = job_manager_from_request(request)
    return {"items": [job.as_dict() for job in manager.list_jobs()]}


@router.get("/jobs/{job_id}")
def get_job(job_id: str, request: Request) -> dict[str, object]:
    manager = job_manager_from_request(request)
    try:
        return manager.get_job(job_id).as_dict()
    except JobNotFound as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc


@router.post("/jobs/discover")
def run_discover(request: Request, background_tasks: BackgroundTasks) -> dict[str, object]:
    settings = settings_from_request(request)
    return _submit(request, background_tasks, "discover", lambda: pipeline.run_discover(settings))


@router.post("/jobs/fetch")
def run_fetch(request: Request, background_tasks: BackgroundTasks) -> dict[str, object]:
    settings = settings_from_request(request)
    return _submit(request, background_tasks, "fetch", lambda: pipeline.run_fetch(settings))


@router.post("/jobs/evaluate")
def run_evaluate(request: Request, background_tasks: BackgroundTasks) -> dict[str, object]:
    settings = settings_from_request(request)
    return _submit(request, background_tasks, "evaluate", lambda: pipeline.run_evaluate(settings))


@router.post("/jobs/publish")
def run_publish(request: Request, background_tasks: BackgroundTasks) -> dict[str, object]:
    settings = settings_from_request(request)
    return _submit(request, background_tasks, "publish", lambda: pipeline.run_publish(settings))


@router.post("/jobs/run")
def run_all(request: Request, background_tasks: BackgroundTasks) -> dict[str, object]:
    settings = settings_from_request(request)
    return _submit(request, background_tasks, "run", lambda: pipeline.run_all(settings))
