from __future__ import annotations

import sqlite3

import feedparser
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import db
from .config import Settings
from .sources import load_sources, manual_candidates

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


def discover_candidates(settings: Settings, conn: sqlite3.Connection) -> dict[str, int]:
    config = load_sources(settings.sources_path)
    session = build_session()
    found = 0
    inserted = 0
    skipped = 0
    sources_failed = 0
    sources_not_modified = 0

    for source in config.sources:
        if not source.enabled or not source.rss_url:
            continue
        state = db.get_source_state(conn, source.name)
        etag = state["etag"] if state else None
        modified = state["modified"] if state else None
        try:
            response = session.get(
                source.rss_url,
                headers=_conditional_headers(state),
                timeout=(10, 30),
                allow_redirects=True,
            )
            if response.status_code == 304:
                db.record_source_state(
                    conn,
                    source_name=source.name,
                    etag=etag,
                    modified=modified,
                    last_status="not_modified",
                )
                sources_not_modified += 1
                continue
            response.raise_for_status()
            parsed = feedparser.parse(response.content)
            if getattr(parsed, "bozo", False):
                bozo_exception = getattr(parsed, "bozo_exception", None)
                raise ValueError(f"feed parse failed: {bozo_exception}")
            etag = response.headers.get("ETag") or etag
            modified = response.headers.get("Last-Modified") or modified
            db.record_source_state(
                conn,
                source_name=source.name,
                etag=etag,
                modified=modified,
                last_status="success",
            )
        except Exception as exc:
            db.record_source_state(
                conn,
                source_name=source.name,
                etag=etag,
                modified=modified,
                last_status="failed",
                last_error=str(exc),
            )
            sources_failed += 1
            continue
        for entry in parsed.entries:
            url = getattr(entry, "link", None)
            title = getattr(entry, "title", None) or url
            if not url:
                continue
            found += 1
            _, _, was_inserted = db.add_candidate(
                conn,
                title=title,
                url=url,
                source_name=source.name,
                source_tags=source.tags,
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
