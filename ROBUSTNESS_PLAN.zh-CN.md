# 流水线健壮性精简改造计划

## 依赖选择

### 使用 urllib3.Retry

`requests` 底层已经使用 `urllib3`，可以直接通过 `HTTPAdapter` 配置重试，不需要额外引入 `tenacity`。

示例：

```python
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def build_session() -> Session:
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
    )
    adapter = HTTPAdapter(max_retries=retry)

    session = Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session
```

### 统一使用 Crawler4AI

抓取阶段统一使用 Crawler4AI，不再保留 `requests`、`trafilatura` 或通用 HTML 转 Markdown fallback。这样抓取行为只有一条路径，失败原因也更容易归类和排查。

抓取链路保持单一路径：

```text
Crawler4AI
```

如果 Crawler4AI 未能返回可用 Markdown，本次抓取记为失败并记录原因。

## 最小数据模型

### source_state

新增一张轻量表，记录 RSS 信源最近一次检查状态和条件请求字段。

```sql
CREATE TABLE IF NOT EXISTS source_state (
    source_name TEXT PRIMARY KEY,
    etag TEXT,
    modified TEXT,
    last_status TEXT NOT NULL,
    last_error TEXT,
    checked_at TEXT NOT NULL
);
```

字段说明：

- `source_name`：对应 `config/sources.yaml` 中的信源名称。
- `etag`：上次 RSS 响应的 `ETag`。
- `modified`：上次 RSS 响应的 `Last-Modified`。
- `last_status`：`success`、`not_modified` 或 `failed`。
- `last_error`：失败原因，成功时为空。
- `checked_at`：最近检查时间。

不新增 `entries_found`、`duration_ms`、`http_status` 等字段。发现阶段的详细数量继续通过 CLI 返回值展示。

### evaluation_failures

新增评估失败表，避免继续复用抓取失败逻辑。

```sql
CREATE TABLE IF NOT EXISTS evaluation_failures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    failed_at TEXT NOT NULL,
    error TEXT NOT NULL,
    attempts INTEGER NOT NULL,
    raw_response TEXT
);
```

字段只保留必要信息：

- 哪篇文章评估失败。
- 什么时候失败。
- 为什么失败。
- 总共尝试了几次。
- 最后一次原始返回是什么，便于排查 JSON 解析或 Pydantic 校验问题。

评估失败不再修改 `articles.status` 为 `failed`。

## 状态语义

`articles.status` 只表达内容评估结果：

```text
candidate
accepted
rejected
low_confidence
```

不再把所有阶段失败都塞进 `articles.status`。

阶段状态从已有表推导：

- 抓取成功：`fetches` 存在 `status='success'`。
- 抓取失败：最新 `fetches` 为 `status='failed'`。
- 评估成功：`evaluations` 存在记录。
- 评估失败：`evaluation_failures` 存在记录。
- 发布状态：不入库，`public/` 是从 accepted 文章重新生成的派生产物。

这样可以避免多份状态不一致。

## Fetch 改造

### 抓取顺序

生产抓取统一使用 Crawler4AI：

```text
fixture -> Crawler4AI
```

说明：

- `fixture` 只用于测试。
- `Crawler4AI` 负责真实页面抓取和正文 Markdown 生成。
- 不再实现 `requests` fallback；Crawler4AI 失败就记录抓取失败。

### Crawler4AI 失败处理

Crawler4AI 返回空内容、异常或超时时，抛出明确错误，例如：

```python
if not result.markdown:
    raise FetchError("crawler4ai returned no markdown")
```

### 元数据

`crawler_metadata` 只保留必要字段：

```json
{
  "crawler": "crawler4ai",
  "final_url": "https://example.com/post",
  "status_code": 200
}
```

暂时不记录 `duration_ms`、`word_count`、`content_hash`、`extraction_score`。这些可以在真实运行中证明需要后再补。

## Evaluate 改造

### 当前问题

当前评估失败调用通用失败记录函数，会写入 `fetches` 并把文章状态改成 `failed`。这会造成三个问题：

- 明明抓取已经成功，却被后续评估失败污染成抓取失败。
- 后续排查时无法区分是网页抓不到，还是 AI 返回异常、schema 校验失败、API 超时。
- OpenAI 调用成功但返回内容无法通过 JSON 解析或 Pydantic 校验时，当前不会把解析错误发回模型修正，而是直接失败。

### 改造方式

新增：

```python
def record_evaluation_failure(
    conn,
    article_id: int,
    *,
    error: str,
    attempts: int,
    raw_response: str | None,
) -> None:
    ...
```

行为：

- 插入 `evaluation_failures`。
- 不修改 `articles.status`。
- 不写入 `fetches`。
- 下次 `evaluate` 仍然可以从已抓取 Markdown 继续评估。

### LLM 输出修正重试

`evaluate_with_ai` 增加一次小循环，覆盖以下失败：

- OpenAI API 调用失败。
- 返回内容为空。
- 返回内容不是合法 JSON。
- JSON 能解析，但不能通过 `EvaluationResult.model_validate_json`。

新增配置：

```text
TAC_EVALUATION_MAX_ATTEMPTS=3
```

默认最多尝试 3 次：首次正常请求 + 最多 2 次重试。OpenAI API 调用失败时重复同一请求；如果已经拿到模型输出但 JSON 解析或 Pydantic 校验失败，后续修正请求必须带上：

- 原始文章标题、URL 和 Markdown。
- 上一次模型原始输出。
- `_extract_json` 或 Pydantic 抛出的具体错误。
- 明确要求模型只返回符合 schema 的 JSON 对象。

示例结构：

```python
last_raw = None
last_error = None

for attempt in range(settings.evaluation_max_attempts):
    response = client.chat.completions.create(
        model=settings.model,
        messages=build_evaluation_messages(
            prompt=prompt,
            user_content=user_content,
            previous_raw=last_raw,
            previous_error=last_error,
        ),
        temperature=0,
        response_format={"type": "json_object"},
        timeout=90,
    )
    last_raw = _completion_content(response)
    try:
        raw_json = _extract_json(last_raw)
        return EvaluationResult.model_validate_json(raw_json), raw_json
    except Exception as exc:
        last_error = str(exc)
```

`build_evaluation_messages` 在首次请求时只发送正常 system/user 消息；修正请求时追加一条 user 消息：

```text
上一次输出无法解析或不符合 schema。
解析/校验错误：
{previous_error}

上一次原始输出：
{previous_raw}

请基于原始文章内容重新输出一个合法 JSON 对象，不要输出 Markdown 代码块或解释文字。
```

所有尝试耗尽后，调用 `record_evaluation_failure`，写入：

- `error`：最后一次 OpenAI、JSON 解析或 Pydantic 校验错误。
- `attempts`：实际尝试次数。
- `raw_response`：最后一次模型原始输出；如果 API 调用阶段失败则为空。

`evaluate_pending` 仍然只排除已经有成功 `evaluations` 的文章。失败过但未成功评估的文章可以在后续运行继续重试；单次运行内由 `settings.evaluation_max_attempts` 控制即时修正次数。

## 限速

先用一个简单配置：

```text
TAC_FETCH_DELAY_SECONDS=1
```

含义是每抓取一篇文章后 sleep 指定秒数。这个方案很朴素，但符合当前同步 CLI 形态。

只有当后续需要并发抓取时，再引入：

- `asyncio`
- `aiolimiter`
- per-host rate limit

第一版不做异步化。

## 报告命令

新增两个轻量 CLI 命令：

```powershell
uv run tac report sources
uv run tac report failures
```

### report sources

读取 `source_state`，输出：

- source_name
- last_status
- last_error
- checked_at

用于判断哪些 RSS 源最近失败。

### report failures

输出两类失败：

- 最新抓取失败：来自 `fetches.status='failed'`。
- 评估失败：来自 `evaluation_failures`。

字段保持简单：

- article_id
- title
- url
- stage
- error

## 实施顺序

1. 新增迁移：`source_state` 和 `evaluation_failures`。
2. 在 `db.py` 新增 source state 读写函数和 `record_evaluation_failure`，评估失败记录 attempts 和 raw_response。
3. 修改 `evaluate.py`，评估失败不再调用抓取失败记录；JSON 解析或 Pydantic 校验失败时带错误信息重传给 LLM 修正。
4. 修改 `discover.py`，使用 `requests.Session` 拉 RSS，再交给 `feedparser` 解析。
5. 修改 `fetch.py`，移除 `requests` fallback，统一使用 Crawler4AI；Crawler4AI 失败时记录抓取失败。
6. 增加 `TAC_FETCH_DELAY_SECONDS`。
7. 增加 `tac report sources` 和 `tac report failures`。
8. 补离线测试：RSS 失败隔离、304 跳过、评估失败不污染抓取状态、LLM 修正重试、Crawler4AI 失败记录。
