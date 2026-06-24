import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from tac.domain.models import EvaluationResult, FeedConfig, ManualUrl, SourceConfig

VALID = {
    "decision": "accept",
    "content_type": "research_article",
    "dimensions": {
        "领域相关性": "high",
        "长期价值": "high",
        "内容深度": "high",
        "原创性": "medium",
        "可迁移性": "high",
        "可读性": "high",
    },
    "summary": "一篇有长期参考价值的文章。",
    "tags": ["Architecture"],
    "recommendation_reason": "解释了取舍和边界。",
    "full_reasoning": "内部判断依据。",
}


def test_evaluation_result_accepts_strict_schema():
    result = EvaluationResult.model_validate(VALID)
    assert result.decision.value == "accept"
    assert result.content_type.value == "research_article"
    assert result.dimensions.long_term_value.value == "high"


def test_evaluation_result_rejects_missing_content_type():
    data = dict(VALID)
    data.pop("content_type")
    with pytest.raises(ValidationError):
        EvaluationResult.model_validate(data)


def test_evaluation_result_rejects_invalid_content_type():
    data = {**VALID, "content_type": "not_a_type"}
    with pytest.raises(ValidationError):
        EvaluationResult.model_validate(data)


def test_evaluation_result_rejects_old_dimensions():
    data = {
        **VALID,
        "dimensions": {
            "工程价值": "high",
            "技术深度": "high",
            "原创性": "medium",
            "可复用性": "high",
            "可读性": "high",
        },
    }
    with pytest.raises(ValidationError):
        EvaluationResult.model_validate(data)


def test_evaluation_result_rejects_missing_field():
    data = dict(VALID)
    data.pop("full_reasoning")
    with pytest.raises(ValidationError):
        EvaluationResult.model_validate(data)


def test_evaluation_result_rejects_removed_confidence_field():
    data = {**VALID, "confidence": "high"}
    with pytest.raises(ValidationError):
        EvaluationResult.model_validate(data)


def test_zh_cn_few_shot_outputs_match_pydantic_schema():
    expected_fields = set(EvaluationResult.model_fields)
    for path in sorted(Path("prompts/zh-CN/few_shots").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))

        assert set(payload) == expected_fields, path.name
        result = EvaluationResult.model_validate(payload)
        assert result.tags, path.name


def test_feed_config_validates_direct_url():
    feed = FeedConfig.model_validate({"type": "direct", "url": "https://example.com/rss.xml"})

    assert feed.url == "https://example.com/rss.xml"


def test_feed_config_rejects_rsshub_full_url_route():
    with pytest.raises(ValidationError, match="feed.route"):
        FeedConfig.model_validate({"type": "rsshub", "route": "https://rsshub.app/zhihu/hot"})


def test_manual_url_accepts_yaml_datetime_published_at():
    item = ManualUrl.model_validate(
        {
            "url": "https://example.com/a",
            "published_at": datetime(2026, 6, 24, 9, 0, tzinfo=UTC),
        }
    )

    assert item.published_at == "2026-06-24T09:00:00Z"


def test_rsshub_source_accepts_route():
    source = SourceConfig.model_validate(
        {"name": "zhihu", "feed": {"type": "rsshub", "route": "/zhihu/hot"}}
    )

    assert source.feed is not None
    assert source.feed.route == "/zhihu/hot"


def test_feed_config_validates_sitemap_url():
    feed = FeedConfig.model_validate({"type": "sitemap", "url": "https://example.com/sitemap.xml"})

    assert feed.url == "https://example.com/sitemap.xml"


def test_feed_config_sitemap_requires_url():
    with pytest.raises(ValidationError, match="feed.url"):
        FeedConfig.model_validate({"type": "sitemap"})


def test_feed_config_listing_requires_url_and_link_selector():
    with pytest.raises(ValidationError, match="feed.url"):
        FeedConfig.model_validate({"type": "listing", "link_selector": "main a.post-link"})
    with pytest.raises(ValidationError, match="feed.link_selector"):
        FeedConfig.model_validate({"type": "listing", "url": "https://example.com/blog"})


def test_feed_config_listing_accepts_optional_fields():
    feed = FeedConfig.model_validate(
        {
            "type": "listing",
            "url": "https://example.com/blog",
            "link_selector": "main article a.post-link",
            "title_selector": "main article h2",
            "url_patterns": ["/blog/20", "/posts/"],
            "base_url": "https://example.com",
        }
    )

    assert feed.link_selector == "main article a.post-link"
    assert feed.title_selector == "main article h2"
    assert feed.url_patterns == ["/blog/20", "/posts/"]
    assert feed.base_url == "https://example.com"


def test_feed_config_listing_rejects_invalid_base_url():
    with pytest.raises(ValidationError, match="feed.base_url"):
        FeedConfig.model_validate(
            {
                "type": "listing",
                "url": "https://example.com/blog",
                "link_selector": "a",
                "base_url": "not-a-url",
            }
        )


def test_sitemap_and_listing_sources_validate():
    sitemap_source = SourceConfig.model_validate(
        {"name": "a", "feed": {"type": "sitemap", "url": "https://example.com/sitemap.xml"}}
    )
    listing_source = SourceConfig.model_validate(
        {
            "name": "b",
            "feed": {"type": "listing", "url": "https://example.com/blog", "link_selector": "a"},
        }
    )

    assert sitemap_source.feed is not None
    assert listing_source.feed is not None
