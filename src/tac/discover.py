from __future__ import annotations

import feedparser

from . import db
from .models import CandidateArticle
from .sources import load_sources, manual_candidates


def discover_candidates(settings, conn) -> dict[str, int]:
    config = load_sources(settings.sources_path)
    found = 0
    inserted = 0
    duplicates = 0

    for source in config.sources:
        if not source.enabled or not source.rss_url:
            continue
        parsed = feedparser.parse(source.rss_url)
        for entry in parsed.entries:
            url = getattr(entry, "link", None)
            title = getattr(entry, "title", None) or url
            if not url:
                continue
            found += 1
            _, status, was_inserted = db.add_candidate(
                conn,
                title=title,
                url=url,
                source_name=source.name,
                source_tags=source.tags,
            )
            if was_inserted:
                inserted += 1
            elif status.value == "duplicate":
                duplicates += 1

    for candidate in manual_candidates(config):
        found += 1
        _, status, was_inserted = db.add_candidate(
            conn,
            title=candidate.title,
            url=candidate.url,
            source_name=candidate.source_name,
            source_tags=candidate.source_tags,
        )
        if was_inserted:
            inserted += 1
        elif status.value == "duplicate":
            duplicates += 1

    return {"found": found, "inserted": inserted, "duplicates": duplicates}

