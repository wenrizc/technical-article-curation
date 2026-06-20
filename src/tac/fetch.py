from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import sleep

from . import db


@dataclass(frozen=True)
class FetchResult:
    markdown: str
    metadata: dict


class FetchError(RuntimeError):
    pass


async def _fetch_with_crawler4ai(url: str) -> FetchResult:
    try:
        from crawl4ai import AsyncWebCrawler  # type: ignore
    except Exception as exc:
        raise FetchError(f"crawler4ai unavailable: {exc}") from exc

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url)
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


def fetch_url(url: str, *, crawler4ai_enabled: bool = True) -> FetchResult:
    if not crawler4ai_enabled:
        raise FetchError("crawler4ai is disabled and no fallback fetcher is configured")
    return asyncio.run(_fetch_with_crawler4ai(url))


def fetch_pending(settings, conn, limit: int | None = None) -> dict[str, int]:
    attempted = 0
    succeeded = 0
    failed = 0
    for article in db.articles_ready_for_fetch(conn, settings.max_retry):
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
                )
            if not result.markdown.strip():
                raise ValueError("empty markdown")
            db.record_fetch_success(conn, int(article["id"]), result.markdown, result.metadata)
            succeeded += 1
        except Exception as exc:
            db.record_failure(conn, int(article["id"]), str(exc))
            failed += 1
        if settings.fetch_delay_seconds > 0:
            sleep(settings.fetch_delay_seconds)
    return {"attempted": attempted, "succeeded": succeeded, "failed": failed}
