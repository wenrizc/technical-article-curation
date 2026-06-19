# Technical Article Curation / 技术文章精选

## Overview / 概述

Technical Article Curation is an AI-assisted pipeline for discovering, evaluating, and publishing high-quality technical articles. The project focuses on long-term engineering value rather than short-lived news, marketing content, or shallow tutorials.

技术文章精选是一个 AI 辅助的内容流水线，用于发现、评估和发布高质量技术文章。项目关注长期工程价值，而不是短期新闻、营销内容或浅层教程。

The MVP is data-first. It publishes stable JSON and Markdown artifacts under `public/`, which can later be consumed by a website, internal knowledge base, or other publishing channel.

MVP 采用数据优先形态，在 `public/` 下发布稳定的 JSON 和 Markdown 产物，后续可以由网站、团队知识库或其他展示渠道消费。

## Goals / 目标

- Discover candidate articles from real technical sources. / 从真实技术来源发现候选文章。
- Fetch and clean article content into Markdown. / 抓取文章正文并清洗为 Markdown。
- Deduplicate obvious repeats before AI evaluation. / 在 AI 评估前过滤明显重复内容。
- Evaluate quality with a strict JSON schema and Pydantic validation. / 使用严格 JSON Schema 和 Pydantic 校验进行质量评估。
- Automatically accept high-confidence, high-quality articles. / 自动收录高置信度高质量文章。
- Store internal state in SQLite for repeatable runs and auditability. / 使用 SQLite 保存内部状态，支持复跑和审计。
- Publish accepted articles as public JSON and Markdown. / 将已收录文章发布为公开 JSON 和 Markdown。

## Non-Goals / 非目标

- This is not a general news aggregator. / 不做通用新闻聚合器。
- The MVP does not provide a web UI or review dashboard. / MVP 不提供网页 UI 或评审后台。
- The MVP does not try to cover every technical source. / MVP 不追求覆盖所有技术来源。
- The MVP does not prioritize real-time publishing. / MVP 不以实时发布为首要目标。
- The MVP does not perform full copyright or takedown automation. / MVP 不实现完整版权处理或自动下架流程。

## Content Criteria / 内容判断标准

Accepted articles should show durable engineering value.

收录文章应具备长期工程价值。

Strong candidates usually include:

高质量候选通常包含：

- Real engineering problems and production experience. / 真实工程问题和生产经验。
- System design, architecture tradeoffs, or implementation details. / 系统设计、架构取舍或实现细节。
- Performance, reliability, security, infrastructure, data, AI engineering, or developer tooling lessons. / 性能、可靠性、安全、基础设施、数据、AI 工程化或开发工具经验。
- Original experiments, case studies, or independent analysis. / 原创实验、案例复盘或独立分析。
- Reusable practices that can transfer to other teams or systems. / 可迁移到其他团队或系统的实践方法。

The system rejects or avoids:

系统默认拒收或规避：

- Pure marketing posts or product release notes. / 纯营销稿或产品发布稿。
- Shallow tutorials with little explanation. / 缺少解释的浅层教程。
- News summaries without engineering analysis. / 没有工程分析的新闻转述。
- Low-quality generated content. / 低质量生成内容。
- Duplicate or highly similar content. / 重复或高度相似内容。
- Articles whose body cannot be fetched with enough useful content. / 正文不可访问或正文信息不足的文章。

## Sources / 信源

The default source configuration is in `config/sources.yaml`. MVP sources are verified RSS/Atom feeds from engineering teams, technical communities, and personal technical blogs.

默认信源配置位于 `config/sources.yaml`。MVP 接入的是已验证可访问的 RSS/Atom 信源，来源包括工程团队、技术社区和个人技术博客。

Included examples:

已接入示例：

- Meituan Tech Team / 美团技术团队
- Youzan Tech / 有赞技术团队
- Cloudflare Blog
- GitHub Engineering
- Dropbox Tech
- Slack Engineering
- Meta Engineering
- Kubernetes Blog
- CNCF Blog
- InfoQ Chinese / InfoQ 中文
- SegmentFault
- Martin Fowler
- Julia Evans
- Brendan Gregg
- Ruan Yi Feng / 阮一峰的网络日志

The source configuration supports RSS/Atom feeds and manual URLs. Manual URLs should point to article pages, not site homepages.

信源配置支持 RSS/Atom 和手动 URL。手动 URL 应指向具体文章页面，而不是站点首页。

## Architecture / 架构

The implementation is a Python package under `src/tac/`.

代码实现是 `src/tac/` 下的 Python 包。

Main modules:

主要模块：

- `cli`: Typer command-line interface. / Typer 命令行入口。
- `config`: environment-based runtime configuration. / 基于环境变量的运行配置。
- `db`: SQLite connection, migrations, and persistence helpers. / SQLite 连接、迁移和持久化工具。
- `models`: Pydantic models and enums. / Pydantic 模型和枚举。
- `sources`: source configuration loading. / 信源配置加载。
- `discover`: RSS/Atom and manual URL discovery. / RSS/Atom 和手动 URL 候选发现。
- `fetch`: article fetching and Markdown extraction. / 文章抓取和 Markdown 提取。
- `evaluate`: AI evaluation with OpenAI SDK and Pydantic validation. / 使用 OpenAI SDK 和 Pydantic 校验进行 AI 评估。
- `publish`: public JSON and Markdown generation. / 公开 JSON 和 Markdown 生成。
- `utils`: URL normalization, title normalization, slug helpers, and time helpers. / URL 归一化、标题归一化、slug 和时间工具。

## CLI / 命令行

The CLI entry point is `tac`.

CLI 入口是 `tac`。

- `tac migrate`: apply SQLite migrations. / 执行 SQLite 迁移。
- `tac discover`: discover candidate articles from configured sources. / 从配置来源发现候选文章。
- `tac fetch`: fetch and clean candidate articles. / 抓取并清洗候选文章。
- `tac evaluate`: evaluate fetched articles with AI. / 使用 AI 评估已抓取文章。
- `tac publish`: publish accepted articles to `public/`. / 将已收录文章发布到 `public/`。
- `tac run`: run migrate, discover, fetch, evaluate, and publish. / 串联执行迁移、发现、抓取、评估和发布。

`fetch`, `evaluate`, and `run` support `--limit` for safer incremental operation.

`fetch`、`evaluate` 和 `run` 支持 `--limit`，便于安全地小批量运行。

## Runtime Configuration / 运行配置

Configuration is provided through environment variables.

配置通过环境变量提供。

- `OPENAI_API_KEY`: API key for AI evaluation. / AI 评估使用的 API key。
- `TAC_MODEL`: model name used by the OpenAI SDK. / OpenAI SDK 使用的模型名。
- `TAC_BASE_URL`: OpenAI-compatible `base_url`. / OpenAI-compatible 服务的 `base_url`。
- `TAC_STATE_DB`: SQLite path, default `data/state.db`. / SQLite 路径，默认 `data/state.db`。
- `TAC_SOURCES_PATH`: source configuration path, default `config/sources.yaml`. / 信源配置路径，默认 `config/sources.yaml`。
- `TAC_PUBLIC_DIR`: publish output directory, default `public`. / 发布目录，默认 `public`。
- `TAC_MAX_RETRY`: max retry count, default `3`. / 最大重试次数，默认 `3`。
- `TAC_CRAWLER4AI_ENABLED`: enabled by default; set to `false`, `0`, `no`, `off`, or `disabled` to use fallback fetching directly. / 默认启用；设置为 `false`、`0`、`no`、`off` 或 `disabled` 时直接使用回退抓取。
- `TAC_PROMPT_LANGUAGE`: prompt language, default `zh-CN`; set to `en` for English summaries and reasons. / 提示词语言，默认 `zh-CN`；设置为 `en` 时输出英文摘要和推荐理由。
- `TAC_PROMPT_PATH`: optional explicit prompt path. / 可选的显式提示词路径。
- `TAC_FEW_SHOT_DIR`: optional explicit few-shot directory. / 可选的显式 few-shot 目录。
- `TAC_AI_RESPONSE_PATH`: test-only fixed AI JSON response. / 测试用固定 AI JSON 响应文件。
- `TAC_FETCH_FIXTURE_PATH`: test-only fixed Markdown content. / 测试用固定 Markdown 内容。

## Fetching / 抓取

The fetch stage defaults to Crawler4AI when the optional `crawler` extra is installed. If Crawler4AI is disabled or fails, the system falls back to `requests + BeautifulSoup + markdownify`.

抓取阶段在安装可选 `crawler` extra 时默认优先使用 Crawler4AI。如果 Crawler4AI 被禁用或执行失败，系统回退到 `requests + BeautifulSoup + markdownify`。

The fallback fetcher uses browser-like headers, follows redirects, retries a small number of times, removes common non-content elements, and converts the main content to Markdown.

回退抓取器会携带常见浏览器请求头、跟随重定向、进行少量重试、移除常见非正文元素，并将主体内容转换为 Markdown。

## Evaluation / 评估

AI evaluation uses the official OpenAI Python SDK with `base_url` support for OpenAI-compatible endpoints.

AI 评估使用官方 OpenAI Python SDK，并通过 `base_url` 支持 OpenAI-compatible 服务。

Prompts are split by language. The default Chinese prompt is stored in `prompts/zh-CN/evaluate.md`, and the English prompt is stored in `prompts/en/evaluate.md`. Few-shot examples are stored as JSON files under each language's `few_shots/` directory.

Prompt 按语言拆分。默认中文提示词位于 `prompts/zh-CN/evaluate.md`，英文提示词位于 `prompts/en/evaluate.md`。few-shot 示例以 JSON 文件形式存放在对应语言目录的 `few_shots/` 下。

The AI response must validate against this strict schema:

AI 响应必须通过以下严格 schema 校验：

- `decision`: `accept`, `reject`, or `low_confidence`. / 收录、拒收或低置信度。
- `confidence`: `high`, `medium`, or `low`. / 置信度。
- `dimensions`: engineering value, technical depth, originality, reusability, and readability. / 工程价值、技术深度、原创性、可复用性和可读性。
- `summary`: public summary. / 公开摘要。
- `tags`: public tags. / 公开标签。
- `recommendation_reason`: public recommendation reason. / 公开推荐理由。
- `full_reasoning`: internal reasoning, never published publicly. / 内部完整判断依据，不公开发布。

Only articles with `decision=accept` and `confidence=high` are automatically accepted.

只有 `decision=accept` 且 `confidence=high` 的文章会自动收录。

## Storage / 存储

Internal state is stored in SQLite, defaulting to `data/state.db`.

内部状态存储在 SQLite 中，默认路径为 `data/state.db`。

Migrations live in `migrations/*.sql`.

迁移文件位于 `migrations/*.sql`。

Core tables:

核心表：

- `articles`: article identity, source, normalized URL/title, slug, status, retry count, and timestamps. / 文章身份、来源、归一化 URL/标题、slug、状态、重试次数和时间戳。
- `fetches`: fetch status, Markdown body, errors, and crawler metadata. / 抓取状态、Markdown 正文、错误和抓取元数据。
- `evaluations`: AI decision, confidence, dimensions, public fields, internal reasoning, model, and raw JSON. / AI 判断、置信度、维度、公开字段、内部判断依据、模型和原始 JSON。

SQLite is the internal source of truth. Published JSON and Markdown are derived artifacts.

SQLite 是内部事实来源。公开 JSON 和 Markdown 是派生产物。

## Publishing / 发布

Accepted articles are published under `public/`.

已收录文章发布到 `public/`。

Output structure:

输出结构：

- `public/index.json`
- `public/articles/{slug}.json`
- `public/articles/{slug}.md`

Public JSON fields:

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

Public JSON must not include internal fields such as `status`, `confidence`, or `full_reasoning`.

公开 JSON 不得包含 `status`、`confidence`、`full_reasoning` 等内部字段。

Markdown files include minimal frontmatter and a visible source block with source name, original URL, and fetch time.

Markdown 文件包含最小 frontmatter，并在正文顶部显示来源名称、原文链接和抓取时间。

## Testing / 测试

The test suite uses unit tests and a small offline end-to-end fixture. It avoids real network and real AI calls by using fixed RSS, Markdown, and AI JSON files.

测试套件包含单元测试和小型离线端到端 fixture。测试通过固定 RSS、Markdown 和 AI JSON 文件避免真实网络和真实 AI 调用。

Run:

运行：

```powershell
uv sync --extra test
uv run pytest
```

## Risks / 风险

The MVP intentionally stores and publishes fetched Markdown content. This creates article mirroring behavior. Published Markdown must preserve source attribution and original URLs, but future work should add explicit takedown handling, source-level mirror policy, and content update/removal workflows.

MVP 会保存并发布抓取后的 Markdown 正文，这会形成文章镜像能力。公开 Markdown 必须保留来源归属和原文链接；后续应补充明确的下架处理、信源级镜像策略以及内容更新/移除流程。
