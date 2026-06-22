# 公开 RSS Feed 接入方案

## Background

当前项目已经提供 `/api/public/articles`、`/api/public/articles/{slug}` 和 `/api/public/index.json` 三个公开 JSON API，只暴露已收录的 `accepted` 文章。项目也支持从上游 RSS/Atom 和 RSSHub 发现候选文章，但这是输入侧能力，不等于对外提供可订阅的 RSS。

本方案补齐输出侧 RSS：让外部阅读器、自动化系统或团队知识库可以通过标准 feed 订阅精选文章。

## Goals

- 提供稳定的公开 RSS 2.0 订阅地址。
- 复用现有公开文章查询逻辑，只输出 `accepted` 文章。
- 使用成熟库生成 XML，避免手写 RSS 序列化、转义和日期格式。
- 支持 HTTP 缓存，减少订阅器轮询带来的数据库压力。
- 保持实现范围小，不改变文章发现、抓取、评估和发布流程。

## Non-Goals

- 不做全文镜像策略的重新设计。
- 不在首版提供每个 source、tag 或搜索词的独立 feed。
- 不替代现有 JSON API。
- 不引入用户认证、私有 feed token 或个性化订阅。
- 不把输入侧 RSSHub 能力和输出侧 RSS feed 混在同一模块中。

## Final Design

新增公开只读接口：

```text
GET /feed.xml
GET /api/public/feed.xml
```

两个路径返回同一份 RSS 2.0 XML。`/feed.xml` 适合阅读器直接发现和订阅，`/api/public/feed.xml` 与现有公开 API 命名保持一致。若只想减少路径数量，可以只保留 `/feed.xml`；但推荐两个都提供，内部复用同一个 handler 或 helper。

响应头：

```text
Content-Type: application/rss+xml; charset=utf-8
Cache-Control: public, max-age=300
ETag: "<hash>"
Last-Modified: "<latest accepted article collected_at or updated_at>"
```

条件请求：

- 客户端发送 `If-None-Match` 且匹配当前 ETag 时返回 `304 Not Modified`。
- 客户端发送 `If-Modified-Since` 且没有更新文章时返回 `304 Not Modified`。
- ETag 优先级高于 Last-Modified。

默认条数：

- RSS feed 默认输出最新 50 篇 accepted 文章。
- 允许 `?limit=`，范围 `1..200`，默认 `50`。
- 不提供分页。RSS 是订阅流，不适合暴露无限分页历史。

推荐依赖：

```toml
dependencies = [
    "feedgen>=1.0.0",
]
```

选择 `feedgen` 的原因：

- 它是专门用于生成 Atom、RSS 和 Podcast feed 的 Python 库。
- PyPI 当前最新版本为 `1.0.0`，发布于 2023-12-25，并标记为 Production/Stable。
- 官方 README 示例提供 `FeedGenerator.rss_str(...)`、`atom_str(...)`、`rss_file(...)` 等生成能力。
- 项目无需直接拼 XML，也无需自己处理 XML escape、RSS 日期格式和 feed/item 结构。

## Data Mapping

Feed 级字段：

| RSS 字段 | 来源 |
| --- | --- |
| `channel.title` | 新增配置 `TAC_PUBLIC_FEED_TITLE`，默认 `技术文章精选` |
| `channel.link` | 新增配置 `TAC_PUBLIC_BASE_URL`，例如 `https://example.com` |
| `channel.description` | 新增配置 `TAC_PUBLIC_FEED_DESCRIPTION`，默认项目简介 |
| `channel.language` | 新增配置 `TAC_PUBLIC_FEED_LANGUAGE`，默认 `zh-CN` |
| `channel.lastBuildDate` | 当前 feed 中最新文章时间 |
| `channel.ttl` | 新增配置 `TAC_PUBLIC_FEED_TTL_MINUTES`，默认 `5` |

Item 级字段：

| RSS 字段 | 来源 |
| --- | --- |
| `item.guid` | 优先使用公开详情 URL；也可使用原文 URL，但推荐详情 URL 更稳定 |
| `item.title` | `articles.title` |
| `item.link` | 公开详情 URL：`${TAC_PUBLIC_BASE_URL}/api/public/articles/{slug}` 或未来站点文章页 |
| `item.source` | 原文 URL 和 source 名称 |
| `item.pubDate` | `collected_at`，缺失时回退到 `updated_at` 或 `created_at` |
| `item.description` | `summary` + `recommendation_reason` 的短摘要 |
| `item.category` | `tags` |

正文策略：

- RSS item 默认不放完整 Markdown 正文。
- `description` 使用 AI 摘要和推荐理由，末尾附原文链接。
- 对 `publish_policy=summary_only` 的文章必须只输出摘要。
- 对 `publish_policy=full_content` 的文章首版也只输出摘要，避免订阅端复制全文带来的版权和体积风险。

## Modules

新增应用层 helper：

```text
src/tac/application/use_cases/generate_feed.py
```

职责：

- 从 `manage_articles.list_public_articles(...)` 读取公开文章。
- 将文章字典转换为 feedgen 的 `FeedGenerator` 和 entry。
- 生成 RSS XML bytes。
- 计算 ETag、Last-Modified 所需元数据。

新增路由：

```text
src/tac/web/routers/public.py
```

职责：

- 接收 `limit` 参数。
- 处理条件请求。
- 返回 `fastapi.Response`，media type 为 `application/rss+xml`。
- 将 `/feed.xml` 根路径注册在 `main.py` 或一个无 prefix 的 public feed router 中。

新增配置：

```text
TAC_PUBLIC_BASE_URL
TAC_PUBLIC_FEED_TITLE
TAC_PUBLIC_FEED_DESCRIPTION
TAC_PUBLIC_FEED_LANGUAGE
TAC_PUBLIC_FEED_TTL_MINUTES
```

`TAC_PUBLIC_BASE_URL` 推荐在生产环境显式配置。未配置时，本地开发可以从请求推断 origin，但生产不应依赖代理头推断永久链接。

## Key Decisions

- 首版使用 RSS 2.0，而不是只提供 Atom。RSS 阅读器兼容性更普遍；`feedgen` 仍然让后续增加 Atom 很轻。
- 使用动态生成，不在发布阶段写死 `public/feed.xml`。这样管理 API 调整文章状态后，订阅输出立即反映最新 accepted 状态。
- 使用摘要 feed，不输出完整 Markdown。项目聚合第三方文章，摘要 feed 更符合版权和带宽边界。
- 使用 `feedgen>=1.0.0`。旧版本曾有 XML 安全问题，依赖约束应避免安装过旧版本。

## Alternatives Considered

### 手写 XML

不采用。RSS 细节包括日期、转义、CDATA、命名空间和可选字段，手写容易在边界字符或阅读器兼容性上出错。

### 只输出 Atom

不采用作为首版默认。Atom 结构更严格，但用户明确希望 RSS 接入，RSS 2.0 更符合订阅器直觉。

### 发布阶段生成静态 `public/feed.xml`

暂不采用。静态文件适合纯静态站点，但当前 FastAPI 已经直接提供公开 API，动态生成可以更自然地复用权限、状态过滤和条件请求。未来如果部署为静态站，可以再让 publish 阶段复用同一个生成 helper 写出文件。

### 每个 source/tag 都生成独立 feed

首版不做。它会引入路由设计、参数规范、缓存 key 和订阅发现问题。等主 feed 稳定后再扩展。

## Tradeoffs and Risks

- 动态 feed 会被阅读器定期轮询，需要 ETag、Last-Modified 和短缓存降低压力。
- `TAC_PUBLIC_BASE_URL` 配置错误会导致 feed item 链接不稳定，需要 README 明确说明。
- RSS 阅读器对 HTML 支持差异较大，`description` 应保持简单文本或保守 HTML。
- 如果未来要输出全文，需要重新评估 `publish_policy`、原文版权和 Markdown 到 HTML 的转换策略。

## Assumptions

- 外部订阅者主要需要“看到有哪些新收录文章”，不需要在 RSS 内阅读完整正文。
- 公开 feed 只包含 accepted 文章，与现有公开 API 一致。
- 首版不需要认证或私有订阅。
- 部署方可以配置一个稳定的 `TAC_PUBLIC_BASE_URL`。

## Follow-Up Plan

1. 添加 `feedgen>=1.0.0` 依赖并更新 lockfile。
2. 在 `settings.py` 增加公开 feed 相关配置。
3. 新增 `generate_feed.py`，集中处理 feed 生成和元数据计算。
4. 在 public router 中新增 `/api/public/feed.xml`，在应用根路由新增 `/feed.xml`。
5. 增加离线测试：
   - 只输出 accepted 文章。
   - RSS XML 可被 `feedparser.parse(...)` 正常解析。
   - `limit` 生效且最大值被限制。
   - ETag 命中返回 304。
   - `summary_only` 文章不输出正文。
6. 更新 README 和 `docs/PROJECT.md`，说明订阅地址、配置项和摘要策略。

