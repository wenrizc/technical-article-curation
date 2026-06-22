from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator


class ArticleStatus(str, Enum):
    candidate = "candidate"
    accepted = "accepted"
    rejected = "rejected"
    low_confidence = "low_confidence"


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
    dimensions: Dimensions
    summary: str
    tags: list[str]
    recommendation_reason: str
    full_reasoning: str

    model_config = {"extra": "forbid"}

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


class FeedConfig(BaseModel):
    type: Literal["direct", "rsshub"]
    url: str | None = None
    route: str | None = None
    instance: str | None = None
    params: dict[str, str | int | bool] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def validate_feed(self) -> FeedConfig:
        if self.type == "direct":
            if not self.url:
                raise ValueError("feed.url is required when feed.type is direct")
            parsed = urlparse(self.url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("feed.url must be an http or https URL")
        if self.type == "rsshub":
            if not self.route:
                raise ValueError("feed.route is required when feed.type is rsshub")
            parsed_route = urlparse(self.route)
            if (
                not self.route.startswith("/")
                or parsed_route.scheme
                or parsed_route.netloc
                or parsed_route.fragment
            ):
                raise ValueError("feed.route must be an absolute path without host or fragment")
        if self.instance:
            parsed_instance = urlparse(self.instance)
            if parsed_instance.scheme not in {"http", "https"} or not parsed_instance.netloc:
                raise ValueError("feed.instance must be an http or https URL")
        for key in self.params:
            if not key.strip():
                raise ValueError("feed.params keys must not be empty")
        return self


class SourceConfig(BaseModel):
    name: str
    enabled: bool = True
    display: Literal["default", "compact", "featured"] = "default"
    feed: FeedConfig | None = None
    site_url: str | None = None
    tags: list[str] = Field(default_factory=list)
    publish_policy: Literal["full_content", "summary_only"] | None = None
    manual_urls: list[ManualUrl] = Field(default_factory=list)

    model_config = {"extra": "forbid"}

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

    @model_validator(mode="after")
    def default_publish_policy(self) -> SourceConfig:
        if self.publish_policy is None:
            self.publish_policy = (
                "summary_only" if self.feed and self.feed.type == "rsshub" else "full_content"
            )
        return self


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
    publish_policy: Literal["full_content", "summary_only"] = "full_content"
