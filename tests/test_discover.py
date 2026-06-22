from concurrent.futures import Future

from tac.application.use_cases.discover_articles import discover_candidates
from tac.infrastructure.db import store as db
from tac.settings import Settings


def _settings(tmp_path, sources_text=None):
    sources = tmp_path / "sources.yaml"
    sources.write_text(
        sources_text
        or """
sources:
  - name: example
    feed:
      type: direct
      url: https://example.com/feed.xml
""",
        encoding="utf-8",
    )
    return Settings(
        state_db=tmp_path / "state.db",
        sources_path=sources,
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


class FakeResponse:
    def __init__(self, *, status_code=200, content=b"", headers=None, error=None):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.headers = {}
        self.calls = []

    def get(self, url, headers, timeout, allow_redirects):
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "timeout": timeout,
                "allow_redirects": allow_redirects,
            }
        )
        return self.responses.pop(0)


def test_discover_records_source_state_and_uses_conditional_headers(tmp_path, monkeypatch):
    conn = db.connect(tmp_path / "state.db")
    db.migrate(conn)
    settings = _settings(tmp_path)
    db.record_source_state(
        conn,
        source_name="example",
        etag='"abc"',
        modified="Wed, 01 Jan 2025 00:00:00 GMT",
        last_status="success",
    )
    feed = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><item><title>Post</title><link>https://example.com/post</link></item></channel></rss>
"""
    session = FakeSession(
        [
            FakeResponse(
                content=feed,
                headers={"ETag": '"def"', "Last-Modified": "Thu, 02 Jan 2025 00:00:00 GMT"},
            )
        ]
    )
    monkeypatch.setattr(
        "tac.application.use_cases.discover_articles.build_session", lambda: session
    )

    result = discover_candidates(settings, conn)
    state = db.get_source_state(conn, "example")

    assert result["inserted"] == 1
    assert session.calls[0]["headers"]["If-None-Match"] == '"abc"'
    assert session.calls[0]["headers"]["If-Modified-Since"] == "Wed, 01 Jan 2025 00:00:00 GMT"
    assert state["last_status"] == "success"
    assert state["etag"] == '"def"'


def test_discover_records_304_without_parsing_entries(tmp_path, monkeypatch):
    conn = db.connect(tmp_path / "state.db")
    db.migrate(conn)
    settings = _settings(tmp_path)
    db.record_source_state(
        conn,
        source_name="example",
        etag='"abc"',
        modified=None,
        last_status="success",
    )
    session = FakeSession([FakeResponse(status_code=304)])
    monkeypatch.setattr(
        "tac.application.use_cases.discover_articles.build_session", lambda: session
    )

    result = discover_candidates(settings, conn)
    state = db.get_source_state(conn, "example")

    assert result["sources_not_modified"] == 1
    assert result["found"] == 0
    assert state["last_status"] == "not_modified"
    assert state["etag"] == '"abc"'


def test_discover_records_source_failure_without_stopping_manual_candidates(tmp_path, monkeypatch):
    settings = _settings(
        tmp_path,
        """
sources:
  - name: example
    feed:
      type: direct
      url: https://example.com/feed.xml
manual_urls:
  - url: https://example.com/manual
    title: Manual
""",
    )
    conn = db.connect(tmp_path / "state.db")
    db.migrate(conn)
    session = FakeSession([FakeResponse(status_code=500, error=RuntimeError("boom"))])
    monkeypatch.setattr(
        "tac.application.use_cases.discover_articles.build_session", lambda: session
    )

    result = discover_candidates(settings, conn)
    state = db.get_source_state(conn, "example")

    assert result["sources_failed"] == 1
    assert result["inserted"] == 1
    assert state["last_status"] == "failed"
    assert "boom" in state["last_error"]


def test_discover_uses_configured_concurrency(tmp_path, monkeypatch):
    settings = _settings(
        tmp_path,
        """
sources:
  - name: one
    feed:
      type: direct
      url: https://example.com/one.xml
  - name: two
    feed:
      type: direct
      url: https://example.com/two.xml
""",
    )
    settings = Settings(**{**settings.__dict__, "discover_max_concurrency": 4})
    conn = db.connect(tmp_path / "state.db")
    db.migrate(conn)
    session = FakeSession([FakeResponse(status_code=304), FakeResponse(status_code=304)])
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

    monkeypatch.setattr(
        "tac.application.use_cases.discover_articles.build_session", lambda: session
    )
    monkeypatch.setattr(
        "tac.application.use_cases.discover_articles.ThreadPoolExecutor", FakeExecutor
    )

    result = discover_candidates(settings, conn)

    assert result["sources_not_modified"] == 2
    assert seen["max_workers"] == 4


def test_discover_builds_rsshub_feed_url_and_records_summary_policy(tmp_path, monkeypatch):
    settings = _settings(
        tmp_path,
        """
sources:
  - name: zhihu
    feed:
      type: rsshub
      route: /zhihu/hot
      params:
        limit: 20
        filter: "AI|工程"
""",
    )
    settings = Settings(
        **{
            **settings.__dict__,
            "rsshub_enabled": True,
            "rsshub_instance": "http://rsshub.local:1200",
        }
    )
    conn = db.connect(tmp_path / "state.db")
    db.migrate(conn)
    feed = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><item><title>Hot</title><link>https://zhihu.com/question/1</link></item></channel></rss>
"""
    session = FakeSession([FakeResponse(content=feed)])
    monkeypatch.setattr(
        "tac.application.use_cases.discover_articles.build_session", lambda: session
    )

    result = discover_candidates(settings, conn)
    article = conn.execute("SELECT * FROM articles WHERE source_name = 'zhihu'").fetchone()

    assert result["inserted"] == 1
    assert (
        session.calls[0]["url"]
        == "http://rsshub.local:1200/zhihu/hot?limit=20&filter=AI%7C%E5%B7%A5%E7%A8%8B"
    )
    assert article["source_publish_policy"] == "summary_only"


def test_discover_records_rsshub_disabled_as_source_failure(tmp_path, monkeypatch):
    settings = _settings(
        tmp_path,
        """
sources:
  - name: zhihu
    feed:
      type: rsshub
      route: /zhihu/hot
""",
    )
    conn = db.connect(tmp_path / "state.db")
    db.migrate(conn)
    session = FakeSession([])
    monkeypatch.setattr(
        "tac.application.use_cases.discover_articles.build_session", lambda: session
    )

    result = discover_candidates(settings, conn)
    state = db.get_source_state(conn, "zhihu")

    assert result["sources_failed"] == 1
    assert result["found"] == 0
    assert state["last_status"] == "failed"
    assert "rsshub is disabled" in state["last_error"]
