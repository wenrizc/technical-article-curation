from tac import db
from tac.config import Settings
from tac.models import EvaluationResult
from tac.publish import publish_public
from tac.services import articles


def _settings(tmp_path) -> Settings:
    return Settings(
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
        prompt_path=tmp_path / "prompt.md",
        few_shot_dir=tmp_path / "few_shots",
    )


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


def test_publish_removes_archived_stale_files(tmp_path):
    settings = _settings(tmp_path)
    conn = db.connect(settings.state_db)
    db.migrate(conn)
    article_id, _, _ = db.add_candidate(
        conn, title="Queue Latency", url="https://example.com/queue", source_name="s"
    )
    db.record_fetch_success(conn, article_id, "# Body", {"crawler": "fixture"})
    db.record_evaluation(conn, article_id, _accepted_result(), settings.model, "{}")

    publish_public(settings, conn)
    article = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    md_path = settings.public_dir / "articles" / f"{article['slug']}.md"
    json_path = settings.public_dir / "articles" / f"{article['slug']}.json"
    assert md_path.exists()
    assert json_path.exists()

    articles.archive_article(conn, article_id)
    publish_public(settings, conn)

    assert not md_path.exists()
    assert not json_path.exists()
