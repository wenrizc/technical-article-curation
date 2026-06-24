from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, ValidationError

from tac.application import pipeline
from tac.application.jobs import JobConflict, JobManager, JobNotFound, JobQueueFull
from tac.application.scheduler import SchedulerService
from tac.application.tag_cache import TagVocabularyCache
from tac.application.use_cases import manage_articles as articles
from tac.application.use_cases import manage_tags as tags
from tac.application.use_cases.discover_articles import (
    _parse_feed_body,
    build_rsshub_feed_url,
    build_session,
    expand_sitemap_entries,
)
from tac.application.use_cases.manage_sources import (
    SourceConflict,
    SourceValidationError,
    read_sources_yaml,
    save_sources_yaml,
)
from tac.domain.models import ArticleStatus, FeedConfig, SourceConfig, TagStatus
from tac.infrastructure.db import store as db
from tac.web.deps import (
    db_conn,
    job_manager_from_request,
    settings_from_request,
    tag_cache_from_request,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


class StatusUpdate(BaseModel):
    status: ArticleStatus


class SourcesUpdate(BaseModel):
    content: str
    previous_hash: str


class TagCreate(BaseModel):
    name: str
    description: str = ""
    status: TagStatus = TagStatus.active


class TagUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: TagStatus | None = None


class TagCandidateApprove(BaseModel):
    tag_id: int | None = None
    name: str | None = None


class RssHubPreviewRequest(BaseModel):
    route: str
    instance: str | None = None
    params: dict[str, str | int | bool] = Field(default_factory=dict)
    limit: int = 10


class SitemapPreviewRequest(BaseModel):
    url: str
    limit: int = 10


class ListingPreviewRequest(BaseModel):
    url: str
    link_selector: str
    title_selector: str | None = None
    url_patterns: list[str] = Field(default_factory=list)
    base_url: str | None = None
    limit: int = 10


def _row_or_404(row):
    if row is None:
        raise HTTPException(status_code=404, detail="not found")
    return articles.article_row_to_dict(row)


def _preview_entry(entry) -> dict[str, object]:
    result = {"title": entry.title, "url": entry.url}
    if entry.published_at:
        result["published_at"] = entry.published_at
    return result


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


def scheduler_from_request(request: Request) -> SchedulerService:
    return request.app.state.scheduler


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
    since: str | None = None,
    until: str | None = None,
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
        since=since,
        until=until,
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


@router.get("/tags")
def list_tags(
    conn: Annotated[sqlite3.Connection, Depends(db_conn)],
    status: str | None = None,
    q: str | None = None,
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, object]:
    return tags.list_tags(conn, status=status, q=q, limit=limit, offset=offset)


@router.post("/tags")
def create_tag(
    payload: TagCreate,
    conn: Annotated[sqlite3.Connection, Depends(db_conn)],
    tag_cache: Annotated[TagVocabularyCache, Depends(tag_cache_from_request)],
) -> dict[str, object]:
    try:
        row = tags.create_tag(
            conn,
            name=payload.name,
            description=payload.description,
            status=payload.status,
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="tag already exists") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    tag_cache.refresh(conn)
    return row


@router.patch("/tags/{tag_id}")
def update_tag(
    tag_id: int,
    payload: TagUpdate,
    conn: Annotated[sqlite3.Connection, Depends(db_conn)],
    tag_cache: Annotated[TagVocabularyCache, Depends(tag_cache_from_request)],
) -> dict[str, object]:
    try:
        row = tags.update_tag(
            conn,
            tag_id,
            name=payload.name,
            description=payload.description,
            status=payload.status,
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="tag already exists") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="tag not found")
    tag_cache.refresh(conn)
    return row


@router.get("/tag-candidates")
def list_tag_candidates(
    conn: Annotated[sqlite3.Connection, Depends(db_conn)],
    status: str | None = "pending",
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, object]:
    return tags.list_tag_candidates(conn, status=status, limit=limit, offset=offset)


@router.post("/tag-candidates/{candidate_id}/approve")
def approve_tag_candidate(
    candidate_id: int,
    payload: TagCandidateApprove,
    conn: Annotated[sqlite3.Connection, Depends(db_conn)],
    tag_cache: Annotated[TagVocabularyCache, Depends(tag_cache_from_request)],
) -> dict[str, object]:
    try:
        row = tags.approve_candidate(
            conn,
            candidate_id,
            tag_id=payload.tag_id,
            name=payload.name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="tag candidate not found")
    tag_cache.refresh(conn)
    return row


@router.post("/tag-candidates/{candidate_id}/reject")
def reject_tag_candidate(
    candidate_id: int,
    conn: Annotated[sqlite3.Connection, Depends(db_conn)],
) -> dict[str, object]:
    row = tags.reject_candidate(conn, candidate_id)
    if row is None:
        raise HTTPException(status_code=404, detail="tag candidate not found")
    return row


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
    tag_cache = tag_cache_from_request(request)
    return _submit(
        request,
        background_tasks,
        "retry-evaluate",
        lambda: pipeline.run_evaluate(settings, article_ids=[article_id], tag_cache=tag_cache),
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


@router.post("/sources/preview-rsshub")
def preview_rsshub(payload: RssHubPreviewRequest, request: Request) -> dict[str, object]:
    settings = settings_from_request(request)
    try:
        feed = FeedConfig(
            type="rsshub",
            route=payload.route,
            instance=payload.instance,
            params=payload.params,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    feed_url = build_rsshub_feed_url(feed, settings)
    try:
        response = build_session().get(
            feed_url,
            headers={},
            timeout=(10, settings.rsshub_timeout_seconds),
            allow_redirects=True,
        )
        response.raise_for_status()
        parsed_entries = _parse_feed_body(SourceConfig(name="preview", feed=feed), response.content)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    max_entries = max(1, min(payload.limit, 50))
    entries = [_preview_entry(entry) for entry in parsed_entries[:max_entries]]
    return {"status": "success", "feed_url": feed_url, "entries": entries}


@router.post("/sources/preview-sitemap")
def preview_sitemap(payload: SitemapPreviewRequest, request: Request) -> dict[str, object]:
    settings = settings_from_request(request)
    try:
        feed = FeedConfig(type="sitemap", url=payload.url)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        session = build_session()
        response = session.get(
            feed.url or "",
            headers={},
            timeout=(10, 30),
            allow_redirects=True,
        )
        response.raise_for_status()
        parsed_entries = expand_sitemap_entries(
            session,
            settings,
            content=response.content,
            current_url=feed.url or "",
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    max_entries = max(1, min(payload.limit, 50))
    entries = [_preview_entry(entry) for entry in parsed_entries[:max_entries]]
    return {"status": "success", "feed_url": feed.url, "entries": entries}


@router.post("/sources/preview-listing")
def preview_listing(payload: ListingPreviewRequest, request: Request) -> dict[str, object]:
    settings = settings_from_request(request)
    try:
        feed = FeedConfig(
            type="listing",
            url=payload.url,
            link_selector=payload.link_selector,
            title_selector=payload.title_selector,
            url_patterns=payload.url_patterns,
            base_url=payload.base_url,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        response = build_session().get(
            feed.url or "",
            headers={},
            timeout=(10, settings.listing_timeout_seconds),
            allow_redirects=True,
        )
        response.raise_for_status()
        parsed_entries = _parse_feed_body(SourceConfig(name="preview", feed=feed), response.content)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    max_entries = max(1, min(payload.limit, 50))
    entries = [_preview_entry(entry) for entry in parsed_entries[:max_entries]]
    return {"status": "success", "feed_url": feed.url, "entries": entries}


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


@router.get("/schedules")
def list_schedules(request: Request) -> dict[str, object]:
    scheduler = scheduler_from_request(request)
    return {"items": scheduler.schedules()}


@router.post("/schedules/{schedule_id}/trigger")
async def trigger_schedule(
    schedule_id: str, request: Request, background_tasks: BackgroundTasks
) -> dict[str, object]:
    scheduler = scheduler_from_request(request)
    try:
        job = await scheduler.trigger(schedule_id, manual=True)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="schedule not found") from exc
    if job["status"] != "skipped":
        manager = job_manager_from_request(request)
        background_tasks.add_task(manager.run_job, str(job["job_id"]))
    return job


@router.post("/jobs/discover")
def run_discover(
    request: Request,
    background_tasks: BackgroundTasks,
    since: str | None = None,
    until: str | None = None,
) -> dict[str, object]:
    settings = settings_from_request(request)
    return _submit(
        request,
        background_tasks,
        "discover",
        lambda: pipeline.run_discover(settings, since=since, until=until),
    )


@router.post("/jobs/fetch")
def run_fetch(request: Request, background_tasks: BackgroundTasks) -> dict[str, object]:
    settings = settings_from_request(request)
    return _submit(request, background_tasks, "fetch", lambda: pipeline.run_fetch(settings))


@router.post("/jobs/evaluate")
def run_evaluate(request: Request, background_tasks: BackgroundTasks) -> dict[str, object]:
    settings = settings_from_request(request)
    tag_cache = tag_cache_from_request(request)
    return _submit(
        request,
        background_tasks,
        "evaluate",
        lambda: pipeline.run_evaluate(settings, tag_cache=tag_cache),
    )


@router.post("/jobs/publish")
def run_publish(request: Request, background_tasks: BackgroundTasks) -> dict[str, object]:
    settings = settings_from_request(request)
    return _submit(request, background_tasks, "publish", lambda: pipeline.run_publish(settings))


@router.post("/jobs/run")
def run_all(
    request: Request,
    background_tasks: BackgroundTasks,
    since: str | None = None,
    until: str | None = None,
) -> dict[str, object]:
    settings = settings_from_request(request)
    tag_cache = tag_cache_from_request(request)
    return _submit(
        request,
        background_tasks,
        "run",
        lambda: pipeline.run_all(settings, since=since, until=until, tag_cache=tag_cache),
    )
