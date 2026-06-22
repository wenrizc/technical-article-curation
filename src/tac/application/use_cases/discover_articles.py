from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from urllib.parse import urlencode

import feedparser
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from tac.domain.models import FeedConfig, SourceConfig
from tac.infrastructure.db import store as db
from tac.infrastructure.sources.yaml_loader import load_sources, manual_candidates
from tac.settings import Settings

RSS_HEADERS = {
    "User-Agent": "technical-article-curation/0.1 (+https://example.invalid)",
    "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
}


def build_session() -> Session:
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = Session()
    session.headers.update(RSS_HEADERS)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def _conditional_headers(state: sqlite3.Row | None) -> dict[str, str]:
    headers: dict[str, str] = {}
    if state:
        if state["etag"]:
            headers["If-None-Match"] = state["etag"]
        if state["modified"]:
            headers["If-Modified-Since"] = state["modified"]
    return headers


@dataclass(frozen=True)
class SourceDiscoveryResult:
    source_name: str
    source_tags: list[str]
    source_publish_policy: str
    etag: str | None
    modified: str | None
    last_status: str
    last_error: str | None
    entries: list[tuple[str, str]]


def build_rsshub_feed_url(feed: FeedConfig, settings: Settings) -> str:
    instance = (feed.instance or settings.rsshub_instance).rstrip("/")
    route = feed.route or ""
    query = urlencode(feed.params, doseq=True)
    return f"{instance}{route}?{query}" if query else f"{instance}{route}"


def build_feed_url(source: SourceConfig, settings: Settings) -> str:
    if source.feed is None:
        raise ValueError("source feed is required")
    if source.feed.type == "direct":
        return source.feed.url or ""
    if not settings.rsshub_enabled:
        raise ValueError("rsshub is disabled")
    return build_rsshub_feed_url(source.feed, settings)


def _discover_source(
    settings: Settings, source: SourceConfig, state: sqlite3.Row | None
) -> SourceDiscoveryResult:
    session = build_session()
    etag = state["etag"] if state else None
    modified = state["modified"] if state else None
    try:
        feed_url = build_feed_url(source, settings)
        timeout = (
            (10, settings.rsshub_timeout_seconds)
            if source.feed and source.feed.type == "rsshub"
            else (10, 30)
        )
        response = session.get(
            feed_url,
            headers=_conditional_headers(state),
            timeout=timeout,
            allow_redirects=True,
        )
        if response.status_code == 304:
            return SourceDiscoveryResult(
                source_name=source.name,
                source_tags=source.tags,
                source_publish_policy=source.publish_policy or "full_content",
                etag=etag,
                modified=modified,
                last_status="not_modified",
                last_error=None,
                entries=[],
            )
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
        if getattr(parsed, "bozo", False):
            bozo_exception = getattr(parsed, "bozo_exception", None)
            raise ValueError(f"feed parse failed: {bozo_exception}")
        etag = response.headers.get("ETag") or etag
        modified = response.headers.get("Last-Modified") or modified
    except Exception as exc:
        return SourceDiscoveryResult(
            source_name=source.name,
            source_tags=source.tags,
            source_publish_policy=source.publish_policy or "full_content",
            etag=etag,
            modified=modified,
            last_status="failed",
            last_error=str(exc),
            entries=[],
        )

    entries = []
    for entry in parsed.entries:
        url = getattr(entry, "link", None)
        title = getattr(entry, "title", None) or url
        if url:
            entries.append((title, url))
    return SourceDiscoveryResult(
        source_name=source.name,
        source_tags=source.tags,
        source_publish_policy=source.publish_policy or "full_content",
        etag=etag,
        modified=modified,
        last_status="success",
        last_error=None,
        entries=entries,
    )


def discover_candidates(settings: Settings, conn: sqlite3.Connection) -> dict[str, int]:
    config = load_sources(settings.sources_path)
    found = 0
    inserted = 0
    skipped = 0
    sources_failed = 0
    sources_not_modified = 0

    feed_sources = [source for source in config.sources if source.enabled and source.feed]
    source_states = {source.name: db.get_source_state(conn, source.name) for source in feed_sources}
    max_workers = max(1, settings.discover_max_concurrency)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_discover_source, settings, source, source_states[source.name])
            for source in feed_sources
        ]
        for future in as_completed(futures):
            result = future.result()
            db.record_source_state(
                conn,
                source_name=result.source_name,
                etag=result.etag,
                modified=result.modified,
                last_status=result.last_status,
                last_error=result.last_error,
            )
            if result.last_status == "failed":
                sources_failed += 1
                continue
            if result.last_status == "not_modified":
                sources_not_modified += 1
                continue
            for title, url in result.entries:
                found += 1
                _, _, was_inserted = db.add_candidate(
                    conn,
                    title=title,
                    url=url,
                    source_name=result.source_name,
                    source_tags=result.source_tags,
                    source_publish_policy=result.source_publish_policy,
                )
                if was_inserted:
                    inserted += 1
                else:
                    skipped += 1

    for candidate in manual_candidates(config):
        found += 1
        _, _, was_inserted = db.add_candidate(
            conn,
            title=candidate.title,
            url=candidate.url,
            source_name=candidate.source_name,
            source_tags=candidate.source_tags,
            source_publish_policy=candidate.publish_policy,
        )
        if was_inserted:
            inserted += 1
        else:
            skipped += 1

    return {
        "found": found,
        "inserted": inserted,
        "skipped": skipped,
        "sources_failed": sources_failed,
        "sources_not_modified": sources_not_modified,
    }
