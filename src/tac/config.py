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
    auto_migrate: bool = True
    http_max_concurrency: int = 16
    job_max_concurrency: int = 1
    job_queue_limit: int = 8
    fetch_max_concurrency: int = 1
    evaluate_max_concurrency: int = 1
    discover_max_concurrency: int = 2
    max_request_body_bytes: int = 1_048_576
    fetch_timeout_seconds: float = 90
    ai_timeout_seconds: float = 90
    job_timeout_seconds: float = 1_800
    fetch_max_markdown_bytes: int = 2_097_152
    job_history_limit: int = 100
    db_busy_timeout_ms: int = 5_000


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
        max_request_body_bytes=_int_from_env("TAC_MAX_REQUEST_BODY_BYTES", 1_048_576, minimum=1),
        fetch_timeout_seconds=_float_from_env("TAC_FETCH_TIMEOUT_SECONDS", 90, minimum=1),
        ai_timeout_seconds=_float_from_env("TAC_AI_TIMEOUT_SECONDS", 90, minimum=1),
        job_timeout_seconds=_float_from_env("TAC_JOB_TIMEOUT_SECONDS", 1_800, minimum=1),
        fetch_max_markdown_bytes=_int_from_env(
            "TAC_FETCH_MAX_MARKDOWN_BYTES", 2_097_152, minimum=1
        ),
        job_history_limit=_int_from_env("TAC_JOB_HISTORY_LIMIT", 100, minimum=1),
        db_busy_timeout_ms=_int_from_env("TAC_DB_BUSY_TIMEOUT_MS", 5_000, minimum=0),
    )
