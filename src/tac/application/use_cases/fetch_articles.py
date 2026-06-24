from __future__ import annotations

import asyncio
import json
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from time import sleep

from bs4 import BeautifulSoup

from tac.infrastructure.db import store as db
from tac.settings import Settings
from tac.shared.dates import TimeRange, parse_datetime

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
    published_at: str | None = None


class FetchError(RuntimeError):
    pass


def _json_ld_dates(soup: BeautifulSoup) -> str | None:
    for script in soup.select('script[type="application/ld+json"]'):
        text = script.string or script.get_text()
        if not text.strip():
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        stack = payload if isinstance(payload, list) else [payload]
        while stack:
            item = stack.pop(0)
            if isinstance(item, list):
                stack.extend(item)
                continue
            if not isinstance(item, dict):
                continue
            for key in ("datePublished", "dateModified", "dateCreated"):
                if parsed := parse_datetime(item.get(key)):
                    return parsed
            graph = item.get("@graph")
            if isinstance(graph, list):
                stack.extend(graph)
    return None


def _embedded_script_dates(html: str) -> str | None:
    date_keys = (
        "datePublished",
        "dateModified",
        "dateCreated",
        "publishedOn",
        "publishedAt",
    )
    key_pattern = "|".join(re.escape(key) for key in date_keys)
    patterns = (
        rf'"(?:{key_pattern})"\s*:\s*"([^"]+)"',
        rf'\\"(?:{key_pattern})\\"\s*:\s*\\"([^"\\]+)\\"',
    )
    for pattern in patterns:
        for match in re.finditer(pattern, html):
            if parsed := parse_datetime(match.group(1)):
                return parsed
    return None


def extract_published_at_from_html(html: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    meta_names = [
        ("property", "article:published_time"),
        ("property", "article:modified_time"),
        ("property", "og:updated_time"),
        ("name", "date"),
        ("name", "pubdate"),
        ("name", "publishdate"),
        ("name", "timestamp"),
        ("name", "DC.date.issued"),
        ("itemprop", "datePublished"),
        ("itemprop", "dateModified"),
    ]
    for attr, value in meta_names:
        node = soup.find("meta", attrs={attr: value})
        if node and (parsed := parse_datetime(node.get("content"))):
            return parsed
    if parsed := _json_ld_dates(soup):
        return parsed
    if parsed := _embedded_script_dates(html):
        return parsed
    for node in soup.find_all("time"):
        if parsed := parse_datetime(node.get("datetime") or node.get_text(strip=True)):
            return parsed
    return None


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
    html = getattr(result, "html", None)
    published_at = extract_published_at_from_html(str(html)) if html else None
    if published_at:
        metadata["published_at"] = published_at
    return FetchResult(markdown=str(markdown).strip(), metadata=metadata, published_at=published_at)


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
    conn: sqlite3.Connection,
    *,
    max_retry: int,
    article_ids: list[int] | None,
    limit: int | None,
) -> list[sqlite3.Row]:
    if article_ids is None:
        articles = db.queued_article_items(conn, stage="fetch", limit=limit)
        if articles:
            return articles
        for article in db.articles_ready_for_fetch(conn, max_retry):
            db.enqueue_article(conn, article_id=int(article["id"]), stage="fetch")
        return db.queued_article_items(conn, stage="fetch", limit=limit)
    if not article_ids:
        return []
    placeholders = ",".join("?" for _ in article_ids)
    return conn.execute(
        f"""
        SELECT NULL AS queue_id, NULL AS range_since, NULL AS range_until, articles.*
        FROM articles
        WHERE id IN ({placeholders})
        ORDER BY id ASC
        """,
        article_ids,
    ).fetchall()


def _row_value(row: sqlite3.Row, key: str) -> object | None:
    try:
        return row[key]
    except (IndexError, KeyError):
        return None


def _fetch_article(
    settings: Settings, article: sqlite3.Row
) -> tuple[int, FetchResult | None, str | None]:
    try:
        source_result = _fetch_from_source_content(article)
        if (
            source_result
            and _markdown_size(source_result.markdown) <= settings.fetch_max_markdown_bytes
        ):
            result = source_result
        elif settings.fetch_fixture_path:
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
        markdown_size = _markdown_size(result.markdown)
        if markdown_size > settings.fetch_max_markdown_bytes:
            raise ValueError(
                f"markdown too large: {markdown_size} > {settings.fetch_max_markdown_bytes}"
            )
        return int(article["id"]), result, None
    except Exception as exc:
        return int(article["id"]), None, str(exc)


def _markdown_size(markdown: str) -> int:
    return len(markdown.encode("utf-8"))


def _fetch_from_source_content(article: sqlite3.Row) -> FetchResult | None:
    """Use content embedded in RSS/RSSHub entries before falling back to page crawling."""

    markdown = _row_value(article, "source_content_markdown")
    if not isinstance(markdown, str) or not markdown.strip():
        return None
    metadata_value = _row_value(article, "source_content_metadata")
    metadata: dict[str, object] = {}
    if isinstance(metadata_value, str) and metadata_value.strip():
        try:
            parsed = json.loads(metadata_value)
        except json.JSONDecodeError:
            parsed = {}
        if isinstance(parsed, dict):
            metadata.update(parsed)
    metadata.update(
        {
            "crawler": "feed-entry",
            "url": article["url"],
            "fallback_target": "crawler4ai",
        }
    )
    published_at = _row_value(article, "published_at")
    return FetchResult(
        markdown=markdown.strip(),
        metadata=metadata,
        published_at=published_at if isinstance(published_at, str) else None,
    )


def fetch_pending(
    settings: Settings,
    conn: sqlite3.Connection,
    limit: int | None = None,
    article_ids: list[int] | None = None,
) -> dict[str, int]:
    succeeded = 0
    failed = 0
    skipped = 0
    queued_evaluate = 0
    articles = _articles_for_fetch(
        conn,
        max_retry=settings.max_retry,
        article_ids=article_ids,
        limit=limit,
    )
    if not articles:
        return {"attempted": 0, "succeeded": 0, "failed": 0, "skipped": 0, "queued_evaluate": 0}

    max_workers = max(1, settings.fetch_max_concurrency)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        queue_by_article_id: dict[int, int] = {}
        range_by_article_id: dict[int, TimeRange] = {}
        for article in articles:
            queue_id = _row_value(article, "queue_id")
            if isinstance(queue_id, int):
                if not db.mark_queue_running(conn, queue_id):
                    continue
                queue_by_article_id[int(article["id"])] = queue_id
                range_by_article_id[int(article["id"])] = TimeRange(
                    since=_row_value(article, "range_since"),
                    until=_row_value(article, "range_until"),
                )
            futures.append(executor.submit(_fetch_article, settings, article))
        for future in as_completed(futures):
            article_id, result, error = future.result()
            queue_id = queue_by_article_id.get(article_id)
            if result and db.record_fetch_success(
                conn, article_id, result.markdown, result.metadata, published_at=result.published_at
            ):
                article = db.get_article(conn, article_id)
                time_range = range_by_article_id.get(article_id, TimeRange())
                if article and not time_range.contains(article["published_at"]):
                    error_message = "published_at is outside requested range"
                    db.mark_article_skipped_out_of_range(conn, article_id, error_message)
                    if queue_id is not None:
                        db.finish_queue_item(
                            conn,
                            queue_id,
                            status="skipped_out_of_range",
                            error=error_message,
                        )
                    skipped += 1
                    continue
                _, was_queued = db.enqueue_article(
                    conn,
                    article_id=article_id,
                    stage="evaluate",
                    range_since=time_range.since,
                    range_until=time_range.until,
                )
                if was_queued:
                    queued_evaluate += 1
                if queue_id is not None:
                    db.finish_queue_item(conn, queue_id, status="succeeded")
                succeeded += 1
            else:
                db.record_failure(conn, article_id, error or "fetch result was not written")
                if queue_id is not None:
                    db.finish_queue_item(
                        conn,
                        queue_id,
                        status="failed",
                        error=error or "fetch result was not written",
                    )
                failed += 1
            if settings.fetch_delay_seconds > 0:
                sleep(settings.fetch_delay_seconds)
    return {
        "attempted": len(articles),
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped,
        "queued_evaluate": queued_evaluate,
    }
