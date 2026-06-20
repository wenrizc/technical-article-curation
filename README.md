# Technical Article Curation

Languages: [English](README.md) | [简体中文](README.zh-CN.md)

AI-assisted technical article curation pipeline. It discovers articles from RSS/Atom feeds and manual URLs, fetches cleaned Markdown, evaluates quality with a strict JSON schema, stores internal state in SQLite, and publishes stable JSON/Markdown artifacts under `public/`.

## Quick Start

```powershell
uv sync --extra test
uv run tac migrate
uv run tac discover
uv run tac fetch
uv run tac evaluate
uv run tac publish
```

Run the full pipeline:

```powershell
uv run tac run
```

## CLI

- `tac migrate`: apply SQLite migrations.
- `tac discover`: discover candidate articles.
- `tac fetch`: fetch and clean article Markdown.
- `tac evaluate`: evaluate fetched articles with AI.
- `tac publish`: publish accepted articles.
- `tac report sources`: report latest RSS source check states.
- `tac report failures`: report latest fetch and evaluation failures.
- `tac run`: run the full pipeline.

`fetch`, `evaluate`, and `run` support `--limit`.

## Configuration

Runtime configuration is read from environment variables.

- `OPENAI_API_KEY`: API key for AI evaluation.
- `TAC_MODEL`: model name used by the OpenAI SDK.
- `TAC_BASE_URL`: OpenAI-compatible `base_url`.
- `TAC_STATE_DB`: SQLite path, default `data/state.db`.
- `TAC_SOURCES_PATH`: source config path, default `config/sources.yaml`.
- `TAC_PUBLIC_DIR`: publish output directory, default `public`.
- `TAC_MAX_RETRY`: max retry count, default `3`.
- `TAC_CRAWLER4AI_ENABLED`: enabled by default. Production article fetching uses Crawler4AI only; disabling it is intended for tests or fixture-driven runs.
- `TAC_FETCH_DELAY_SECONDS`: delay after each article fetch attempt, default `1`.
- `TAC_EVALUATION_MAX_ATTEMPTS`: max AI evaluation attempts per article, default `3`.
- `TAC_PROMPT_LANGUAGE`: prompt language, default `zh-CN`; set to `en` for English summaries and reasons.
- `TAC_PROMPT_PATH`: optional explicit prompt path.
- `TAC_FEW_SHOT_DIR`: optional explicit few-shot directory.
- `TAC_AI_RESPONSE_PATH`: test-only fixed AI JSON response.
- `TAC_FETCH_FIXTURE_PATH`: test-only fixed Markdown content.

AI calls use the official `openai` Python SDK. `TAC_MODEL` is passed as the model name, and `TAC_BASE_URL` is passed to the SDK as `base_url`.

## Testing

```powershell
uv sync --extra test
uv run ruff check .
uv run ruff format .
uv run pytest
```

Ruff provides linting and formatting. The tests use offline fixtures and do not require real network or real AI calls.

## Documentation

See [docs/PROJECT.md](docs/PROJECT.md) for the full project design and feature description.
