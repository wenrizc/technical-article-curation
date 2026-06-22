import pytest
from pydantic import ValidationError

from tac.domain.models import EvaluationResult, FeedConfig, SourceConfig

VALID = {
    "decision": "accept",
    "dimensions": {
        "工程价值": "high",
        "技术深度": "high",
        "原创性": "medium",
        "可复用性": "high",
        "可读性": "high",
    },
    "summary": "一篇有长期工程价值的文章。",
    "tags": ["Architecture"],
    "recommendation_reason": "解释了取舍和边界。",
    "full_reasoning": "内部判断依据。",
}


def test_evaluation_result_accepts_strict_schema():
    result = EvaluationResult.model_validate(VALID)
    assert result.decision.value == "accept"
    assert result.dimensions.engineering_value.value == "high"


def test_evaluation_result_rejects_missing_field():
    data = dict(VALID)
    data.pop("full_reasoning")
    with pytest.raises(ValidationError):
        EvaluationResult.model_validate(data)


def test_evaluation_result_rejects_removed_confidence_field():
    data = {**VALID, "confidence": "high"}
    with pytest.raises(ValidationError):
        EvaluationResult.model_validate(data)


def test_feed_config_validates_direct_url():
    feed = FeedConfig.model_validate({"type": "direct", "url": "https://example.com/rss.xml"})

    assert feed.url == "https://example.com/rss.xml"


def test_feed_config_rejects_rsshub_full_url_route():
    with pytest.raises(ValidationError, match="feed.route"):
        FeedConfig.model_validate({"type": "rsshub", "route": "https://rsshub.app/zhihu/hot"})


def test_rsshub_source_defaults_to_summary_only_publish_policy():
    source = SourceConfig.model_validate(
        {"name": "zhihu", "feed": {"type": "rsshub", "route": "/zhihu/hot"}}
    )

    assert source.publish_policy == "summary_only"


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


def test_sitemap_and_listing_default_to_full_content_publish_policy():
    sitemap_source = SourceConfig.model_validate(
        {"name": "a", "feed": {"type": "sitemap", "url": "https://example.com/sitemap.xml"}}
    )
    listing_source = SourceConfig.model_validate(
        {
            "name": "b",
            "feed": {"type": "listing", "url": "https://example.com/blog", "link_selector": "a"},
        }
    )

    assert sitemap_source.publish_policy == "full_content"
    assert listing_source.publish_policy == "full_content"
