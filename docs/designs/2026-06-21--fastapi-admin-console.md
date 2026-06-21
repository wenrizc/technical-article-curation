# FastAPI 管理控制台重构设计

## 背景

当前项目是基于 Typer CLI 的技术文章精选流水线，主要命令包括 `migrate`、`discover`、`fetch`、`evaluate`、`publish` 和 `run`。用户希望将项目改造为 FastAPI 后端项目，删除 CLI 入口，并提供一个不依赖前端框架的基础 HTML 管理页面，用于查看文章状态、处理失败、触发流水线任务、编辑信源配置。

## 目标

- 将运行入口从 CLI 改为 FastAPI。
- 提供无前端框架的 HTML/CSS/JS 管理控制台。
- 管理页默认展示所有文章，包括归档文章。
- 管理 API 全量可见，包括 `archived`。
- 公开 API 自动排除 `archived`。
- 支持后台任务执行，页面通过轮询查看任务状态。
- 支持编辑 `config/sources.yaml`，保存前使用现有 Pydantic 模型校验。
- 新增文章 `archived` 状态，并记录归档前状态。
- 文章列表和公开查询必须使用服务端分页、筛选和排序，避免一次性加载全量数据。
- 默认面向 2 核 2GB 服务器配置合理并发限制，并允许通过环境变量调整。
- 明确本机管理场景下的同源写保护、SQLite 运行参数、任务超时、文件原子写入和发布产物清理规则。

## 非目标

- 首版不做登录认证。
- 首版不引入 React、Vue、Svelte 等前端框架。
- 首版不引入 Celery、RQ 等独立任务队列。
- 首版不做多用户权限、审计日志或复杂审批流。
- 首版不保留 Typer CLI。

## 最终设计

项目改造为 FastAPI 应用，启动命令改为：

```powershell
uv run uvicorn tac.app:app --reload
```

FastAPI 提供三类能力：

- 管理页面：`/admin`
- 管理 API：`/api/admin/*`
- 公开 API：`/api/public/*`

管理页面由服务端返回静态 HTML，页面使用原生 JavaScript 调用管理 API。后台任务使用 FastAPI `BackgroundTasks` 执行，服务端维护轻量任务状态，前端轮询 `GET /api/admin/jobs/{job_id}`。

管理服务仅允许本机访问。首版不做登录认证，但应在中间件或依赖中限制请求来源为本机地址，例如 `127.0.0.1`、`::1` 或本机回环连接。

本机访问不等于没有写风险。浏览器访问恶意网页时，恶意网页仍可能尝试请求 `localhost` 管理接口。因此所有会修改状态的管理 API 还必须做同源写保护：

- 不启用宽松 CORS，不允许 `*`。
- 校验 `Host` 只允许本机 host 和配置的端口。
- 对 `POST`、`PUT`、`PATCH`、`DELETE` 校验 `Origin` 或 `Referer` 为同源。
- `/admin` 页面生成一次性或会话级 CSRF token，前端写请求通过 `X-TAC-CSRF` 发送。
- 缺失或不匹配时返回 `403 Forbidden`。

默认部署假设是单进程单 worker。由于首版任务状态在应用进程内维护，且 SQLite 写入不适合高并发，2 核 2GB 服务器默认不建议启动多个 Uvicorn worker。后续如果任务状态迁移到数据库或外部队列，再重新评估多 worker 部署。

删除 CLI 后，FastAPI 应在启动阶段执行数据库迁移。默认 `TAC_AUTO_MIGRATE=true`，迁移失败时应用启动失败，不进入半可用状态。

## 页面功能

### 概览区

展示以下统计：

- 总文章数
- `candidate`
- `accepted`
- `rejected`
- `low_confidence`
- `archived`
- 抓取失败数
- 评估失败数
- 最近发布数量

### 最近失败区

展示抓取失败和评估失败：

- 文章标题
- URL
- 阶段
- 错误原因
- 最近更新时间
- 操作按钮

支持：

- 重试抓取
- 重新评估

### 所有文章运维表

管理页默认展示所有文章，包括 `archived`。

表格字段：

- 标题
- 来源
- 状态
- 抓取状态
- 评估状态
- 重试次数
- 更新时间
- 操作

筛选能力：

- 状态筛选，包含 `archived`
- 来源筛选
- 关键词搜索
- 只看失败
- 服务端分页
- 服务端排序

分页默认值：

- 默认每页 50 条。
- 允许用户选择 20、50、100。
- 后端 `page_size` 最大限制为 200。
- 默认按 `updated_at DESC, id DESC` 排序。
- 页面状态应反映到 URL 查询参数，刷新页面后保留筛选条件。

列表接口只返回表格所需字段，不返回完整 Markdown、原始 AI JSON 或完整失败历史。详情数据通过 `GET /api/admin/articles/{id}` 懒加载。

搜索体验：

- 关键词搜索在前端做 300ms debounce。
- 搜索范围首版限定为标题、URL、来源名称。
- 不在首版引入全文搜索；如果文章量明显增长，再考虑 SQLite FTS。

行操作：

- 重试抓取
- 重新评估
- 改状态
- archive
- unarchive

### 文章详情

文章详情页或详情抽屉展示：

- 原始 URL
- 归一化 URL
- 来源标签
- 当前状态
- 归档前状态
- 最近抓取 Markdown 预览
- 最新评估结果
- 失败记录
- 原始 AI JSON，默认折叠

### 信源编辑

信源编辑采用 YAML 文本编辑器。

行为：

- 读取当前 `config/sources.yaml`
- 用户直接编辑 YAML 文本
- 保存前使用 `SourcesFile` Pydantic 模型校验
- 校验失败时返回具体错误
- 保存成功后可从页面触发 `discover`

## API 设计

### 管理页面

- `GET /admin`

返回无框架 HTML 管理页面。

### 管理 API

- `GET /api/admin/summary`
- `GET /api/admin/articles`
- `GET /api/admin/articles/{id}`
- `POST /api/admin/articles/{id}/retry-fetch`
- `POST /api/admin/articles/{id}/retry-evaluate`
- `POST /api/admin/articles/{id}/status`
- `POST /api/admin/articles/{id}/archive`
- `POST /api/admin/articles/{id}/unarchive`
- `GET /api/admin/failures`
- `GET /api/admin/sources`
- `PUT /api/admin/sources`
- `GET /api/admin/jobs`
- `POST /api/admin/jobs/discover`
- `POST /api/admin/jobs/fetch`
- `POST /api/admin/jobs/evaluate`
- `POST /api/admin/jobs/publish`
- `POST /api/admin/jobs/run`
- `GET /api/admin/jobs/{job_id}`

管理 API 可以查询到全部文章，包括 `archived`。

当请求数、任务数或队列长度超过并发限制时，管理 API 应返回明确错误：

- HTTP 请求并发超限：`429 Too Many Requests`
- 后台任务执行中且不允许并发：`409 Conflict`
- 后台任务队列已满：`429 Too Many Requests`

`GET /api/admin/articles` 支持查询参数：

- `page`：页码，从 1 开始。
- `page_size`：每页数量，默认 50，最大 200。
- `status`：文章状态，可选。
- `source`：来源名称，可选。
- `q`：关键词，可选，匹配标题、URL、来源名称。
- `failed_only`：是否只看抓取或评估失败。
- `sort`：排序字段，首版支持 `updated_at`、`created_at`、`collected_at`、`retry_count`。
- `order`：`asc` 或 `desc`。

响应结构应包含：

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 50,
  "has_next": false
}
```

`GET /api/admin/failures` 也应分页或限制返回数量，默认返回最近 50 条失败记录。

`GET /api/admin/sources` 返回当前 YAML 文本和内容 hash。`PUT /api/admin/sources` 必须携带基于旧内容的 hash；如果保存时文件已被其他进程或页面修改，返回 `409 Conflict`，避免覆盖他人的编辑。

### 公开 API

- `GET /api/public/articles`
- `GET /api/public/articles/{slug}`
- `GET /api/public/index.json`

公开 API 必须始终排除 `status = 'archived'` 的文章。无论调用方查询收录文章还是未收录文章，归档文章都不可被返回。

`GET /api/public/articles` 同样使用分页查询，默认只返回公开列表字段。公开详情通过 `slug` 单独查询。

公开 API 不应直接把 `public/articles/*.json` 或 `public/articles/*.md` 作为权威数据源；应从 SQLite 查询当前状态并执行 `archived` 过滤。若仍保留 `public/` 静态产物，`publish` 必须清理已归档或不再收录文章的旧文件，避免直接文件路径还能访问旧内容。

## 数据库改造

`articles.status` 增加：

```text
archived
```

`articles` 新增字段：

```sql
previous_status TEXT;
archived_at TEXT;
```

状态枚举变为：

```text
candidate
accepted
rejected
low_confidence
archived
```

归档行为：

- `archive`：将当前状态保存到 `previous_status`，设置 `status = 'archived'`，写入 `archived_at`。
- `unarchive`：恢复 `previous_status`；如果 `previous_status` 为空，则恢复为 `candidate`；同时清空 `archived_at`。
- 直接改状态允许在五种状态之间任意切换。

直接改状态到 `archived` 时，也应补齐归档语义：

- 如果原状态不是 `archived`，保存原状态到 `previous_status`。
- 写入 `archived_at`。

直接从 `archived` 改到其他状态时，应执行取消归档语义：

- 设置目标状态。
- 清空 `archived_at`。
- 可以保留或清空 `previous_status`。首版建议清空，避免后续误恢复。

为支持分页和筛选，迁移应补充或确认以下索引：

```sql
CREATE INDEX IF NOT EXISTS idx_articles_status_updated_at ON articles(status, updated_at);
CREATE INDEX IF NOT EXISTS idx_articles_source_name ON articles(source_name);
CREATE INDEX IF NOT EXISTS idx_articles_updated_at ON articles(updated_at);
CREATE INDEX IF NOT EXISTS idx_articles_collected_at ON articles(collected_at);
```

关键词搜索首版可使用 `LIKE`，但查询必须分页并限制 `page_size`。如果后续文章量达到数万级，应增加 FTS 表或专门搜索索引。

SQLite 运行参数：

- 连接应按请求或后台任务创建，不跨线程长期共享。
- 每个连接开启 `PRAGMA foreign_keys = ON`。
- 默认启用 `PRAGMA journal_mode = WAL`，降低读写互相阻塞。
- 默认启用 `PRAGMA busy_timeout = 5000`，可通过 `TAC_DB_BUSY_TIMEOUT_MS` 配置。
- 默认使用短事务，抓取和 AI 请求不能包在数据库写事务里。

## 并发限制

首版按 2 核 2GB 服务器设计保守默认值，优先保证稳定性、内存可控和 SQLite 状态一致。

默认并发预算：

| 能力 | 环境变量 | 默认值 | 说明 |
| --- | --- | --- | --- |
| HTTP 动态请求并发 | `TAC_HTTP_MAX_CONCURRENCY` | `16` | 管理页和 API 的动态请求总并发上限。 |
| 后台任务执行并发 | `TAC_JOB_MAX_CONCURRENCY` | `1` | 同一时间只跑一个后台流水线任务。 |
| 后台任务排队长度 | `TAC_JOB_QUEUE_LIMIT` | `8` | 防止页面重复点击堆积任务。 |
| 抓取并发 | `TAC_FETCH_MAX_CONCURRENCY` | `1` | Crawler4AI 较占内存，小机器默认串行抓取。 |
| 评估并发 | `TAC_EVALUATE_MAX_CONCURRENCY` | `1` | 控制 AI 请求成本、速率和内存峰值。 |
| RSS 发现并发 | `TAC_DISCOVER_MAX_CONCURRENCY` | `2` | RSS 请求较轻，但仍限制并发。 |

资源和超时默认值：

| 能力 | 环境变量 | 默认值 | 说明 |
| --- | --- | --- | --- |
| 请求体大小 | `TAC_MAX_REQUEST_BODY_BYTES` | `1048576` | 限制 YAML 保存等写请求，避免大请求占满内存。 |
| 单篇抓取超时 | `TAC_FETCH_TIMEOUT_SECONDS` | `90` | 防止 Crawler4AI 长时间占住任务槽。 |
| 单次 AI 请求超时 | `TAC_AI_TIMEOUT_SECONDS` | `90` | 替代硬编码超时，便于按模型供应商调整。 |
| 后台任务总超时 | `TAC_JOB_TIMEOUT_SECONDS` | `1800` | 防止任务永久运行。 |
| 抓取 Markdown 最大字节数 | `TAC_FETCH_MAX_MARKDOWN_BYTES` | `2097152` | 避免超大正文写入 SQLite 和页面详情。 |
| 任务历史保留数 | `TAC_JOB_HISTORY_LIMIT` | `100` | 避免内存中的任务记录无限增长。 |

实现要求：

- FastAPI 层使用应用级 `asyncio.Semaphore` 或等价机制限制动态请求并发。
- 后台任务入口使用全局任务执行信号量，默认 `1`，避免 `run`、`fetch`、`evaluate` 同时写 SQLite。
- 单篇文章的 `retry-fetch` 和 `retry-evaluate` 也进入同一后台任务通道，不直接在请求线程内执行。
- 同一篇文章同一阶段不允许重复入队，避免重复抓取或重复评估。
- `run` 任务执行期间，默认拒绝新的 `discover`、`fetch`、`evaluate`、`publish` 任务，除非后续显式支持排队策略。
- 抓取和评估阶段即使后续改成批量并发，也必须分别受 `TAC_FETCH_MAX_CONCURRENCY` 和 `TAC_EVALUATE_MAX_CONCURRENCY` 控制。
- SQLite 写操作集中在服务层串行提交，不允许多个后台任务同时长时间持有写事务。
- 后台任务超过 `TAC_JOB_TIMEOUT_SECONDS` 后标记为失败，并记录超时原因。
- 任务状态首版保存在内存中，应用重启后任务历史会丢失；页面应能展示“任务状态已丢失，请查看数据库状态或重新触发”的错误。
- 只保留最近 `TAC_JOB_HISTORY_LIMIT` 条任务状态，旧任务可从内存清理。

推荐启动方式仍为：

```powershell
uv run uvicorn tac.app:app --host 127.0.0.1 --port 8000 --reload
```

生产或长期运行时应去掉 `--reload`。在首版架构下不建议增加 `--workers`。

## 状态一致性和文件安全

### 状态写入保护

后台任务和人工操作可能同时触达同一篇文章。即使后台任务默认串行，管理 API 仍可能在任务运行中修改状态。为避免竞态：

- 所有文章状态变更必须通过统一服务函数完成，不能在 API 层直接写 SQL。
- `archive`、`unarchive`、`set status`、评估结果回写都必须重新读取当前状态后再更新。
- 评估结果回写前必须确认文章仍允许被评估；如果文章已变为 `archived`，本次评估结果只记录为跳过或失败，不得把状态改回 `accepted`。
- 抓取成功回写前必须确认文章仍存在且未归档；已归档文章不再写入新的抓取成功结果。
- `archive` 对已归档文章应是幂等操作；`unarchive` 对非归档文章也应是幂等操作。

### 文件原子写入

`sources.yaml` 和 `public/` 产物都涉及文件写入，必须避免半写入文件：

- 保存 `sources.yaml` 时先写临时文件，`fsync` 后原子替换。
- 保存前必须完成 YAML 解析和 `SourcesFile` 校验。
- 保存时保留最近一次备份，例如 `sources.yaml.bak`。
- `publish` 写 `index.json`、文章 JSON 和 Markdown 时也使用临时文件加原子替换。
- `publish` 完成后清理不再属于当前发布集合的旧文章文件，尤其是已归档文章的旧产物。

### URL 和路径约束

- 信源 URL 和手工 URL 首版只允许 `http`、`https`。
- 公共详情接口按 `slug` 查询数据库，不允许把用户输入直接拼成文件路径。
- 静态文件服务不能暴露数据库、配置文件、迁移文件或项目根目录。
- 错误响应和日志不得输出 API key、完整请求头或其他敏感环境变量。

## 模块拆分

建议新增或调整模块：

- `src/tac/app.py`：FastAPI 应用入口。
- `src/tac/api/admin.py`：管理 API。
- `src/tac/api/public.py`：公开 API。
- `src/tac/api/jobs.py`：后台任务 API。
- `src/tac/admin_static/`：HTML、CSS、JS。
- `src/tac/pipeline.py`：流水线编排服务。
- `src/tac/jobs.py`：轻量任务状态管理。

删除或停用：

- `src/tac/cli.py`
- `pyproject.toml` 中的 `tac = "tac.cli:app"` CLI script。

保留并复用：

- `discover.py`
- `fetch.py`
- `evaluate.py`
- `publish.py`
- `db.py`
- `sources.py`
- `models.py`
- `config.py`

## 关键决策

- 使用 FastAPI 作为唯一运行入口，而不是继续保留 CLI。
- 使用无框架 HTML 页面，避免首版前端复杂化。
- 使用 `BackgroundTasks`，不引入独立队列。
- 首版不做认证，但限制本机访问。
- `archived` 是正式文章状态，同时记录归档前状态。
- 管理 API 和公开 API 分离，避免公开接口误暴露归档文章。
- 信源编辑采用 YAML 文本编辑，而不是表单化编辑。

## 替代方案

- 保留 CLI 并新增 FastAPI：已拒绝。用户明确要求彻底删除 CLI。
- 纯静态 HTML：已拒绝。无法支持重试、改状态、编辑信源和后台任务。
- 标准库 HTTP 服务：已拒绝。用户明确选择 FastAPI。
- 完整登录系统：已拒绝。首版只允许本机访问。
- 表单化编辑信源：暂不采用。YAML 文本编辑更轻，也能保留现有配置表达力。

## 风险与取舍

- 删除 CLI 会破坏现有 README、测试和本地操作习惯，需要同步更新文档和测试。
- `BackgroundTasks` 适合轻量本地管理，不适合多进程、多实例或可靠任务队列场景。
- 不做认证但允许修改数据，必须严格限制本机访问，避免误暴露到公网。
- YAML 文本编辑保留灵活性，但用户需要理解配置格式。
- 直接允许任意改状态会带来状态不一致风险，需要在后端统一封装状态变更逻辑。
- `archived` 对公开 API 不可见的约束应在查询层集中实现，避免不同接口遗漏过滤条件。
- 如果列表接口一次性返回完整正文、原始 AI JSON 或全量文章，页面会很快变慢；首版必须坚持分页、懒加载和字段裁剪。
- 2 核 2GB 环境下 Crawler4AI 和 AI 评估可能造成明显内存和连接压力，默认后台任务、抓取和评估都应串行执行。
- 如果用多个 Uvicorn worker，首版内存任务状态和并发锁会失效；除非引入数据库任务表或外部队列，否则不支持多 worker。
- 本机无认证管理页仍有浏览器跨站写请求风险，因此必须做同源写保护和 CSRF token。
- 归档文章如果已经被发布为静态文件，必须在下一次 publish 中清理旧文件；否则公开 API 虽然过滤了归档状态，直接文件路径仍可能访问旧内容。
- 内存任务状态在进程重启后会丢失，首版接受该限制，但页面和文档必须明确。

## 基础性能和体验优化

- 所有文章列表、失败列表和公开文章列表都必须服务端分页。
- 表格接口只返回轻量字段，详情接口再返回 Markdown、评估 JSON 和失败历史。
- 默认排序使用 `updated_at DESC, id DESC`，保证最新变化优先可见。
- 搜索、筛选、分页、排序都通过 URL 查询参数表达。
- 前端搜索输入使用 debounce，避免每次按键都请求后端。
- 后台任务按钮点击后立即返回任务 ID，页面轮询任务状态，不阻塞主线程。
- 后台任务轮询间隔建议 2 秒，任务完成或失败后停止轮询。
- 任务运行期间，对应按钮进入禁用或 loading 状态，避免重复触发。
- 页面应识别 `409` 和 `429`，提示当前已有任务运行或请求过多，而不是当作普通失败。
- 页面应识别 `403`，提示管理页面需要从同源 `/admin` 打开。
- 概览卡和文章列表分接口加载，任一接口失败不应阻塞整个页面。
- 列表空状态、错误状态、加载状态必须明确展示。
- Markdown 正文和原始 AI JSON 默认折叠，避免详情视图首次渲染过重。
- 详情页 Markdown 预览默认截断，完整内容可通过显式展开或下载查看。

## 实施计划

1. 增加数据库迁移，支持 `archived`、`previous_status`、`archived_at`。
2. 扩展 `ArticleStatus` 模型和数据库查询函数。
3. 抽出流水线编排服务，供 FastAPI 调用。
4. 新增 FastAPI 应用入口、本机访问限制和同源写保护。
5. 实现管理 API、公开 API、后台任务状态、并发限制和超时控制。
6. 实现无框架管理页面。
7. 删除 CLI 入口和 `pyproject.toml` scripts 配置。
8. 更新 README 和项目文档中的运行命令。
9. 增加离线测试，覆盖归档过滤、分页查询、管理 API、CSRF/同源保护、信源校验、文件原子写入和后台任务触发。

## 假设

- 首版部署场景是本机或内网开发机器，而不是公网服务。
- 页面功能以运维和补救为主，不追求复杂内容编辑体验。
- 公开 API 是新增能力，但发布到 `public/` 的 JSON/Markdown 仍可保留。
- 如果后续需要生产化运行，应重新评估认证、任务队列、并发锁和审计日志。
