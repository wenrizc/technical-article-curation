# 技术文章精选

语言：[English](README.md) | [简体中文](README.zh-CN.md)

AI 辅助的技术文章精选流水线。系统从 RSS/Atom 和手动 URL 发现候选文章，抓取并清洗为 Markdown，用严格 JSON Schema 评估内容质量，将内部状态保存到 SQLite，并在 `public/` 下发布稳定的 JSON/Markdown 数据。

## 快速开始

```powershell
uv sync --extra test
uv run uvicorn tac.app:app --host 127.0.0.1 --port 8000 --reload
```

打开本地管理控制台：

<http://127.0.0.1:8000/admin>

FastAPI 应用默认在启动时执行 SQLite 迁移。发现、抓取、评估、发布和完整流水线都通过管理页触发为后台任务。

## FastAPI

服务提供：

- `/admin`：无前端框架的轻量管理控制台。
- `/api/admin/*`：管理 API，可查询全部文章，包括 `archived`。
- `/api/public/*`：公开查询 API，始终排除 `archived`。

主要后台任务入口：

- `POST /api/admin/jobs/discover`
- `POST /api/admin/jobs/fetch`
- `POST /api/admin/jobs/evaluate`
- `POST /api/admin/jobs/publish`
- `POST /api/admin/jobs/run`
- `GET /api/admin/jobs/{job_id}`

## 配置

运行配置通过环境变量提供。

- `OPENAI_API_KEY`：AI 评估使用的 API key。
- `TAC_MODEL`：OpenAI SDK 使用的模型名。
- `TAC_BASE_URL`：OpenAI-compatible 服务的 `base_url`。
- `TAC_STATE_DB`：SQLite 路径，默认 `data/state.db`。
- `TAC_SOURCES_PATH`：信源配置路径，默认 `config/sources.yaml`。
- `TAC_PUBLIC_DIR`：发布目录，默认 `public`。
- `TAC_MAX_RETRY`：最大重试次数，默认 `3`。
- `TAC_CRAWLER4AI_ENABLED`：默认启用。生产文章抓取只使用 Crawler4AI；关闭它主要用于测试或 fixture 驱动运行。
- `TAC_FETCH_DELAY_SECONDS`：每次文章抓取后等待的秒数，默认 `1`。
- `TAC_EVALUATION_MAX_ATTEMPTS`：每篇文章 AI 评估最多尝试次数，默认 `3`。
- `TAC_PROMPT_LANGUAGE`：提示词语言，默认 `zh-CN`；设置为 `en` 时输出英文摘要和推荐理由。
- `TAC_PROMPT_PATH`：可选的显式提示词路径。
- `TAC_FEW_SHOT_DIR`：可选的显式 few-shot 目录。
- `TAC_AI_RESPONSE_PATH`：测试用固定 AI JSON 响应文件。
- `TAC_FETCH_FIXTURE_PATH`：测试用固定 Markdown 内容。
- `TAC_AUTO_MIGRATE`：FastAPI 启动时执行迁移，默认 `true`。
- `TAC_HTTP_MAX_CONCURRENCY`：动态 HTTP 请求并发，默认 `16`。
- `TAC_JOB_MAX_CONCURRENCY`：后台任务并发，默认 `1`。
- `TAC_JOB_QUEUE_LIMIT`：后台任务排队长度，默认 `8`。
- `TAC_FETCH_MAX_CONCURRENCY`：抓取并发，默认 `1`。
- `TAC_EVALUATE_MAX_CONCURRENCY`：评估并发，默认 `1`。
- `TAC_DISCOVER_MAX_CONCURRENCY`：RSS 发现并发，默认 `2`。
- `TAC_MAX_REQUEST_BODY_BYTES`：写请求体大小限制，默认 `1048576`。
- `TAC_FETCH_TIMEOUT_SECONDS`：单篇文章抓取超时，默认 `90`。
- `TAC_AI_TIMEOUT_SECONDS`：AI 请求超时，默认 `90`。
- `TAC_JOB_TIMEOUT_SECONDS`：后台任务总超时，默认 `1800`。
- `TAC_FETCH_MAX_MARKDOWN_BYTES`：抓取 Markdown 大小限制，默认 `2097152`。
- `TAC_JOB_HISTORY_LIMIT`：内存任务历史保留数量，默认 `100`。
- `TAC_DB_BUSY_TIMEOUT_MS`：SQLite busy timeout，默认 `5000`。

AI 调用使用官方 `openai` Python SDK。`TAC_MODEL` 作为模型名传入，`TAC_BASE_URL` 作为 SDK 的 `base_url` 传入。

## 测试

```powershell
uv sync --extra test
uv run ruff check .
uv run ruff format .
uv run pytest
```

Ruff 用于静态检查和格式化。测试使用离线 fixture，不依赖真实网络或真实 AI 调用。

## 文档

完整项目设计和功能说明见 [docs/PROJECT.zh-CN.md](docs/PROJECT.zh-CN.md)。
