import sys
from concurrent.futures import Future
from types import SimpleNamespace

import pytest

from tac.application.use_cases.evaluate_articles import evaluate_pending
from tac.application.use_cases.fetch_articles import (
    FetchError,
    FetchResult,
    fetch_pending,
    fetch_url,
)
from tac.infrastructure.db import store as db
from tac.settings import Settings


def test_fetch_url_fails_when_crawler4ai_disabled():
    with pytest.raises(FetchError, match="disabled"):
        fetch_url("https://example.com/article", crawler4ai_enabled=False)


def test_fetch_url_falls_back_to_http_strategy_when_browser_missing(monkeypatch):
    class FakeCrawler:
        def __init__(self, crawler_strategy=None):
            self.crawler_strategy = crawler_strategy

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def arun(self, url):
            if self.crawler_strategy is None:
                raise RuntimeError(
                    "BrowserType.launch: Executable doesn't exist. "
                    "Please run the following command to download new browsers: playwright install"
                )
            return SimpleNamespace(
                markdown="# Article\n\nBody",
                status_code=200,
                url=url,
            )

    class FakeHTTPCrawlerConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeAsyncHTTPCrawlerStrategy:
        def __init__(self, config):
            self.config = config

    monkeypatch.setitem(sys.modules, "crawl4ai", SimpleNamespace(AsyncWebCrawler=FakeCrawler))
    monkeypatch.setitem(
        sys.modules,
        "crawl4ai.async_crawler_strategy",
        SimpleNamespace(
            AsyncHTTPCrawlerStrategy=FakeAsyncHTTPCrawlerStrategy,
            HTTPCrawlerConfig=FakeHTTPCrawlerConfig,
        ),
    )

    result = fetch_url("https://example.com/article", crawler4ai_enabled=True)

    assert result.markdown == "# Article\n\nBody"
    assert result.metadata["crawler"] == "crawler4ai-http"
    assert "fallback_reason" in result.metadata


def test_fetch_pending_records_crawler4ai_failure(tmp_path, monkeypatch):
    conn = db.connect(tmp_path / "state.db")
    db.migrate(conn)
    article_id, _, _ = db.add_candidate(
        conn,
        title="Title",
        url="https://example.com/article",
        source_name="s",
    )

    settings = Settings(
        state_db=tmp_path / "state.db",
        sources_path=tmp_path / "sources.yaml",
        public_dir=tmp_path / "public",
        max_retry=3,
        model="fixture-model",
        base_url="https://example.invalid/v1",
        api_key=None,
        ai_response_path=None,
        fetch_fixture_path=None,
        crawler4ai_enabled=True,
        fetch_delay_seconds=0,
        evaluation_max_attempts=3,
        prompt_language="zh-CN",
        prompt_path=tmp_path / "evaluate.md",
        few_shot_dir=tmp_path / "few_shots",
    )

    def fail(url, *, crawler4ai_enabled=True, timeout_seconds=90):
        raise FetchError("crawler4ai returned no markdown")

    monkeypatch.setattr("tac.application.use_cases.fetch_articles.fetch_url", fail)

    result = fetch_pending(settings, conn)
    fetch = conn.execute("SELECT * FROM fetches WHERE article_id = ?", (article_id,)).fetchone()
    article = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()

    assert result["failed"] == 1
    assert fetch["status"] == "failed"
    assert "no markdown" in fetch["error"]
    assert article["status"] == "candidate"


def test_fetch_pending_prefers_feed_entry_content(tmp_path, monkeypatch):
    conn = db.connect(tmp_path / "state.db")
    db.migrate(conn)
    article_id, _, _ = db.add_candidate(
        conn,
        title="RSSHub Article",
        url="https://example.com/rsshub/article",
        source_name="rsshub",
        source_content_markdown="# RSS Body\n\nFull text from feed.",
        source_content_metadata={"feed_type": "rsshub"},
    )
    settings = Settings(
        state_db=tmp_path / "state.db",
        sources_path=tmp_path / "sources.yaml",
        public_dir=tmp_path / "public",
        max_retry=3,
        model="fixture-model",
        base_url="https://example.invalid/v1",
        api_key=None,
        ai_response_path=None,
        fetch_fixture_path=None,
        crawler4ai_enabled=False,
        fetch_delay_seconds=0,
        evaluation_max_attempts=3,
        prompt_language="zh-CN",
        prompt_path=tmp_path / "evaluate.md",
        few_shot_dir=tmp_path / "few_shots",
    )

    def unexpected_fetch(*args, **kwargs):
        raise AssertionError("Crawler4AI should not be called when feed content is available")

    monkeypatch.setattr("tac.application.use_cases.fetch_articles.fetch_url", unexpected_fetch)

    result = fetch_pending(settings, conn)
    fetch = conn.execute("SELECT * FROM fetches WHERE article_id = ?", (article_id,)).fetchone()
    evaluate_queue = conn.execute(
        "SELECT * FROM article_queue WHERE article_id = ? AND stage = 'evaluate'",
        (article_id,),
    ).fetchone()

    assert result["succeeded"] == 1
    assert fetch["content_markdown"] == "# RSS Body\n\nFull text from feed."
    assert '"crawler": "feed-entry"' in fetch["crawler_metadata"]
    assert evaluate_queue["status"] == "queued"


def test_fetch_pending_falls_back_to_crawler_when_feed_entry_content_too_large(
    tmp_path, monkeypatch
):
    conn = db.connect(tmp_path / "state.db")
    db.migrate(conn)
    article_id, _, _ = db.add_candidate(
        conn,
        title="Large Feed Article",
        url="https://example.com/large",
        source_name="rss",
        source_content_markdown="x" * 20,
    )
    settings = Settings(
        state_db=tmp_path / "state.db",
        sources_path=tmp_path / "sources.yaml",
        public_dir=tmp_path / "public",
        max_retry=3,
        model="fixture-model",
        base_url="https://example.invalid/v1",
        api_key=None,
        ai_response_path=None,
        fetch_fixture_path=None,
        crawler4ai_enabled=True,
        fetch_delay_seconds=0,
        evaluation_max_attempts=3,
        prompt_language="zh-CN",
        prompt_path=tmp_path / "evaluate.md",
        few_shot_dir=tmp_path / "few_shots",
        fetch_max_markdown_bytes=10,
    )

    def fetch(_url, *, crawler4ai_enabled=True, timeout_seconds=90):
        return FetchResult(markdown="short", metadata={"crawler": "crawler4ai"})

    monkeypatch.setattr("tac.application.use_cases.fetch_articles.fetch_url", fetch)

    result = fetch_pending(settings, conn)
    fetch_row = conn.execute("SELECT * FROM fetches WHERE article_id = ?", (article_id,)).fetchone()

    assert result["succeeded"] == 1
    assert fetch_row["content_markdown"] == "short"
    assert '"crawler": "crawler4ai"' in fetch_row["crawler_metadata"]


def test_fetch_pending_skips_out_of_range_after_page_date_extraction(tmp_path, monkeypatch):
    conn = db.connect(tmp_path / "state.db")
    db.migrate(conn)
    article_id, _, _ = db.add_candidate(
        conn,
        title="Title",
        url="https://example.com/article",
        source_name="s",
    )
    db.enqueue_article(
        conn,
        article_id=article_id,
        stage="fetch",
        range_since="2026-01-01T00:00:00Z",
        range_until="2027-01-01T00:00:00Z",
    )
    settings = Settings(
        state_db=tmp_path / "state.db",
        sources_path=tmp_path / "sources.yaml",
        public_dir=tmp_path / "public",
        max_retry=3,
        model="fixture-model",
        base_url="https://example.invalid/v1",
        api_key=None,
        ai_response_path=None,
        fetch_fixture_path=None,
        crawler4ai_enabled=True,
        fetch_delay_seconds=0,
        evaluation_max_attempts=3,
        prompt_language="zh-CN",
        prompt_path=tmp_path / "evaluate.md",
        few_shot_dir=tmp_path / "few_shots",
    )

    def fetch(_url, *, crawler4ai_enabled=True, timeout_seconds=90):
        return FetchResult(
            markdown="# Body",
            metadata={"crawler": "fixture"},
            published_at="2025-06-01T00:00:00Z",
        )

    monkeypatch.setattr("tac.application.use_cases.fetch_articles.fetch_url", fetch)

    result = fetch_pending(settings, conn)
    article = db.get_article(conn, article_id)
    queue = conn.execute(
        "SELECT * FROM article_queue WHERE article_id = ?", (article_id,)
    ).fetchone()
    evaluate_queue_count = conn.execute(
        "SELECT COUNT(*) FROM article_queue WHERE article_id = ? AND stage = 'evaluate'",
        (article_id,),
    ).fetchone()[0]

    assert result["skipped"] == 1
    assert article["published_at"] == "2025-06-01T00:00:00Z"
    assert article["status"] == "skipped_out_of_range"
    assert queue["status"] == "skipped_out_of_range"
    assert evaluate_queue_count == 0
    assert evaluate_pending(settings, conn)["attempted"] == 0


def test_fetch_pending_uses_configured_concurrency(tmp_path, monkeypatch):
    conn = db.connect(tmp_path / "state.db")
    db.migrate(conn)
    for index in range(2):
        db.add_candidate(
            conn,
            title=f"Title {index}",
            url=f"https://example.com/article-{index}",
            source_name="s",
        )
    settings = Settings(
        state_db=tmp_path / "state.db",
        sources_path=tmp_path / "sources.yaml",
        public_dir=tmp_path / "public",
        max_retry=3,
        model="fixture-model",
        base_url="https://example.invalid/v1",
        api_key=None,
        ai_response_path=None,
        fetch_fixture_path=tmp_path / "article.md",
        crawler4ai_enabled=False,
        fetch_delay_seconds=0,
        evaluation_max_attempts=3,
        prompt_language="zh-CN",
        prompt_path=tmp_path / "evaluate.md",
        few_shot_dir=tmp_path / "few_shots",
        fetch_max_concurrency=3,
    )
    settings.fetch_fixture_path.write_text("# Body", encoding="utf-8")
    seen = {}

    class FakeExecutor:
        def __init__(self, max_workers):
            seen["max_workers"] = max_workers

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def submit(self, fn, *args):
            future = Future()
            future.set_result(fn(*args))
            return future

    monkeypatch.setattr("tac.application.use_cases.fetch_articles.ThreadPoolExecutor", FakeExecutor)

    result = fetch_pending(settings, conn)

    assert result["succeeded"] == 2
    assert seen["max_workers"] == 3
