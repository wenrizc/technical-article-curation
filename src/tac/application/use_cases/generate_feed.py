from __future__ import annotations

import hashlib
import html
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import format_datetime, parsedate_to_datetime
from urllib.parse import urljoin
from xml.etree.ElementTree import Element, SubElement, tostring

from tac.application.use_cases import manage_articles as articles
from tac.settings import Settings


@dataclass(frozen=True)
class PublicFeed:
    content: bytes
    etag: str
    last_modified: str | None


def _parse_iso(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _item_time(item: dict[str, object]) -> datetime | None:
    return (
        _parse_iso(item.get("published_at"))
        or _parse_iso(item.get("collected_at"))
        or _parse_iso(item.get("updated_at"))
        or _parse_iso(item.get("created_at"))
    )


def _http_date(value: datetime | None) -> str | None:
    if value is None:
        return None
    return format_datetime(value.astimezone(UTC), usegmt=True)


def _article_url(settings: Settings, slug: object) -> str:
    return urljoin(settings.public_base_url.rstrip("/") + "/", f"api/public/articles/{slug}")


def _description(item: dict[str, object]) -> str:
    parts = [
        str(item.get("summary") or "").strip(),
        str(item.get("recommendation_reason") or "").strip(),
        f"原文：{item.get('url')}",
    ]
    return "\n\n".join(part for part in parts if part)


def _generate_with_feedgen(
    settings: Settings, items: list[dict[str, object]], last_build: datetime | None
) -> bytes | None:
    try:
        from feedgen.feed import FeedGenerator  # type: ignore
    except Exception:
        return None

    fg = FeedGenerator()
    fg.title(settings.public_feed_title)
    fg.link(href=settings.public_base_url, rel="alternate")
    fg.description(settings.public_feed_description)
    fg.language(settings.public_feed_language)
    fg.ttl(settings.public_feed_ttl_minutes)
    if last_build is not None:
        fg.lastBuildDate(last_build)
    for item in items:
        url = _article_url(settings, item.get("slug"))
        entry = fg.add_entry()
        entry.id(url)
        entry.guid(url, permalink=True)
        entry.title(str(item.get("title") or ""))
        entry.link(href=url)
        entry.source(url=str(item.get("url") or ""), title=str(item.get("source") or ""))
        entry.description(html.escape(_description(item)))
        published = _item_time(item)
        if published is not None:
            entry.pubDate(published)
        for tag in item.get("tags") or []:
            entry.category({"term": str(tag)})
    return bytes(fg.rss_str(pretty=True))


def _text(parent: Element, name: str, value: object) -> Element:
    child = SubElement(parent, name)
    child.text = str(value)
    return child


def _generate_with_stdlib(
    settings: Settings, items: list[dict[str, object]], last_build: datetime | None
) -> bytes:
    rss = Element("rss", {"version": "2.0"})
    channel = SubElement(rss, "channel")
    _text(channel, "title", settings.public_feed_title)
    _text(channel, "link", settings.public_base_url)
    _text(channel, "description", settings.public_feed_description)
    _text(channel, "language", settings.public_feed_language)
    _text(channel, "ttl", settings.public_feed_ttl_minutes)
    if last_build is not None:
        _text(channel, "lastBuildDate", format_datetime(last_build, usegmt=True))
    for item in items:
        entry = SubElement(channel, "item")
        url = _article_url(settings, item.get("slug"))
        _text(entry, "guid", url).set("isPermaLink", "true")
        _text(entry, "title", item.get("title") or "")
        _text(entry, "link", url)
        _text(entry, "description", _description(item))
        source = _text(entry, "source", item.get("source") or "")
        source.set("url", str(item.get("url") or ""))
        published = _item_time(item)
        if published is not None:
            _text(entry, "pubDate", format_datetime(published, usegmt=True))
        for tag in item.get("tags") or []:
            _text(entry, "category", tag)
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(
        rss, encoding="utf-8", short_empty_elements=False
    )


def generate_public_feed(
    settings: Settings, conn: sqlite3.Connection, *, limit: int = 50
) -> PublicFeed:
    page = articles.list_public_articles(conn, page=1, page_size=limit)
    items = page.items
    item_times = [time for item in items if (time := _item_time(item)) is not None]
    last_build = max(item_times, default=None)
    content = _generate_with_feedgen(settings, items, last_build) or _generate_with_stdlib(
        settings, items, last_build
    )
    etag = '"' + hashlib.sha256(content).hexdigest() + '"'
    return PublicFeed(content=content, etag=etag, last_modified=_http_date(last_build))


def is_not_modified(
    feed: PublicFeed, *, if_none_match: str | None, if_modified_since: str | None
) -> bool:
    if if_none_match:
        return if_none_match.strip() == feed.etag
    if if_modified_since and feed.last_modified:
        try:
            requested = parsedate_to_datetime(if_modified_since)
            current = parsedate_to_datetime(feed.last_modified)
        except (TypeError, ValueError):
            return False
        return requested >= current
    return False
