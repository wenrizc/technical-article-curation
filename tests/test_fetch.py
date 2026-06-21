import pytest

from tac import db
from tac.config import Settings
from tac.fetch import FetchError, fetch_pending, fetch_url


def test_fetch_url_fails_when_crawler4ai_disabled():
    with pytest.raises(FetchError, match="disabled"):
        fetch_url("https://example.com/article", crawler4ai_enabled=False)


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

    monkeypatch.setattr("tac.fetch.fetch_url", fail)

    result = fetch_pending(settings, conn)
    fetch = conn.execute("SELECT * FROM fetches WHERE article_id = ?", (article_id,)).fetchone()
    article = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()

    assert result["failed"] == 1
    assert fetch["status"] == "failed"
    assert "no markdown" in fetch["error"]
    assert article["status"] == "candidate"
