# 技术文章精选

语言：[English](PROJECT.md) | [简体中文](PROJECT.zh-CN.md)

## 概述

技术文章精选是一个 AI 辅助的内容流水线，用于发现、评估和发布高质量技术文章。项目关注长期工程价值，而不是短期新闻、营销内容或浅层教程。

项目采用数据优先形态，在 `public/` 下发布稳定的 JSON 和 Markdown 产物，后续可以由网站、团队知识库或其他展示渠道消费。

## 目标

- 从真实技术来源发现候选文章。
- 抓取文章正文并清洗为 Markdown。
- 在 AI 评估前过滤明显重复内容。
- 使用严格 JSON Schema 和 Pydantic 校验进行质量评估。
- 自动收录高置信度高质量文章。
- 使用 SQLite 保存内部状态，支持复跑和审计。
- 将已收录文章发布为公开 JSON 和 Markdown。

## 非目标

- 不做通用新闻聚合器。
- 当前实现不提供网页 UI 或评审后台。
- 当前实现不追求覆盖所有技术来源。
- 当前实现不以实时发布为首要目标。
- 当前实现不提供完整版权处理或自动下架流程。

## 内容判断标准

收录文章应具备长期工程价值。

高质量候选通常包含：

- 真实工程问题和生产经验。
- 系统设计、架构取舍或实现细节。
- 性能、可靠性、安全、基础设施、数据、AI 工程化或开发工具经验。
- 原创实验、案例复盘或独立分析。
- 可迁移到其他团队或系统的实践方法。

系统默认拒收或规避：

- 纯营销稿或产品发布稿。
- 缺少解释的浅层教程。
- 没有工程分析的新闻转述。
- 低质量生成内容。
- 重复或高度相似内容。
- 正文不可访问或正文信息不足的文章。

## 信源

默认信源配置位于 `config/sources.yaml`。当前接入的是已验证可访问的 RSS/Atom 信源，来源包括工程团队、技术社区和个人技术博客。

已接入示例：

- 美团技术团队
- 有赞技术团队
- Cloudflare Blog
- GitHub Engineering
- Dropbox Tech
- Slack Engineering
- Meta Engineering
- Kubernetes Blog
- CNCF Blog
- InfoQ 中文
- SegmentFault
- Martin Fowler
- Julia Evans
- Brendan Gregg
- 阮一峰的网络日志

信源配置支持 RSS/Atom 和手动 URL。手动 URL 应指向具体文章页面，而不是站点首页。

## 架构

代码实现是 `src/tac/` 下的 Python 包。

主要模块：

- `cli`：Typer 命令行入口。
- `config`：基于环境变量的运行配置。
- `db`：SQLite 连接、迁移和持久化工具。
- `models`：Pydantic 模型和枚举。
- `sources`：信源配置加载。
- `discover`：RSS/Atom 和手动 URL 候选发现。
- `fetch`：文章抓取和 Markdown 提取。
- `evaluate`：使用 OpenAI SDK 和 Pydantic 校验进行 AI 评估。
- `publish`：公开 JSON 和 Markdown 生成。
- `utils`：URL 归一化、slug 和时间工具。

## 命令行

CLI 入口是 `tac`。

- `tac migrate`：执行 SQLite 迁移。
- `tac discover`：从配置来源发现候选文章。
- `tac fetch`：抓取并清洗候选文章。
- `tac evaluate`：使用 AI 评估已抓取文章。
- `tac publish`：将已收录文章发布到 `public/`。
- `tac report sources`：查看最近 RSS 信源检查状态。
- `tac report failures`：查看最新抓取失败和评估失败。
- `tac run`：串联执行迁移、发现、抓取、评估和发布。

`fetch`、`evaluate` 和 `run` 支持 `--limit`，便于安全地小批量运行。

## 运行配置

配置通过环境变量提供。

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

## 发现

RSS/Atom 发现使用带重试能力的 `requests.Session` 处理临时 HTTP 失败。每个信源的最新 `ETag` 和 `Last-Modified` 会记录到 SQLite，后续运行会发送条件请求头。遇到 `304 Not Modified` 时跳过该信源解析。

信源级失败会单独记录，不会污染文章状态，也不会阻止手动 URL 或其他信源继续处理。

## 抓取

生产文章抓取只使用 Crawler4AI。测试运行仍可通过 `TAC_FETCH_FIXTURE_PATH` 注入固定 Markdown 内容。

如果 Crawler4AI 返回空 Markdown、抛出异常、不可用，或在没有 fixture 的情况下被关闭，本次抓取会在 `fetches` 中记录为失败。抓取失败不会改变文章的内容评估状态。

## 评估

AI 评估使用官方 OpenAI Python SDK，并通过 `base_url` 支持 OpenAI-compatible 服务。

Prompt 按语言拆分。默认中文提示词位于 `prompts/zh-CN/evaluate.md`，英文提示词位于 `prompts/en/evaluate.md`。few-shot 示例以 JSON 文件形式存放在对应语言目录的 `few_shots/` 下。

AI 响应必须通过以下严格 schema 校验：

- `decision`：收录、拒收或低置信度。
- `confidence`：置信度。
- `dimensions`：工程价值、技术深度、原创性、可复用性和可读性。
- `summary`：公开摘要。
- `tags`：公开标签。
- `recommendation_reason`：公开推荐理由。
- `full_reasoning`：内部完整判断依据，不公开发布。

只有 `decision=accept` 且 `confidence=high` 的文章会自动收录。

评估失败会记录到 `evaluation_failures`，不会写入 `fetches`，也不会修改文章状态。如果模型返回空内容、非法 JSON，或 JSON 无法通过 Pydantic 校验，评估器会最多按 `TAC_EVALUATION_MAX_ATTEMPTS` 重试，并把上一次原始输出和具体解析/校验错误发回模型修正。

## 存储

内部状态存储在 SQLite 中，默认路径为 `data/state.db`。

迁移文件位于 `migrations/*.sql`。

核心表：

- `articles`：文章身份、来源、归一化 URL、slug、状态、重试次数和时间戳。
- `fetches`：抓取状态、Markdown 正文、错误和抓取元数据。
- `evaluations`：AI 判断、置信度、维度、公开字段、内部判断依据、模型和原始 JSON。
- `source_state`：最近 RSS 信源检查状态和条件请求字段。
- `evaluation_failures`：评估失败记录，包括错误、尝试次数和最后一次模型原始返回。

`articles.status` 只表示内容评估状态：`candidate`、`accepted`、`rejected` 或 `low_confidence`。流水线失败状态从 `fetches`、`source_state` 和 `evaluation_failures` 推导。

SQLite 是内部事实来源。公开 JSON 和 Markdown 是派生产物。

## 发布

已收录文章发布到 `public/`。

输出结构：

- `public/index.json`
- `public/articles/{slug}.json`
- `public/articles/{slug}.md`

公开 JSON 字段：

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

公开 JSON 不得包含 `status`、`confidence`、`full_reasoning` 等内部字段。

Markdown 文件包含最小 frontmatter，并在正文顶部显示来源名称、原文链接和抓取时间。

## 测试

测试套件包含单元测试和小型离线端到端 fixture。测试通过固定 RSS、Markdown 和 AI JSON 文件避免真实网络和真实 AI 调用。

运行：

```powershell
uv sync --extra test
uv run ruff check .
uv run ruff format .
uv run pytest
```

## 风险

当前实现会保存并发布抓取后的 Markdown 正文，这会形成文章镜像能力。公开 Markdown 必须保留来源归属和原文链接；后续应补充明确的下架处理、信源级镜像策略以及内容更新/移除流程。
