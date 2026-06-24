# 技术与成长精选信源扩展调研

调研时间：2026-06-23

## 口径

本轮按“技术与成长精选”重新扩展信源，优先收录计算机领域长期参考价值内容：

- 工程实践：架构、基础设施、数据库、性能、可靠性、开发者工具、开源工程。
- 技术深文：编程语言、系统设计、安全、浏览器、图形、AI 工程。
- 科研议题：论文解读、AI/ML 研究、数据库/系统研究、研究团队博客。
- 成长内容：学习路线、求学/职业经历、Staff+ 工程师经验、工程领导力、个人成长心得。

排除或暂缓：

- 新闻流、社区媒体、活动快讯、产品发布为主的厂商营销博客。
- RSS/列表页不可达、返回 HTML 而非 feed、需要登录/API key、或当前 RSSHub 路由 503/超时的源。
- Medium 主站 `medium.com/feed/...` 当前网络不可达的源，除非有独立域名 feed 可用。

## 已接入新源

### 公司、开源与工程实践

| 信源 | 接入方式 | 判断 |
| --- | --- | --- |
| Jane Street Tech Blog | direct `https://blog.janestreet.com/feed.xml` | OCaml、形式化方法、FPGA、系统和编程语言深文，100 条可解析。 |
| Ramp Builders Blog | direct `https://engineering.ramp.com/rss.xml` | AI 工程、agent identity、token spend pipeline 等，44 条可解析；保留但依赖后续评估过滤产品化文章。 |
| Medium Engineering | direct `https://medium.engineering/feed` | Medium 自身工程博客，包含 Android、图片优化、推荐算法等，10 条可解析。 |
| Figma Engineering | listing `https://www.figma.com/blog/engineering/` | 无 RSS；使用 `main a[href*="/blog/"]:has(p)` 抽取实际文章卡片，48 条可解析。 |
| Sourcegraph Blog | direct `https://sourcegraph.com/blog/feed.rss` | AI coding、代码库理解、安全自动化；feed 内 localhost 链接可由项目现有归一化逻辑修正。 |
| Blender Developers Blog | direct `https://code.blender.org/feed/` | 开源图形软件工程、Cycles、Geometry Nodes、质量工程。 |
| Artsy Engineering | direct `https://artsy.github.io/feed` | 前端、Next.js、部署风险、TypeScript、CI 等实践。 |

### 科研、论文与学习

| 信源 | 接入方式 | 判断 |
| --- | --- | --- |
| Stanford Hazy Research | RSSHub `/stanford/hazyresearch/blog` | 本地 RSSHub 可通，AI systems、local AI、kernel、information theory 等研究/工程交叉内容。 |
| Andy Pavlo Database Blog | RSSHub `/cmu/andypavlo/blog` | 本地 RSSHub 可通，数据库年度回顾和数据库系统研究观点。 |
| BAIR Blog | direct `https://bair.berkeley.edu/blog/feed.xml` | Berkeley AI 研究博客，理论、推理、世界模型等。 |
| CMU ML Blog | direct `https://blog.ml.cmu.edu/feed/` | CMU ML 研究博客，当前 feed 条目少但质量高。 |
| Distill | direct `https://distill.pub/rss.xml` | 经典 ML 可视化和解释性文章，虽然已停更但存量长期价值高。 |
| The Gradient | direct `https://thegradient.pub/rss/` | AI 研究评论、alignment、数学与 ML 文章。 |
| fast.ai | direct `https://www.fast.ai/index.xml` | AI 学习、编程教育、工具实践；正确 feed 是 `index.xml`。 |
| Import AI | direct `https://jack-clark.net/feed/` | AI 研究动态和趋势综述，保留为研究观察类，依赖后续评估过滤短新闻。 |
| Stanford AI Lab Blog | direct `https://ai.stanford.edu/blog/feed.xml` | Stanford AI Lab 研究文章，feed 链接为相对路径，项目会按 `site_url` 归一化。 |

### 个人技术与成长

| 信源 | 接入方式 | 判断 |
| --- | --- | --- |
| Will Larson | direct `https://lethain.com/feeds.xml` | 工程领导力、组织扩张、职业判断，符合成长精选。 |
| StaffEng | direct `https://staffeng.com/index.xml` | Staff+ 工程师访谈和职业路径，59 条可解析。 |
| Charity Majors | direct `https://charity.wtf/feed/` | observability、工程纪律、组织与 AI 时代工程实践。 |
| Lara Hogan | direct `https://larahogan.me/feed.xml` | 管理、团队、反馈、职业成长。 |
| Armin Ronacher | direct `https://lucumr.pocoo.org/feed.atom` | Python/Flask 作者的工具、开源、AI 与工程随笔；部分非技术文章交给评估过滤。 |
| Erik Bernhardsson | direct `https://erikbern.com/index.xml` | 工程系统、软件组织、数据/算法随笔，172 条可解析。 |
| matklad | direct `https://matklad.github.io/feed.xml` | 编程语言、软件设计、架构和工程判断。 |
| fasterthanli.me | direct `https://fasterthanli.me/index.xml` | Rust、系统、性能和长篇技术教程。 |
| Xe Iaso | direct `https://xeiaso.net/blog.rss` | Go、系统、网络和 AI 工程随笔；少量轻内容交给评估过滤。 |

### 精选、聚合与成长媒体

| 信源 | 接入方式 | 判断 |
| --- | --- | --- |
| The Morning Paper | direct `https://blog.acolyer.org/feed/` | 论文解读经典源，已停更但存量长期价值高。 |
| ByteByteGo Newsletter | direct `https://blog.bytebytego.com/feed` | 系统设计和工程组织精选，保留为聚合/精选源。 |
| LeadDev | direct `https://leaddev.com/feed` | 工程管理、技术成长和 AI 时代工程组织文章。 |
| Commoncog | direct `https://commoncog.com/rss/` | 学习、sensemaking、软件组织与个人成长。 |
| The Pragmatic Engineer | direct `https://newsletter.pragmaticengineer.com/feed` | 工程职业、行业和管理深文；含新闻栏目，依赖评估过滤。 |

### 第二轮新增

| 信源 | 接入方式 | 判断 |
| --- | --- | --- |
| TigerBeetle Blog | direct `https://tigerbeetle.com/blog/atom.xml` | 高密度数据库/分布式系统技术深文。 |
| OpenTelemetry Blog | direct `https://opentelemetry.io/blog/index.xml` | 可观测性和遥测工程内容。 |
| Prometheus Blog | direct `https://prometheus.io/blog/feed.xml` | 监控与时序系统工程实践。 |
| Systems Approach | direct `https://systemsapproach.org/feed/` | 网络与系统架构解释型文章，长期参考价值高。 |
| Dan Luu | direct `https://danluu.com/atom.xml` | 系统、工程与产业观察长文。 |
| Thorsten Ball | direct `https://thorstenball.com/atom.xml` | 编程职业与软件设计随笔。 |
| Ben Hoyt | direct `https://benhoyt.com/writings/rss.xml` | Go/Python/工程实践深文。 |
| Ken Shirriff | direct `https://www.righto.com/feeds/posts/default?alt=rss` | 硬件逆向与计算机史/底层原理。 |
| John Regehr | direct `https://blog.regehr.org/feed` | 编译器、形式化方法、LLVM 相关研究型文章。 |
| SIGPLAN Blog | direct `https://blog.sigplan.org/feed/` | 编程语言与研究讨论。 |
| Niko Matsakis | direct `https://smallcultfollowing.com/babysteps/index.xml` | Rust 语言设计与软件设计。 |
| Without Boats | direct `https://without.boats/index.xml` | Rust、类型系统和设计推演。 |
| Faultlore | direct `https://faultlore.com/blah/rss.xml` | Rust、编译器和内存模型。 |
| Max Bernstein | direct `https://bernsteinbear.com/feed.xml` | 编译器、静态分析和系统技术文章。 |
| Overreacted | direct `https://overreacted.io/rss.xml` | 前端与软件设计高质量长文。 |
| Tonsky | direct `https://tonsky.me/atom.xml` | UI、编程和工程思考。 |
| Hynek Schlawack | direct `https://hynek.me/atom.xml` | Python 工程、虚拟环境、容器实践。 |
| Glyph | direct `https://blog.glyph.im/feeds/all.atom.xml` | Python、代码评审、AI 与工程判断。 |
| Jessitron | direct `https://jessitron.com/feed/` | 工程领导力、系统思维和技术成长。 |
| Code Without Rules | direct `https://codewithoutrules.com/atom.xml` | Python/工程成长与实践文章。 |
| Addy Osmani | direct `https://addyosmani.com/rss.xml` | 前端/AI/工程领导力文章。 |

## 已检查但未接入

| 候选 | 结果 | 理由 |
| --- | --- | --- |
| Uber Engineering | 406 | 当前 feed 请求不可用。 |
| Airbnb Engineering | 连接 Medium 失败 | `medium.com/feed/...` 当前网络不可达。 |
| Discord Engineering | 连接失败 | 当前网络不可达。 |
| DoorDash Engineering | 403 | 当前请求被拒绝。 |
| LinkedIn Engineering | 404 | 测试 feed 不存在。 |
| Pinterest Engineering | 连接 Medium 失败 | 当前网络不可达。 |
| Shopify Engineering | 返回 HTML、0 feed 条目 | `blog.atom` 不再是有效 feed。 |
| Etsy Code as Craft | 连接失败 | 当前网络不可达。 |
| Quora Engineering | 连接失败 | 当前网络不可达。 |
| eBay Tech | 可访问但偏公司创新/产品内容 | 不符合高价值技术文章优先口径。 |
| PayPal Tech | 连接 Medium 失败 | 当前网络不可达。 |
| Databricks Engineering | 列表页混入方案、伙伴、产品内容 | 厂商产品/方案文章占比较高，暂缓。 |
| Snowflake Engineering | 列表页可抽取但产品更新占比高 | 暂缓，避免厂商营销内容进入源。 |
| Notion Engineering | 列表页混入董事会、产品、案例页 | 不作为工程技术源接入。 |
| Hugging Face Blog | 直连失败，RSSHub `/huggingface/blog` 返回 503 | 当前抓取链路不可用。 |
| Mistral AI News | 连接失败 | 且命名上偏 news，暂缓。 |
| Google Research | 直连失败，RSSHub `/google/research` 返回 503 | 当前 RSSHub 路由不可用。 |
| Google DeepMind Blog | 直连超时 | 暂不接入。 |
| Meta AI Blog | RSSHub `/meta/ai/blog` 返回 503 | 当前 RSSHub 路由不可用。 |
| Anthropic Research | RSSHub 路由超时 | 已有 Anthropic Engineering 和 Frontier Red Team，研究页暂缓。 |
| StaffEng `/feed.xml`、`/rss.xml` | 404 | 正确 feed 为 `/index.xml`，已接入。 |
| Lara Hogan `/blog/feed/` | 404 | 正确 feed 为 `/feed.xml`，已接入。 |
| fast.ai `/feed.xml` | 404 | 正确 feed 为 `/index.xml`，已接入。 |
| Software Lead Weekly | 返回 HTML、0 feed 条目 | 未找到有效 feed。 |
| Leadership in Tech | 404 | 未找到有效 feed。 |
| Quastor | 404 或 DNS 失败 | 未找到可用 feed。 |
| Pointer | 404 | 未找到有效 feed。 |
| Papers We Love | feed 仅 meetup 新闻或空 release | 不符合文章源口径。 |
| Galois | 404 | 旧 feed 不可用。 |
| Algolia Blog | 404 | 旧 feed 不可用。 |
| Atlassian Blog | 返回 HTML、0 feed 条目 | 未接入。 |
| 8th Light Insights | feed 可用但咨询/活动/团队内容混杂 | 暂缓。 |
| LiveRamp Engineering | 404 | 旧接口不可用。 |
| DuckDB Blog | 可用，但当前样本以 release 为主 | 暂缓，避免源内过多版本公告。 |
| DoltHub Blog | 可用，但当前样本以产品/更新为主 | 暂缓。 |
| Rust Blog / Inside Rust | 可用，但版本与项目公告占比高 | 暂缓。 |
| Apache Arrow Blog | 可用，但发布/社区更新偏多 | 暂缓。 |
| Zig News | 可用，但公告与版本更新偏多 | 暂缓。 |
| Dan Luu 相关替代源 | 未继续添加 | 需要逐篇过滤非计算机主题内容。 |

## RSSHub 结论

本地 RSSHub 已验证可用并接入：

- `/stanford/hazyresearch/blog`
- `/cmu/andypavlo/blog`
- 既有 `/anthropic/engineering`、`/anthropic/red`、`/openai/research`

本轮验证不可用或不稳定，暂不接入：

- `/huggingface/blog`
- `/huggingface/daily-papers/week/20`
- `/meta/ai/blog`
- `/google/research`
- `/anthropic/research`
