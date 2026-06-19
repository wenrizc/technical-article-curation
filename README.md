# Technical Article Curation

AI-assisted technical article curation pipeline. The MVP discovers articles from configured RSS/Atom feeds and manual URLs, fetches cleaned Markdown, evaluates quality with a strict JSON schema, stores state in SQLite, and publishes stable JSON/Markdown artifacts under `public/`.

## Quick Start

```powershell
uv sync --extra test
uv run tac migrate
uv run tac discover
uv run tac fetch
uv run tac evaluate
uv run tac publish
```

For a full run:

```powershell
uv run tac run
```

Runtime configuration is read from environment variables. Common variables:

- `OPENAI_API_KEY`
- `TAC_MODEL`
- `TAC_BASE_URL`
- `TAC_STATE_DB`
- `TAC_SOURCES_PATH`
- `TAC_PUBLIC_DIR`
- `TAC_MAX_RETRY`
- `TAC_CRAWLER4AI_ENABLED`：默认启用。设置为 `false`、`0`、`no` 或 `off` 时跳过 Crawler4AI，直接使用 `requests + BeautifulSoup + markdownify` 回退抓取。

AI 调用通过官方 `openai` Python SDK 执行。`TAC_MODEL` 是模型名，`TAC_BASE_URL` 会传给 SDK 的 `base_url`，用于 OpenAI-compatible endpoint。
