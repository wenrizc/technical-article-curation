# 技术与成长精选

## 概述

技术与成长精选是一个 AI 辅助的内容流水线，用于发现、评估和发布计算机领域高质量内容。项目关注长期参考价值，既包括工程实践和技术深文，也包括科研议题、论文理解、学习路线、求学经历和开发者成长心得。

项目采用数据优先形态，在 `public/` 下发布稳定的 JSON 和 Markdown 产物，后续可以由网站、团队知识库或其他展示渠道消费。

## 目标

- 从真实技术、科研和开发者成长来源发现候选内容。
- 抓取文章正文并清洗为 Markdown。
- 在 AI 评估前过滤明显重复内容。
- 使用严格 JSON Schema 和 Pydantic 校验进行质量评估。
- 根据 `decision` 自动收录高质量文章。
- 使用 SQLite 保存内部状态，支持复跑和审计。
- 将已收录文章发布为公开 JSON 和 Markdown。

## 非目标

- 不做通用新闻聚合器。
- 当前实现不提供多用户认证、角色权限或完整评审工作流。
- 当前实现不追求覆盖所有技术来源。
- 当前实现不以实时发布为首要目标。
- 当前实现不提供完整版权处理或自动下架流程。

## 内容判断标准

收录内容应具备计算机领域长期参考价值。

高质量候选通常包含：

- 真实工程问题和生产经验。
- 系统设计、架构取舍或实现细节。
- 性能、可靠性、安全、基础设施、数据、AI 工程化或开发工具经验。
- 计算机科研议题、论文解读、研究方向分析、实验方法或学术脉络梳理。
- 计算机科研方法、选题、复现、实验设计、负结果或研究训练反思。
- 具体的学习路线、求学路径、课程/论文/项目组合和阶段性方法。
- 原创实验、案例复盘或独立分析。
- 可迁移到其他团队、系统、学习阶段、研究方向或职业情境的方法。

系统默认拒收或规避：

- 纯营销稿或产品发布稿。
- 缺少解释的浅层教程。
- 没有工程分析的新闻转述。
- 泛泛人生感悟、鸡汤或无计算机主题的个人随笔。
- 只罗列论文标题但缺少理解和判断的周报。
- 低质量生成内容。
- 重复或高度相似内容。
- 正文不可访问或正文信息不足的文章。

## 信源

默认信源配置位于 `config/sources.yaml`。当前接入的是已验证可访问的 RSS/Atom 信源，来源包括工程团队、技术社区和个人技术博客。平台型来源可以通过 RSSHub 作为上游 feed 接入。

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

信源配置统一使用 `feed` 字段。`feed.type=direct` 直接请求 RSS/Atom URL，`feed.type=rsshub` 通过 RSSHub route 生成 feed URL。手动 URL 应指向具体文章页面，而不是站点首页。

```yaml
sources:
  - name: "Cloudflare Blog"
    site_url: "https://blog.cloudflare.com/"
    feed:
      type: "direct"
      url: "https://blog.cloudflare.com/rss/"

  - name: "知乎热榜"
    site_url: "https://www.zhihu.com/hot"
    publish_policy: "summary_only"
    feed:
      type: "rsshub"
      route: "/zhihu/hot"
      params:
        limit: 20
```

## 架构

代码实现是 `src/tac/` 下的 Python 包，当前按入口层、应用层、领域层、基础设施层和共享工具分层。

主要模块：

- `main`：FastAPI 应用入口和应用工厂。
- `settings`：基于环境变量的运行配置。
- `web`：HTTP 层，包括依赖注入、安全中间件、管理 API、公开 API 和管理页静态资源。
- `application`：应用编排层，包括后台任务、完整流水线和各阶段 use case。
- `domain`：Pydantic 模型、枚举和领域数据结构。
- `infrastructure`：SQLite 持久化、信源 YAML 读取等外部资源适配。
- `shared`：URL 归一化、slug、时间、原子写文件和 YAML 标量等通用工具。

## FastAPI

服务入口是 `tac.main:app`。

本地运行：

```powershell
uv run uvicorn tac.main:app --host 127.0.0.1 --port 1104 --reload
```

- `/admin`：本地轻量管理控制台。
- `/api/admin/*`：管理 API，可查询和调整内部文章状态。
- `/api/public/*`：公开 API，只返回已收录的 `accepted` 文章。
- `/feed.xml` 和 `/api/public/feed.xml`：公开 RSS 2.0 订阅。

管理任务接口用于触发后台任务：

- `POST /api/admin/jobs/discover`
- `POST /api/admin/jobs/fetch`
- `POST /api/admin/jobs/evaluate`
- `POST /api/admin/jobs/publish`
- `POST /api/admin/jobs/run`
- `GET /api/admin/jobs/{job_id}`

## 运行配置

配置通过环境变量提供。

- `OPENAI_API_KEY`：AI 评估使用的 API key。
- `TAC_MODEL`：OpenAI SDK 使用的模型名。
- `TAC_BASE_URL`：OpenAI-compatible 服务的 `base_url`。
- `TAC_STATE_DB`：SQLite 路径，默认 `data/state.db`。
- `TAC_MIGRATIONS_DIR`：SQLite 迁移目录，默认 `migrations`。
- `TAC_SOURCES_PATH`：信源配置路径，默认 `config/sources.yaml`。
- `TAC_PUBLIC_DIR`：发布目录，默认 `public`。
- `TAC_MAX_RETRY`：最大重试次数，默认 `3`。
- `TAC_CRAWLER4AI_ENABLED`：默认启用。生产文章抓取只使用 Crawler4AI；关闭它主要用于测试或 fixture 驱动运行。生产运行请安装 `--extra crawler`。
  Crawler4AI 当前依赖 `lxml<6`，`--extra crawler` 建议使用 Python 3.11-3.13；Python 3.14 可运行核心服务、测试和 fixture 驱动流程。
- `TAC_FETCH_DELAY_SECONDS`：每次文章抓取后等待的秒数，默认 `1`。
- `TAC_EVALUATION_MAX_ATTEMPTS`：每篇文章 AI 评估最多尝试次数，默认 `3`。
- `TAC_PROMPT_LANGUAGE`：提示词语言，当前仅支持 `zh-CN`。
- `TAC_PROMPT_PATH`：可选的显式提示词路径。
- `TAC_FEW_SHOT_DIR`：可选的显式 few-shot 目录。
- `TAC_AI_RESPONSE_PATH`：测试用固定 AI JSON 响应文件。
- `TAC_FETCH_FIXTURE_PATH`：测试用固定 Markdown 内容。
- `TAC_AUTO_MIGRATE`：FastAPI 启动时执行 SQLite 迁移，默认 `true`。
- `TAC_HTTP_MAX_CONCURRENCY`：动态 HTTP 请求并发，默认 `16`。
- `TAC_JOB_MAX_CONCURRENCY`：后台任务并发，默认 `1`。
- `TAC_JOB_QUEUE_LIMIT`：后台任务排队长度，默认 `8`。
- `TAC_FETCH_MAX_CONCURRENCY`：阶段内文章抓取并发，默认 `1`。
- `TAC_EVALUATE_MAX_CONCURRENCY`：阶段内 AI 评估并发，默认 `1`。
- `TAC_DISCOVER_MAX_CONCURRENCY`：阶段内 RSS 发现并发，默认 `2`。
- `TAC_MAX_REQUEST_BODY_BYTES`：写请求体大小限制，默认 `1048576`。
- `TAC_FETCH_TIMEOUT_SECONDS`：单篇文章抓取超时，默认 `90`。
- `TAC_AI_TIMEOUT_SECONDS`：AI 请求超时，默认 `90`。
- `TAC_JOB_TIMEOUT_SECONDS`：后台任务总超时，默认 `1800`。
- `TAC_FETCH_MAX_MARKDOWN_BYTES`：抓取 Markdown 大小限制，默认 `2097152`。
- `TAC_JOB_HISTORY_LIMIT`：内存任务历史保留数量，默认 `100`。
- `TAC_DB_BUSY_TIMEOUT_MS`：SQLite busy timeout，默认 `5000`。
- `TAC_SCHEDULER_ENABLED`：启用内置定时调度，默认 `false`。
- `TAC_SCHEDULE_RUN_CRON`：完整流水线 `run` 的 5 段 cron 表达式，默认 `0 8 * * *`。
- `TAC_SCHEDULE_TIMEZONE`：定时调度时区，默认 `UTC`。
- `TAC_SCHEDULER_POLL_SECONDS`：调度器轮询间隔，默认 `30`。
- `TAC_RSSHUB_ENABLED`：启用 RSSHub feed 来源，默认 `false`。
- `TAC_RSSHUB_INSTANCE`：默认 RSSHub 实例地址，默认 `http://127.0.0.1:1200`。
- `TAC_RSSHUB_STARTUP_CHECK`：启动时检查 RSSHub 可达性，默认 `false`。
- `TAC_RSSHUB_STRICT_STARTUP`：RSSHub 检查失败时阻止应用启动，默认 `false`。
- `TAC_RSSHUB_TIMEOUT_SECONDS`：RSSHub feed 请求超时时间，默认 `30`。
- `TAC_PUBLIC_BASE_URL`：公开链接基准地址，默认 `http://127.0.0.1:1104`。
- `TAC_PUBLIC_FEED_TITLE`：公开 RSS 标题，默认 `技术与成长精选`。
- `TAC_PUBLIC_FEED_DESCRIPTION`：公开 RSS 描述。
- `TAC_PUBLIC_FEED_LANGUAGE`：公开 RSS 语言，默认 `zh-CN`。
- `TAC_PUBLIC_FEED_TTL_MINUTES`：公开 RSS TTL，默认 `5`。

## 发现

Feed 发现使用带重试能力的 `requests.Session` 处理临时 HTTP 失败。普通 RSS/Atom 直接请求 `feed.url`，RSSHub 来源先用 `TAC_RSSHUB_INSTANCE` 和 `feed.route` 拼出 feed URL。每个信源的最新 `ETag` 和 `Last-Modified` 会记录到 SQLite，后续运行会发送条件请求头。遇到 `304 Not Modified` 时跳过该信源解析。

信源级失败会单独记录，不会污染文章状态，也不会阻止手动 URL 或其他信源继续处理。

## 抓取

生产文章抓取只使用 Crawler4AI。测试运行仍可通过 `TAC_FETCH_FIXTURE_PATH` 注入固定 Markdown 内容。

如果 Crawler4AI 返回空 Markdown、抛出异常、不可用，或在没有 fixture 的情况下被关闭，本次抓取会在 `fetches` 中记录为失败。抓取失败不会改变文章的内容评估状态。

## 评估

AI 评估使用官方 OpenAI Python SDK，并通过 `base_url` 支持 OpenAI-compatible 服务。

默认中文提示词位于 `prompts/zh-CN/evaluate.md`。few-shot 示例以 JSON 文件形式存放在 `prompts/zh-CN/few_shots/` 下。

AI 响应必须通过以下严格 schema 校验：

- `decision`：收录、拒收或低置信度。
- `content_type`：技术文章、工程实践、科研议题、科研思考、学习路线、个人心得、职业经验或工具笔记。
- `dimensions`：领域相关性、长期价值、内容深度、原创性、可迁移性和可读性。
- `summary`：公开摘要。
- `tags`：从正式词库中选择的公开标签。
- `suggested_tags`：AI 希望新增到词库的标签建议。
- `recommendation_reason`：公开推荐理由。
- `full_reasoning`：内部完整判断依据，不公开发布。

只有 `decision=accept` 的文章会自动收录。

服务启动时会把 `tag_vocabulary` 中的 active 标签加载到内存缓存，评估提示词会动态注入这份正式词库。管理端创建、更新或审批标签时，会先更新 SQLite，再刷新内存缓存。`tags` 命中正式词库后会绑定到文章；`suggested_tags` 和误放入 `tags` 的词库外标签会进入 `tag_candidates` 等待人工审核。

评估失败会记录到 `evaluation_failures`，不会写入 `fetches`，也不会修改文章状态。如果模型返回空内容、非法 JSON，或 JSON 无法通过 Pydantic 校验，评估器会最多按 `TAC_EVALUATION_MAX_ATTEMPTS` 重试，并把上一次原始输出和具体解析/校验错误发回模型修正。

## 存储

内部状态存储在 SQLite 中，默认路径为 `data/state.db`。

迁移文件位于 `migrations/*.sql`。当前没有独立迁移任务入口；服务启动和每次流水线阶段运行前会自动执行未应用迁移。

核心表：

- `articles`：文章身份、来源、归一化 URL、slug、状态、重试次数和时间戳。
- `fetches`：抓取状态、Markdown 正文、错误和抓取元数据。
- `evaluations`：AI 判断、维度、公开字段、内部判断依据、模型和原始 JSON。
- `tag_vocabulary`：人工维护的正式标签词库，active 标签会注入评估提示词并用于公开发布。
- `tag_candidates`：AI 建议或误放入 `tags` 的词库外标签，等待管理端人工审核。
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
- `content_type`
- `summary`
- `tags`
- `recommendation_reason`
- `dimensions`
- `markdown_path`

公开 JSON 不得包含 `status`、`full_reasoning` 等内部字段。

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
