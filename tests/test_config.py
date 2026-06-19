import pytest

from tac.config import get_settings


def test_prompt_language_defaults_to_chinese(monkeypatch):
    monkeypatch.delenv("TAC_PROMPT_LANGUAGE", raising=False)
    monkeypatch.delenv("TAC_PROMPT_PATH", raising=False)
    monkeypatch.delenv("TAC_FEW_SHOT_DIR", raising=False)

    settings = get_settings()

    assert settings.prompt_language == "zh-CN"
    assert settings.prompt_path.as_posix() == "prompts/zh-CN/evaluate.md"
    assert settings.few_shot_dir.as_posix() == "prompts/zh-CN/few_shots"


def test_prompt_language_supports_english(monkeypatch):
    monkeypatch.setenv("TAC_PROMPT_LANGUAGE", "english")
    monkeypatch.delenv("TAC_PROMPT_PATH", raising=False)
    monkeypatch.delenv("TAC_FEW_SHOT_DIR", raising=False)

    settings = get_settings()

    assert settings.prompt_language == "en"
    assert settings.prompt_path.as_posix() == "prompts/en/evaluate.md"
    assert settings.few_shot_dir.as_posix() == "prompts/en/few_shots"


def test_prompt_language_rejects_unknown_value(monkeypatch):
    monkeypatch.setenv("TAC_PROMPT_LANGUAGE", "fr")

    with pytest.raises(ValueError, match="TAC_PROMPT_LANGUAGE"):
        get_settings()
