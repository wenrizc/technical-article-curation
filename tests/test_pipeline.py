from pathlib import Path

from tac.application.pipeline import run_all, run_evaluate, run_fetch
from tac.infrastructure.db import store as db
from tac.settings import Settings


def _settings(tmp_path) -> Settings:
    return Settings(
        state_db=tmp_path / "state.db",
        sources_path=Path("tests/fixtures/sources/manual.yaml"),
        public_dir=tmp_path / "public",
        max_retry=3,
        model="fixture-model",
        base_url="https://example.invalid/v1",
        api_key=None,
        ai_response_path=Path("tests/fixtures/ai/accept.json"),
        fetch_fixture_path=Path("tests/fixtures/markdown/queue-latency.md"),
        crawler4ai_enabled=False,
        fetch_delay_seconds=0,
        evaluation_max_attempts=3,
        prompt_language="zh-CN",
        prompt_path=Path("prompts/zh-CN/evaluate.md"),
        few_shot_dir=Path("prompts/zh-CN/few_shots"),
    )


def test_pipeline_run_all_offline(tmp_path):
    settings = _settings(tmp_path)

    result = run_all(settings)

    assert result["discover"]["inserted"] == 1
    assert result["fetch"]["succeeded"] == 1
    assert result["evaluate"]["accepted"] == 1
    assert result["publish"]["published"] == 1


def test_pipeline_retry_single_article_fetch_and_evaluate(tmp_path):
    settings = _settings(tmp_path)
    conn = db.connect(settings.state_db)
    db.migrate(conn)
    article_id, _, _ = db.add_candidate(
        conn,
        title="Queue Latency",
        url="https://example.com/blog/queue-latency",
        source_name="manual",
    )
    conn.close()

    fetch_result = run_fetch(settings, article_ids=[article_id])
    evaluate_result = run_evaluate(settings, article_ids=[article_id])

    assert fetch_result["succeeded"] == 1
    assert evaluate_result["accepted"] == 1
