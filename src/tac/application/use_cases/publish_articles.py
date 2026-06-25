from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from tac.infrastructure.db import store as db
from tac.settings import Settings
from tac.shared.utils import atomic_write_text, yaml_scalar


def _frontmatter(article: sqlite3.Row, tags: list[str]) -> str:
    tag_lines = "\n".join(f"  - {yaml_scalar(tag)}" for tag in tags)
    return (
        "---\n"
        f"title: {yaml_scalar(article['title'])}\n"
        f"url: {yaml_scalar(article['url'])}\n"
        f"source: {yaml_scalar(article['source_name'])}\n"
        f"content_type: {yaml_scalar(article['content_type'])}\n"
        f"published_at: {yaml_scalar(article['published_at'] or '')}\n"
        f"collected_at: {yaml_scalar(article['collected_at'] or '')}\n"
        "tags:\n"
        f"{tag_lines}\n"
        "---\n\n"
    )


def _source_block(article: sqlite3.Row, fetched_at: str) -> str:
    return (
        "> 来源信息\n"
        f">\n> - 来源：{article['source_name']}\n"
        f"> - 原文：{article['url']}\n"
        f"> - 原文时间：{article['published_at'] or '未知'}\n"
        f"> - 抓取时间：{fetched_at}\n\n"
    )


def _public_record(article: sqlite3.Row, tags: list[str]) -> dict[str, object]:
    slug = article["slug"]
    record = {
        "slug": slug,
        "title": article["title"],
        "url": article["url"],
        "source": article["source_name"],
        "published_at": article["published_at"],
        "collected_at": article["collected_at"],
        "content_type": article["content_type"],
        "summary": article["summary"],
        "tags": tags,
        "recommendation_reason": article["recommendation_reason"],
        "markdown_path": f"articles/{slug}.md",
    }
    return record


def publish_public(settings: Settings, conn: sqlite3.Connection) -> dict[str, int]:
    public_dir: Path = settings.public_dir
    articles_dir = public_dir / "articles"
    articles_dir.mkdir(parents=True, exist_ok=True)
    records = []
    expected_files: set[Path] = set()
    for article in db.accepted_articles_for_publish(conn):
        tags = json.loads(article["tags"])
        record = _public_record(article, tags)
        records.append(record)
        slug = article["slug"]
        md_path = articles_dir / f"{slug}.md"
        json_path = articles_dir / f"{slug}.json"
        expected_files.add(json_path)
        expected_files.add(md_path)
        md = (
            _frontmatter(article, tags)
            + _source_block(article, article["fetched_at"])
            + article["content_markdown"].strip()
            + "\n"
        )
        atomic_write_text(md_path, md)
        atomic_write_text(json_path, json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    for path in articles_dir.glob("*"):
        if path.is_file() and path.suffix in {".json", ".md"} and path not in expected_files:
            path.unlink()
    atomic_write_text(
        public_dir / "index.json",
        json.dumps(records, ensure_ascii=False, indent=2) + "\n",
    )
    return {"published": len(records)}
