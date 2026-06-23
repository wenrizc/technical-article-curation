import pytest

from tac.settings import get_settings


def test_prompt_language_defaults_to_chinese(monkeypatch):
    monkeypatch.delenv("TAC_PROMPT_LANGUAGE", raising=False)
    monkeypatch.delenv("TAC_PROMPT_PATH", raising=False)
    monkeypatch.delenv("TAC_FEW_SHOT_DIR", raising=False)
    monkeypatch.delenv("TAC_MIGRATIONS_DIR", raising=False)

    settings = get_settings()

    assert settings.prompt_language == "zh-CN"
    assert settings.prompt_path.as_posix() == "prompts/zh-CN/evaluate.md"
    assert settings.few_shot_dir.as_posix() == "prompts/zh-CN/few_shots"
    assert settings.migrations_dir.as_posix() == "migrations"


def test_prompt_language_rejects_english(monkeypatch):
    monkeypatch.setenv("TAC_PROMPT_LANGUAGE", "english")

    with pytest.raises(ValueError, match="TAC_PROMPT_LANGUAGE"):
        get_settings()


def test_prompt_language_rejects_unknown_value(monkeypatch):
    monkeypatch.setenv("TAC_PROMPT_LANGUAGE", "fr")

    with pytest.raises(ValueError, match="TAC_PROMPT_LANGUAGE"):
        get_settings()


def test_robustness_settings_from_env(monkeypatch):
    monkeypatch.setenv("TAC_FETCH_DELAY_SECONDS", "0.25")
    monkeypatch.setenv("TAC_EVALUATION_MAX_ATTEMPTS", "5")
    monkeypatch.setenv("TAC_MIGRATIONS_DIR", "db/migrations")

    settings = get_settings()

    assert settings.fetch_delay_seconds == 0.25
    assert settings.evaluation_max_attempts == 5
    assert settings.migrations_dir.as_posix() == "db/migrations"


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
        "TAC_SCHEDULER_ENABLED",
        "TAC_SCHEDULE_RUN_CRON",
        "TAC_SCHEDULE_TIMEZONE",
        "TAC_SCHEDULER_POLL_SECONDS",
        "TAC_RSSHUB_ENABLED",
        "TAC_RSSHUB_INSTANCE",
        "TAC_RSSHUB_STARTUP_CHECK",
        "TAC_RSSHUB_STRICT_STARTUP",
        "TAC_RSSHUB_TIMEOUT_SECONDS",
        "TAC_PUBLIC_BASE_URL",
        "TAC_PUBLIC_FEED_TITLE",
        "TAC_PUBLIC_FEED_DESCRIPTION",
        "TAC_PUBLIC_FEED_LANGUAGE",
        "TAC_PUBLIC_FEED_TTL_MINUTES",
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
    assert settings.scheduler_enabled is False
    assert settings.schedule_run_cron == "0 8 * * *"
    assert settings.schedule_timezone == "UTC"
    assert settings.scheduler_poll_seconds == 30
    assert settings.rsshub_enabled is False
    assert settings.rsshub_instance == "http://127.0.0.1:1200"
    assert settings.rsshub_startup_check is False
    assert settings.rsshub_strict_startup is False
    assert settings.rsshub_timeout_seconds == 30
    assert settings.public_base_url == "http://127.0.0.1:1104"
    assert settings.public_feed_title == "技术文章精选"
    assert settings.public_feed_description == "AI 辅助精选的高质量技术文章"
    assert settings.public_feed_language == "zh-CN"
    assert settings.public_feed_ttl_minutes == 5


def test_admin_runtime_settings_reject_invalid_values(monkeypatch):
    monkeypatch.setenv("TAC_HTTP_MAX_CONCURRENCY", "0")

    with pytest.raises(ValueError, match="TAC_HTTP_MAX_CONCURRENCY"):
        get_settings()
