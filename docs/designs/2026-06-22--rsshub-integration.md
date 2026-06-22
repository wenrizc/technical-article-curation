# RSSHub 上游发现集成方案

## 背景

当前项目的发现阶段主要依赖两类入口：

- RSS/Atom：`sources[].rss_url` 被解析为候选文章列表。
- 手动 URL：`manual_urls` 被直接当作具体文章 URL 写入候选。

这种设计适合已经提供 RSS 的技术博客、工程团队博客和个人站点，但对知乎、微信公众号、B 站、微博、少数派、V2EX、GitHub 等平台型内容源覆盖不足。如果项目为每个平台各自实现爬取逻辑，会快速膨胀成通用爬虫系统，带来维护、合规、反爬和运行依赖成本。

RSSHub 已经把大量网站和平台适配为 RSS/Atom/JSON Feed，并支持自部署、路由参数、过滤、条数限制、全文模式等能力。更合理的方案是把 RSSHub 作为当前项目的上游发现服务：RSSHub 负责把平台内容转换为 feed，当前项目继续负责候选去重、正文抓取、AI 评估和发布。

## 目标

- 将 RSSHub 作为可选上游发现层，复用其平台 route 和 feed 输出能力。
- 直接重构现有 RSS 信源字段，形成统一的 feed 配置模型。
- 普通 RSS 和 RSSHub 都作为 feed source 处理，只是 feed URL 的生成方式不同。
- 支持本地开发或部署时同时启动 RSSHub sidecar 服务。
- 当前项目不复制、不修改、不内嵌 RSSHub 代码，只通过 HTTP 消费 feed。
- 对 RSSHub 源提供健康检查、错误记录和管理页预览能力。
- 明确 RSSHub 只解决“发现候选 URL”，不改变正文抓取、AI 评估和发布主流程。

## 非目标

- 不把 RSSHub route 代码迁入当前 Python 项目。
- 不由 FastAPI 主进程直接托管 RSSHub 的 Node.js 运行时。
- 不绕过登录、验证码、付费墙或平台反爬限制。
- 不保证公共 `rsshub.app` 实例的可用性或稳定性。
- 不实现 RSSHub Radar 自动识别所有页面。
- 不保持旧版 `rss_url` 配置兼容；配置文件可以随本方案迁移。

## 推荐设计

整体架构：

```text
RSSHub 实例
  -> RSSHub route 输出 RSS/Atom
  -> tac FeedDiscovery 拼接并拉取 feed
  -> 复用现有 feedparser 解析
  -> db.add_candidate()
  -> fetch_pending()
  -> evaluate_pending()
  -> publish_public()
```

RSSHub 是外部服务或 sidecar。当前项目只保存 RSSHub 实例地址、route 和参数，不保存 RSSHub 内部实现。

将现有 RSS 发现逻辑升级为统一的 `FeedDiscovery`：

1. 从 source 配置读取 `feed`。
2. 如果 `feed.type=direct`，直接使用 `feed.url`。
3. 如果 `feed.type=rsshub`，用 `feed.route`、`feed.params` 和 RSSHub 实例拼接 URL。
4. 把解析到的条目写成候选文章。
5. 把 feed 请求失败记录到 `source_state`。

## 配置设计

统一后的普通 RSS 配置：

```yaml
sources:
  - name: "Cloudflare Blog"
    site_url: "https://blog.cloudflare.com/"
    enabled: true
    tags: ["Infrastructure", "Security", "Performance"]
    feed:
      type: "direct"
      url: "https://blog.cloudflare.com/rss/"
```

RSSHub 配置：

```yaml
sources:
  - name: "知乎热榜"
    site_url: "https://www.zhihu.com/hot"
    enabled: true
    display: "default"
    tags: ["Zhihu", "Community", "China"]
    feed:
      type: "rsshub"
      route: "/zhihu/hot"
      instance: "http://127.0.0.1:1200"
      params:
        limit: 20
        filter: "工程|架构|AI"
        filterout: "广告|招聘"
```

字段含义：

- `feed.type`：feed 来源类型。`direct` 表示直接请求 RSS/Atom URL，`rsshub` 表示通过 RSSHub route 生成 RSS/Atom URL。
- `feed.url`：`direct` 类型的 RSS/Atom URL。
- `feed.route`：`rsshub` 类型的 RSSHub route path，例如 `/zhihu/hot`。
- `feed.instance`：可选。未配置时使用全局 `TAC_RSSHUB_INSTANCE`。
- `feed.params`：可选。透传给 RSSHub 的查询参数，例如 `limit`、`filter`、`filterout`、`mode`。
- `site_url`：原平台页面地址，用于展示和人工追溯。
- `tags`：继续作为候选文章的来源标签。

校验规则：

- 每个自动发现 source 必须配置 `feed`。
- `feed.type=direct` 时必须提供 `feed.url`。
- `feed.type=rsshub` 时必须提供 `feed.route`。
- `feed.route` 必须以 `/` 开头，禁止完整 URL，避免绕过实例配置和 SSRF 风险。
- `feed.instance` 必须是 `http://` 或 `https://` 开头。
- 现有 `config/sources.yaml` 中的 `rss_url` 字段需要迁移为 `feed.type=direct` + `feed.url`。

## 运行配置

新增环境变量：

```text
TAC_RSSHUB_ENABLED=false
TAC_RSSHUB_INSTANCE=http://127.0.0.1:1200
TAC_RSSHUB_STARTUP_CHECK=false
TAC_RSSHUB_STRICT_STARTUP=false
TAC_RSSHUB_TIMEOUT_SECONDS=30
```

含义：

- `TAC_RSSHUB_ENABLED`：是否启用 `feed.type=rsshub` 信源。
- `TAC_RSSHUB_INSTANCE`：默认 RSSHub 实例地址。
- `TAC_RSSHUB_STARTUP_CHECK`：FastAPI 启动时是否检查 RSSHub 可达性。
- `TAC_RSSHUB_STRICT_STARTUP`：检查失败时是否阻止应用启动。
- `TAC_RSSHUB_TIMEOUT_SECONDS`：RSSHub feed 请求超时时间。

推荐默认值保持保守：即使配置了 RSSHub feed，也只有显式启用后才执行相关源。这样测试和普通 RSS 使用场景不会被外部服务影响。

## 本地 Sidecar 启动

推荐通过 Docker Compose 或开发脚本同时启动当前项目和 RSSHub。

推荐方式：

```yaml
services:
  tac:
    build: .
    command: uv run uvicorn tac.main:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "8000:8000"
    environment:
      TAC_RSSHUB_ENABLED: "true"
      TAC_RSSHUB_INSTANCE: "http://rsshub:1200"
      TAC_RSSHUB_STARTUP_CHECK: "true"
    depends_on:
      - rsshub

  rsshub:
    image: diygod/rsshub:chromium-bundled
    ports:
      - "1200:1200"
    environment:
      CACHE_TYPE: memory
```

这个方式的边界清楚：

- Docker Compose 负责 RSSHub 进程生命周期。
- RSSHub 负责平台适配、缓存和浏览器依赖。
- 当前 FastAPI 应用只负责调用 RSSHub。

不推荐在 `tac.main` 的 lifespan 中用 `subprocess` 启动 RSSHub。原因是 Node.js 依赖、端口占用、日志、退出清理、健康检查、Chromium/Puppeteer 和 Redis 配置都会被迫塞进 Python 应用生命周期，长期维护成本高。

如果需要进一步改善开发体验，可以新增一个开发命令：

```bash
uv run tac dev --with-rsshub
```

这个命令可以作为 CLI 便利层启动 compose 或提示启动 RSSHub，但仍不应成为 FastAPI 应用启动的一部分。

## 领域模型改造

直接更新 `SourceConfig` 的 feed 字段：

```python
class FeedConfig(BaseModel):
    type: Literal["direct", "rsshub"]
    url: str | None = None
    route: str | None = None
    instance: str | None = None
    params: dict[str, str | int | bool] = Field(default_factory=dict)


class SourceConfig(BaseModel):
    name: str
    enabled: bool = True
    display: Literal["default", "compact", "featured"] = "default"
    feed: FeedConfig | None = None
    site_url: str | None = None
    tags: list[str] = Field(default_factory=list)
    manual_urls: list[ManualUrl] = Field(default_factory=list)
```

校验规则：

- `feed.type=direct` 时 `url` 必填。
- `feed.type=rsshub` 时 `route` 必填。
- `route` 必须是 path，不允许带 scheme、host 或 fragment。
- `params` 的 key 必须是非空字符串。
- `params` 的 value 只允许简单标量，最终用标准 URL 编码拼接。

## Adapter 设计

建议把现有 RSS 发现逻辑整理为统一 feed discovery 结构：

```text
src/tac/application/discovery/
  __init__.py
  feed.py
```

`feed.py` 承载普通 RSS 和 RSSHub feed 发现逻辑。RSSHub 不需要独立 adapter，只需要在解析前把 `feed.type=rsshub` 转换为实际 feed URL。

统一返回结构：

```python
@dataclass(frozen=True)
class DiscoveryResult:
    source_name: str
    source_tags: list[str]
    etag: str | None
    modified: str | None
    last_status: str
    last_error: str | None
    entries: list[tuple[str, str]]
```

feed URL 生成：

```python
def build_feed_url(source: SourceConfig, settings: Settings) -> str:
    if source.feed is None:
        raise ValueError("source feed is required")
    if source.feed.type == "direct":
        return source.feed.url or ""
    return build_rsshub_feed_url(source.feed, settings)
```

RSSHub URL 拼接示例：

```python
def build_rsshub_feed_url(feed: FeedConfig, settings: Settings) -> str:
    instance = feed.instance or settings.rsshub_instance
    route = feed.route or ""
    query = urlencode(feed.params, doseq=True)
    return f"{instance.rstrip('/')}{route}?{query}" if query else f"{instance.rstrip('/')}{route}"
```

拼接后的 URL 进入现有 `_discover_source` 等价逻辑，不需要重复写 feed 解析代码。

## 健康检查与错误处理

启动时健康检查只做可选提醒，不应默认阻止应用启动。

建议行为：

- `TAC_RSSHUB_STARTUP_CHECK=false`：不检查。
- `TAC_RSSHUB_STARTUP_CHECK=true` 且检查成功：记录可用状态。
- 检查失败且 `TAC_RSSHUB_STRICT_STARTUP=false`：记录 warning，应用继续启动。
- 检查失败且 `TAC_RSSHUB_STRICT_STARTUP=true`：应用启动失败。

发现阶段行为：

- RSSHub 请求失败时，写入 `source_state.last_status=failed`。
- 错误记录包含 HTTP 状态码、超时或解析错误。
- 单个 RSSHub 源失败不影响其他源和 manual candidates。
- 如果 RSSHub 返回 304，沿用当前 `not_modified` 逻辑。

需要注意，RSSHub 公共实例可能限流或不稳定。生产建议使用自建实例。

## API 与管理页

管理页需要提供 RSSHub route 预览接口：

```text
POST /api/admin/sources/preview-rsshub
```

请求体传入：

```json
{
  "route": "/zhihu/hot",
  "instance": "http://127.0.0.1:1200",
  "params": {
    "limit": 10
  }
}
```

返回：

```json
{
  "status": "success",
  "feed_url": "http://127.0.0.1:1200/zhihu/hot?limit=10",
  "entries": [
    {
      "title": "...",
      "url": "..."
    }
  ]
}
```

管理页需要支持：

- RSSHub 实例地址展示。
- route 输入。
- 参数编辑。
- 预览前 N 条结果。
- 最近发现状态和错误原因。

## 内容与合规边界

RSSHub 只作为候选发现来源，不意味着当前项目可以公开镜像所有平台正文。

建议保持以下边界：

- 公开发布时保留原文链接和来源。
- 对知乎、微信公众号等平台内容，优先发布摘要、推荐理由、标签和跳转链接。
- 全文抓取只用于内部评估时，也应遵守平台条款、授权和访问限制。
- 不通过 RSSHub 或 fetch 阶段绕过登录、验证码、付费墙或明确限制。

当前项目已经具备保存并发布 Markdown 的能力。接入 RSSHub 后，信源覆盖会明显扩大，因此需要补充信源级发布策略，例如：

```yaml
sources:
  - name: "知乎热榜"
    feed:
      type: "rsshub"
      route: "/zhihu/hot"
    publish_policy: "summary_only"
```

该策略应与 RSSHub 集成一起纳入设计，避免平台型内容被默认全文镜像。

## 交付范围

- 配置与文档
  - 新增 RSSHub 环境变量。
  - 把现有 `rss_url` 配置迁移为 `feed.type=direct`。
  - 新增 `feed.type=rsshub` 配置说明。
  - README 或 `docs/PROJECT.md` 增加 RSSHub sidecar 运行方式。

- 模型与配置校验
  - 新增 `FeedConfig`。
  - `SourceConfig` 使用 `feed` 表达普通 RSS 和 RSSHub。
  - 增加配置解析测试，覆盖 direct、rsshub 和非法 route。

- Feed discovery
  - 抽出当前 RSS 发现逻辑为 `FeedDiscovery`。
  - `FeedDiscovery` 负责生成 feed URL、请求 feed、解析条目和记录状态。
  - `discover_candidates()` 对所有带 `feed` 的 source 使用同一条发现路径。

- 健康检查
  - Settings 增加 RSSHub 相关配置。
  - FastAPI lifespan 中按配置执行可选检查。
  - 检查失败按 strict / non-strict 策略处理。

- 本地 sidecar
  - 新增 `compose.dev.yml` 或在现有 compose 中加入 `rsshub` 服务。
  - 文档说明 `docker compose up` 同时启动 TAC 和 RSSHub。

- 管理页预览
  - 增加 RSSHub route 预览 API。
  - 管理页支持输入 route、params 并展示候选条目。

- 信源级发布策略
  - 增加 `publish_policy` 配置。
  - RSSHub 平台型来源默认使用 `summary_only`，避免无意公开全文镜像。
  - 发布逻辑根据策略决定是否输出 Markdown 正文。

## 测试计划

- `feed.type=direct` 会直接请求 `feed.url`。
- `feed.type=rsshub` 会使用全局 `TAC_RSSHUB_INSTANCE` 拼接 URL。
- `feed.type=rsshub` 的 source 级 `feed.instance` 会覆盖全局实例。
- `feed.params` 会被正确 URL 编码。
- 非法 route，例如完整 URL 或空 route，会配置校验失败。
- RSSHub 返回的 RSS fixture 会被解析并写入候选。
- RSSHub 请求失败时只记录该 source 失败，不影响其他源。
- `TAC_RSSHUB_ENABLED=false` 时跳过或拒绝执行 `feed.type=rsshub` 源。
- 启动健康检查在 strict=false 时失败不阻止应用启动。
- 启动健康检查在 strict=true 时失败会阻止应用启动。

测试应使用本地 fixture 和 monkeypatch，不依赖真实 RSSHub 实例或真实网络。

## 关键决策

- RSSHub 作为上游发现服务，而不是内嵌库。
- 当前项目通过 HTTP 消费 RSSHub feed，不复制 RSSHub 代码。
- 本地同时启动通过 Docker Compose sidecar 实现，不放进 FastAPI 主进程。
- 普通 RSS 和 RSSHub 统一走 `FeedDiscovery`，RSSHub 只是 feed URL 生成方式之一。
- 不保留旧版 `rss_url` 字段，默认配置同步迁移到 `feed`。
- YAML 配置、后台发现和管理页预览作为同一个交付范围完成。
- 生产建议自建 RSSHub 实例，不依赖公共实例。

## 替代方案

### 直接把 RSSHub 代码嵌入当前项目

RSSHub 是 Node.js/TypeScript 项目，当前项目是 Python/FastAPI。直接嵌入会引入跨运行时构建、依赖管理、日志、调试和 license 复杂度。RSSHub 官方仓库使用 AGPL-3.0 license，复制或修改代码还需要认真处理开源义务。

不推荐。

### FastAPI 启动时 subprocess 拉起 RSSHub

这种方案可以实现“一条 uvicorn 命令带起所有东西”，但会把 Node 服务管理问题塞进 Python 应用。端口冲突、进程退出、日志归集、健康检查、Chromium 和 Redis 配置都会变复杂。

不推荐作为主路径。可以作为开发脚本包装 Docker Compose。

### 自研知乎、微信公众号等平台爬虫

自研平台爬虫可以更深度控制字段和抓取策略，但维护成本高，且更容易碰到合规和反爬边界。当前项目的核心价值是技术文章精选，不是平台爬虫框架。

不作为本方案目标。

## 风险与权衡

- RSSHub 源质量取决于具体 route 和上游平台可访问性。
- 公共 RSSHub 实例可能限流、不稳定或临时不可用。
- 自建 RSSHub 增加一个服务组件，需要部署、日志和升级管理。
- 部分 RSSHub route 可能需要额外环境变量、浏览器或缓存配置。
- RSSHub 扩大内容来源后，公开发布 Markdown 的版权和平台条款风险会增加。
- `mode=fulltext` 等能力可能带来更强的正文镜像效果，需要谨慎启用。

## 假设

- 用户主要希望借助 RSSHub 扩展平台型技术内容来源。
- 当前项目仍以 AI 精选和发布为核心，不追求成为通用爬虫。
- 本地开发环境可以接受 Docker Compose 作为推荐启动方式。
- 生产环境可以部署自建 RSSHub 或显式配置外部 RSSHub 实例。
- 管理页需要支持 RSSHub 预览；完整信源编辑器不是本方案重点。

## 完成标准

本方案完成时应具备完整闭环：统一 `feed` 配置解析、direct RSS 请求、RSSHub URL 拼接、复用 RSS 解析、离线测试、compose sidecar、启动健康检查、管理页预览和信源级发布策略。RSSHub Radar 自动识别不纳入本方案。

参考资料：

- RSSHub 官方文档：https://docs.rsshub.app/
- RSSHub GitHub 仓库：https://github.com/DIYgod/RSSHub
- RSSHub Radar：https://github.com/DIYgod/RSSHub-Radar
