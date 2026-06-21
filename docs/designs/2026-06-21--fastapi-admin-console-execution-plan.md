# FastAPI 管理控制台执行计划

来源设计文档：`docs/designs/2026-06-21--fastapi-admin-console.md`

## 执行原则

- 每个阶段都必须让项目保持可测试状态。
- 先实现数据模型、状态语义和查询边界，再实现 API 和页面。
- 管理 API 可以全量可见；公开 API 和发布产物必须排除 `archived`。
- 后台任务、抓取、评估默认串行，优先保证 2 核 2GB 机器稳定运行。
- 测试必须使用离线 fixture，不依赖真实网络或真实 AI。
- 删除 CLI 放在后段执行，避免中途失去现有调试入口。

## 阶段 0：准备和基线确认

目标：确认当前行为和测试基线，避免重构过程中混入无关变更。

改动范围：无代码改动。

任务：

- 记录当前 `git status`，保留用户已有变更。
- 运行现有检查：
  - `uv run ruff check .`
  - `uv run pytest`
- 确认现有离线端到端测试覆盖 `discover -> fetch/evaluate -> publish` 的基本链路。

验收：

- 明确当前测试基线。
- 如果已有测试失败，先记录原因，不把失败归因到本次重构。

## 阶段 1：依赖和配置扩展

目标：为 FastAPI、测试客户端、并发限制和运行参数准备配置层。

主要文件：

- `pyproject.toml`
- `src/tac/config.py`
- `.env.example`
- `README.md`
- `README.zh-CN.md`

任务：

- 将运行依赖从 Typer 迁移到 FastAPI：
  - 新增 `fastapi`
  - 新增 `uvicorn`
  - 后续删除 `typer`
- 测试依赖补充 `httpx`，用于 FastAPI `TestClient`。
- 在 `Settings` 中新增配置项：
  - `auto_migrate`
  - `http_max_concurrency`
  - `job_max_concurrency`
  - `job_queue_limit`
  - `fetch_max_concurrency`
  - `evaluate_max_concurrency`
  - `discover_max_concurrency`
  - `max_request_body_bytes`
  - `fetch_timeout_seconds`
  - `ai_timeout_seconds`
  - `job_timeout_seconds`
  - `fetch_max_markdown_bytes`
  - `job_history_limit`
  - `db_busy_timeout_ms`
- 为整数、浮点和正数配置增加解析 helper。
- 更新 `.env.example` 中的新环境变量。

验收：

- `get_settings()` 能返回所有新增配置的默认值。
- 非法 `TAC_PROMPT_LANGUAGE` 等现有校验保持不变。
- 新增配置有单元测试覆盖。

测试：

- `uv run pytest tests/test_config.py`

## 阶段 2：数据库迁移、模型和状态服务

目标：先把 `archived` 语义和查询边界落到数据库与服务层。

主要文件：

- `migrations/003_fastapi_admin_state.sql`
- `src/tac/models.py`
- `src/tac/db.py`
- `src/tac/services/articles.py`
- `tests/test_db.py`
- `tests/test_models.py`

任务：

- 新增迁移：
  - `articles.previous_status TEXT`
  - `articles.archived_at TEXT`
  - 分页和筛选索引：
    - `idx_articles_status_updated_at`
    - `idx_articles_source_name`
    - `idx_articles_updated_at`
    - `idx_articles_collected_at`
- 扩展 `ArticleStatus`：
  - `candidate`
  - `accepted`
  - `rejected`
  - `low_confidence`
  - `archived`
- 更新 `db.connect()`：
  - `PRAGMA foreign_keys = ON`
  - `PRAGMA journal_mode = WAL`
  - `PRAGMA busy_timeout = <settings/default>`
- 新增统一文章状态服务：
  - `set_article_status`
  - `archive_article`
  - `unarchive_article`
  - `can_write_fetch_result`
  - `can_write_evaluation_result`
- 直接改为 `archived` 时补齐 `previous_status` 和 `archived_at`。
- 从 `archived` 改回其他状态时清空 `archived_at` 和 `previous_status`。
- `archive` 和 `unarchive` 保持幂等。
- 更新抓取和评估回写逻辑：
  - 归档文章不得被新的抓取成功覆盖。
  - 归档文章不得被评估结果改回 `accepted`。

验收：

- 归档前状态被正确保存。
- 取消归档能恢复 `previous_status`，为空时恢复 `candidate`。
- 公开查询和发布查询不会返回 `archived`。
- 管理查询可以返回 `archived`。

测试：

- `test_archive_records_previous_status`
- `test_unarchive_restores_previous_status_and_clears_archived_at`
- `test_set_status_to_archived_applies_archive_semantics`
- `test_set_status_from_archived_clears_archive_fields`
- `test_public_queries_exclude_archived`
- `test_management_queries_include_archived`
- `test_fetch_evaluation_do_not_unarchive_article`

## 阶段 3：分页查询、详情查询和发布一致性

目标：把列表接口需要的数据访问能力做稳定，避免 API 层拼 SQL。

主要文件：

- `src/tac/db.py`
- `src/tac/services/articles.py`
- `src/tac/publish.py`
- `tests/test_db.py`
- `tests/test_publish.py`

任务：

- 新增管理文章分页查询：
  - `page`
  - `page_size`
  - `status`
  - `source`
  - `q`
  - `failed_only`
  - `sort`
  - `order`
- 限制 `page_size <= 200`。
- 排序字段白名单化。
- 列表查询只返回轻量字段。
- 新增文章详情查询，包含：
  - 最新成功抓取
  - 最新评估
  - 最新抓取失败
  - 最新评估失败
- 新增失败分页查询，默认最近 50 条。
- 修改 `publish_public()`：
  - 仅发布当前 `accepted` 且非 `archived` 文章。
  - 写文件使用临时文件和原子替换。
  - 清理不再属于当前发布集合的旧文章 JSON/Markdown。

验收：

- 列表查询不会返回正文和原始 AI JSON。
- 搜索、筛选、分页、排序组合可用。
- 归档文章旧产物会在 publish 后被清理。

测试：

- `test_admin_articles_pagination_default_order`
- `test_admin_articles_page_size_is_capped`
- `test_admin_articles_search_title_url_source`
- `test_admin_articles_failed_only`
- `test_publish_removes_archived_stale_files`
- `test_publish_writes_files_atomically`

## 阶段 4：流水线服务化

目标：把现有 CLI 编排能力转成 FastAPI 可调用的服务层。

主要文件：

- `src/tac/pipeline.py`
- `src/tac/discover.py`
- `src/tac/fetch.py`
- `src/tac/evaluate.py`
- `src/tac/publish.py`
- `tests/test_e2e.py`

任务：

- 新增 `pipeline.py`：
  - `run_migrate`
  - `run_discover`
  - `run_fetch`
  - `run_evaluate`
  - `run_publish`
  - `run_all`
- 每个函数内部创建独立数据库连接。
- 后台任务不能复用请求线程中的连接。
- `fetch` 和 `evaluate` 支持按文章 ID 执行单篇重试。
- 将 `evaluate.py` 的 AI timeout 改为使用 `settings.ai_timeout_seconds`。
- 将 `fetch.py` 的抓取超时和 Markdown 最大大小接入配置。
- `run_all` 的返回结构保留现有 CLI JSON 结果语义，便于测试迁移。

验收：

- 服务层能独立跑完整离线链路。
- 单篇 retry fetch / retry evaluate 可通过服务层执行。
- 外部网络和真实 AI 仍可通过 fixture 替代。

测试：

- 更新 `test_offline_e2e_fixture`
- 新增 `test_pipeline_run_all_offline`
- 新增 `test_pipeline_retry_single_article_fetch`
- 新增 `test_pipeline_retry_single_article_evaluate`

## 阶段 5：后台任务管理和并发限制

目标：实现内存任务状态、队列限制、超时和重复任务保护。

主要文件：

- `src/tac/jobs.py`
- `src/tac/config.py`
- `tests/test_jobs.py`

任务：

- 定义任务状态：
  - `queued`
  - `running`
  - `succeeded`
  - `failed`
  - `skipped`
- 定义任务字段：
  - `job_id`
  - `kind`
  - `status`
  - `created_at`
  - `started_at`
  - `finished_at`
  - `result`
  - `error`
  - `target_article_id`
- 实现 `JobManager`：
  - 队列长度限制
  - 执行并发限制
  - 任务历史保留上限
  - 同篇文章同阶段去重
  - `run` 任务运行时拒绝其他流水线任务
  - 超时标记失败
- 对外提供：
  - `submit_job`
  - `list_jobs`
  - `get_job`
  - `is_duplicate_job`
- 超限返回由 API 层映射为 `409` 或 `429`。

验收：

- 同一时间默认只运行一个后台任务。
- 队列满时拒绝新任务。
- 任务完成后可查询结果。
- 任务历史超过上限会清理旧任务。

测试：

- `test_job_queue_limit_returns_rejection`
- `test_job_conflict_when_run_is_running`
- `test_duplicate_article_stage_job_is_rejected`
- `test_job_timeout_marks_failed`
- `test_job_history_limit_prunes_old_jobs`

## 阶段 6：FastAPI 应用入口和安全中间件

目标：建立新的唯一运行入口，并加上本机访问、同源写保护、请求体和请求并发限制。

主要文件：

- `src/tac/app.py`
- `src/tac/security.py`
- `src/tac/api/__init__.py`
- `tests/test_app_security.py`

任务：

- 新增 `create_app(settings: Settings | None = None)`。
- 应用启动时根据 `TAC_AUTO_MIGRATE` 执行迁移。
- 增加中间件或依赖：
  - 本机访问限制
  - Host 白名单
  - Origin/Referer 同源校验
  - CSRF token 校验
  - 请求体大小限制
  - HTTP 动态请求并发限制
- `/admin` 页面生成 CSRF token，并让前端写请求带 `X-TAC-CSRF`。
- 只对写请求执行 CSRF 和 Origin/Referer 校验。
- 不启用宽松 CORS。

验收：

- 非本机请求被拒绝。
- 非同源写请求被拒绝。
- 缺失 CSRF 的写请求被拒绝。
- 大请求体被拒绝。
- 自动迁移失败时应用启动失败。

测试：

- `test_admin_get_returns_csrf_token`
- `test_write_without_csrf_returns_403`
- `test_write_wrong_origin_returns_403`
- `test_request_body_too_large_returns_413`
- `test_auto_migrate_runs_on_startup`

## 阶段 7：管理 API

目标：提供管理控制台所需的全部 API。

主要文件：

- `src/tac/api/admin.py`
- `src/tac/api/jobs.py`
- `src/tac/services/sources.py`
- `tests/test_admin_api.py`
- `tests/test_sources_api.py`

任务：

- 实现 `GET /api/admin/summary`。
- 实现 `GET /api/admin/articles`。
- 实现 `GET /api/admin/articles/{id}`。
- 实现状态操作：
  - `POST /api/admin/articles/{id}/status`
  - `POST /api/admin/articles/{id}/archive`
  - `POST /api/admin/articles/{id}/unarchive`
- 实现重试操作：
  - `POST /api/admin/articles/{id}/retry-fetch`
  - `POST /api/admin/articles/{id}/retry-evaluate`
- 实现 `GET /api/admin/failures`。
- 实现信源编辑：
  - `GET /api/admin/sources`
  - `PUT /api/admin/sources`
- `GET sources` 返回 YAML 文本和 hash。
- `PUT sources` 校验 hash、解析 YAML、Pydantic 校验、原子写入和备份。
- 实现任务 API：
  - `GET /api/admin/jobs`
  - `GET /api/admin/jobs/{job_id}`
  - `POST /api/admin/jobs/discover`
  - `POST /api/admin/jobs/fetch`
  - `POST /api/admin/jobs/evaluate`
  - `POST /api/admin/jobs/publish`
  - `POST /api/admin/jobs/run`

验收：

- 管理 API 能看到 `archived`。
- 状态操作语义与服务层一致。
- 任务 API 立即返回 `job_id`。
- sources 保存冲突返回 `409`。
- YAML 校验错误返回可读错误。

测试：

- `test_admin_summary_counts_all_statuses`
- `test_admin_articles_includes_archived`
- `test_admin_status_update`
- `test_admin_archive_unarchive`
- `test_retry_fetch_submits_job`
- `test_retry_evaluate_submits_job`
- `test_sources_update_requires_matching_hash`
- `test_sources_update_validates_yaml`

## 阶段 8：公开 API

目标：提供对外查询接口，并严格排除 `archived`。

主要文件：

- `src/tac/api/public.py`
- `tests/test_public_api.py`

任务：

- 实现 `GET /api/public/articles`：
  - 分页
  - 状态筛选
  - 只返回公开轻量字段
  - 永远排除 `archived`
- 实现 `GET /api/public/articles/{slug}`：
  - 从 SQLite 按 slug 查询
  - 不从 `public/` 静态文件直接读取
  - `archived` 返回 `404`
- 实现 `GET /api/public/index.json`：
  - 返回与公开列表一致的数据结构或兼容 `public/index.json` 的记录集合
  - 仍以 SQLite 当前状态为准

验收：

- 已归档文章在所有公开 API 中不可见。
- 管理 API 可见同一篇归档文章。
- 公共详情不会拼接文件路径。

测试：

- `test_public_articles_exclude_archived`
- `test_public_detail_archived_returns_404`
- `test_public_index_excludes_archived`
- `test_public_article_detail_by_slug`

## 阶段 9：无框架管理页面

目标：实现可用但不重的 HTML 管理控制台。

主要文件：

- `src/tac/admin_static/admin.html`
- `src/tac/admin_static/admin.css`
- `src/tac/admin_static/admin.js`
- `src/tac/app.py`
- `tests/test_admin_page.py`

任务：

- 页面结构：
  - 顶部概览卡
  - 任务按钮区
  - 最近失败区
  - 所有文章表
  - 文章详情抽屉
  - 信源 YAML 编辑面板
- 表格能力：
  - 状态筛选
  - 来源筛选
  - 关键词搜索 debounce
  - 只看失败
  - 分页
  - 排序
  - URL query 状态同步
- 行操作：
  - 重试抓取
  - 重新评估
  - 改状态
  - archive
  - unarchive
- 任务轮询：
  - 点击任务按钮后立即显示 job ID
  - 2 秒轮询
  - 完成或失败后停止
- 错误体验：
  - `403` 显示同源/CSRF 提示
  - `409` 显示已有任务或编辑冲突
  - `429` 显示请求过多或队列已满
- Markdown 和原始 JSON 默认折叠。
- 详情 Markdown 默认截断。

验收：

- 浏览器打开 `/admin` 能完成主要运维流程。
- 不依赖任何前端框架或构建步骤。
- 文本在常见桌面和窄屏宽度下不明显溢出。

测试：

- `test_admin_page_served`
- `test_admin_page_includes_csrf_bootstrap`
- `test_static_assets_served_only_under_admin_static`

手工验收：

- 启动：
  - `uv run uvicorn tac.app:app --host 127.0.0.1 --port 8000 --reload`
- 打开：
  - `http://127.0.0.1:8000/admin`
- 验证分页、筛选、详情、任务按钮、YAML 校验错误。

## 阶段 10：删除 CLI 和更新文档

目标：完成入口切换，避免 README 和依赖继续指向旧 CLI。

主要文件：

- `src/tac/cli.py`
- `pyproject.toml`
- `README.md`
- `README.zh-CN.md`
- `docs/PROJECT.md`
- `docs/PROJECT.zh-CN.md`
- `tests/test_e2e.py`

任务：

- 删除 `src/tac/cli.py`。
- 删除 `[project.scripts] tac = "tac.cli:app"`。
- 从依赖中移除 `typer`。
- README 启动命令改为：
  - `uv run uvicorn tac.app:app --reload`
- 原 CLI 命令说明替换为：
  - 管理页面
  - 管理 API
  - 公开 API
  - 后台任务入口
- 更新项目文档中的架构描述。
- 删除或改造 CLI 测试。

验收：

- 文档中不再推荐 `uv run tac ...`。
- 项目唯一服务入口是 `tac.app:app`。
- 测试不再依赖 Typer CLI。

测试：

- `uv run ruff check .`
- `uv run pytest`

## 阶段 11：端到端验收和回归

目标：确认重构完成后核心链路、管理能力和公开过滤都能闭环。

任务：

- 使用离线 fixture 验证完整链路：
  - discover
  - fetch
  - evaluate
  - publish
  - public API
  - admin API
- 验证归档闭环：
  - accepted 文章可公开查询
  - archive 后管理 API 可见
  - archive 后公开 API 不可见
  - publish 后旧静态产物被清理
  - unarchive 后恢复到 previous status
- 验证任务闭环：
  - run 返回 job ID
  - job 状态从 queued/running 到 succeeded
  - 冲突任务返回 409
  - 队列满返回 429
- 验证安全边界：
  - 缺 CSRF 写请求失败
  - 非同源写请求失败
  - 大请求体失败

最终验收命令：

```powershell
uv run ruff check .
uv run ruff format .
uv run pytest
uv run uvicorn tac.app:app --host 127.0.0.1 --port 8000 --reload
```

## 建议提交切分

1. `feat: add admin state migration`
2. `feat: add article status services`
3. `feat: add paginated article queries`
4. `feat: add FastAPI app and security guards`
5. `feat: add background job manager`
6. `feat: add admin and public APIs`
7. `feat: add lightweight admin console`
8. `feat: replace CLI with FastAPI entrypoint`
9. `docs: update FastAPI admin documentation`

## 风险优先级

高优先级：

- `archived` 公开过滤遗漏。
- 旧 `public/` 文件没有清理。
- 后台任务和手动改状态产生竞态。
- 无认证本机页面被跨站写请求利用。
- SQLite 写锁导致请求卡死。

中优先级：

- 页面全量加载导致卡顿。
- 任务状态重启后丢失。
- YAML 保存覆盖并发编辑。
- 多 worker 部署导致内存锁失效。

低优先级：

- 页面视觉 polish。
- 复杂全文搜索。
- 完整任务取消。
- 多用户权限。

## 完成定义

- `uv run uvicorn tac.app:app --reload` 可启动。
- `/admin` 可完成查看、筛选、分页、详情、归档、重试、任务触发和 YAML 校验保存。
- `/api/admin/*` 可见全量文章，包括 `archived`。
- `/api/public/*` 永远不可见 `archived`。
- `publish` 不会留下已归档文章的旧公开产物。
- 所有新增配置有默认值并可通过环境变量覆盖。
- 所有新增核心行为有离线测试。
- README 和项目文档不再指向旧 CLI 入口。
