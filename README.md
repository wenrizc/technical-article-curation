# Technical Article Curation

Languages: [English](README.md) | [简体中文](README.zh-CN.md)

AI-assisted technical article curation pipeline. It discovers articles from RSS/Atom feeds and manual URLs, fetches cleaned Markdown, evaluates quality with a strict JSON schema, stores internal state in SQLite, and publishes stable JSON/Markdown artifacts under `public/`.

## Quick Start

```powershell
uv sync --extra test
uv run uvicorn tac.app:app --host 127.0.0.1 --port 8000 --reload
```

Open the local admin console:

<http://127.0.0.1:8000/admin>

The FastAPI app runs SQLite migrations on startup by default. Use the admin page to trigger discover, fetch, evaluate, publish, or the full pipeline as background jobs.

## FastAPI

The service exposes:

- `/admin`: lightweight no-framework management console.
- `/api/admin/*`: management API. It can see all articles, including `archived`.
- `/api/public/*`: public query API. It always excludes `archived`.

Main management job endpoints:

- `POST /api/admin/jobs/discover`
- `POST /api/admin/jobs/fetch`
- `POST /api/admin/jobs/evaluate`
- `POST /api/admin/jobs/publish`
- `POST /api/admin/jobs/run`
- `GET /api/admin/jobs/{job_id}`

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
- `TAC_AUTO_MIGRATE`: run migrations on FastAPI startup, default `true`.
- `TAC_HTTP_MAX_CONCURRENCY`: dynamic HTTP request concurrency, default `16`.
- `TAC_JOB_MAX_CONCURRENCY`: background job concurrency, default `1`.
- `TAC_JOB_QUEUE_LIMIT`: queued background job limit, default `8`.
- `TAC_FETCH_MAX_CONCURRENCY`: fetch concurrency, default `1`.
- `TAC_EVALUATE_MAX_CONCURRENCY`: evaluation concurrency, default `1`.
- `TAC_DISCOVER_MAX_CONCURRENCY`: RSS discovery concurrency, default `2`.
- `TAC_MAX_REQUEST_BODY_BYTES`: max write request body size, default `1048576`.
- `TAC_FETCH_TIMEOUT_SECONDS`: per-article fetch timeout, default `90`.
- `TAC_AI_TIMEOUT_SECONDS`: AI request timeout, default `90`.
- `TAC_JOB_TIMEOUT_SECONDS`: background job timeout, default `1800`.
- `TAC_FETCH_MAX_MARKDOWN_BYTES`: fetched Markdown size limit, default `2097152`.
- `TAC_JOB_HISTORY_LIMIT`: in-memory job history limit, default `100`.
- `TAC_DB_BUSY_TIMEOUT_MS`: SQLite busy timeout, default `5000`.

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
