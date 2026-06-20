# 技术文章精选

语言：[English](README.md) | [简体中文](README.zh-CN.md)

AI 辅助的技术文章精选流水线。系统从 RSS/Atom 和手动 URL 发现候选文章，抓取并清洗为 Markdown，用严格 JSON Schema 评估内容质量，将内部状态保存到 SQLite，并在 `public/` 下发布稳定的 JSON/Markdown 数据。

## 快速开始

```powershell
uv sync --extra test
uv run tac migrate
uv run tac discover
uv run tac fetch
uv run tac evaluate
uv run tac publish
```

运行完整流水线：

```powershell
uv run tac run
```

## 命令行

- `tac migrate`：执行 SQLite 迁移。
- `tac discover`：发现候选文章。
- `tac fetch`：抓取并清洗文章 Markdown。
- `tac evaluate`：使用 AI 评估已抓取文章。
- `tac publish`：发布已收录文章。
- `tac report sources`：查看最近 RSS 信源检查状态。
- `tac report failures`：查看最新抓取失败和评估失败。
- `tac run`：执行完整流水线。

`fetch`、`evaluate` 和 `run` 支持 `--limit`，便于小批量运行。

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
