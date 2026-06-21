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


def test_robustness_settings_from_env(monkeypatch):
    monkeypatch.setenv("TAC_FETCH_DELAY_SECONDS", "0.25")
    monkeypatch.setenv("TAC_EVALUATION_MAX_ATTEMPTS", "5")

    settings = get_settings()

    assert settings.fetch_delay_seconds == 0.25
    assert settings.evaluation_max_attempts == 5


def test_admin_runtime_settings_defaults(monkeypatch):
    for name in [
        "TAC_AUTO_MIGRATE",
        "TAC_HTTP_MAX_CONCURRENCY",
        "TAC_JOB_MAX_CONCURRENCY",
        "TAC_JOB_QUEUE_LIMIT",
        "TAC_FETCH_MAX_CONCURRENCY",
        "TAC_EVALUATE_MAX_CONCURRENCY",
        "TAC_DISCOVER_MAX_CONCURRENCY",
        "TAC_MAX_REQUEST_BODY_BYTES",
        "TAC_FETCH_TIMEOUT_SECONDS",
        "TAC_AI_TIMEOUT_SECONDS",
        "TAC_JOB_TIMEOUT_SECONDS",
        "TAC_FETCH_MAX_MARKDOWN_BYTES",
        "TAC_JOB_HISTORY_LIMIT",
        "TAC_DB_BUSY_TIMEOUT_MS",
    ]:
        monkeypatch.delenv(name, raising=False)

    settings = get_settings()

    assert settings.auto_migrate is True
    assert settings.http_max_concurrency == 16
    assert settings.job_max_concurrency == 1
    assert settings.job_queue_limit == 8
    assert settings.fetch_max_concurrency == 1
    assert settings.evaluate_max_concurrency == 1
    assert settings.discover_max_concurrency == 2
    assert settings.max_request_body_bytes == 1_048_576
    assert settings.fetch_timeout_seconds == 90
    assert settings.ai_timeout_seconds == 90
    assert settings.job_timeout_seconds == 1_800
    assert settings.fetch_max_markdown_bytes == 2_097_152
    assert settings.job_history_limit == 100
    assert settings.db_busy_timeout_ms == 5_000


def test_admin_runtime_settings_reject_invalid_values(monkeypatch):
    monkeypatch.setenv("TAC_HTTP_MAX_CONCURRENCY", "0")

    with pytest.raises(ValueError, match="TAC_HTTP_MAX_CONCURRENCY"):
        get_settings()
