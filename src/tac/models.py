from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ArticleStatus(str, Enum):
    candidate = "candidate"
    accepted = "accepted"
    rejected = "rejected"
    low_confidence = "low_confidence"
    archived = "archived"


class Decision(str, Enum):
    accept = "accept"
    reject = "reject"
    low_confidence = "low_confidence"


class Level(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class Dimensions(BaseModel):
    engineering_value: Level = Field(alias="工程价值")
    technical_depth: Level = Field(alias="技术深度")
    originality: Level = Field(alias="原创性")
    reusability: Level = Field(alias="可复用性")
    readability: Level = Field(alias="可读性")

    model_config = {"populate_by_name": True}


class EvaluationResult(BaseModel):
    decision: Decision
    confidence: Level
    dimensions: Dimensions
    summary: str
    tags: list[str]
    recommendation_reason: str
    full_reasoning: str

    @field_validator("summary", "recommendation_reason", "full_reasoning")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be empty")
        return value.strip()

    @field_validator("tags")
    @classmethod
    def tags_non_empty(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        if not cleaned:
            raise ValueError("tags must not be empty")
        return cleaned


class ManualUrl(BaseModel):
    url: str
    title: str | None = None
    tags: list[str] = Field(default_factory=list)


class SourceConfig(BaseModel):
    name: str
    enabled: bool = True
    display: Literal["default", "compact", "featured"] = "default"
    rss_url: str | None = None
    site_url: str | None = None
    tags: list[str] = Field(default_factory=list)
    manual_urls: list[ManualUrl] = Field(default_factory=list)

    @field_validator("manual_urls", mode="before")
    @classmethod
    def coerce_manual_urls(cls, value: Any) -> Any:
        if value is None:
            return []
        result: list[Any] = []
        for item in value:
            if isinstance(item, str):
                result.append({"url": item})
            else:
                result.append(item)
        return result


class SourcesFile(BaseModel):
    sources: list[SourceConfig] = Field(default_factory=list)
    manual_urls: list[ManualUrl] = Field(default_factory=list)

    @field_validator("manual_urls", mode="before")
    @classmethod
    def coerce_manual_urls(cls, value: Any) -> Any:
        if value is None:
            return []
        result: list[Any] = []
        for item in value:
            if isinstance(item, str):
                result.append({"url": item})
            else:
                result.append(item)
        return result


class CandidateArticle(BaseModel):
    title: str
    url: str
    source_name: str
    source_tags: list[str] = Field(default_factory=list)
