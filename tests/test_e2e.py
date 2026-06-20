import json
from pathlib import Path

from tac import db
from tac.config import Settings
from tac.discover import discover_candidates
from tac.evaluate import evaluate_pending
from tac.publish import publish_public


def test_offline_e2e_fixture(tmp_path, monkeypatch):
    state_db = tmp_path / "state.db"
    public_dir = tmp_path / "public"
    settings = Settings(
        state_db=state_db,
        sources_path=Path("tests/fixtures/sources/manual.yaml"),
        public_dir=public_dir,
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
    conn = db.connect(state_db)
    db.migrate(conn)

    discover_result = discover_candidates(settings, conn)
    assert discover_result["inserted"] == 1
    article = conn.execute("SELECT * FROM articles").fetchone()
    markdown = open("tests/fixtures/markdown/queue-latency.md", encoding="utf-8").read()
    db.record_fetch_success(conn, int(article["id"]), markdown, {"crawler": "fixture"})

    evaluate_result = evaluate_pending(settings, conn)
    assert evaluate_result["accepted"] == 1
    publish_result = publish_public(settings, conn)
    assert publish_result["published"] == 1

    index = json.loads((public_dir / "index.json").read_text(encoding="utf-8"))
    assert len(index) == 1
    public_keys = set(index[0])
    assert "confidence" not in public_keys
    assert "full_reasoning" not in public_keys
    assert "status" not in public_keys
    assert index[0]["markdown_path"].endswith(".md")
    md_path = public_dir / index[0]["markdown_path"]
    markdown_output = md_path.read_text(encoding="utf-8")
    assert "来源信息" in markdown_output
    assert "https://example.com/blog/queue-latency" in markdown_output
