# 内置 Cron 调度与持久任务审计

## 背景

当前流水线只能通过管理页或 `/api/admin/jobs/*` 手动触发。`JobManager` 把任务状态保存在进程内的 `OrderedDict` 中，服务重启后任务历史会丢失，正在运行或排队中的状态也无法恢复为可审计记录。

用户希望不要依赖外部 `cron`、`systemd timer` 或 GitHub Actions，而是在系统内部提供类似 cron 的定时调度能力。

## 目标

- 在 FastAPI 服务进程内启动内置调度器，到点自动触发流水线任务。
- 支持类似 cron 的配置方式，例如每天固定时间运行 `run`。
- 手动触发和定时触发共用同一个任务提交、执行、并发控制和状态查询路径。
- 每次任务运行都写入 SQLite，服务重启后仍能查询历史、错误、耗时和触发来源。
- 定时触发遇到已有任务运行时不破坏现有互斥规则，并留下可追踪记录。

## 非目标

- 不做分布式调度；默认只支持单个 FastAPI 服务实例安全运行调度器。
- 不引入独立 worker、消息队列或外部调度服务。
- 不在第一阶段实现复杂的 Web UI cron 编辑器；可以先通过环境变量或配置文件启用。
- 不保证服务停机期间错过的每个时间点都会补跑；可以后续再加 missed run 策略。

## 推荐设计

新增三个概念：

- `JobStore`：SQLite 持久化适配器，负责写入和查询 job run。
- `JobManager`：继续负责提交、排队、并发限制和执行，但每次状态变化同步写入 `JobStore`。
- `SchedulerService`：FastAPI lifespan 中启动的进程内调度器，读取 cron 配置，到点调用 `JobManager.submit_job(...)`。

整体流程：

```text
cron 配置
  -> SchedulerService 到点触发
  -> JobManager.submit_job(kind, runner, trigger="schedule", schedule_id="daily-run")
  -> SQLite job_runs 插入 queued
  -> JobManager.run_job(job_id)
  -> SQLite job_runs 更新 running / succeeded / failed / skipped
```

手动按钮和 API 触发也走同一条路径，只是 `trigger="manual"`，`schedule_id` 为空。

## 配置方案

建议先用环境变量提供一个最小可用入口：

```bash
TAC_SCHEDULER_ENABLED=true
TAC_SCHEDULE_RUN_CRON="0 8 * * *"
TAC_SCHEDULE_TIMEZONE="Asia/Shanghai"
```

第一阶段只内置完整流水线 `run` 的定时任务，避免配置面过大。后续可扩展为 YAML：

```yaml
schedules:
  - id: daily-run
    enabled: true
    kind: run
    cron: "0 8 * * *"
    timezone: Asia/Shanghai
    overlap_policy: skip
```

`overlap_policy` 推荐先只支持 `skip`：到点时如果已有冲突任务运行或队列满，就记录一次 `skipped`，而不是强行插队或并发运行。

## 数据库改造

新增迁移 `005_job_runs.sql`：

```sql
CREATE TABLE job_runs (
    job_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    trigger TEXT NOT NULL DEFAULT 'manual',
    schedule_id TEXT,
    target_article_id INTEGER,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    result_json TEXT,
    error TEXT
);

CREATE INDEX idx_job_runs_created_at ON job_runs(created_at);
CREATE INDEX idx_job_runs_status ON job_runs(status);
CREATE INDEX idx_job_runs_schedule_id ON job_runs(schedule_id);
```

字段含义：

- `trigger`：`manual`、`schedule` 或以后可能的 `api`。
- `schedule_id`：定时任务标识，例如 `daily-run`。
- `result_json`：成功时的任务结果，使用 JSON 存储。
- `error`：失败或跳过原因。

重启时，历史中的 `queued` / `running` 任务已经不可能继续由旧进程执行，应在应用启动时修正为 `failed`，错误写为 `job interrupted by service restart`。这样审计记录不会假装任务仍在运行。

## 应用生命周期

在 `src/tac/main.py` 的 lifespan 中：

1. 执行 SQLite migration。
2. 创建 `JobStore` 和 `JobManager`。
3. 标记上次遗留的 `queued` / `running` 任务为失败。
4. 如果 `TAC_SCHEDULER_ENABLED=true`，启动 `SchedulerService`。
5. 应用关闭时停止调度器。

需要注意：当前 `JobManager` 在 `create_app()` 阶段创建，建议改为仍可在创建时实例化，但在 lifespan 启动阶段执行 `manager.recover_interrupted_jobs()`，并启动 scheduler。

## 调度实现选择

首版采用项目内置的轻量 5 段 cron 解析器和一个 asyncio 轮询任务，而不是新增 APScheduler 依赖。原因是当前只内置一个完整流水线 `run` schedule，配置面很小，手写实现能保持依赖更少、启动路径更直接。

当前支持：

- 5 段 cron 表达式：分钟、小时、日期、月份、星期。
- `*`、逗号列表、区间和步长，例如 `*/15`、`9-18`。
- IANA 时区名，例如 `UTC`、`Asia/Shanghai`。
- 到点提交任务，冲突或队列满时记录 `skipped` 审计行。

当前不支持：

- 服务停机期间错过的运行自动补偿。
- 多个动态 schedule。
- APScheduler 风格的 misfire、coalesce 和持久 trigger 配置。

如果后续需要更复杂的调度语义，可以再引入 APScheduler 或 croniter；届时需要把 `SchedulerService` 的 cron 解析和 next-run 计算替换为库实现，并保留 `JobManager` 提交与审计路径不变。

## 并发与冲突策略

沿用现有规则：

- `run` 与任何其他 active job 冲突。
- 普通阶段任务与 active `run` 冲突。
- 同一文章的 retry job 不能重复排队。
- 队列长度仍受 `TAC_JOB_QUEUE_LIMIT` 控制。

定时任务触发时，如果遇到 `JobConflict` 或 `JobQueueFull`：

- 不抛到 scheduler 外层导致调度器异常。
- 写入一条 `skipped` job run，`error` 记录具体原因。
- 管理页可以显示“定时任务到点了，但因为已有任务运行而跳过”。

## API 与管理页

现有接口可以保持：

- `GET /api/admin/jobs`
- `GET /api/admin/jobs/{job_id}`
- `POST /api/admin/jobs/run`

建议新增：

- `GET /api/admin/schedules`：查看启用的定时配置、下一次运行时间、最近一次运行结果。
- `POST /api/admin/schedules/{schedule_id}/trigger`：手动触发某个 schedule 对应任务，`trigger="manual"`，但保留 `schedule_id`。

管理页第一阶段只需要在 Jobs 区域展示 `trigger`、`schedule_id`、`started_at`、`finished_at` 和错误信息即可。

## 实施阶段

1. 持久化 job run
   - 新增 `job_runs` migration。
   - 新增 `tac.infrastructure.db.jobs` 或在 `store.py` 中加入 job run CRUD。
   - 修改 `JobManager`，提交、开始、结束、跳过均写 SQLite。
   - `GET /api/admin/jobs` 改为从持久历史读取。

2. 内置 scheduler
   - 新增 Settings：`scheduler_enabled`、`schedule_run_cron`、`schedule_timezone`。
   - 新增 `src/tac/application/scheduler.py`。
   - 在 lifespan 启停 scheduler。
   - 到点触发 `pipeline.run_all(settings)`。

3. 可观测性和管理页
   - Jobs 列表展示触发来源和 schedule id。
   - 新增 schedules 查询 API。
   - README 更新配置说明。

4. 测试
   - `JobManager` 状态变更会写入 SQLite。
   - 重启恢复会把遗留 running/queued 标为 failed。
   - 定时触发成功提交 job。
   - 定时触发遇到冲突时产生 skipped 审计记录。
   - 配置解析校验 cron 表达式和时区。

## 关键决策

- 内置调度器只负责“提交任务”，不直接跑流水线逻辑。
- Job 审计记录以 SQLite 为准，内存只保留运行期 runner 和并发状态。
- 第一阶段只支持一个 `run` schedule，降低配置复杂度。
- 冲突时采用 `skip`，并写审计记录，避免定时任务无限堆积。

## 风险与权衡

- 进程内调度依赖 FastAPI 服务常驻；服务停机期间不会自动运行。
- 多实例部署会导致多个实例同时调度，需要后续增加 SQLite lease 或禁用多实例调度。
- 内置 cron 解析器覆盖了首版需求，但不等价于完整 cron 调度系统；复杂调度应后续换用成熟库。
- 如果任务执行时间经常超过调度间隔，`skip` 会丢弃部分周期；这是运营上更可控的默认行为。

## 假设

- 生产部署是单实例 FastAPI 服务。
- 最常见需求是每天或每小时跑完整流水线。
- 短期内不需要用户在管理页动态编辑 cron。
- SQLite 是任务审计的权威数据源。

## 后续计划

优先实现 `job_runs` 持久化，再接入 `SchedulerService`。这样即使还没有开启定时调度，手动任务的历史审计问题也会先被解决。
