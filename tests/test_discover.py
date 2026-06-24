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
        discover_since_days=None,
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


def test_discover_strips_invalid_feed_control_chars(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    conn = db.connect(tmp_path / "state.db")
    db.migrate(conn)
    feed = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><item>
  <title>Post</title>
  <link>https://example.com/post</link>
  <description>bad \x08 char</description>
</item></channel></rss>
"""
    session = FakeSession([FakeResponse(content=feed)])
    monkeypatch.setattr(
        "tac.application.use_cases.discover_articles.build_session", lambda: session
    )

    result = discover_candidates(settings, conn)
    article = conn.execute("SELECT * FROM articles WHERE source_name = 'example'").fetchone()

    assert result["inserted"] == 1
    assert article["url"] == "https://example.com/post"


def test_discover_records_rss_published_at_and_queues_fetch(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    conn = db.connect(tmp_path / "state.db")
    db.migrate(conn)
    feed = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><item>
  <title>Post</title>
  <link>https://example.com/post</link>
  <pubDate>Mon, 01 Jun 2026 10:00:00 GMT</pubDate>
</item></channel></rss>
"""
    session = FakeSession([FakeResponse(content=feed)])
    monkeypatch.setattr(
        "tac.application.use_cases.discover_articles.build_session", lambda: session
    )

    result = discover_candidates(settings, conn)
    article = conn.execute("SELECT * FROM articles WHERE source_name = 'example'").fetchone()
    queue = conn.execute(
        "SELECT * FROM article_queue WHERE article_id = ?", (article["id"],)
    ).fetchone()

    assert result["queued_fetch"] == 1
    assert article["published_at"] == "2026-06-01T10:00:00Z"
    assert queue["stage"] == "fetch"
    assert queue["status"] == "queued"


def test_discover_normalizes_feed_entry_urls(tmp_path, monkeypatch):
    settings = _settings(
        tmp_path,
        """
sources:
  - name: example
    site_url: https://example.com/blog/
    feed:
      type: direct
      url: https://example.com/feed.xml
""",
    )
    conn = db.connect(tmp_path / "state.db")
    db.migrate(conn)
    feed = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item><title>Relative</title><link>/blog/relative</link></item>
  <item><title>Localhost</title><link>http://localhost:5174/blog/local</link></item>
</channel></rss>
"""
    session = FakeSession([FakeResponse(content=feed)])
    monkeypatch.setattr(
        "tac.application.use_cases.discover_articles.build_session", lambda: session
    )

    result = discover_candidates(settings, conn)
    rows = conn.execute(
        "SELECT url FROM articles WHERE source_name = 'example' ORDER BY title"
    ).fetchall()

    assert result["inserted"] == 2
    assert [row["url"] for row in rows] == [
        "https://example.com/blog/local",
        "https://example.com/blog/relative",
    ]


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


def test_discover_builds_rsshub_feed_url(tmp_path, monkeypatch):
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
    assert result["inserted"] == 1
    assert (
        session.calls[0]["url"]
        == "http://rsshub.local:1200/zhihu/hot?limit=20&filter=AI%7C%E5%B7%A5%E7%A8%8B"
    )


def test_discover_records_feed_entry_content_for_fetch_priority(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    conn = db.connect(tmp_path / "state.db")
    db.migrate(conn)
    feed = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><item>
  <title>Post</title>
  <link>https://example.com/post</link>
  <description><![CDATA[<article><h1>Post</h1><p>RSSHub full text body</p></article>]]></description>
</item></channel></rss>
"""
    session = FakeSession([FakeResponse(content=feed)])
    monkeypatch.setattr(
        "tac.application.use_cases.discover_articles.build_session", lambda: session
    )

    result = discover_candidates(settings, conn)
    article = conn.execute("SELECT * FROM articles WHERE source_name = 'example'").fetchone()

    assert result["inserted"] == 1
    assert "RSSHub full text body" in article["source_content_markdown"]
    assert '"field": "summary"' in article["source_content_metadata"]


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


def test_discover_sitemap_parses_urlset_and_inserts_candidates(tmp_path, monkeypatch):
    settings = _settings(
        tmp_path,
        """
sources:
  - name: fowler
    feed:
      type: sitemap
      url: https://martinfowler.com/sitemap.xml
""",
    )
    conn = db.connect(tmp_path / "state.db")
    db.migrate(conn)
    sitemap = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://martinfowler.com/articles/refactoring.html</loc>
    <lastmod>2026-05-20</lastmod>
  </url>
  <url><loc>https://martinfowler.com/articles/microservices.html</loc></url>
</urlset>
"""
    session = FakeSession([FakeResponse(content=sitemap)])
    monkeypatch.setattr(
        "tac.application.use_cases.discover_articles.build_session", lambda: session
    )

    result = discover_candidates(settings, conn)
    state = db.get_source_state(conn, "fowler")
    rows = conn.execute(
        "SELECT url, published_at FROM articles WHERE source_name = 'fowler' ORDER BY url"
    ).fetchall()

    assert result["inserted"] == 2
    assert state["last_status"] == "success"
    assert [row["url"] for row in rows] == [
        "https://martinfowler.com/articles/microservices.html",
        "https://martinfowler.com/articles/refactoring.html",
    ]
    assert rows[1]["published_at"] == "2026-05-20T00:00:00Z"


def test_discover_sitemapindex_expands_nested_sitemaps(tmp_path, monkeypatch):
    settings = _settings(
        tmp_path,
        """
sources:
  - name: fowler
    feed:
      type: sitemap
      url: https://martinfowler.com/sitemap.xml
""",
    )
    conn = db.connect(tmp_path / "state.db")
    db.migrate(conn)
    sitemap_index = b"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://martinfowler.com/sitemap-posts.xml</loc></sitemap>
  <sitemap><loc>https://martinfowler.com/sitemap-pages.xml</loc></sitemap>
</sitemapindex>
"""
    posts = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://martinfowler.com/articles/refactoring.html</loc></url>
</urlset>
"""
    pages = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://martinfowler.com/articles/microservices.html</loc></url>
</urlset>
"""
    session = FakeSession(
        [
            FakeResponse(content=sitemap_index),
            FakeResponse(content=posts),
            FakeResponse(content=pages),
        ]
    )
    monkeypatch.setattr(
        "tac.application.use_cases.discover_articles.build_session", lambda: session
    )

    result = discover_candidates(settings, conn)
    rows = conn.execute(
        "SELECT url FROM articles WHERE source_name = 'fowler' ORDER BY url"
    ).fetchall()

    assert result["inserted"] == 2
    assert [row["url"] for row in rows] == [
        "https://martinfowler.com/articles/microservices.html",
        "https://martinfowler.com/articles/refactoring.html",
    ]
    assert session.calls[1]["url"] == "https://martinfowler.com/sitemap-posts.xml"
    assert session.calls[2]["url"] == "https://martinfowler.com/sitemap-pages.xml"


def test_discover_sitemap_uses_conditional_headers(tmp_path, monkeypatch):
    settings = _settings(
        tmp_path,
        """
sources:
  - name: fowler
    feed:
      type: sitemap
      url: https://martinfowler.com/sitemap.xml
""",
    )
    conn = db.connect(tmp_path / "state.db")
    db.migrate(conn)
    db.record_source_state(
        conn,
        source_name="fowler",
        etag='"abc"',
        modified="Wed, 01 Jan 2025 00:00:00 GMT",
        last_status="success",
    )
    session = FakeSession([FakeResponse(status_code=304)])
    monkeypatch.setattr(
        "tac.application.use_cases.discover_articles.build_session", lambda: session
    )

    result = discover_candidates(settings, conn)
    state = db.get_source_state(conn, "fowler")

    assert result["sources_not_modified"] == 1
    assert state["last_status"] == "not_modified"
    assert session.calls[0]["headers"]["If-None-Match"] == '"abc"'


def test_discover_listing_extracts_links_via_selector(tmp_path, monkeypatch):
    settings = _settings(
        tmp_path,
        """
sources:
  - name: blog
    feed:
      type: listing
      url: https://example.com/blog
      link_selector: "main article a.post-link"
      url_patterns: ["/blog/2024"]
""",
    )
    conn = db.connect(tmp_path / "state.db")
    db.migrate(conn)
    html = b"""<!doctype html><html><body>
      <main>
        <article><a class="post-link" href="/blog/2024/foo">Foo</a></article>
        <article><a class="post-link" href="/blog/2023/bar">Bar</a></article>
        <article><a class="post-link" href="https://example.com/blog/2024/baz">Baz</a></article>
        <article><a class="other" href="/blog/2024/qux">Ignored</a></article>
      </main>
    </body></html>"""
    session = FakeSession([FakeResponse(content=html)])
    monkeypatch.setattr(
        "tac.application.use_cases.discover_articles.build_session", lambda: session
    )

    result = discover_candidates(settings, conn)
    rows = conn.execute(
        "SELECT url FROM articles WHERE source_name = 'blog' ORDER BY url"
    ).fetchall()
    urls = [row["url"] for row in rows]

    assert result["inserted"] == 2
    # 相对链接按 listing url 的 origin 解析;url_patterns 过滤掉 2023 那条和 .other 那条。
    assert "https://example.com/blog/2024/foo" in urls
    assert "https://example.com/blog/2024/baz" in urls
    assert all("/blog/2023/" not in url for url in urls)


def test_discover_listing_disabled_records_source_failure(tmp_path, monkeypatch):
    settings = _settings(
        tmp_path,
        """
sources:
  - name: blog
    feed:
      type: listing
      url: https://example.com/blog
      link_selector: "main a"
""",
    )
    settings = Settings(**{**settings.__dict__, "discovery_listing_enabled": False})
    conn = db.connect(tmp_path / "state.db")
    db.migrate(conn)
    session = FakeSession([])
    monkeypatch.setattr(
        "tac.application.use_cases.discover_articles.build_session", lambda: session
    )

    result = discover_candidates(settings, conn)
    state = db.get_source_state(conn, "blog")

    assert result["sources_failed"] == 1
    assert result["found"] == 0
    assert state["last_status"] == "failed"
    assert "listing is disabled" in state["last_error"]
