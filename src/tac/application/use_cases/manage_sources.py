from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from pydantic import ValidationError

from tac.domain.models import SourcesFile
from tac.shared.utils import atomic_write_text, short_hash


class SourceConflict(RuntimeError):
    pass


class SourceValidationError(ValueError):
    pass


@dataclass(frozen=True)
class SourcesYaml:
    content: str
    content_hash: str


def read_sources_yaml(path: Path) -> SourcesYaml:
    content = path.read_text(encoding="utf-8")
    return SourcesYaml(content=content, content_hash=short_hash(content, length=16))


def _validate_url(url: str) -> None:
    scheme = urlsplit(url).scheme.lower()
    if scheme not in {"http", "https"}:
        raise SourceValidationError(f"unsupported URL scheme: {url}")


def validate_sources_yaml(content: str) -> SourcesFile:
    try:
        data = yaml.safe_load(content) or {}
        parsed = SourcesFile.model_validate(data)
    except (yaml.YAMLError, ValidationError) as exc:
        raise SourceValidationError(str(exc)) from exc
    for item in parsed.manual_urls:
        _validate_url(item.url)
    for source in parsed.sources:
        if source.feed and source.feed.url:
            _validate_url(source.feed.url)
        if source.feed and source.feed.instance:
            _validate_url(source.feed.instance)
        if source.site_url:
            _validate_url(source.site_url)
        for item in source.manual_urls:
            _validate_url(item.url)
    return parsed


def save_sources_yaml(path: Path, *, content: str, previous_hash: str) -> SourcesYaml:
    current = read_sources_yaml(path)
    if current.content_hash != previous_hash:
        raise SourceConflict("sources file changed")
    validate_sources_yaml(content)
    backup = path.with_name(f"{path.name}.bak")
    if path.exists():
        shutil.copyfile(path, backup)
    atomic_write_text(path, content)
    try:
        directory_fd = os.open(path.parent, os.O_RDONLY)
    except OSError:
        return read_sources_yaml(path)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    return read_sources_yaml(path)
