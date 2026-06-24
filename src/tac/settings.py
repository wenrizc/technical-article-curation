from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    state_db: Path
    sources_path: Path
    public_dir: Path
    max_retry: int
    model: str
    base_url: str
    api_key: str | None
    ai_response_path: Path | None
    fetch_fixture_path: Path | None
    crawler4ai_enabled: bool
    fetch_delay_seconds: float
    evaluation_max_attempts: int
    prompt_language: str
    prompt_path: Path
    few_shot_dir: Path
    migrations_dir: Path = Path("migrations")
    auto_migrate: bool = True
    http_max_concurrency: int = 16
    job_max_concurrency: int = 1
    job_queue_limit: int = 8
    fetch_max_concurrency: int = 1
    evaluate_max_concurrency: int = 1
    discover_max_concurrency: int = 2
    discover_since_days: int | None = 1
    discover_since: str | None = None
    discover_until: str | None = None
    max_request_body_bytes: int = 1_048_576
    fetch_timeout_seconds: float = 90
    ai_timeout_seconds: float = 90
    job_timeout_seconds: float = 1_800
    fetch_max_markdown_bytes: int = 2_097_152
    job_history_limit: int = 100
    db_busy_timeout_ms: int = 5_000
    scheduler_enabled: bool = False
    schedule_run_cron: str = "0 8 * * *"
    schedule_timezone: str = "UTC"
    scheduler_poll_seconds: float = 30
    rsshub_enabled: bool = False
    rsshub_instance: str = "http://127.0.0.1:1200"
    rsshub_startup_check: bool = False
    rsshub_strict_startup: bool = False
    rsshub_timeout_seconds: float = 30
    discovery_listing_enabled: bool = True
    listing_timeout_seconds: float = 30
    public_base_url: str = "http://127.0.0.1:1104"
    public_feed_title: str = "技术与成长精选"
    public_feed_description: str = "AI 辅助精选的计算机领域技术、科研与成长内容"
    public_feed_language: str = "zh-CN"
    public_feed_ttl_minutes: int = 5


def _path_from_env(name: str, default: str) -> Path:
    return Path(os.environ.get(name, default))


def _bool_from_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off", "disabled"}


def _int_from_env(name: str, default: int, *, minimum: int = 0) -> int:
    value = int(os.environ.get(name, str(default)))
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _optional_int_from_env(
    name: str, *, minimum: int = 0, default: int | None = None
) -> int | None:
    raw = os.environ.get(name)
    if raw is None:
        return default
    if not raw.strip():
        return None
    value = int(raw)
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _float_from_env(name: str, default: float, *, minimum: float = 0) -> float:
    value = float(os.environ.get(name, str(default)))
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _prompt_language() -> str:
    value = os.environ.get("TAC_PROMPT_LANGUAGE", "zh-CN").strip()
    aliases = {
        "zh": "zh-CN",
        "zh-cn": "zh-CN",
        "cn": "zh-CN",
        "chinese": "zh-CN",
    }
    normalized = aliases.get(value.lower(), value)
    if normalized != "zh-CN":
        raise ValueError("TAC_PROMPT_LANGUAGE must be zh-CN")
    return normalized


def get_settings() -> Settings:
    prompt_language = _prompt_language()
    return Settings(
        state_db=_path_from_env("TAC_STATE_DB", "data/state.db"),
        migrations_dir=_path_from_env("TAC_MIGRATIONS_DIR", "migrations"),
        sources_path=_path_from_env("TAC_SOURCES_PATH", "config/sources.yaml"),
        public_dir=_path_from_env("TAC_PUBLIC_DIR", "public"),
        max_retry=int(os.environ.get("TAC_MAX_RETRY", "3")),
        model=os.environ.get("TAC_MODEL", "gpt-4.1-mini"),
        base_url=os.environ.get("TAC_BASE_URL", "https://api.openai.com/v1"),
        api_key=os.environ.get("OPENAI_API_KEY"),
        ai_response_path=(
            Path(os.environ["TAC_AI_RESPONSE_PATH"])
            if os.environ.get("TAC_AI_RESPONSE_PATH")
            else None
        ),
        fetch_fixture_path=(
            Path(os.environ["TAC_FETCH_FIXTURE_PATH"])
            if os.environ.get("TAC_FETCH_FIXTURE_PATH")
            else None
        ),
        crawler4ai_enabled=_bool_from_env("TAC_CRAWLER4AI_ENABLED", True),
        fetch_delay_seconds=float(os.environ.get("TAC_FETCH_DELAY_SECONDS", "1")),
        evaluation_max_attempts=int(os.environ.get("TAC_EVALUATION_MAX_ATTEMPTS", "3")),
        prompt_language=prompt_language,
        prompt_path=_path_from_env("TAC_PROMPT_PATH", f"prompts/{prompt_language}/evaluate.md"),
        few_shot_dir=_path_from_env("TAC_FEW_SHOT_DIR", f"prompts/{prompt_language}/few_shots"),
        auto_migrate=_bool_from_env("TAC_AUTO_MIGRATE", True),
        http_max_concurrency=_int_from_env("TAC_HTTP_MAX_CONCURRENCY", 16, minimum=1),
        job_max_concurrency=_int_from_env("TAC_JOB_MAX_CONCURRENCY", 1, minimum=1),
        job_queue_limit=_int_from_env("TAC_JOB_QUEUE_LIMIT", 8, minimum=0),
        fetch_max_concurrency=_int_from_env("TAC_FETCH_MAX_CONCURRENCY", 1, minimum=1),
        evaluate_max_concurrency=_int_from_env("TAC_EVALUATE_MAX_CONCURRENCY", 1, minimum=1),
        discover_max_concurrency=_int_from_env("TAC_DISCOVER_MAX_CONCURRENCY", 2, minimum=1),
        discover_since_days=_optional_int_from_env(
            "TAC_DISCOVER_SINCE_DAYS", minimum=1, default=1
        ),
        discover_since=os.environ.get("TAC_DISCOVER_SINCE"),
        discover_until=os.environ.get("TAC_DISCOVER_UNTIL"),
        max_request_body_bytes=_int_from_env("TAC_MAX_REQUEST_BODY_BYTES", 1_048_576, minimum=1),
        fetch_timeout_seconds=_float_from_env("TAC_FETCH_TIMEOUT_SECONDS", 90, minimum=1),
        ai_timeout_seconds=_float_from_env("TAC_AI_TIMEOUT_SECONDS", 90, minimum=1),
        job_timeout_seconds=_float_from_env("TAC_JOB_TIMEOUT_SECONDS", 1_800, minimum=1),
        fetch_max_markdown_bytes=_int_from_env(
            "TAC_FETCH_MAX_MARKDOWN_BYTES", 2_097_152, minimum=1
        ),
        job_history_limit=_int_from_env("TAC_JOB_HISTORY_LIMIT", 100, minimum=1),
        db_busy_timeout_ms=_int_from_env("TAC_DB_BUSY_TIMEOUT_MS", 5_000, minimum=0),
        scheduler_enabled=_bool_from_env("TAC_SCHEDULER_ENABLED", False),
        schedule_run_cron=os.environ.get("TAC_SCHEDULE_RUN_CRON", "0 8 * * *").strip(),
        schedule_timezone=os.environ.get("TAC_SCHEDULE_TIMEZONE", "UTC").strip(),
        scheduler_poll_seconds=_float_from_env("TAC_SCHEDULER_POLL_SECONDS", 30, minimum=1),
        rsshub_enabled=_bool_from_env("TAC_RSSHUB_ENABLED", False),
        rsshub_instance=os.environ.get("TAC_RSSHUB_INSTANCE", "http://127.0.0.1:1200").strip(),
        rsshub_startup_check=_bool_from_env("TAC_RSSHUB_STARTUP_CHECK", False),
        rsshub_strict_startup=_bool_from_env("TAC_RSSHUB_STRICT_STARTUP", False),
        rsshub_timeout_seconds=_float_from_env("TAC_RSSHUB_TIMEOUT_SECONDS", 30, minimum=1),
        discovery_listing_enabled=_bool_from_env("TAC_DISCOVERY_LISTING_ENABLED", True),
        listing_timeout_seconds=_float_from_env("TAC_LISTING_TIMEOUT_SECONDS", 30, minimum=1),
        public_base_url=os.environ.get("TAC_PUBLIC_BASE_URL", "http://127.0.0.1:1104").strip(),
        public_feed_title=os.environ.get("TAC_PUBLIC_FEED_TITLE", "技术与成长精选").strip(),
        public_feed_description=os.environ.get(
            "TAC_PUBLIC_FEED_DESCRIPTION", "AI 辅助精选的计算机领域技术、科研与成长内容"
        ).strip(),
        public_feed_language=os.environ.get("TAC_PUBLIC_FEED_LANGUAGE", "zh-CN").strip(),
        public_feed_ttl_minutes=_int_from_env("TAC_PUBLIC_FEED_TTL_MINUTES", 5, minimum=1),
    )
