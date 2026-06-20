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


def _path_from_env(name: str, default: str) -> Path:
    return Path(os.environ.get(name, default))


def _bool_from_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off", "disabled"}


def _prompt_language() -> str:
    value = os.environ.get("TAC_PROMPT_LANGUAGE", "zh-CN").strip()
    aliases = {
        "zh": "zh-CN",
        "zh-cn": "zh-CN",
        "cn": "zh-CN",
        "chinese": "zh-CN",
        "en": "en",
        "en-us": "en",
        "english": "en",
    }
    normalized = aliases.get(value.lower(), value)
    if normalized not in {"zh-CN", "en"}:
        raise ValueError("TAC_PROMPT_LANGUAGE must be one of: zh-CN, en")
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
    )
