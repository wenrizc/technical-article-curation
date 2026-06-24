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


class TagStatus(str, Enum):
    active = "active"
    disabled = "disabled"


class TagCandidateStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class Decision(str, Enum):
    accept = "accept"
    reject = "reject"
    low_confidence = "low_confidence"


class Level(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class ContentType(str, Enum):
    technical_article = "technical_article"
    engineering_case = "engineering_case"
    research_article = "research_article"
    research_reflection = "research_reflection"
    learning_path = "learning_path"
    personal_reflection = "personal_reflection"
    career_experience = "career_experience"
    tooling_note = "tooling_note"


class Dimensions(BaseModel):
    domain_relevance: Level = Field(alias="领域相关性")
    long_term_value: Level = Field(alias="长期价值")
    content_depth: Level = Field(alias="内容深度")
    originality: Level = Field(alias="原创性")
    transferability: Level = Field(alias="可迁移性")
    readability: Level = Field(alias="可读性")

    model_config = {"populate_by_name": True, "extra": "forbid"}


class EvaluationResult(BaseModel):
    decision: Decision
    content_type: ContentType
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
    published_at: str | None = None
    tags: list[str] = Field(default_factory=list)


class FeedConfig(BaseModel):
    type: Literal["direct", "rsshub", "sitemap", "listing"]
    url: str | None = None
    route: str | None = None
    instance: str | None = None
    params: dict[str, str | int | bool] = Field(default_factory=dict)
    # listing 类型专用:从列表页抽取文章链接的 CSS 选择器。
    link_selector: str | None = None
    # listing 可选:抽取标题的 CSS 选择器,默认取 <a> 自身文本。
    title_selector: str | None = None
    # listing 可选:只保留 URL 中包含任一子串的链接,空表示不过滤。
    url_patterns: list[str] = Field(default_factory=list)
    # listing 可选:解析相对链接的基准地址,默认取 listing url 的 origin。
    base_url: str | None = None

    model_config = {"extra": "forbid"}

    @staticmethod
    def _require_http_url(field: str, value: str | None) -> None:
        """校验字段必须是 http/https 的完整 URL。"""
        if not value:
            raise ValueError(f"{field} is required")
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"{field} must be an http or https URL")

    @model_validator(mode="after")
    def validate_feed(self) -> FeedConfig:
        if self.type in {"direct", "sitemap"}:
            self._require_http_url("feed.url", self.url)
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
        if self.type == "listing":
            self._require_http_url("feed.url", self.url)
            if not (self.link_selector and self.link_selector.strip()):
                raise ValueError(
                    "feed.link_selector is required and must not be empty when feed.type is listing"
                )
            if self.base_url is not None:
                self._require_http_url("feed.base_url", self.base_url)
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
    published_at: str | None = None
    source_tags: list[str] = Field(default_factory=list)
    publish_policy: Literal["full_content", "summary_only"] = "full_content"
