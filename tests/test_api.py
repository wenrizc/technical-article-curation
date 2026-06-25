import asyncio
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from types import SimpleNamespace

import feedparser
import pytest
from fastapi.testclient import TestClient
from requests import RequestException
from starlette.requests import Request
from starlette.responses import Response

from tac.domain.models import ArticleStatus, EvaluationResult
from tac.infrastructure.db import store as db
from tac.main import create_app
from tac.settings import Settings
from tac.web.security import guard_request


def _settings(tmp_path, **overrides) -> Settings:
    sources_path = tmp_path / "sources.yaml"
    sources_path.write_text("sources: []\nmanual_urls: []\n", encoding="utf-8")
    values = {
        "state_db": tmp_path / "state.db",
        "sources_path": sources_path,
        "public_dir": tmp_path / "public",
        "max_retry": 3,
        "model": "fixture-model",
        "base_url": "https://example.invalid/v1",
        "api_key": None,
        "ai_response_path": Path("tests/fixtures/ai/accept.json"),
        "fetch_fixture_path": Path("tests/fixtures/markdown/queue-latency.md"),
        "crawler4ai_enabled": False,
        "fetch_delay_seconds": 0,
        "evaluation_max_attempts": 3,
        "prompt_language": "zh-CN",
        "prompt_path": Path("prompts/zh-CN/evaluate.md"),
        "few_shot_dir": Path("prompts/zh-CN/few_shots"),
    }
    values.update(overrides)
    return Settings(**values)


def _csrf(client: TestClient) -> str:
    response = client.get("/admin")
    response.raise_for_status()
    match = re.search(r'name="tac-csrf" content="([^"]+)"', response.text)
    assert match
    return match.group(1)


def _headers(token: str) -> dict[str, str]:
    return {"X-TAC-CSRF": token, "Origin": "http://testserver"}


def _accepted_result(
    tags: list[str] | None = None,
    suggested_tags: list[str] | None = None,
) -> EvaluationResult:
    return EvaluationResult.model_validate(
        {
            "decision": "accept",
            "content_type": "engineering_case",
            "summary": "摘要",
            "tags": tags or ["Architecture"],
            "suggested_tags": suggested_tags or [],
            "recommendation_reason": "推荐理由",
        }
    )


async def _run_guard_request(
    settings: Settings,
    *,
    headers: dict[str, str],
    chunks: list[dict[str, object]],
    method: str = "POST",
    path: str = "/api/admin/sources",
    client_host: str = "testclient",
) -> Response:
    app = SimpleNamespace(
        state=SimpleNamespace(
            settings=settings,
            csrf_token="token",
            http_semaphore=asyncio.Semaphore(1),
            public_http_semaphore=asyncio.Semaphore(1),
        )
    )
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [(key.lower().encode(), value.encode()) for key, value in headers.items()],
        "client": (client_host, 1234),
        "server": ("testserver", 80),
        "app": app,
    }
    events = list(chunks)

    async def receive():
        if events:
            return events.pop(0)
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(scope, receive)

    async def call_next(current_request: Request) -> Response:
        await current_request.body()
        return Response(content=b"ok")

    return await guard_request(request, call_next)


def _seed_accepted(
    settings: Settings,
    tags: list[str] | None = None,
    suggested_tags: list[str] | None = None,
) -> int:
    conn = db.connect(settings.state_db)
    db.migrate(conn)
    article_id, _, _ = db.add_candidate(
        conn, title="Queue Latency", url="https://example.com/queue", source_name="manual"
    )
    db.record_fetch_success(conn, article_id, "# Body", {"crawler": "fixture"})
    db.record_evaluation(
        conn,
        article_id,
        _accepted_result(tags, suggested_tags),
        settings.model,
        "{}",
    )
    conn.close()
    return article_id


def _seed_article(
    settings: Settings,
    *,
    title: str,
    url: str,
    source_name: str = "manual",
) -> int:
    conn = db.connect(settings.state_db)
    db.migrate(conn)
    article_id, _, _ = db.add_candidate(
        conn,
        title=title,
        url=url,
        source_name=source_name,
    )
    db.record_fetch_success(conn, article_id, f"# {title}\n\nSecret body", {"crawler": "fixture"})
    db.record_evaluation(conn, article_id, _accepted_result(), settings.model, "{}")
    conn.close()
    return article_id


def test_admin_page_served_with_csrf(tmp_path):
    app = create_app(_settings(tmp_path))
    with TestClient(app) as client:
        response = client.get("/admin")

    assert response.status_code == 200
    assert 'name="tac-csrf"' in response.text


def test_rsshub_strict_startup_check_fails_app_start(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise RequestException("offline")

    monkeypatch.setattr("tac.main.get", fail)
    app = create_app(
        _settings(
            tmp_path,
            rsshub_startup_check=True,
            rsshub_strict_startup=True,
        )
    )

    with pytest.raises(RuntimeError, match="rsshub startup check failed"), TestClient(app):
        pass


def test_write_without_csrf_returns_403(tmp_path):
    app = create_app(_settings(tmp_path))
    with TestClient(app) as client:
        response = client.post("/api/admin/jobs/run", headers={"Origin": "http://testserver"})

    assert response.status_code == 403


def test_write_wrong_origin_returns_403(tmp_path):
    app = create_app(_settings(tmp_path))
    with TestClient(app) as client:
        token = _csrf(client)
        response = client.post(
            "/api/admin/jobs/run",
            headers={"X-TAC-CSRF": token, "Origin": "https://evil.example"},
        )

    assert response.status_code == 403


def test_request_body_too_large_returns_413(tmp_path):
    app = create_app(_settings(tmp_path, max_request_body_bytes=4))
    with TestClient(app) as client:
        token = _csrf(client)
        response = client.put(
            "/api/admin/sources",
            headers=_headers(token),
            json={"content": "sources: []\n", "previous_hash": "bad"},
        )

    assert response.status_code == 413


def test_public_read_guard_allows_remote_clients(tmp_path):
    settings = _settings(tmp_path)

    response = asyncio.run(
        _run_guard_request(
            settings,
            method="GET",
            path="/api/public/index.json",
            headers={"host": "curation.example"},
            chunks=[{"type": "http.request", "body": b"", "more_body": False}],
            client_host="203.0.113.10",
        )
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=300"


def test_admin_guard_still_blocks_remote_clients(tmp_path):
    settings = _settings(tmp_path)

    response = asyncio.run(
        _run_guard_request(
            settings,
            method="GET",
            path="/api/admin/summary",
            headers={"host": "curation.example"},
            chunks=[{"type": "http.request", "body": b"", "more_body": False}],
            client_host="203.0.113.10",
        )
    )

    assert response.status_code == 403


def test_public_write_guard_returns_405(tmp_path):
    settings = _settings(tmp_path)

    response = asyncio.run(
        _run_guard_request(
            settings,
            method="POST",
            path="/api/public/index.json",
            headers={"host": "curation.example"},
            chunks=[{"type": "http.request", "body": b"{}", "more_body": False}],
            client_host="203.0.113.10",
        )
    )

    assert response.status_code == 405


def test_request_body_too_large_without_content_length_returns_413(tmp_path):
    settings = _settings(tmp_path, max_request_body_bytes=4)

    response = asyncio.run(
        _run_guard_request(
            settings,
            headers={
                "host": "testserver",
                "origin": "http://testserver",
                "x-tac-csrf": "token",
            },
            chunks=[
                {"type": "http.request", "body": b"ab", "more_body": True},
                {"type": "http.request", "body": b"cde", "more_body": False},
            ],
        )
    )

    assert response.status_code == 413


def test_request_body_too_large_with_spoofed_content_length_returns_413(tmp_path):
    settings = _settings(tmp_path, max_request_body_bytes=4)

    response = asyncio.run(
        _run_guard_request(
            settings,
            headers={
                "host": "testserver",
                "origin": "http://testserver",
                "x-tac-csrf": "token",
                "content-length": "1",
            },
            chunks=[
                {"type": "http.request", "body": b"ab", "more_body": True},
                {"type": "http.request", "body": b"cde", "more_body": False},
            ],
        )
    )

    assert response.status_code == 413


def test_admin_summary_and_articles_report_current_statuses(tmp_path):
    settings = _settings(tmp_path)
    _seed_accepted(settings)
    app = create_app(settings)

    with TestClient(app) as client:
        summary = client.get("/api/admin/summary").json()
        page = client.get("/api/admin/articles?status=accepted").json()

    assert summary["accepted"] == 1
    assert page["total"] == 1
    assert page["items"][0]["status"] == "accepted"


def test_admin_source_names(tmp_path):
    settings = _settings(tmp_path)
    _seed_accepted(settings)
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/api/admin/source-names")

    assert response.json()["items"] == ["manual"]


def test_admin_status_update(tmp_path):
    settings = _settings(tmp_path)
    article_id = _seed_accepted(settings)
    app = create_app(settings)

    with TestClient(app) as client:
        token = _csrf(client)
        rejected = client.post(
            f"/api/admin/articles/{article_id}/status",
            headers=_headers(token),
            json={"status": "rejected"},
        ).json()

    assert rejected["status"] == "rejected"


def test_public_api_only_exposes_accepted_articles(tmp_path):
    settings = _settings(tmp_path)
    article_id = _seed_accepted(settings)
    conn = db.connect(settings.state_db)
    slug = conn.execute("SELECT slug FROM articles WHERE id = ?", (article_id,)).fetchone()["slug"]
    conn.execute(
        "UPDATE articles SET status = ? WHERE id = ?",
        (ArticleStatus.low_confidence.value, article_id),
    )
    conn.commit()
    conn.close()
    app = create_app(settings)

    with TestClient(app) as client:
        page = client.get("/api/public/articles?status=all").json()
        detail = client.get(f"/api/public/articles/{slug}")
        index = client.get("/api/public/index.json").json()

    assert page["total"] == 0
    assert detail.status_code == 404
    assert index == []


def test_public_api_returns_full_content_markdown(tmp_path):
    settings = _settings(tmp_path)
    conn = db.connect(settings.state_db)
    db.migrate(conn)
    article_id, _, _ = db.add_candidate(
        conn,
        title="Hot",
        url="https://example.com/hot",
        source_name="rsshub",
    )
    db.record_fetch_success(conn, article_id, "# Body", {"crawler": "fixture"})
    db.record_evaluation(conn, article_id, _accepted_result(), settings.model, "{}")
    slug = conn.execute("SELECT slug FROM articles WHERE id = ?", (article_id,)).fetchone()["slug"]
    conn.close()
    app = create_app(settings)

    with TestClient(app) as client:
        detail = client.get(f"/api/public/articles/{slug}").json()

    assert detail["content_markdown"] == "# Body"
    assert detail["content_type"] == "engineering_case"


def test_public_index_json_returns_all_accepted_articles(tmp_path):
    settings = _settings(tmp_path)
    conn = db.connect(settings.state_db)
    db.migrate(conn)
    for index in range(201):
        article_id, _, _ = db.add_candidate(
            conn,
            title=f"Accepted {index}",
            url=f"https://example.com/{index}",
            source_name="manual",
        )
        db.record_fetch_success(conn, article_id, "# Body", {"crawler": "fixture"})
        db.record_evaluation(conn, article_id, _accepted_result(), settings.model, "{}")
    conn.close()
    app = create_app(settings)

    with TestClient(app) as client:
        index = client.get("/api/public/index.json").json()

    assert len(index) == 201


def test_public_rss_feed_outputs_accepted_articles(tmp_path):
    settings = _settings(tmp_path, public_base_url="https://curation.example")
    _seed_article(settings, title="Accepted", url="https://example.com/a")
    rejected_id = _seed_article(settings, title="Rejected", url="https://example.com/r")
    conn = db.connect(settings.state_db)
    conn.execute(
        "UPDATE articles SET status = ? WHERE id = ?",
        (ArticleStatus.rejected.value, rejected_id),
    )
    conn.commit()
    conn.close()
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/api/public/feed.xml")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/rss+xml")
    parsed = feedparser.parse(response.content)
    assert parsed.feed.title == "技术与成长精选"
    assert [entry.title for entry in parsed.entries] == ["Accepted"]
    assert parsed.entries[0].link.startswith("https://curation.example/api/public/articles/")
    assert parsed.entries[0].source.title == "manual"
    assert parsed.entries[0].source.href == "https://example.com/a"
    assert any(tag["term"] == "工程实践" for tag in parsed.entries[0].tags)


def test_public_rss_feed_limit_and_etag_304(tmp_path):
    settings = _settings(tmp_path)
    _seed_article(settings, title="First", url="https://example.com/1")
    _seed_article(settings, title="Second", url="https://example.com/2")
    app = create_app(settings)

    with TestClient(app) as client:
        first = client.get("/feed.xml?limit=1")
        cached = client.get("/feed.xml?limit=1", headers={"If-None-Match": first.headers["etag"]})

    assert first.status_code == 200
    assert cached.status_code == 304
    parsed = feedparser.parse(first.content)
    assert len(parsed.entries) == 1


def test_public_rss_feed_last_modified_uses_latest_item_time(tmp_path):
    settings = _settings(tmp_path)
    recent_id = _seed_article(settings, title="Recent Fallback", url="https://example.com/recent")
    old_id = _seed_article(settings, title="Old Collected", url="https://example.com/old")
    conn = db.connect(settings.state_db)
    conn.execute(
        """
        UPDATE articles
        SET collected_at = NULL,
            updated_at = '2026-06-22T10:00:00+00:00',
            created_at = '2026-06-20T10:00:00+00:00'
        WHERE id = ?
        """,
        (recent_id,),
    )
    conn.execute(
        """
        UPDATE articles
        SET collected_at = '2026-06-21T10:00:00+00:00',
            updated_at = '2026-06-21T10:00:00+00:00'
        WHERE id = ?
        """,
        (old_id,),
    )
    conn.commit()
    conn.close()
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/feed.xml")

    assert response.status_code == 200
    last_modified = parsedate_to_datetime(response.headers["last-modified"])
    assert last_modified == datetime(2026, 6, 22, 10, 0, tzinfo=UTC)


def test_public_rss_feed_handles_rsshub_article(tmp_path):
    settings = _settings(tmp_path)
    _seed_article(
        settings,
        title="RSSHub Article",
        url="https://example.com/s",
        source_name="rsshub",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/api/public/feed.xml")

    parsed = feedparser.parse(response.content)
    assert parsed.entries[0].title == "RSSHub Article"
    assert parsed.entries[0].source.title == "rsshub"
    assert "推荐理由" in parsed.entries[0].description


def test_sources_update_requires_matching_hash_and_valid_yaml(tmp_path):
    settings = _settings(tmp_path)
    app = create_app(settings)

    with TestClient(app) as client:
        token = _csrf(client)
        current = client.get("/api/admin/sources").json()
        conflict = client.put(
            "/api/admin/sources",
            headers=_headers(token),
            json={"content": "sources: []\n", "previous_hash": "bad"},
        )
        invalid = client.put(
            "/api/admin/sources",
            headers=_headers(token),
            json={
                "content": (
                    "sources:\n  - name: bad\n    feed:\n      type: direct\n      url: ftp://bad\n"
                ),
                "previous_hash": current["content_hash"],
            },
        )
        saved = client.put(
            "/api/admin/sources",
            headers=_headers(token),
            json={
                "content": "sources: []\nmanual_urls:\n  - https://example.com/a\n",
                "previous_hash": current["content_hash"],
            },
        )

    assert conflict.status_code == 409
    assert invalid.status_code == 422
    assert saved.status_code == 200
    assert (settings.sources_path.with_name("sources.yaml.bak")).exists()


def test_preview_rsshub_returns_feed_entries(tmp_path, monkeypatch):
    settings = _settings(tmp_path, rsshub_instance="http://rsshub.local:1200")
    app = create_app(settings)
    feed = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><item><title>Hot</title><link>https://example.com/hot</link></item></channel></rss>
"""

    class Response:
        status_code = 200
        content = feed

        def raise_for_status(self):
            return None

    class Session:
        def get(self, url, headers, timeout, allow_redirects):
            assert url == "http://rsshub.local:1200/zhihu/hot?limit=1"
            assert headers == {}
            assert timeout == (10, 30)
            assert allow_redirects is True
            return Response()

    monkeypatch.setattr("tac.web.routers.admin.build_session", lambda: Session())

    with TestClient(app) as client:
        token = _csrf(client)
        response = client.post(
            "/api/admin/sources/preview-rsshub",
            headers=_headers(token),
            json={"route": "/zhihu/hot", "params": {"limit": 1}},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["feed_url"] == "http://rsshub.local:1200/zhihu/hot?limit=1"
    assert payload["entries"] == [{"title": "Hot", "url": "https://example.com/hot"}]


def test_retry_fetch_submits_job(tmp_path):
    settings = _settings(tmp_path)
    article_id = _seed_accepted(settings)
    app = create_app(settings)

    with TestClient(app) as client:
        token = _csrf(client)
        response = client.post(
            f"/api/admin/articles/{article_id}/retry-fetch", headers=_headers(token)
        )

    assert response.status_code == 200
    assert response.json()["kind"] == "retry-fetch"


def test_admin_tag_vocabulary_create_and_list(tmp_path):
    settings = _settings(tmp_path)
    app = create_app(settings)

    with TestClient(app) as client:
        token = _csrf(client)
        created = client.post(
            "/api/admin/tags",
            headers=_headers(token),
            json={"name": "DX", "description": "开发者体验主题"},
        )
        listed = client.get("/api/admin/tags?q=DX")

    assert created.status_code == 200
    assert created.json()["name"] == "DX"
    assert listed.json()["items"][0]["description"] == "开发者体验主题"
    assert "DX" in app.state.tag_cache.names()


def test_admin_tag_candidate_approval_updates_public_tags(tmp_path):
    settings = _settings(tmp_path)
    article_id = _seed_accepted(
        settings,
        tags=["Architecture"],
        suggested_tags=["New Niche Tag"],
    )
    app = create_app(settings)

    with TestClient(app) as client:
        token = _csrf(client)
        candidates = client.get("/api/admin/tag-candidates").json()
        approved = client.post(
            f"/api/admin/tag-candidates/{candidates['items'][0]['id']}/approve",
            headers=_headers(token),
            json={},
        )
        slug = client.get(f"/api/admin/articles/{article_id}").json()["article"]["slug"]
        public_detail = client.get(f"/api/public/articles/{slug}").json()

    assert approved.status_code == 200
    assert public_detail["tags"] == ["Architecture", "New Niche Tag"]
    assert "New Niche Tag" in app.state.tag_cache.names()


def test_schedules_api_lists_and_triggers_builtin_run(tmp_path):
    settings = _settings(tmp_path, scheduler_enabled=True, schedule_run_cron="0 8 * * *")
    app = create_app(settings)

    with TestClient(app) as client:
        token = _csrf(client)
        schedules = client.get("/api/admin/schedules").json()
        triggered = client.post("/api/admin/schedules/run/trigger", headers=_headers(token)).json()

    assert schedules["items"][0]["schedule_id"] == "run"
    assert schedules["items"][0]["enabled"] is True
    assert triggered["kind"] == "run"
    assert triggered["schedule_id"] == "run"
    assert triggered["trigger"] == "manual"
