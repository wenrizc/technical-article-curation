from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from urllib.parse import urlencode, urljoin, urlsplit
from xml.etree import ElementTree

import feedparser
from bs4 import BeautifulSoup
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


def _request_timeout(settings: Settings, feed: FeedConfig | None) -> tuple[int, float]:
    """按信源类型选择 (connect, read) 超时。rsshub/listing 走各自配置,其余默认 30s。"""
    if feed and feed.type == "rsshub":
        return (10, settings.rsshub_timeout_seconds)
    if feed and feed.type == "listing":
        return (10, settings.listing_timeout_seconds)
    return (10, 30)


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
    feed_type = source.feed.type
    if feed_type in {"direct", "sitemap"}:
        return source.feed.url or ""
    if feed_type == "listing":
        if not settings.discovery_listing_enabled:
            raise ValueError("listing is disabled")
        return source.feed.url or ""
    if feed_type == "rsshub":
        if not settings.rsshub_enabled:
            raise ValueError("rsshub is disabled")
        return build_rsshub_feed_url(source.feed, settings)
    raise ValueError(f"unsupported feed type: {feed_type}")


def _parse_feed_body(source: SourceConfig, content: bytes) -> list[tuple[str, str]]:
    """解析抓取到的信源内容,返回 (title, url) 列表。

    direct/rsshub 复用 feedparser;sitemap 走 ElementTree(urlset 不被 feedparser
    识别为 feed entries);listing 用 CSS 选择器抽取链接。失败统一抛异常,由调用方
    记录为 source failed。
    """
    feed = source.feed
    if feed is None:
        raise ValueError("source feed is required")
    if feed.type == "listing":
        return _parse_listing_body(feed, content)
    if feed.type == "sitemap":
        return _parse_sitemap_body(content)
    parsed = feedparser.parse(content)
    if getattr(parsed, "bozo", False):
        bozo_exception = getattr(parsed, "bozo_exception", None)
        raise ValueError(f"feed parse failed: {bozo_exception}")
    entries: list[tuple[str, str]] = []
    for entry in parsed.entries:
        url = getattr(entry, "link", None)
        title = getattr(entry, "title", None) or url
        if url:
            entries.append((title, url))
    return entries


def _parse_sitemap_body(content: bytes) -> list[tuple[str, str]]:
    """解析 sitemap.xml 的 urlset,返回 (url, url) 列表。

    feedparser 不识别 sitemap urlset,这里用 ElementTree 手动解析。<loc> 可能带
    sitemap namespace,也兼容无 namespace 的写法;标题在 sitemap 中通常缺失,回退为 URL。
    """
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as exc:
        raise ValueError(f"sitemap parse failed: {exc}") from exc
    # namespace 形如 {http://www.sitemaps.org/schemas/sitemap/0.9}
    namespace = ""
    if root.tag.startswith("{"):
        namespace = root.tag.split("}", 1)[0] + "}"
    locations = [node.text for node in root.iter(f"{namespace}loc")]
    entries: list[tuple[str, str]] = []
    for loc in locations:
        url = (loc or "").strip()
        if url:
            entries.append((url, url))
    return entries


def _parse_listing_body(feed: FeedConfig, content: bytes) -> list[tuple[str, str]]:
    """从 HTML 列表页抽取文章链接。

    使用 link_selector 选出文章锚点,base_url 或 feed.url 的 origin 解析相对链接,
    url_patterns 非空时只保留 URL 含任一子串的链接。标题优先用 title_selector,
    否则取锚点文本,都没有则用 URL。
    """
    soup = BeautifulSoup(content, "lxml")
    base = feed.base_url
    if not base and feed.url:
        # 相对链接默认按列表页 origin 解析,而非整页 URL,避免带上路径段。
        split = urlsplit(feed.url)
        base = f"{split.scheme}://{split.netloc}"
    link_nodes = soup.select(feed.link_selector or "a")
    title_nodes = (
        soup.select(feed.title_selector)
        if feed.title_selector and feed.title_selector.strip()
        else None
    )
    patterns = [p.strip() for p in feed.url_patterns if p and p.strip()]
    entries: list[tuple[str, str]] = []
    for index, node in enumerate(link_nodes):
        href = node.get("href")
        if not href:
            continue
        href = href.strip()
        if not href or href.startswith("#") or href.lower().startswith(("javascript:", "mailto:")):
            continue
        resolved = urljoin(base or "", href) if base else href
        if patterns and not any(pattern in resolved for pattern in patterns):
            continue
        title = None
        if title_nodes is not None and index < len(title_nodes):
            title = title_nodes[index].get_text(strip=True) or None
        if not title:
            title = node.get_text(strip=True) or resolved
        entries.append((title, resolved))
    return entries


def _discover_source(
    settings: Settings, source: SourceConfig, state: sqlite3.Row | None
) -> SourceDiscoveryResult:
    session = build_session()
    etag = state["etag"] if state else None
    modified = state["modified"] if state else None
    try:
        feed_url = build_feed_url(source, settings)
        timeout = _request_timeout(settings, source.feed)
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
        entries = _parse_feed_body(source, response.content)
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
