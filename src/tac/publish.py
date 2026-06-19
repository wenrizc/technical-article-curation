from __future__ import annotations

import json
from pathlib import Path

from . import db
from .utils import yaml_scalar


def _frontmatter(article, tags: list[str]) -> str:
    tag_lines = "\n".join(f"  - {yaml_scalar(tag)}" for tag in tags)
    return (
        "---\n"
        f"title: {yaml_scalar(article['title'])}\n"
        f"url: {yaml_scalar(article['url'])}\n"
        f"source: {yaml_scalar(article['source_name'])}\n"
        f"collected_at: {yaml_scalar(article['collected_at'] or '')}\n"
        "tags:\n"
        f"{tag_lines}\n"
        "---\n\n"
    )


def _source_block(article, fetched_at: str) -> str:
    return (
        "> 来源信息\n"
        f">\n> - 来源：{article['source_name']}\n"
        f"> - 原文：{article['url']}\n"
        f"> - 抓取时间：{fetched_at}\n\n"
    )


def _public_record(article, tags: list[str], dimensions: dict) -> dict:
    slug = article["slug"]
    return {
        "slug": slug,
        "title": article["title"],
        "url": article["url"],
        "source": article["source_name"],
        "collected_at": article["collected_at"],
        "summary": article["summary"],
        "tags": tags,
        "recommendation_reason": article["recommendation_reason"],
        "dimensions": dimensions,
        "markdown_path": f"articles/{slug}.md",
    }


def publish_public(settings, conn) -> dict[str, int]:
    public_dir: Path = settings.public_dir
    articles_dir = public_dir / "articles"
    articles_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for article in db.accepted_articles_for_publish(conn):
        tags = json.loads(article["tags"])
        dimensions = json.loads(article["dimensions"])
        record = _public_record(article, tags, dimensions)
        records.append(record)
        slug = article["slug"]
        md = (
            _frontmatter(article, tags)
            + _source_block(article, article["fetched_at"])
            + article["content_markdown"].strip()
            + "\n"
        )
        (articles_dir / f"{slug}.md").write_text(md, encoding="utf-8")
        (articles_dir / f"{slug}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    (public_dir / "index.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"published": len(records)}

