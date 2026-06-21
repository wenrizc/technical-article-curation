import re
from pathlib import Path

from fastapi.testclient import TestClient

from tac import db
from tac.app import create_app
from tac.config import Settings
from tac.models import EvaluationResult
from tac.services import articles


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


def _accepted_result() -> EvaluationResult:
    return EvaluationResult.model_validate(
        {
            "decision": "accept",
            "confidence": "high",
            "dimensions": {
                "工程价值": "high",
                "技术深度": "high",
                "原创性": "medium",
                "可复用性": "high",
                "可读性": "high",
            },
            "summary": "摘要",
            "tags": ["Architecture"],
            "recommendation_reason": "推荐理由",
            "full_reasoning": "内部原因",
        }
    )


def _seed_accepted(settings: Settings) -> int:
    conn = db.connect(settings.state_db)
    db.migrate(conn)
    article_id, _, _ = db.add_candidate(
        conn, title="Queue Latency", url="https://example.com/queue", source_name="manual"
    )
    db.record_fetch_success(conn, article_id, "# Body", {"crawler": "fixture"})
    db.record_evaluation(conn, article_id, _accepted_result(), settings.model, "{}")
    conn.close()
    return article_id


def test_admin_page_served_with_csrf(tmp_path):
    app = create_app(_settings(tmp_path))
    with TestClient(app) as client:
        response = client.get("/admin")

    assert response.status_code == 200
    assert 'name="tac-csrf"' in response.text


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


def test_admin_summary_and_articles_include_archived(tmp_path):
    settings = _settings(tmp_path)
    article_id = _seed_accepted(settings)
    conn = db.connect(settings.state_db)
    articles.archive_article(conn, article_id)
    conn.close()
    app = create_app(settings)

    with TestClient(app) as client:
        summary = client.get("/api/admin/summary").json()
        page = client.get("/api/admin/articles?status=archived").json()

    assert summary["archived"] == 1
    assert page["total"] == 1
    assert page["items"][0]["status"] == "archived"


def test_admin_source_names(tmp_path):
    settings = _settings(tmp_path)
    _seed_accepted(settings)
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/api/admin/source-names")

    assert response.json()["items"] == ["manual"]


def test_admin_archive_unarchive_status_update(tmp_path):
    settings = _settings(tmp_path)
    article_id = _seed_accepted(settings)
    app = create_app(settings)

    with TestClient(app) as client:
        token = _csrf(client)
        archived = client.post(
            f"/api/admin/articles/{article_id}/archive", headers=_headers(token)
        ).json()
        restored = client.post(
            f"/api/admin/articles/{article_id}/unarchive", headers=_headers(token)
        ).json()
        rejected = client.post(
            f"/api/admin/articles/{article_id}/status",
            headers=_headers(token),
            json={"status": "rejected"},
        ).json()

    assert archived["status"] == "archived"
    assert restored["status"] == "accepted"
    assert rejected["status"] == "rejected"


def test_public_api_excludes_archived(tmp_path):
    settings = _settings(tmp_path)
    article_id = _seed_accepted(settings)
    conn = db.connect(settings.state_db)
    slug = conn.execute("SELECT slug FROM articles WHERE id = ?", (article_id,)).fetchone()["slug"]
    articles.archive_article(conn, article_id)
    conn.close()
    app = create_app(settings)

    with TestClient(app) as client:
        page = client.get("/api/public/articles?status=all").json()
        detail = client.get(f"/api/public/articles/{slug}")
        index = client.get("/api/public/index.json").json()

    assert page["total"] == 0
    assert detail.status_code == 404
    assert index == []


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
                "content": "sources:\n  - rss_url: ftp://bad\n",
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
