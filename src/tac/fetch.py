from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import sleep

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as html_to_markdown

from . import db


@dataclass(frozen=True)
class FetchResult:
    markdown: str
    metadata: dict


FALLBACK_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36 technical-article-curation/0.1"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


async def _fetch_with_crawler4ai(url: str) -> FetchResult | None:
    try:
        from crawl4ai import AsyncWebCrawler  # type: ignore
    except Exception:
        return None

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url)
        markdown = getattr(result, "markdown", None)
        if not markdown:
            return None
        return FetchResult(
            markdown=str(markdown).strip(),
            metadata={"crawler": "crawler4ai", "url": url},
        )


def _fallback_fetch(url: str, retries: int = 2) -> FetchResult:
    session = requests.Session()
    session.headers.update(FALLBACK_HEADERS)
    last_error: Exception | None = None
    response: requests.Response | None = None
    for attempt in range(retries + 1):
        try:
            response = session.get(url, timeout=(10, 30), allow_redirects=True)
            response.raise_for_status()
            break
        except requests.RequestException as exc:
            last_error = exc
            if attempt >= retries:
                raise
            sleep(0.5 * (attempt + 1))
    if response is None:
        raise RuntimeError(f"fallback fetch failed: {last_error}")
    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding
    soup = BeautifulSoup(response.text, "html.parser")
    for selector in ["script", "style", "noscript", "nav", "footer", "header"]:
        for tag in soup.select(selector):
            tag.decompose()
    main = soup.find("article") or soup.find("main") or soup.body or soup
    markdown = html_to_markdown(str(main), heading_style="ATX")
    markdown = "\n".join(line.rstrip() for line in markdown.splitlines()).strip()
    return FetchResult(
        markdown=markdown,
        metadata={
            "crawler": "requests+beautifulsoup+markdownify",
            "url": url,
            "status_code": response.status_code,
            "final_url": response.url,
        },
    )


def fetch_url(url: str, *, crawler4ai_enabled: bool = True) -> FetchResult:
    if crawler4ai_enabled:
        try:
            crawler_result = asyncio.run(_fetch_with_crawler4ai(url))
        except Exception:
            crawler_result = None
        if crawler_result and crawler_result.markdown:
            return crawler_result
    return _fallback_fetch(url)


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
    return {"attempted": attempted, "succeeded": succeeded, "failed": failed}
