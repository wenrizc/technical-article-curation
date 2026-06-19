from pathlib import Path

from tac.config import Settings
from tac.evaluate import evaluate_with_ai


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
        prompt_path=prompt,
        few_shot_dir=few_shots,
    )

    calls = {}

    class FakeMessage:
        content = """{
          "decision": "accept",
          "confidence": "high",
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

    monkeypatch.setattr("tac.evaluate.OpenAI", FakeOpenAI)

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
