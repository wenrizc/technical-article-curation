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
    prompt_path: Path
    few_shot_dir: Path


def _path_from_env(name: str, default: str) -> Path:
    return Path(os.environ.get(name, default))


def _bool_from_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off", "disabled"}


def get_settings() -> Settings:
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
        prompt_path=_path_from_env("TAC_PROMPT_PATH", "prompts/evaluate.md"),
        few_shot_dir=_path_from_env("TAC_FEW_SHOT_DIR", "prompts/few_shots"),
    )
