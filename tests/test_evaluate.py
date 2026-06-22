from concurrent.futures import Future

from tac.application.use_cases.evaluate_articles import evaluate_pending, evaluate_with_ai
from tac.infrastructure.db import store as db
from tac.settings import Settings


def test_evaluate_with_ai_uses_openai_sdk(monkeypatch, tmp_path):
    prompt = tmp_path / "evaluate.md"
    prompt.write_text("Return JSON only.", encoding="utf-8")
    few_shots = tmp_path / "few_shots"
    few_shots.mkdir()

    settings = Settings(
        state_db=tmp_path / "state.db",
        sources_path=tmp_path / "sources.yaml",
        public_dir=tmp_path / "public",
        max_retry=3,
        model="openai/test-model",
        base_url="https://llm.example/v1",
        api_key="test-key",
        ai_response_path=None,
        fetch_fixture_path=None,
        crawler4ai_enabled=False,
        fetch_delay_seconds=0,
        evaluation_max_attempts=3,
        prompt_language="zh-CN",
        prompt_path=prompt,
        few_shot_dir=few_shots,
    )

    calls = {}

    class FakeMessage:
        content = """{
          "decision": "accept",
          "dimensions": {
            "工程价值": "high",
            "技术深度": "high",
            "原创性": "medium",
            "可复用性": "high",
            "可读性": "high"
          },
          "summary": "summary",
          "tags": ["Architecture"],
          "recommendation_reason": "reason",
          "full_reasoning": "internal reason"
        }"""

    class FakeChoice:
        message = FakeMessage()

    class FakeResponse:
        choices = [FakeChoice()]

    class FakeCompletions:
        def create(self, **kwargs):
            calls["create"] = kwargs
            return FakeResponse()

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            calls["client"] = kwargs
            self.chat = FakeChat()

    monkeypatch.setattr("tac.application.use_cases.evaluate_articles.OpenAI", FakeOpenAI)

    result, raw_json = evaluate_with_ai(
        settings,
        title="Title",
        url="https://example.com",
        content_markdown="# Body",
    )

    assert result.decision.value == "accept"
    assert raw_json.strip().startswith("{")
    assert calls["client"]["api_key"] == "test-key"
    assert calls["client"]["base_url"] == "https://llm.example/v1"
    assert calls["create"]["model"] == "openai/test-model"
    assert calls["create"]["response_format"] == {"type": "json_object"}
    assert calls["create"]["timeout"] == settings.ai_timeout_seconds


def test_evaluate_with_ai_retries_invalid_json_with_repair_prompt(monkeypatch, tmp_path):
    prompt = tmp_path / "evaluate.md"
    prompt.write_text("Return JSON only.", encoding="utf-8")
    few_shots = tmp_path / "few_shots"
    few_shots.mkdir()

    settings = Settings(
        state_db=tmp_path / "state.db",
        sources_path=tmp_path / "sources.yaml",
        public_dir=tmp_path / "public",
        max_retry=3,
        model="openai/test-model",
        base_url="https://llm.example/v1",
        api_key="test-key",
        ai_response_path=None,
        fetch_fixture_path=None,
        crawler4ai_enabled=False,
        fetch_delay_seconds=0,
        evaluation_max_attempts=2,
        prompt_language="zh-CN",
        prompt_path=prompt,
        few_shot_dir=few_shots,
    )

    calls = []
    contents = iter(
        [
            "not json",
            """{
              "decision": "accept",
              "dimensions": {
                "工程价值": "high",
                "技术深度": "high",
                "原创性": "medium",
                "可复用性": "high",
                "可读性": "high"
              },
              "summary": "summary",
              "tags": ["Architecture"],
              "recommendation_reason": "reason",
              "full_reasoning": "internal reason"
            }""",
        ]
    )

    class FakeMessage:
        def __init__(self, content):
            self.content = content

    class FakeChoice:
        def __init__(self, content):
            self.message = FakeMessage(content)

    class FakeResponse:
        def __init__(self, content):
            self.choices = [FakeChoice(content)]

    class FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            return FakeResponse(next(contents))

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = FakeChat()

    monkeypatch.setattr("tac.application.use_cases.evaluate_articles.OpenAI", FakeOpenAI)

    result, _ = evaluate_with_ai(
        settings,
        title="Title",
        url="https://example.com",
        content_markdown="# Body",
    )

    assert result.decision.value == "accept"
    assert len(calls) == 2
    assert "上一次输出无法解析" in calls[1]["messages"][-1]["content"]
    assert "not json" in calls[1]["messages"][-1]["content"]


def test_evaluate_with_ai_repeats_original_request_after_api_failure(monkeypatch, tmp_path):
    prompt = tmp_path / "evaluate.md"
    prompt.write_text("Return JSON only.", encoding="utf-8")
    few_shots = tmp_path / "few_shots"
    few_shots.mkdir()

    settings = Settings(
        state_db=tmp_path / "state.db",
        sources_path=tmp_path / "sources.yaml",
        public_dir=tmp_path / "public",
        max_retry=3,
        model="openai/test-model",
        base_url="https://llm.example/v1",
        api_key="test-key",
        ai_response_path=None,
        fetch_fixture_path=None,
        crawler4ai_enabled=False,
        fetch_delay_seconds=0,
        evaluation_max_attempts=2,
        prompt_language="zh-CN",
        prompt_path=prompt,
        few_shot_dir=few_shots,
    )
    calls = []

    class FakeMessage:
        content = """{
          "decision": "reject",
          "dimensions": {
            "工程价值": "low",
            "技术深度": "low",
            "原创性": "low",
            "可复用性": "low",
            "可读性": "medium"
          },
          "summary": "summary",
          "tags": ["News"],
          "recommendation_reason": "reason",
          "full_reasoning": "internal reason"
        }"""

    class FakeChoice:
        message = FakeMessage()

    class FakeResponse:
        choices = [FakeChoice()]

    class FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise RuntimeError("rate limited")
            return FakeResponse()

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = FakeChat()

    monkeypatch.setattr("tac.application.use_cases.evaluate_articles.OpenAI", FakeOpenAI)

    result, _ = evaluate_with_ai(
        settings,
        title="Title",
        url="https://example.com",
        content_markdown="# Body",
    )

    assert result.decision.value == "reject"
    assert len(calls) == 2
    assert calls[0]["messages"] == calls[1]["messages"]


def test_evaluate_pending_uses_configured_concurrency(tmp_path, monkeypatch):
    conn = db.connect(tmp_path / "state.db")
    db.migrate(conn)
    ai_response = tmp_path / "accept.json"
    ai_response.write_text(
        """{
          "decision": "accept",
          "dimensions": {
            "工程价值": "high",
            "技术深度": "high",
            "原创性": "medium",
            "可复用性": "high",
            "可读性": "high"
          },
          "summary": "summary",
          "tags": ["Architecture"],
          "recommendation_reason": "reason",
          "full_reasoning": "internal reason"
        }""",
        encoding="utf-8",
    )
    for index in range(2):
        article_id, _, _ = db.add_candidate(
            conn,
            title=f"Title {index}",
            url=f"https://example.com/article-{index}",
            source_name="s",
        )
        db.record_fetch_success(conn, article_id, "# Body", {"crawler": "fixture"})
    settings = Settings(
        state_db=tmp_path / "state.db",
        sources_path=tmp_path / "sources.yaml",
        public_dir=tmp_path / "public",
        max_retry=3,
        model="fixture-model",
        base_url="https://example.invalid/v1",
        api_key=None,
        ai_response_path=ai_response,
        fetch_fixture_path=None,
        crawler4ai_enabled=False,
        fetch_delay_seconds=0,
        evaluation_max_attempts=3,
        prompt_language="zh-CN",
        prompt_path=tmp_path / "evaluate.md",
        few_shot_dir=tmp_path / "few_shots",
        evaluate_max_concurrency=5,
    )
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
        "tac.application.use_cases.evaluate_articles.ThreadPoolExecutor", FakeExecutor
    )

    result = evaluate_pending(settings, conn)

    assert result["accepted"] == 2
    assert seen["max_workers"] == 5
