# 技术文章精选

AI 辅助的技术文章精选流水线。系统从 RSS/Atom、RSSHub feed、sitemap、HTML 列表页和手动 URL 发现候选文章，抓取并清洗为 Markdown，用严格 JSON Schema 评估内容质量，将内部状态保存到 SQLite，并在 `public/` 下发布稳定的 JSON/Markdown 数据。

## 快速开始

```powershell
uv sync --extra test --extra crawler
uv run uvicorn tac.main:app --host 127.0.0.1 --port 8000 --reload
```

打开本地管理控制台：

<http://127.0.0.1:8000/admin>

FastAPI 应用默认在启动时执行 SQLite 迁移。发现、抓取、评估、发布和完整流水线都通过管理页触发为后台任务。

新的实现入口是 `tac.main:app`。

SQLite 迁移没有单独的管理 API 或后台任务入口；服务启动和每次流水线阶段运行前会自动执行未应用的 `migrations/*.sql`。

## FastAPI

服务提供：

- `/admin`：无前端框架的轻量管理控制台。
- `/api/admin/*`：管理 API，可查询和调整内部文章状态。
- `/api/public/*`：公开查询 API，只返回已收录的 `accepted` 文章。
- `/feed.xml` 和 `/api/public/feed.xml`：公开 RSS 2.0 订阅。

主要后台任务入口：

- `POST /api/admin/jobs/discover`
- `POST /api/admin/jobs/fetch`
- `POST /api/admin/jobs/evaluate`
- `POST /api/admin/jobs/publish`
- `POST /api/admin/jobs/run`
- `GET /api/admin/jobs/{job_id}`
- `GET /api/admin/schedules`
- `POST /api/admin/schedules/run/trigger`

## 配置

运行配置通过环境变量提供。

- `OPENAI_API_KEY`：AI 评估使用的 API key。
- `TAC_MODEL`：OpenAI SDK 使用的模型名。
- `TAC_BASE_URL`：OpenAI-compatible 服务的 `base_url`。
- `TAC_STATE_DB`：SQLite 路径，默认 `data/state.db`。
- `TAC_MIGRATIONS_DIR`：SQLite 迁移目录，默认 `migrations`。
- `TAC_SOURCES_PATH`：信源配置路径，默认 `config/sources.yaml`。
- `TAC_PUBLIC_DIR`：发布目录，默认 `public`。
- `TAC_MAX_RETRY`：最大重试次数，默认 `3`。
- `TAC_CRAWLER4AI_ENABLED`：默认启用。生产文章抓取只使用 Crawler4AI；关闭它主要用于测试或 fixture 驱动运行。生产运行请按快速开始安装 `--extra crawler`。
  Crawler4AI 当前依赖 `lxml<6`，`--extra crawler` 建议使用 Python 3.11-3.13；Python 3.14 可运行核心服务、测试和 fixture 驱动流程。
- `TAC_FETCH_DELAY_SECONDS`：每次文章抓取后等待的秒数，默认 `1`。
- `TAC_EVALUATION_MAX_ATTEMPTS`：每篇文章 AI 评估最多尝试次数，默认 `3`。
- `TAC_PROMPT_LANGUAGE`：提示词语言，当前仅支持 `zh-CN`。
- `TAC_PROMPT_PATH`：可选的显式提示词路径。
- `TAC_FEW_SHOT_DIR`：可选的显式 few-shot 目录。
- `TAC_AI_RESPONSE_PATH`：测试用固定 AI JSON 响应文件。
- `TAC_FETCH_FIXTURE_PATH`：测试用固定 Markdown 内容。
- `TAC_AUTO_MIGRATE`：FastAPI 启动时执行迁移，默认 `true`。
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
- `TAC_RSSHUB_TIMEOUT_SECONDS`：RSSHub feed 请求超时，默认 `30`。
- `TAC_DISCOVERY_LISTING_ENABLED`：启用 HTML 列表页（`feed.type: listing`）发现来源，默认 `true`。
- `TAC_LISTING_TIMEOUT_SECONDS`：HTML 列表页请求超时，默认 `30`。
- `TAC_PUBLIC_BASE_URL`：公开链接基准地址，默认 `http://127.0.0.1:8000`。
- `TAC_PUBLIC_FEED_TITLE`：公开 RSS 标题，默认 `技术文章精选`。
- `TAC_PUBLIC_FEED_DESCRIPTION`：公开 RSS 描述。
- `TAC_PUBLIC_FEED_LANGUAGE`：公开 RSS 语言，默认 `zh-CN`。
- `TAC_PUBLIC_FEED_TTL_MINUTES`：公开 RSS TTL，默认 `5`。

信源配置统一使用 `feed` 字段：

```yaml
sources:
  - name: "Cloudflare Blog"
    site_url: "https://blog.cloudflare.com/"
    feed:
      type: "direct"
      url: "https://blog.cloudflare.com/rss/"

  - name: "知乎热榜"
    site_url: "https://www.zhihu.com/hot"
    tags: ["Zhihu", "Community"]
    feed:
      type: "rsshub"
      route: "/zhihu/hot"
      params:
        limit: 20

  - name: "Martin Fowler"
    site_url: "https://martinfowler.com/"
    tags: ["Architecture", "Software Design", "Personal Blog"]
    feed:
      type: "sitemap"
      url: "https://martinfowler.com/sitemap.xml"

  - name: "某博客"
    site_url: "https://example.com/blog"
    tags: ["Engineering", "Personal Blog"]
    feed:
      type: "listing"
      url: "https://example.com/blog"
      link_selector: "main article a.post-link"
      # 可选:用 title_selector 单独取标题,否则取锚点文本
      title_selector: "main article h2"
      # 可选:只保留 URL 含任一子串的链接,空表示不过滤
      url_patterns: ["/blog/20"]
      # 可选:解析相对链接的基准地址,默认取 listing url 的 origin
      base_url: "https://example.com"
```

本地同时启动 TAC 和 RSSHub：

```powershell
docker compose -f compose.dev.yml up
```

启用内置定时调度示例：

```powershell
$env:TAC_SCHEDULER_ENABLED="true"
$env:TAC_SCHEDULE_RUN_CRON="0 8 * * *"
$env:TAC_SCHEDULE_TIMEZONE="Asia/Shanghai"
uv run uvicorn tac.main:app --host 127.0.0.1 --port 8000 --reload
```

后台任务历史会写入 SQLite 的 `job_runs` 表，服务重启后仍可通过 `/api/admin/jobs` 查询。若重启前存在 `queued` 或 `running` 任务，启动时会标记为 `failed` 并记录中断原因。

AI 调用使用官方 `openai` Python SDK。`TAC_MODEL` 作为模型名传入，`TAC_BASE_URL` 作为 SDK 的 `base_url` 传入。

AI 评估输出使用严格 JSON schema。当前顶层字段为 `decision`、`dimensions`、`summary`、`tags`、`recommendation_reason` 和 `full_reasoning`；不再包含独立 `confidence` 字段。系统只根据 `decision` 判断结果：`accept` 自动收录，`reject` 拒收，`low_confidence` 留待复核。

## 测试

```powershell
uv sync --extra test
uv run ruff check .
uv run ruff format .
uv run pytest
```

Ruff 用于静态检查和格式化。测试使用离线 fixture，不依赖真实网络或真实 AI 调用。

## 文档

完整项目设计和功能说明见 [docs/PROJECT.md](docs/PROJECT.md)。
