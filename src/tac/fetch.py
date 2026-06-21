from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass
from time import sleep

from . import db
from .config import Settings


@dataclass(frozen=True)
class FetchResult:
    markdown: str
    metadata: dict[str, object]


class FetchError(RuntimeError):
    pass


async def _fetch_with_crawler4ai(url: str, *, timeout_seconds: float) -> FetchResult:
    try:
        from crawl4ai import AsyncWebCrawler  # type: ignore
    except Exception as exc:
        raise FetchError(f"crawler4ai unavailable: {exc}") from exc

    async with AsyncWebCrawler() as crawler:
        result = await asyncio.wait_for(crawler.arun(url=url), timeout=timeout_seconds)
        markdown = getattr(result, "markdown", None)
        if not markdown:
            raise FetchError("crawler4ai returned no markdown")
        status_code = getattr(result, "status_code", None)
        final_url = getattr(result, "url", None) or url
        return FetchResult(
            markdown=str(markdown).strip(),
            metadata={
                "crawler": "crawler4ai",
                "final_url": final_url,
                "status_code": status_code,
            },
        )


def fetch_url(
    url: str, *, crawler4ai_enabled: bool = True, timeout_seconds: float = 90
) -> FetchResult:
    if not crawler4ai_enabled:
        raise FetchError("crawler4ai is disabled and no fallback fetcher is configured")
    return asyncio.run(_fetch_with_crawler4ai(url, timeout_seconds=timeout_seconds))


def _articles_for_fetch(
    conn: sqlite3.Connection, *, max_retry: int, article_ids: list[int] | None
) -> list[sqlite3.Row]:
    if article_ids is None:
        return db.articles_ready_for_fetch(conn, max_retry)
    if not article_ids:
        return []
    placeholders = ",".join("?" for _ in article_ids)
    return conn.execute(
        f"""
        SELECT * FROM articles
        WHERE id IN ({placeholders})
          AND status != 'archived'
        ORDER BY id ASC
        """,
        article_ids,
    ).fetchall()


def fetch_pending(
    settings: Settings,
    conn: sqlite3.Connection,
    limit: int | None = None,
    article_ids: list[int] | None = None,
) -> dict[str, int]:
    attempted = 0
    succeeded = 0
    failed = 0
    for article in _articles_for_fetch(conn, max_retry=settings.max_retry, article_ids=article_ids):
        if limit is not None and attempted >= limit:
            break
        attempted += 1
        try:
            if settings.fetch_fixture_path:
                result = FetchResult(
                    markdown=settings.fetch_fixture_path.read_text(encoding="utf-8"),
                    metadata={"crawler": "fixture", "url": article["url"]},
                )
            else:
                result = fetch_url(
                    article["url"],
                    crawler4ai_enabled=settings.crawler4ai_enabled,
                    timeout_seconds=settings.fetch_timeout_seconds,
                )
            if not result.markdown.strip():
                raise ValueError("empty markdown")
            markdown_size = len(result.markdown.encode("utf-8"))
            if markdown_size > settings.fetch_max_markdown_bytes:
                raise ValueError(
                    f"markdown too large: {markdown_size} > {settings.fetch_max_markdown_bytes}"
                )
            if db.record_fetch_success(conn, int(article["id"]), result.markdown, result.metadata):
                succeeded += 1
            else:
                failed += 1
        except Exception as exc:
            db.record_failure(conn, int(article["id"]), str(exc))
            failed += 1
        if settings.fetch_delay_seconds > 0:
            sleep(settings.fetch_delay_seconds)
    return {"attempted": attempted, "succeeded": succeeded, "failed": failed}
