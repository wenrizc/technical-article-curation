from __future__ import annotations

from pathlib import Path

import yaml

from tac.domain.models import CandidateArticle, SourcesFile


def load_sources(path: Path) -> SourcesFile:
    if not path.exists():
        raise FileNotFoundError(f"sources file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return SourcesFile.model_validate(data)


def manual_candidates(config: SourcesFile) -> list[CandidateArticle]:
    candidates: list[CandidateArticle] = []
    for item in config.manual_urls:
        candidates.append(
            CandidateArticle(
                title=item.title or item.url,
                url=item.url,
                source_name="manual",
                published_at=item.published_at,
                source_tags=item.tags,
                publish_policy="full_content",
            )
        )
    for source in config.sources:
        if not source.enabled:
            continue
        for item in source.manual_urls:
            candidates.append(
                CandidateArticle(
                    title=item.title or item.url,
                    url=item.url,
                    source_name=source.name,
                    published_at=item.published_at,
                    source_tags=[*source.tags, *item.tags],
                    publish_policy=source.publish_policy or "full_content",
                )
            )
    return candidates
