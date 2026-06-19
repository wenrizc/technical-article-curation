# Technical Article Curation

Languages: [English](PROJECT.md) | [简体中文](PROJECT.zh-CN.md)

## Overview

Technical Article Curation is an AI-assisted pipeline for discovering, evaluating, and publishing high-quality technical articles. The project focuses on long-term engineering value rather than short-lived news, marketing content, or shallow tutorials.

The project is data-first. It publishes stable JSON and Markdown artifacts under `public/`, which can later be consumed by a website, internal knowledge base, or other publishing channel.

## Goals

- Discover candidate articles from real technical sources.
- Fetch and clean article content into Markdown.
- Deduplicate obvious repeats before AI evaluation.
- Evaluate quality with a strict JSON schema and Pydantic validation.
- Automatically accept high-confidence, high-quality articles.
- Store internal state in SQLite for repeatable runs and auditability.
- Publish accepted articles as public JSON and Markdown.

## Non-Goals

- This is not a general news aggregator.
- The current implementation does not provide a web UI or review dashboard.
- The current implementation does not try to cover every technical source.
- The current implementation does not prioritize real-time publishing.
- The current implementation does not perform full copyright or takedown automation.

## Content Criteria

Accepted articles should show durable engineering value.

Strong candidates usually include:

- Real engineering problems and production experience.
- System design, architecture tradeoffs, or implementation details.
- Performance, reliability, security, infrastructure, data, AI engineering, or developer tooling lessons.
- Original experiments, case studies, or independent analysis.
- Reusable practices that can transfer to other teams or systems.

The system rejects or avoids:

- Pure marketing posts or product release notes.
- Shallow tutorials with little explanation.
- News summaries without engineering analysis.
- Low-quality generated content.
- Duplicate or highly similar content.
- Articles whose body cannot be fetched with enough useful content.

## Sources

The default source configuration is in `config/sources.yaml`. Current sources are verified RSS/Atom feeds from engineering teams, technical communities, and personal technical blogs.

Included examples:

- Meituan Tech Team
- Youzan Tech
- Cloudflare Blog
- GitHub Engineering
- Dropbox Tech
- Slack Engineering
- Meta Engineering
- Kubernetes Blog
- CNCF Blog
- InfoQ Chinese
- SegmentFault
- Martin Fowler
- Julia Evans
- Brendan Gregg
- Ruan Yi Feng

The source configuration supports RSS/Atom feeds and manual URLs. Manual URLs should point to article pages, not site homepages.

## Architecture

The implementation is a Python package under `src/tac/`.

Main modules:

- `cli`: Typer command-line interface.
- `config`: environment-based runtime configuration.
- `db`: SQLite connection, migrations, and persistence helpers.
- `models`: Pydantic models and enums.
- `sources`: source configuration loading.
- `discover`: RSS/Atom and manual URL discovery.
- `fetch`: article fetching and Markdown extraction.
- `evaluate`: AI evaluation with OpenAI SDK and Pydantic validation.
- `publish`: public JSON and Markdown generation.
- `utils`: URL normalization, title normalization, slug helpers, and time helpers.

## CLI

The CLI entry point is `tac`.

- `tac migrate`: apply SQLite migrations.
- `tac discover`: discover candidate articles from configured sources.
- `tac fetch`: fetch and clean candidate articles.
- `tac evaluate`: evaluate fetched articles with AI.
- `tac publish`: publish accepted articles to `public/`.
- `tac run`: run migrate, discover, fetch, evaluate, and publish.

`fetch`, `evaluate`, and `run` support `--limit` for safer incremental operation.

## Runtime Configuration

Configuration is provided through environment variables.

- `OPENAI_API_KEY`: API key for AI evaluation.
- `TAC_MODEL`: model name used by the OpenAI SDK.
- `TAC_BASE_URL`: OpenAI-compatible `base_url`.
- `TAC_STATE_DB`: SQLite path, default `data/state.db`.
- `TAC_SOURCES_PATH`: source configuration path, default `config/sources.yaml`.
- `TAC_PUBLIC_DIR`: publish output directory, default `public`.
- `TAC_MAX_RETRY`: max retry count, default `3`.
- `TAC_CRAWLER4AI_ENABLED`: enabled by default; set to `false`, `0`, `no`, `off`, or `disabled` to use fallback fetching directly.
- `TAC_PROMPT_LANGUAGE`: prompt language, default `zh-CN`; set to `en` for English summaries and reasons.
- `TAC_PROMPT_PATH`: optional explicit prompt path.
- `TAC_FEW_SHOT_DIR`: optional explicit few-shot directory.
- `TAC_AI_RESPONSE_PATH`: test-only fixed AI JSON response.
- `TAC_FETCH_FIXTURE_PATH`: test-only fixed Markdown content.

## Fetching

The fetch stage defaults to Crawler4AI when the optional `crawler` extra is installed. If Crawler4AI is disabled or fails, the system falls back to `requests + BeautifulSoup + markdownify`.

The fallback fetcher uses browser-like headers, follows redirects, retries a small number of times, removes common non-content elements, and converts the main content to Markdown.

## Evaluation

AI evaluation uses the official OpenAI Python SDK with `base_url` support for OpenAI-compatible endpoints.

Prompts are split by language. The default Chinese prompt is stored in `prompts/zh-CN/evaluate.md`, and the English prompt is stored in `prompts/en/evaluate.md`. Few-shot examples are stored as JSON files under each language's `few_shots/` directory.

The AI response must validate against this strict schema:

- `decision`: `accept`, `reject`, or `low_confidence`.
- `confidence`: `high`, `medium`, or `low`.
- `dimensions`: engineering value, technical depth, originality, reusability, and readability.
- `summary`: public summary.
- `tags`: public tags.
- `recommendation_reason`: public recommendation reason.
- `full_reasoning`: internal reasoning, never published publicly.

Only articles with `decision=accept` and `confidence=high` are automatically accepted.

## Storage

Internal state is stored in SQLite, defaulting to `data/state.db`.

Migrations live in `migrations/*.sql`.

Core tables:

- `articles`: article identity, source, normalized URL/title, slug, status, retry count, and timestamps.
- `fetches`: fetch status, Markdown body, errors, and crawler metadata.
- `evaluations`: AI decision, confidence, dimensions, public fields, internal reasoning, model, and raw JSON.

SQLite is the internal source of truth. Published JSON and Markdown are derived artifacts.

## Publishing

Accepted articles are published under `public/`.

Output structure:

- `public/index.json`
- `public/articles/{slug}.json`
- `public/articles/{slug}.md`

Public JSON fields:

- `slug`
- `title`
- `url`
- `source`
- `collected_at`
- `summary`
- `tags`
- `recommendation_reason`
- `dimensions`
- `markdown_path`

Public JSON must not include internal fields such as `status`, `confidence`, or `full_reasoning`.

Markdown files include minimal frontmatter and a visible source block with source name, original URL, and fetch time.

## Testing

The test suite uses unit tests and a small offline end-to-end fixture. It avoids real network and real AI calls by using fixed RSS, Markdown, and AI JSON files.

Run:

```powershell
uv sync --extra test
uv run pytest
```

## Risks

The current implementation intentionally stores and publishes fetched Markdown content. This creates article mirroring behavior. Published Markdown must preserve source attribution and original URLs, but future work should add explicit takedown handling, source-level mirror policy, and content update/removal workflows.
