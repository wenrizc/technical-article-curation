# Technical Article Curation / 技术文章精选

AI-assisted technical article curation pipeline. It discovers articles from RSS/Atom feeds and manual URLs, fetches cleaned Markdown, evaluates quality with a strict JSON schema, stores internal state in SQLite, and publishes stable JSON/Markdown artifacts under `public/`.

AI 辅助的技术文章精选流水线。系统从 RSS/Atom 和手动 URL 发现候选文章，抓取并清洗为 Markdown，用严格 JSON Schema 评估内容质量，将内部状态保存到 SQLite，并在 `public/` 下发布稳定的 JSON/Markdown 数据。

## Quick Start / 快速开始

```powershell
uv sync --extra test
uv run tac migrate
uv run tac discover
uv run tac fetch
uv run tac evaluate
uv run tac publish
```

Run the full pipeline:

运行完整流水线：

```powershell
uv run tac run
```

## CLI / 命令行

- `tac migrate`: apply SQLite migrations. / 执行 SQLite 迁移。
- `tac discover`: discover candidate articles. / 发现候选文章。
- `tac fetch`: fetch and clean article Markdown. / 抓取并清洗文章 Markdown。
- `tac evaluate`: evaluate fetched articles with AI. / 使用 AI 评估已抓取文章。
- `tac publish`: publish accepted articles. / 发布已收录文章。
- `tac run`: run the full pipeline. / 执行完整流水线。

`fetch`, `evaluate`, and `run` support `--limit`.

`fetch`、`evaluate` 和 `run` 支持 `--limit`，便于小批量运行。

## Configuration / 配置

Runtime configuration is read from environment variables.

运行配置通过环境变量提供。

- `OPENAI_API_KEY`: API key for AI evaluation. / AI 评估使用的 API key。
- `TAC_MODEL`: model name used by the OpenAI SDK. / OpenAI SDK 使用的模型名。
- `TAC_BASE_URL`: OpenAI-compatible `base_url`. / OpenAI-compatible 服务的 `base_url`。
- `TAC_STATE_DB`: SQLite path, default `data/state.db`. / SQLite 路径，默认 `data/state.db`。
- `TAC_SOURCES_PATH`: source config path, default `config/sources.yaml`. / 信源配置路径，默认 `config/sources.yaml`。
- `TAC_PUBLIC_DIR`: publish output directory, default `public`. / 发布目录，默认 `public`。
- `TAC_MAX_RETRY`: max retry count, default `3`. / 最大重试次数，默认 `3`。
- `TAC_CRAWLER4AI_ENABLED`: enabled by default. Set to `false`, `0`, `no`, `off`, or `disabled` to skip Crawler4AI and use `requests + BeautifulSoup + markdownify` directly. / 默认启用。设置为 `false`、`0`、`no`、`off` 或 `disabled` 时跳过 Crawler4AI，直接使用 `requests + BeautifulSoup + markdownify` 回退抓取。
- `TAC_AI_RESPONSE_PATH`: test-only fixed AI JSON response. / 测试用固定 AI JSON 响应文件。
- `TAC_FETCH_FIXTURE_PATH`: test-only fixed Markdown content. / 测试用固定 Markdown 内容。

AI calls use the official `openai` Python SDK. `TAC_MODEL` is passed as the model name, and `TAC_BASE_URL` is passed to the SDK as `base_url`.

AI 调用使用官方 `openai` Python SDK。`TAC_MODEL` 作为模型名传入，`TAC_BASE_URL` 作为 SDK 的 `base_url` 传入。

## Testing / 测试

```powershell
uv sync --extra test
uv run pytest
```

The tests use offline fixtures and do not require real network or real AI calls.

测试使用离线 fixture，不依赖真实网络或真实 AI 调用。

## Documentation / 文档

See [docs/PROJECT.md](docs/PROJECT.md) for the full bilingual project design and feature description.

完整的中英双语项目设计和功能说明见 [docs/PROJECT.md](docs/PROJECT.md)。
