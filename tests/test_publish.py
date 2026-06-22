import json

from tac.application.use_cases import manage_articles as articles
from tac.application.use_cases.publish_articles import publish_public
from tac.domain.models import ArticleStatus, EvaluationResult
from tac.infrastructure.db import store as db
from tac.settings import Settings


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


def test_publish_removes_stale_files_for_unaccepted_articles(tmp_path):
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

    articles.set_article_status(conn, article_id, ArticleStatus.low_confidence)
    publish_public(settings, conn)

    assert not md_path.exists()
    assert not json_path.exists()


def test_publish_summary_only_skips_markdown_body(tmp_path):
    settings = _settings(tmp_path)
    conn = db.connect(settings.state_db)
    db.migrate(conn)
    article_id, _, _ = db.add_candidate(
        conn,
        title="Hot Topic",
        url="https://example.com/hot",
        source_name="rsshub",
        source_publish_policy="summary_only",
    )
    db.record_fetch_success(conn, article_id, "# Body", {"crawler": "fixture"})
    db.record_evaluation(conn, article_id, _accepted_result(), settings.model, "{}")

    publish_public(settings, conn)
    article = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    md_path = settings.public_dir / "articles" / f"{article['slug']}.md"
    json_path = settings.public_dir / "articles" / f"{article['slug']}.json"
    record = json.loads(json_path.read_text(encoding="utf-8"))

    assert not md_path.exists()
    assert json_path.exists()
    assert record["publish_policy"] == "summary_only"
    assert "markdown_path" not in record
