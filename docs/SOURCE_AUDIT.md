# 信源逐项审评

生成日期：2026-06-23

本文档审查 `config/sources.yaml` 当前 127 个信源。审查方式不是只看源名，而是实际访问每个源的 `feed.url` 或 listing 页面，抽取最近 6 个条目，并打开前 2 篇文章页确认正文形态。临时抓取结果保存在 `/tmp/tac_source_probe_v2.json` 和 `/tmp/tac_source_probe_v2.md`，不提交到仓库。

本轮实际抓取结果：

| 项目 | 数量 |
| --- | ---: |
| 配置源总数 | 127 |
| feed/listing 可访问 | 124 |
| 成功解析出最近条目 | 122 |
| 成功打开的文章页样本 | 223 |
| 建议保留 | 75 |
| 建议删除 | 52 |

## 判断口径

“高价值技术文章”指稳定产出工程实践、系统设计、实现细节、性能分析、故障复盘、安全研究、语言/运行时机制、数据库/基础设施内部机制、AI/ML 工程或研究深度内容的文章。

删除并不表示站点没有任何好文章，而是表示当前自动抓取入口不适合作为默认源。只要当前入口持续混入新闻、发布日志、厂商产品更新、营销方案、浅教程、社区问答、周报、个人生活或碎片笔记，就建议删除或改成更窄的工程/研究入口。

## 建议保留

| # | 源 | 实际抽检样本 | 保留理由 |
| --- | --- | --- | --- |
| 1 | [美团技术团队](https://tech.meituan.com/) | “美团海报生成 AIGC 技术创新与实践”；“用 Agent 评测思路管理 AI Coding” | 有业务场景、架构流程、模型评测和工程落地细节，符合中文高价值工程源。 |
| 2 | [有赞技术团队](https://tech.youzan.com/) | “知识库检索匹配的服务化实践”；“Spark App 血缘解析方案” | 最近样本仍是搜索、血缘、模型部署等具体工程实践。 |
| 3 | [Cloudflare Blog](https://blog.cloudflare.com/) | “How we found a bug in the hyper HTTP library”；“Build your own vulnerability harness” | 虽是厂商博客，但样本包含开源库缺陷、安全 harness、网络/边缘工程细节，技术密度足够。 |
| 4 | [GitHub Engineering](https://github.blog/engineering/) | “Modernizing GitHub Issues navigation performance”；“How GitHub uses eBPF to improve deployment safety” | 明确工程栏目，近期样本是性能优化、eBPF、搜索高可用等内部工程经验。 |
| 5 | [Dropbox Tech](https://dropbox.tech/) | “Improving storage efficiency in Magic Pocket”；“Introducing Nova, our internal platform for coding agents” | 存储、平台、安全和 AI agent 工程实践较具体。 |
| 6 | [Slack Engineering](https://slack.engineering/) | “Slack AI: The Path to Multi-Cloud”；“From SSH to REST...” | 样本有多云 LLM 服务、数据管道改造、E2E 测试等真实工程内容。 |
| 7 | [Meta Engineering](https://engineering.fb.com/) | “Adopting AV1 for RTC at Scale”；“Migrating Data Ingestion Systems at Meta Scale” | 超大规模视频、数据、推荐、可靠性和安全系统实践，价值高。 |
| 8 | [Kubernetes Blog](https://kubernetes.io/blog/) | “Reconciling the Past: Correcting Records for Unfixed Kubernetes CVEs”；“Announcing etcd 3.7.0-beta.0” | 有公告噪音，但 Kubernetes/etcd/CVE 机制类内容对云原生读者有直接价值。 |
| 12 | [Martin Fowler](https://martinfowler.com/) | “Building Reliable Agentic AI Systems”；“The test suite as a regression sensor” | 架构、测试、AI 系统可靠性和软件设计内容长期价值高；需过滤 fragments。 |
| 13 | [Julia Evans](https://jvns.ca/) | “Moving away from Tailwind...”；“Examples for the tcpdump and dig man pages” | 调试、Linux、网络和工具解释清楚，个人源信噪比高。 |
| 14 | [Brendan Gregg](https://www.brendangregg.com/blog/) | “Third Stage Engineering”；“Why I joined OpenAI” | 性能工程权威源；近期有个人动态，需过滤，但核心技术价值仍强。 |
| 17 | [Anthropic Engineering](https://www.anthropic.com/engineering) | “How we contain Claude across products”；“April 23 postmortem” | 明确工程栏目，包含安全边界、事故复盘、Agent 工程等具体内容。 |
| 20 | [Amazon Science](https://www.amazon.science/) | “EC2’s formally verified isolation engine”；“How flat is replacing fat in AWS data center networks” | 本轮样本不是普通新闻，而是形式化验证、芯片、网络拓扑和 agent 系统研究，保留。 |
| 25 | [Microsoft Research Blog](https://www.microsoft.com/en-us/research/blog/) | “Ire identifies another LOTUSLITE specimen”；“Vega: Zero-knowledge proofs...” | 研究入口，样本包含恶意软件分析、ZK 身份、agent 系统，技术性强于产品博客。 |
| 27 | [NVIDIA Technical Blog](https://developer.nvidia.com/blog/) | “CCCL Runtime: A Modern C++ Runtime for CUDA”；“Enable Real-Time AI...” | GPU、CUDA、AI/HPC 和系统优化文章具体，属于可保留的高技术厂商源。 |
| 29 | [Netflix TechBlog](https://netflixtechblog.com/) | “How Netflix Simplified Batch Compute with Kueue”；“Data Projects: Managing Data Assets...” | 大规模数据、推荐、批计算和平台工程实践稳定。 |
| 31 | [Lyft Engineering](https://eng.lyft.com/) | “Metric Semantic Layer...”；“Unified, Self-Routing Support Ops Ticketing System” | 数据治理、平台和业务系统工程经验具体。 |
| 32 | [Spotify Engineering](https://engineering.atspotify.com/) | “The Context Layer Behind Spotify's Data Assistant”；“Scaling Developer Experience...” | 数据助手、开发者体验、LLM eval 和平台工程内容较具体。 |
| 33 | [Canva Engineering](https://www.canva.dev/blog/engineering/) | “From Intern Project to Production...”；“Measuring Commercial Impact at Scale” | 工程栏目仍有产品工程、前端和平台实践；需过滤招聘/面试类文章。 |
| 34 | [Grab Tech](https://engineering.grab.com/) | “Palana: secure platform for autonomous AI Agents”；“Apache Flink data ingestion platform” | 大规模业务场景下的数据、平台、安全和 AI agent 工程，保留。 |
| 35 | [Yelp Engineering](https://engineeringblog.yelp.com/) | “How Partition Access Visualizations Reduced Data Lake S3 Cost by 33%”；“Migrating from Webpack to Rspack” | 成本优化、构建性能、Server-Driven UI 等具体工程案例。 |
| 36 | [Instacart Tech Blog](https://tech.instacart.com/) | “Rebuilding Ads Retrieval”；“Semantic IDs: Product Understanding at Scale” | 搜索、广告、商品理解和多租户营销平台，技术问题明确。 |
| 37 | [Salesforce Engineering](https://engineering.salesforce.com/) | “How Data 360 Segmentation Processes a Quadrillion Records”；“Maintaining Code Quality at Agent Speed” | 是厂商工程栏目，但样本有大规模数据处理和 AI 工程治理细节。 |
| 39 | [Square Developer Blog](https://developer.squareup.com/blog/) | “An analysis of the Square and Cash App outage”；“A Massively Multi-user Datastore...” | 之前按开发者平台误判；实际样本有事故复盘、安全研究和数据系统设计，应保留。 |
| 42 | [PlanetScale Blog](https://planetscale.com/blog) | “Introducing database traffic control”；“The feedback loops behind Kubernetes” | feed 很大且解析有风险，但站点样本有数据库、Vitess 和工程内容；建议后续改成 engineering/Vitess 窄入口。 |
| 43 | [Fly.io Blog](https://fly.io/blog/) | “Litestream Writable VFS”；“The Design & Implementation of Sprites” | 运行时、SQLite、边缘部署和底层实现文章质量高。 |
| 44 | [Tailscale Blog](https://tailscale.com/blog/) | “Redundancy only matters if you can reach it”；“More Tailscale tricks...” | 网络、安全和分布式基础设施内容较强；需过滤产品功能文。 |
| 61 | [GitHub Security Lab](https://github.blog/security/) | “Reducing false positives at scale”；“Securing the git push pipeline...” | 代码安全、漏洞、供应链和平台安全研究，保留。 |
| 63 | [Trail of Bits Blog](https://blog.trailofbits.com/) | “Factoring short-sleeve RSA keys with polynomials”；“We hardened zizmor...” | 安全研究、审计、漏洞和工具分析，深度稳定。 |
| 65 | [MDN Blog](https://developer.mozilla.org/en-US/blog/) | “Under the hood of MDN's new frontend”；“Image formats: Codecs and compression tools” | 非营销源，Web 平台和前端技术解释有长期价值。 |
| 66 | [Mozilla Hacks](https://hacks.mozilla.org/) | “Behind the Scenes Hardening Firefox...”；“Trustworthy JavaScript for the Open Web” | 浏览器、Web 平台和开放 Web 技术内容明确。 |
| 67 | [WebKit Blog](https://webkit.org/blog/) | “The golden rule of Customizable Select”；“Introducing the Field Guide to Grid Lanes” | WebKit/Web 标准/浏览器实现细节，保留；需过滤 STP release notes。 |
| 68 | [V8 Blog](https://v8.dev/blog) | “How we made JSON.stringify more than twice as fast”；“Speculative Optimizations for WebAssembly...” | JavaScript 引擎、性能和运行时内部机制，高价值。 |
| 70 | [Go Blog](https://go.dev/blog/) | “Type Construction and Cycle Detection”；“Allocating on the Stack” | Go 官方源近期样本是语言/编译器/运行时技术文章，保留。 |
| 73 | [Simon Willison](https://simonwillison.net/) | “Prompt Injection as Role Confusion”；“Porting Moebius... to run in the browser” | LLM、Web、SQLite 和工具实践密度高。 |
| 75 | [Hillel Wayne](https://www.hillelwayne.com/) | “Some Silly Z3 Scripts I Wrote”；“A Very Early History of Algebraic Data Types” | 软件设计、形式化方法和编程语言内容有深度；需过滤非技术随笔。 |
| 79 | [Brave New Geek](https://bravenewgeek.com/) | “Controller-Driven Infrastructure as Code”；“Platform Engineering as a Service” | 分布式系统、平台工程和基础设施设计，主题匹配。 |
| 80 | [Marc Brooker](https://brooker.co.za/blog/) | “Meet Alice. Alice is impatient.”；“Agentic software development hypothesis” | 分布式系统、可靠性和工程方法文章质量高。 |
| 81 | [Eli Bendersky](https://eli.thegreenplace.net/) | “Plugins case study: Pluggy”；“Notes on Fourier series” | 编程语言、系统、Python/Go/C 和数学解释稳定。 |
| 82 | [Null Program](https://nullprogram.com/) | “Concurrent, atomic MSI hash tables”；“dcmake: a new CMake debugger UI” | C、系统编程、工具和底层实现，保留。 |
| 83 | [John D. Cook](https://www.johndcook.com/blog/) | “Formalizing a ring theorem with Lean 4 and Claude”；“Queens on a prime order board” | 数学、统计、编程和工程计算补充源。 |
| 84 | [Jay Alammar](https://jalammar.github.io/) | “The Illustrated Stable Diffusion”；“The Illustrated Retrieval Transformer” | 虽有迁移/产品观点，但核心是高质量 ML 可视化解释。 |
| 85 | [Lilian Weng](https://lilianweng.github.io/) | “Active Learning”；“Diffusion Models” | AI/ML 综述深度高，长期参考价值强。 |
| 86 | [Chip Huyen](https://huyenchip.com/) | “Common pitfalls when building generative AI applications”；“Building A Generative AI Platform” | ML 系统、数据和 AI 产品工程，实践价值高。 |
| 87 | [Eugene Yan](https://eugeneyan.com/) | “Patterns for Building Cybersecurity Evals”；“Using LLMs to Secure Source Code” | 推荐、搜索、LLM eval 和 ML 工程实践具体。 |
| 88 | [Sebastian Raschka](https://sebastianraschka.com/) | “GLM-5.2 and IndexShare...”；“LLM Research Papers...” | ML/LLM 论文和技术解释稳定。 |
| 89 | [Jeremy Kun](https://www.jeremykun.com/) | “CKKS... Encoding”；“Deterministic Primality Testing...” | 算法、数学、密码和计算机科学解释，保留。 |
| 90 | [Red Blob Games](https://www.redblobgames.com/) | “Highlighting interactive code blocks”；“Writing a guide to SDF fonts” | 算法可视化和交互解释是稀缺高质量源。 |
| 91 | [Daniel Lemire](https://lemire.me/blog/) | “Parsing JSON at compile time with C++26 static reflection”；“microarchitecture levels in Go” | 性能、C++、Go、数据库和底层优化，保留。 |
| 92 | [MaskRay](https://maskray.me/blog/) | “Recent LLVM hash table improvements”；“Recent lld/ELF performance improvements” | 编译器、链接器、LLVM/ELF 和系统工具链，强技术源。 |
| 93 | [Josh W Comeau](https://www.joshwcomeau.com/) | “CSS vs. JavaScript”；“Scroll-Driven Animations” | 高质量前端、CSS、React 和交互工程文章。 |
| 94 | [Jake Archibald](https://jakearchibald.com/) | “Importing vs fetching JSON”；“Fetch streams are great...” | Web 平台和浏览器 API 深度文章，保留。 |
| 95 | [ACM Queue Articles](https://queue.acm.org/) | “In Code They Think; In Proof We Trust”；“From Technical Debt to Cognitive and Intent Debt” | 系统、软件工程和研究型深度文章，主源级别。 |
| 96 | [LoRexxar Blog](https://lorexxar.cn/) | “Ghost Bits，Java WAF之殇？”；“AI.Re.” | 中文安全研究和技术分析源，保留。 |
| 97 | [CoolShell](https://coolshell.cn/) | “是微服务架构不香还是云不香？”；“我看 ChatGPT...” | 中文经典技术源；更新少且有观点文，但历史文章价值高。 |
| 100 | [Bram.us](https://www.bram.us) | “View Transitions...”；“CSS position: sticky...” | CSS、浏览器能力、Web 标准和前端实验，保留。 |
| 101 | [Thomas Schatzl](https://tschatzl.github.io/) | “JDK 26 G1/Parallel/Serial GC changes”；“New Write Barriers for G1” | JVM GC/OpenJDK 性能窄而深。 |
| 104 | [Skywind Inside](https://www.skywind.me/blog/) | “在 Vim 里实现可定制表单对话框”；“单头文件 C++ 游戏开发库” | 中文系统、C++、工具和工程经验，技术性强。 |
| 105 | [Wang Yi AI](https://wangyi.ai/) | “Building a Language Transformer Step by Step”；“HRM Explained...” | 本轮样本是 AI/ML 从原理到实现的长文解释，应保留。 |
| 108 | [Crunchy Data Blog](https://www.crunchydata.com/blog) | “Postgres Serials Should be BIGINT”；“PostGIS Performance...” | PostgreSQL 性能、扩展和运维文章具体；可接受的数据库厂商技术源。 |
| 109 | [ClickHouse Blog](https://clickhouse.com/blog) | “pg_clickhouse v0.3.2”；“How Spyne simplified their CDC pipeline...” | 有产品噪音，但 OLAP、CDC、性能和数据库工程内容足够强。 |
| 110 | [LWN.net](https://lwn.net/) | “Free-threaded Python: past, present, and future”；Linux/security headlines | Linux 内核、开源和系统软件深度报道，保留。 |
| 111 | [Memcached Blog](https://memcached.org/blog/) | “Judging the Cost of Replacing Cached Items”；“Paper Review: MemC3” | 缓存系统内部机制，更新少但主题深。 |
| 112 | [Racket Blog](https://blog.racket-lang.org/) | “Parallel Threads in Racket v9.0”；“Rhombus v1.0” | 语言生态和实现类内容，保留但过滤纯版本公告。 |
| 113 | [Mitchell Hashimoto](https://mitchellh.com/) | “Simdutf Can Now Be Used Without libc++”；“Ghostty Is Leaving GitHub” | 基础设施、终端、Zig 和工具链个人实践，质量高。 |
| 114 | [Fzakaria Blog](https://fzakaria.com/) | “Nix needs relocatable binaries”；“linker pessimization” | feed 抽检超时，但站点页样本是 Nix、ELF、构建和链接器技术，保留。 |
| 115 | [Alex Chan](https://alexwlchan.net/) | “What can wonky APIs tell us about the web?”；“Using Pytester...” | Web、Python、测试和工具实践文章完整。 |
| 116 | [Andy Atkinson](https://andyatkinson.com/) | “Splitting to 8 Primary DBs”；“What are SLRUs and MultiXacts...” | PostgreSQL/Rails 扩展和故障复盘，具体可复用。 |
| 117 | [Adrien Grand](https://jpountz.github.io/) | “An ode to self-optimizing query plans”；“Vectorized evaluation...” | 搜索、Lucene、数据库查询和性能，保留。 |
| 118 | [Anders Murphy](https://andersmurphy.com/) | “The perils of UUID primary keys in SQLite”；“100000 TPS over a billion rows...” | feed 抽检超时，但站点样本是 SQLite/数据库实践，保留。 |
| 119 | [RIPE Labs](https://labs.ripe.net/) | “Discovery of IPv6 Router Addresses...”；“What We Learned from a Multi-Service Vulnerability Disclosure” | 网络测量、DNS、路由和安全研究价值高；需过滤治理/会议内容。 |
| 120 | [Daniel Stenberg](https://daniel.haxx.se/blog/) | “QUERY with curl”；“A human in control” | curl、HTTP、网络协议和开源维护，权威技术源。 |
| 121 | [Random Oracle](https://blog.randomoracle.io/) | “Mark-of-the-web and pinning installers to sites”；“ScreenConnect redux...” | 安全研究和系统分析，保留。 |
| 122 | [Argus Systems Blog](https://blog.argus-systems.ai/) | “OpenBSD PPP authentication bypass”；“Zabbix SQL Injection...” | 样本少但都是安全研究型文章，保留观察。 |
| 127 | [Google DeepMind Blog](https://deepmind.google/blog/) | “Securing the future of AI agents”；“DiffusionGemma...” | AI 研究和安全内容有原创性；需过滤合作公告和产品宣传。 |

## 建议删除

| # | 源 | 实际抽检样本 | 删除理由 |
| --- | --- | --- | --- |
| 9 | [CNCF Blog](https://www.cncf.io/blog/) | “KubeCon... Unite in China”；“Flipkart Wins CNCF End User Case Study...” | 夹杂活动、公告、案例、会员/生态内容；虽偶有好文，但自动源信噪比不稳定。 |
| 10 | [InfoQ 中文](https://www.infoq.cn/) | “人人都是 Builder 的时代...”；“TDSQL 用一套内核...” | 媒体源，新闻、软文、采访和厂商稿混杂，正文抓取也不稳定。 |
| 11 | [SegmentFault](https://segmentfault.com/) | “怎么使用 codex？”；“在线进制转换工具推荐？” | 社区问答流，质量离散且多为求助/工具推荐，不适合作为精选源。 |
| 15 | [阮一峰的网络日志](https://www.ruanyifeng.com/blog/) | “科技爱好者周刊...”连续 3 条 | 当前入口主要是周刊和链接发现，不是具体技术文章源。 |
| 16 | [OpenAI News](https://openai.com/news/) | “How Omio is building...” “Daybreak...” | 官方新闻/案例/产品入口，工程细节不可控；应找工程或研究子源。 |
| 18 | [Anthropic News](https://www.anthropic.com/news) | “Claude Corps”；“office partnerships...” | 新闻和产品发布入口，已由 Anthropic Engineering 覆盖真正技术内容。 |
| 19 | [Claude Code Releases](https://github.com/anthropics/claude-code/releases) | “v2.1.186”；“v2.1.185” | 纯发布日志，不是技术文章。 |
| 21 | [AWS News Blog](https://aws.amazon.com/blogs/aws/) | “AWS Weekly Roundup”；“Announcing EC2 G7...” | AWS 服务发布和产品更新为主，删除。 |
| 22 | [AWS Architecture Blog](https://aws.amazon.com/blogs/architecture/) | “Secure multi-tenant RAG with Amazon Bedrock...” | 以 AWS 产品组合、解决方案架构和客户案例为主，不符合去厂商产品流的要求。 |
| 23 | [AWS Machine Learning Blog](https://aws.amazon.com/blogs/machine-learning/) | “Building pay-per-intelligence... Bedrock”；“Running ComfyUI on SageMaker” | 主要围绕 AWS 服务教程和产品能力，删除。 |
| 24 | [Microsoft Developer Blogs](https://devblogs.microsoft.com/) | “Stop overloading your skills”；“When your agent extensions fight...” | 总入口过宽，混合观点、工具、平台和产品内容；保留更窄的 Research/TypeScript 也需另审。 |
| 26 | [Azure Blog](https://azure.microsoft.com/en-us/blog/) | “Modernize your data with Azure Storage”；“Build 2026...” | Azure 产品、迁移方案和发布宣传为主。 |
| 28 | [Apple Developer News](https://developer.apple.com/news/) | “License Agreement now available”；“Changes to iOS in Brazil” | Apple 开发者公告，不是技术文章。 |
| 30 | [Stripe Engineering](https://stripe.com/blog/engineering) | “What Link data tells us about AI spending”；“Stripe Projects adds...” | 当前 feed 是 Stripe 全站博客而非纯工程 feed，近期多为商业/产品内容；建议删除或寻找工程专用 RSS。 |
| 38 | [Heroku Blog](https://blog.heroku.com/) | “Heroku March 2026 Update”；“Heroku CLI v11” | PaaS 产品更新和平台公告为主。 |
| 40 | [Datadog Blog](https://www.datadoghq.com/blog/) | “Datadog MCP Apps”；“Automate threat hunting with Datadog...” | 可观测性厂商产品、教程和营销混杂，删除。 |
| 41 | [HashiCorp Blog](https://www.hashicorp.com/blog) | “Introducing tfctl”；“Terraform MCP server is now GA” | Terraform/Vault/HCP 产品更新和教程为主。 |
| 45 | [Grafana Blog](https://grafana.com/blog/) | “ObservabilityCON 2026”；“Grafana Assistant Investigations” | 活动、产品发布和教程混杂，删除。 |
| 46 | [Elastic Blog](https://www.elastic.co/blog/) | “AI adoption in security”；“Elastic Security simplifies...” | 搜索/安全厂商产品和行业内容占比高。 |
| 47 | [Red Hat Developer Blog](https://developers.redhat.com/blog/) | “Connect EvalHub...”；“Building ... on OpenShift” | 企业平台教程和产品生态文章为主。 |
| 48 | [Supabase Blog](https://supabase.com/blog) | “Supabase Series F”；“Official ChatGPT App” | 产品、融资、平台公告混杂；即使偶有 Postgres 技术，也不适合作默认源。 |
| 49 | [Sentry Blog](https://blog.sentry.io/) | “Snapshots, now in beta”；“Works on my machine...” | 产品功能、开发者体验和营销混杂；若需要应找工程子栏目。 |
| 50 | [Confluent Blog](https://www.confluent.io/blog/) | “Introducing dbt Adapter for Confluent Cloud”；“Build vs Buy Streaming...” | Kafka/流处理厂商方案、产品和营销内容多。 |
| 51 | [Docker Blog](https://www.docker.com/blog/) | “Docker Content Trust retirement”；“Docker Hardened Images...” | Docker 产品、安全能力和生态公告为主。 |
| 52 | [DigitalOcean Blog](https://www.digitalocean.com/blog) | “DigitalOcean Inference Engine”；“What We Learned Hiring...” | 典型云厂商产品/招聘/平台内容，不应出现在默认源。 |
| 53 | [Neon Blog](https://neon.com/blog) | “Introducing neon.ts”；“provision Neon in Vercel CLI” | 近期围绕 Neon 产品和开发体验；不作为默认源。 |
| 54 | [Prisma Blog](https://www.prisma.io/blog) | “Search the Prisma Docs...”；“App Hosting and Compute Platforms...” | ORM 产品、文档、托管和生态内容为主。 |
| 55 | [Pulumi Blog](https://www.pulumi.com/blog/) | “Cloudflare-First Networking as Code”；“AI code review built for infrastructure” | IaC 产品、方案和教程属性强。 |
| 56 | [Sourcegraph Blog](https://sourcegraph.com/blog) | “Sourcegraph MCP server...”；“Automating Security Triage...” | 产品、AI 编程和安全自动化营销混合，删除。 |
| 57 | [Dagster Blog](https://dagster.io/blog) | “Dagster Almanack”；“How to Orchestrate dbt with Dagster” | 数据编排厂商方法论和产品教程为主。 |
| 58 | [dbt Labs Blog](https://www.getdbt.com/blog) | “Fivetran + dbt Labs...” “dbt migration guide” | 行业活动、迁移、产品生态和营销内容多。 |
| 59 | [Akamai Blog](https://www.akamai.com/blog) | feed 返回 403 | 当前入口不可抓，且综合博客通常混杂威胁资讯、产品和市场内容。 |
| 60 | [GitHub Changelog](https://github.blog/changelog/) | “New features...” “AI credits consumed...” | 产品变更日志，不是技术文章。 |
| 62 | [Auth0 Blog](https://auth0.com/blog/) | “Passkey Adoption Is Rising...” “AI Agents Are Not Users...” | 身份厂商观点、教程和产品语境混合；不作为默认源。 |
| 64 | [Cloudflare Radar Blog](https://blog.cloudflare.com/tag/radar/) | 抽检结果与 Cloudflare 主 feed 重复 | 当前配置没有得到独立 Radar 流，删除重复源。 |
| 69 | [Rust Blog](https://blog.rust-lang.org/) | “Announcing Rust 1.96.0”；Cargo CVE advisories | 当前入口以发布、基金会和安全公告为主；技术文章可另找 Inside Rust 或作者源。 |
| 71 | [Python Insider](https://blog.python.org/) | “Python 3.15 beta”；“Python 3.14.6...” | Python 发布和治理公告为主。 |
| 72 | [Node.js Blog](https://nodejs.org/en/blog) | “Node.js 26.3.1”；“Security Releases” | 版本发布和安全公告为主。 |
| 74 | [Dan Luu](https://danluu.com/) | feed 解析失败；主页抽检多为 Patreon 链接 | 历史文章很强，但当前自动入口不稳定，不适合默认抓取；旧文适合人工精选。 |
| 76 | [Coding Horror](https://blog.codinghorror.com/) | “Rural Guaranteed Minimum Income”；“Thank You...” | 当前内容偏社会/个人/工程文化，不是具体技术文章。 |
| 77 | [Joel on Software](https://www.joelonsoftware.com/) | “Progress on the Block Protocol”；“HASH...” | 经典但当前入口偏产品/团队/历史内容，不适合自动精选。 |
| 78 | [Aphyr](https://aphyr.com/) | “More Fake Mastodon Signups”；podcast 条目 | 历史 Jepsen 文章极强，但当前 feed 多为非技术/播客/个人内容；建议手工精选旧文。 |
| 98 | [Chawye Hsu](https://chawyehsu.com/) | “虚幻勇士的记忆”；“独立游戏与原声带” | 当前入口混入回忆、游戏、工具推荐，技术密度不足。 |
| 99 | [Jimmy Song](https://jimmysong.io) | “Yin-Yang Layer”；“Five Elements Layer” | 当前样本偏概念模型、资料/书稿和方法论，不是具体技术文章。 |
| 102 | [Wener Live & Life](https://wener.me/) | “故事的重新开始”；“我记录思考的方式...” | 个人知识库/生活/笔记流混杂，自动源噪音高。 |
| 103 | [Afoo](https://afoo.me/) | “无法马上验证收益的投入”；“Token 经济学三原则” | 当前样本偏观点、AI 使用体验和管理思考，具体技术密度不足。 |
| 106 | [Innei](https://innei.in) | “第一次东京”；“当生活被 AI 占满...” | 虽有高质量前端文，但同一 feed 混入生活 notes；除非有 tech-only feed，否则删除。 |
| 107 | [Baiyun Blog](https://baiyun.me/) | “IPTV 内网融合教程”；“观影指南”；“住宅 IP 体验” | 消费/网络/个人工具教程混杂，不适合作为精选技术源。 |
| 123 | [NixOS Blog](https://nixos.org/blog/) | “NixOS 26.05 released”；“Framework Partnership...” | 当前配置是 announcements RSS，发布和基金会公告为主。 |
| 124 | [TypeScript Blog](https://devblogs.microsoft.com/typescript/) | “Announcing TypeScript 7.0 RC”；“Announcing TypeScript 6.0” | 当前入口几乎全是版本公告；若要 TS 深文，应另找编译器/设计作者源。 |
| 125 | [Spring Blog](https://spring.io/blog) | “This Week in Spring”；“Bootiful Podcast...” | 周报、播客、版本和框架生态更新混杂，删除。 |
| 126 | [Google Blog](https://blog.google/) | “Cannes Lions... YouTube”；“financial advertiser verification” | Google 综合官方博客过宽，产品、市场、社会议题混杂。 |

## 删除公司源替代复核

本节只复核“建议删除”列表里属于公司、厂商、基金会或产品组织的源。复核目标是避免把错误入口删掉之后遗漏真正的工程博客。例如 `Claude Code Releases` 是发布日志，不应作为文章源；更合适的候选是 [Claude Blog](https://claude.com/blog) 或已保留的 [Anthropic Engineering](https://www.anthropic.com/engineering)。

| 原删除源 | 公司/组织 | 找到的更合适入口 | 结论 |
| --- | --- | --- | --- |
| OpenAI News | OpenAI | [OpenAI Engineering](https://openai.com/news/engineering/)、[OpenAI Developer Blog](https://developers.openai.com/blog) | 建议替换为更窄入口，但当前本地抓取返回 403，需要先验证 crawler 能否访问；不要继续用 `openai.com/news/rss.xml` 总新闻源。 |
| Anthropic News、Claude Code Releases | Anthropic / Claude | [Claude Blog](https://claude.com/blog)、[Anthropic Engineering](https://www.anthropic.com/engineering) | 建议删除 news/releases；新增 Claude Blog 作为 listing 候选，重点抓 `Claude Code`、`Agents`、`Enterprise AI` 类文章；Anthropic Engineering 已保留。 |
| AWS News Blog、AWS Architecture Blog、AWS Machine Learning Blog | Amazon / AWS | [Amazon Builders' Library](https://aws.amazon.com/builders-library/)、[Amazon Science](https://www.amazon.science/) | 建议用 Builders' Library 替代 AWS 新闻/方案博客；Amazon Science 已保留。AWS Architecture/ML 仍不建议直接加入，产品方案味道太重。 |
| Microsoft Developer Blogs、Azure Blog | Microsoft | [Engineering@Microsoft](https://devblogs.microsoft.com/engineering-at-microsoft/)；RSS: [Engineering@Microsoft Feed](https://devblogs.microsoft.com/engineering-at-microsoft/feed/)；[Microsoft Research Blog](https://www.microsoft.com/en-us/research/blog/) | 建议新增 Engineering@Microsoft；Microsoft Research 已保留。不要用 DevBlogs 总入口或 Azure 总博客。 |
| Apple Developer News | Apple | [Apple Machine Learning Research](https://machinelearning.apple.com/research/)；RSS: [Apple ML RSS](https://machinelearning.apple.com/rss.xml) | 建议新增 Apple ML Research。Apple Developer News 仍删除；WebKit Blog 已保留。 |
| Stripe Engineering | Stripe | [Stripe Engineering](https://stripe.com/blog/engineering) | 原配置的 RSS 抓到 Stripe 全站商业/产品内容；建议保留页面入口但改成 listing 抓取工程栏目，不使用 `https://stripe.com/blog/feed.rss`。 |
| Heroku Blog | Heroku / Salesforce | [Heroku Engineering category](https://www.heroku.com/blog/category/engineering/)、[Heroku Engineering Feed](https://www.heroku.com/blog/category/engineering/feed/) | 有工程分类，但抽检仍混入 Heroku 平台更新、集成和产品文章；暂不建议加入默认源。 |
| Datadog Blog | Datadog | [Datadog Engineering](https://www.datadoghq.com/blog/engineering/)、[Datadog Engineering RSS](https://www.datadoghq.com/blog/engineering/index.xml) | 建议用 Engineering 分类替换总博客；抽检样本包含迁移、恶意代码检测、PostgreSQL 高可用等工程文章。 |
| HashiCorp Blog | HashiCorp | [HashiCorp engineering tag](https://www.hashicorp.com/blog/tags/engineering) | 找到工程标签，但本地访问返回 429/Vercel checkpoint；暂不加入，除非后续能稳定抓取。 |
| Grafana Blog | Grafana Labs | 未找到足够稳定的独立工程博客入口 | 继续删除。Grafana 总博客产品、活动、发布内容太多。 |
| Elastic Blog | Elastic | [Elastic Security Labs](https://www.elastic.co/security-labs)、[Elastic Search Labs](https://www.elastic.co/search-labs/blog) | 建议不要恢复 Elastic 总博客；可新增 Security Labs / Search Labs 两个更窄 listing 源。 |
| Red Hat Developer Blog | Red Hat | [Red Hat Research Blog](https://research.redhat.com/blog/)、[Red Hat Research Feed](https://research.redhat.com/feed/) | 建议用 Red Hat Research 替代 Developer Blog；Developer Blog 仍删除。 |
| Supabase Blog | Supabase | [Supabase Engineering](https://supabase.com/blog/categories/engineering) | 建议改用 engineering category listing；抽检样本包含 OrioleDB、pgvector、Postgres bloat 等技术内容。 |
| Sentry Blog | Sentry | [Sentry Engineering](https://blog.sentry.io/engineering/) | 建议作为 listing 候选；页面存在工程分类，但 RSS 仍是全站 feed，不能直接用原 RSS。 |
| Confluent Blog | Confluent | 未找到可稳定过滤的工程博客；`/blog/tag/engineering/` 和 `/blog/tag/kafka-internals/` 返回总博客/404 | 继续删除。 |
| Docker Blog | Docker | 发现可能存在 engineering 分类，但本地访问多次连接被重置 | 暂不加入；先保持删除。 |
| DigitalOcean Blog | DigitalOcean | [DigitalOcean Engineering tag](https://www.digitalocean.com/blog/tags/engineering) | 有工程标签页，但页面仍处在 DigitalOcean 总博客体系内，抓取信噪比需二次验证；暂不作为默认源。 |
| Neon Blog | Neon | [Neon Engineering Blog](https://neon.com/blog/category/engineering) | 建议改用 engineering category listing，而不是 Neon 总博客 RSS。 |
| Prisma Blog | Prisma | 未确认稳定工程分类；`?tag=engineering` 不足以证明可过滤 | 继续删除。 |
| Pulumi Blog | Pulumi | [Pulumi engineering tag](https://www.pulumi.com/blog/tag/engineering/) | 建议作为候选源；样本包含分布式调度、Python 性能、CLI 性能等工程文章，但 RSS 仍是总博客，需要 listing 或标签过滤。 |
| Sourcegraph Blog | Sourcegraph | `?category=engineering` 仍返回总博客/产品 AI 内容 | 继续删除；除非后续找到真正独立的工程 feed。 |
| Dagster Blog | Dagster | 未找到工程标签，`/blog/tags/engineering` 返回 404 | 继续删除。 |
| dbt Labs Blog | dbt Labs | 未找到工程分类，`/blog/category/engineering` 返回 404 | 继续删除。 |
| Akamai Blog | Akamai | [Akamai Security Research](https://www.akamai.com/blog/security-research) | 不恢复 Akamai 总博客；可新增 Security Research listing 候选。 |
| GitHub Changelog | GitHub | [GitHub Engineering](https://github.blog/engineering/)、[GitHub Security Lab](https://github.blog/security/) | 不需要新增；两个更合适入口已保留。 |
| Auth0 Blog | Auth0 / Okta | [Auth0 Engineering](https://auth0.com/blog/engineering/) | 建议作为 listing 候选；样本包含 OpenFGA 算法、P99 自调优等，但 RSS 是全站 feed，不能直接用原 RSS。 |
| Cloudflare Radar Blog | Cloudflare | [Cloudflare Blog](https://blog.cloudflare.com/) 已保留 | 当前 Radar 配置与主 feed 重复，不新增；如果后续能验证独立 Radar RSS，再单独评估。 |
| Rust Blog、Python Insider、Node.js Blog、NixOS Blog、TypeScript Blog、Spring Blog | 语言/开源项目或厂商项目 | 未找到比当前配置更适合的公司工程博客入口；部分项目有内部/设计讨论入口但不是稳定精选文章源 | 继续删除这些公告型入口；后续应找作者博客、RFC、编译器团队文章或项目技术深文源。 |
| Google Blog | Google | [Google Research Blog](https://research.google/blog/)、[Google DeepMind Blog](https://deepmind.google/blog/) | Google DeepMind 已保留；Google Research 可作为候选，但本地访问 `research.google` 超时，需要后续验证可抓取性。Google 综合博客继续删除。 |

优先新增候选：Claude Blog、Amazon Builders' Library、Engineering@Microsoft、Apple Machine Learning Research、Datadog Engineering、Supabase Engineering、Neon Engineering、Elastic Security Labs/Search Labs、Red Hat Research、Pulumi Engineering、Akamai Security Research、Auth0 Engineering。  
需要 listing 抓取或标签过滤的候选不应直接套用原总博客 RSS，否则会重新引入产品、发布和营销内容。

## 后续建议

1. 先按本文档删除或禁用 52 个源，避免低信噪比内容进入发现阶段。
2. 对保留但有噪音的源增加评估器负面规则：发布日志、周报、活动、招聘、融资、客户案例、产品 GA、SDK 上新、价格/套餐、纯观点文章默认低分。
3. 对 PlanetScale、Stripe、Sentry、Supabase、Rust、TypeScript 这类“站点可能有好文章但当前入口不理想”的源，后续只在找到更窄的工程/研究/RFC/作者 feed 后再加入。
4. 对公司源新增时优先使用独立工程/研究/安全入口；没有 RSS 的页面用 listing 抓取，并用 URL 路径、页面标签或标题规则过滤，不要退回总博客 RSS。
