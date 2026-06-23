from __future__ import annotations

import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from time import sleep

from tac.infrastructure.db import store as db
from tac.settings import Settings

FETCH_HEADERS = {
    "User-Agent": "technical-article-curation/0.1 (+https://example.invalid)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_PLAYWRIGHT_CHECKED = False
_PLAYWRIGHT_FALLBACK_REASON: str | None = None


@dataclass(frozen=True)
class FetchResult:
    markdown: str
    metadata: dict[str, object]


class FetchError(RuntimeError):
    pass


def _crawler_result(
    result: object,
    *,
    crawler_name: str,
    fallback_reason: str | None = None,
    requested_url: str,
) -> FetchResult:
    markdown = getattr(result, "markdown", None)
    if not markdown:
        error = getattr(result, "error_message", None)
        suffix = f": {error}" if error else ""
        raise FetchError(f"{crawler_name} returned no markdown{suffix}")
    status_code = getattr(result, "status_code", None)
    final_url = getattr(result, "url", None) or requested_url
    metadata: dict[str, object] = {
        "crawler": crawler_name,
        "final_url": final_url,
        "status_code": status_code,
    }
    if fallback_reason:
        metadata["fallback_reason"] = fallback_reason
    return FetchResult(markdown=str(markdown).strip(), metadata=metadata)


def _browser_unavailable(exc: Exception) -> bool:
    message = str(exc)
    return "Executable doesn't exist" in message and "playwright install" in message


async def _playwright_fallback_reason() -> str | None:
    """预检 Chromium 是否存在,避免每次抓取都先触发浏览器启动失败。"""
    global _PLAYWRIGHT_CHECKED, _PLAYWRIGHT_FALLBACK_REASON
    if _PLAYWRIGHT_CHECKED:
        return _PLAYWRIGHT_FALLBACK_REASON

    _PLAYWRIGHT_CHECKED = True
    try:
        from pathlib import Path

        from playwright.async_api import async_playwright  # type: ignore
    except Exception:
        return None

    try:
        async with async_playwright() as playwright:
            executable_path = playwright.chromium.executable_path
    except Exception:
        return None
    if not Path(executable_path).exists():
        _PLAYWRIGHT_FALLBACK_REASON = f"playwright chromium executable not found: {executable_path}"
    return _PLAYWRIGHT_FALLBACK_REASON


async def _fetch_with_crawler4ai_http(
    url: str, *, timeout_seconds: float, fallback_reason: str
) -> FetchResult:
    try:
        from crawl4ai import AsyncWebCrawler  # type: ignore
        from crawl4ai.async_crawler_strategy import (  # type: ignore
            AsyncHTTPCrawlerStrategy,
            HTTPCrawlerConfig,
        )
    except Exception as exc:
        raise FetchError(f"crawler4ai http fallback unavailable: {exc}") from exc

    strategy = AsyncHTTPCrawlerStrategy(
        HTTPCrawlerConfig(headers=FETCH_HEADERS, follow_redirects=True)
    )
    async with AsyncWebCrawler(crawler_strategy=strategy) as crawler:
        result = await asyncio.wait_for(crawler.arun(url=url), timeout=timeout_seconds)
        return _crawler_result(
            result,
            crawler_name="crawler4ai-http",
            fallback_reason=fallback_reason,
            requested_url=url,
        )


async def _fetch_with_crawler4ai(url: str, *, timeout_seconds: float) -> FetchResult:
    try:
        from crawl4ai import AsyncWebCrawler  # type: ignore
    except Exception as exc:
        raise FetchError(f"crawler4ai unavailable: {exc}") from exc

    fallback_reason = await _playwright_fallback_reason()
    if fallback_reason:
        return await _fetch_with_crawler4ai_http(
            url,
            timeout_seconds=timeout_seconds,
            fallback_reason=fallback_reason,
        )

    try:
        async with AsyncWebCrawler() as crawler:
            result = await asyncio.wait_for(crawler.arun(url=url), timeout=timeout_seconds)
            return _crawler_result(
                result,
                crawler_name="crawler4ai",
                requested_url=url,
            )
    except Exception as exc:
        if not _browser_unavailable(exc):
            raise
        return await _fetch_with_crawler4ai_http(
            url,
            timeout_seconds=timeout_seconds,
            fallback_reason=str(exc).splitlines()[0],
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
        ORDER BY id ASC
        """,
        article_ids,
    ).fetchall()


def _fetch_article(
    settings: Settings, article: sqlite3.Row
) -> tuple[int, FetchResult | None, str | None]:
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
        return int(article["id"]), result, None
    except Exception as exc:
        return int(article["id"]), None, str(exc)


def fetch_pending(
    settings: Settings,
    conn: sqlite3.Connection,
    limit: int | None = None,
    article_ids: list[int] | None = None,
) -> dict[str, int]:
    succeeded = 0
    failed = 0
    articles = _articles_for_fetch(conn, max_retry=settings.max_retry, article_ids=article_ids)
    if limit is not None:
        articles = articles[:limit]
    if not articles:
        return {"attempted": 0, "succeeded": 0, "failed": 0}

    max_workers = max(1, settings.fetch_max_concurrency)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_fetch_article, settings, article) for article in articles]
        for future in as_completed(futures):
            article_id, result, error = future.result()
            if result and db.record_fetch_success(
                conn, article_id, result.markdown, result.metadata
            ):
                succeeded += 1
            else:
                db.record_failure(conn, article_id, error or "fetch result was not written")
                failed += 1
            if settings.fetch_delay_seconds > 0:
                sleep(settings.fetch_delay_seconds)
    return {"attempted": len(articles), "succeeded": succeeded, "failed": failed}
