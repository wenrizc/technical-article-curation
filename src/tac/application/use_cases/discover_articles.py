from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit
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
from tac.shared.dates import TimeRange, build_time_range, parse_datetime

RSS_HEADERS = {
    "User-Agent": "technical-article-curation/0.1 (+https://example.invalid)",
    "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
}

MAX_SITEMAP_DEPTH = 3
MAX_SITEMAP_FILES = 32


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
class DiscoveredEntry:
    title: str
    url: str
    published_at: str | None = None
    source_content_markdown: str | None = None
    source_content_metadata: dict[str, object] | None = None


@dataclass(frozen=True)
class SourceDiscoveryResult:
    source_name: str
    source_tags: list[str]
    etag: str | None
    modified: str | None
    last_status: str
    last_error: str | None
    entries: list[DiscoveredEntry]


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


def _entry_published_at(entry: object) -> str | None:
    return (
        parse_datetime(getattr(entry, "published_parsed", None))
        or parse_datetime(getattr(entry, "published", None))
        or parse_datetime(getattr(entry, "updated_parsed", None))
        or parse_datetime(getattr(entry, "updated", None))
    )


def _parse_feed_body(source: SourceConfig, content: bytes) -> list[DiscoveredEntry]:
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
        return _sitemap_url_entries(content)
    parsed = feedparser.parse(_strip_invalid_xml_control_chars(content))
    if getattr(parsed, "bozo", False):
        bozo_exception = getattr(parsed, "bozo_exception", None)
        raise ValueError(f"feed parse failed: {bozo_exception}")
    entries: list[DiscoveredEntry] = []
    for entry in parsed.entries:
        url = getattr(entry, "link", None)
        title = getattr(entry, "title", None) or url
        if url:
            source_content, source_content_metadata = _entry_source_content(entry)
            entries.append(
                DiscoveredEntry(
                    title=title,
                    url=_normalize_feed_entry_url(source, url),
                    published_at=_entry_published_at(entry),
                    source_content_markdown=source_content,
                    source_content_metadata=source_content_metadata,
                )
            )
    return entries


def _entry_source_content(entry: object) -> tuple[str | None, dict[str, object] | None]:
    """Extract article-like content embedded in RSS/Atom entries."""

    content_items = getattr(entry, "content", None)
    if isinstance(content_items, list):
        for item in content_items:
            value = _entry_field(item, "value")
            if value:
                markdown = _html_or_text_to_markdown(value)
                if markdown:
                    return markdown, {
                        "source": "feed_entry",
                        "field": "content",
                        "content_type": _entry_field(item, "type"),
                    }
    summary = (
        _entry_field(entry, "summary")
        or _entry_field(getattr(entry, "summary_detail", None), "value")
        or _entry_field(entry, "description")
    )
    if summary:
        markdown = _html_or_text_to_markdown(summary)
        if markdown:
            return markdown, {"source": "feed_entry", "field": "summary"}
    return None, None


def _entry_field(item: object, field: str) -> str | None:
    if item is None:
        return None
    value = item.get(field) if isinstance(item, dict) else getattr(item, field, None)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _html_or_text_to_markdown(value: str) -> str | None:
    """Convert feed embedded HTML or text to plain Markdown-compatible text."""

    text = value.strip()
    if not text:
        return None
    if "<" not in text or ">" not in text:
        return text
    soup = BeautifulSoup(text, "lxml")
    for node in soup(["script", "style"]):
        node.decompose()
    markdown = soup.get_text("\n", strip=True)
    return markdown or None


def _strip_invalid_xml_control_chars(content: bytes) -> bytes:
    """移除 RSS/Atom 中会导致 XML 解析失败的 ASCII 控制字符。"""
    invalid = bytes(code for code in range(32) if code not in {9, 10, 13})
    return content.translate(None, invalid)


def _normalize_feed_entry_url(source: SourceConfig, url: str) -> str:
    """把 feed 条目链接归一为可抓取的绝对 URL。"""
    cleaned = url.strip()
    feed = source.feed
    base = source.site_url or (feed.url if feed and feed.url else None)
    if not base:
        return cleaned

    parsed = urlsplit(cleaned)
    base_parsed = urlsplit(base)
    if parsed.scheme in {"http", "https"}:
        if parsed.hostname in {"localhost", "127.0.0.1", "0.0.0.0"} and base_parsed.netloc:
            # 一些静态站点 feed 会错误带出本地开发地址,实际文章路径仍可按站点域名解析。
            return urlunsplit(
                (
                    base_parsed.scheme or "https",
                    base_parsed.netloc,
                    parsed.path,
                    parsed.query,
                    parsed.fragment,
                )
            )
        return cleaned
    return urljoin(base, cleaned)


def _parse_sitemap_body(content: bytes) -> tuple[str, list[DiscoveredEntry]]:
    """解析 sitemap XML,返回根类型和 loc 列表。"""
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as exc:
        raise ValueError(f"sitemap parse failed: {exc}") from exc
    root_name = root.tag.split("}", 1)[-1]
    if root_name not in {"urlset", "sitemapindex"}:
        raise ValueError(f"unsupported sitemap root: {root_name}")
    # namespace 形如 {http://www.sitemaps.org/schemas/sitemap/0.9}
    namespace = ""
    if root.tag.startswith("{"):
        namespace = root.tag.split("}", 1)[0] + "}"
    entries: list[DiscoveredEntry] = []
    for node in root.findall(f"{namespace}url"):
        loc = node.find(f"{namespace}loc")
        url = ((loc.text if loc is not None else "") or "").strip()
        if url:
            lastmod = node.find(f"{namespace}lastmod")
            entries.append(
                DiscoveredEntry(
                    title=url,
                    url=url,
                    published_at=parse_datetime(lastmod.text if lastmod is not None else None),
                )
            )
    for node in root.findall(f"{namespace}sitemap"):
        loc = node.find(f"{namespace}loc")
        url = ((loc.text if loc is not None else "") or "").strip()
        if url:
            entries.append(DiscoveredEntry(title=url, url=url))
    return root_name, entries


def _sitemap_url_entries(content: bytes) -> list[DiscoveredEntry]:
    root_name, entries = _parse_sitemap_body(content)
    if root_name != "urlset":
        raise ValueError("sitemapindex requires recursive expansion")
    return entries


def expand_sitemap_entries(
    session: Session,
    settings: Settings,
    *,
    content: bytes,
    current_url: str,
    depth: int = 0,
    seen: set[str] | None = None,
    remaining_files: list[int] | None = None,
) -> list[DiscoveredEntry]:
    if depth > MAX_SITEMAP_DEPTH:
        raise ValueError(f"sitemap nesting too deep: {current_url}")
    if remaining_files is None:
        remaining_files = [MAX_SITEMAP_FILES]
    if remaining_files[0] <= 0:
        raise ValueError("sitemap expansion limit exceeded")
    remaining_files[0] -= 1

    root_name, entries = _parse_sitemap_body(content)
    if root_name == "urlset":
        return entries

    seen = seen or {current_url}
    discovered: list[DiscoveredEntry] = []
    for entry in entries:
        sitemap_url = entry.url
        if sitemap_url in seen:
            continue
        seen.add(sitemap_url)
        response = session.get(
            sitemap_url,
            headers={},
            timeout=(10, 30),
            allow_redirects=True,
        )
        response.raise_for_status()
        discovered.extend(
            expand_sitemap_entries(
                session,
                settings,
                content=response.content,
                current_url=sitemap_url,
                depth=depth + 1,
                seen=seen,
                remaining_files=remaining_files,
            )
        )
    return discovered


def _parse_listing_body(feed: FeedConfig, content: bytes) -> list[DiscoveredEntry]:
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
    entries: list[DiscoveredEntry] = []
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
        entries.append(DiscoveredEntry(title=title, url=resolved))
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
                etag=etag,
                modified=modified,
                last_status="not_modified",
                last_error=None,
                entries=[],
            )
        response.raise_for_status()
        if source.feed and source.feed.type == "sitemap":
            entries = expand_sitemap_entries(
                session,
                settings,
                content=response.content,
                current_url=feed_url,
            )
        else:
            entries = _parse_feed_body(source, response.content)
        etag = response.headers.get("ETag") or etag
        modified = response.headers.get("Last-Modified") or modified
    except Exception as exc:
        return SourceDiscoveryResult(
            source_name=source.name,
            source_tags=source.tags,
            etag=etag,
            modified=modified,
            last_status="failed",
            last_error=str(exc),
            entries=[],
        )

    return SourceDiscoveryResult(
        source_name=source.name,
        source_tags=source.tags,
        etag=etag,
        modified=modified,
        last_status="success",
        last_error=None,
        entries=entries,
    )


def _settings_time_range(
    settings: Settings, *, since: str | None = None, until: str | None = None
) -> TimeRange:
    return build_time_range(
        since=since if since is not None else settings.discover_since,
        until=until if until is not None else settings.discover_until,
        since_days=settings.discover_since_days,
    )


def _add_candidate_and_queue_fetch(
    settings: Settings,
    conn: sqlite3.Connection,
    *,
    title: str,
    url: str,
    source_name: str,
    published_at: str | None,
    source_tags: list[str],
    source_content_markdown: str | None,
    source_content_metadata: dict[str, object] | None,
    time_range: TimeRange,
) -> tuple[bool, bool, bool]:
    if published_at and not time_range.contains(published_at):
        return False, False, True
    article_id, status, was_inserted = db.add_candidate(
        conn,
        title=title,
        url=url,
        source_name=source_name,
        published_at=published_at,
        source_tags=source_tags,
        source_content_markdown=source_content_markdown,
        source_content_metadata=source_content_metadata,
    )
    was_queued = False
    if status.value == "candidate" and db.latest_successful_fetch(conn, article_id) is None:
        _, was_queued = db.enqueue_article(
            conn,
            article_id=article_id,
            stage="fetch",
            range_since=time_range.since,
            range_until=time_range.until,
        )
    return was_inserted, was_queued, False


def discover_candidates(
    settings: Settings,
    conn: sqlite3.Connection,
    *,
    since: str | None = None,
    until: str | None = None,
) -> dict[str, int]:
    config = load_sources(settings.sources_path)
    time_range = _settings_time_range(settings, since=since, until=until)
    found = 0
    inserted = 0
    queued_fetch = 0
    skipped = 0
    out_of_range = 0
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
            for entry in result.entries:
                found += 1
                was_inserted, was_queued, was_out_of_range = _add_candidate_and_queue_fetch(
                    settings,
                    conn,
                    title=entry.title,
                    url=entry.url,
                    source_name=result.source_name,
                    published_at=entry.published_at,
                    source_tags=result.source_tags,
                    source_content_markdown=entry.source_content_markdown,
                    source_content_metadata=entry.source_content_metadata,
                    time_range=time_range,
                )
                if was_out_of_range:
                    out_of_range += 1
                    skipped += 1
                    continue
                if was_inserted:
                    inserted += 1
                else:
                    skipped += 1
                if was_queued:
                    queued_fetch += 1

    for candidate in manual_candidates(config):
        found += 1
        was_inserted, was_queued, was_out_of_range = _add_candidate_and_queue_fetch(
            settings,
            conn,
            title=candidate.title,
            url=candidate.url,
            source_name=candidate.source_name,
            published_at=candidate.published_at,
            source_tags=candidate.source_tags,
            source_content_markdown=None,
            source_content_metadata=None,
            time_range=time_range,
        )
        if was_out_of_range:
            out_of_range += 1
            skipped += 1
            continue
        if was_inserted:
            inserted += 1
        else:
            skipped += 1
        if was_queued:
            queued_fetch += 1

    return {
        "found": found,
        "inserted": inserted,
        "queued_fetch": queued_fetch,
        "skipped": skipped,
        "out_of_range": out_of_range,
        "sources_failed": sources_failed,
        "sources_not_modified": sources_not_modified,
    }
