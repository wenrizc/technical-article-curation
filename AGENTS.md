# Repository Guidelines

## 项目结构与模块划分

核心代码位于 `src/tac/`，FastAPI 入口是 `src/tac/main.py`。代码按分层目录组织：`web/` 放 HTTP 路由、依赖、安全中间件和静态管理页；`application/` 放后台任务、流水线编排和各阶段 use case；`domain/` 放 Pydantic 模型和枚举；`infrastructure/` 放 SQLite、信源 YAML 等外部资源适配；`shared/` 放通用工具。默认源配置在 `config/sources.yaml`，数据库迁移脚本在 `migrations/`，评估提示词在 `prompts/<locale>/`，设计文档在 `docs/`。测试代码集中在 `tests/`，离线夹具放在 `tests/fixtures/`。

## 构建、测试与开发命令

本项目使用 `uv` 管理环境与执行命令：

```powershell
uv sync --extra test
uv run uvicorn tac.main:app --host 127.0.0.1 --port 1104 --reload
uv run ruff check .
uv run ruff format .
uv run pytest
```

`uv sync --extra test` 用于安装运行、测试和开发检查依赖。`uv run uvicorn tac.main:app --host 127.0.0.1 --port 1104 --reload` 启动本地 FastAPI 服务，应用默认在启动时执行 SQLite 迁移，流水线阶段通过管理页或 `/api/admin/jobs/*` 后台任务触发。`uv run ruff check .` 运行静态检查，`uv run ruff format .` 统一格式化代码。`uv run pytest` 运行全部离线测试。

## 编码风格与命名约定

项目目标版本为 Python 3.11+，整体风格参考 Google Python Style Guide，并以 `ruff` / `ruff format` 的结果为提交前基线。保持明确类型标注、标准库/第三方/本地导入分组，以及与现有 Pydantic 数据模型一致的写法。统一使用 4 个空格缩进；模块名、函数名、变量名使用 `snake_case`，类名使用 `PascalCase`，常量使用 `UPPER_CASE`，例如 `Settings` 和 `RSS_HEADERS`。

函数命名应直接反映流水线行为，避免过度抽象。新增公共函数、复杂函数或非显而易见的分支应补充 Google 风格 docstring；短小私有 helper 可在语义清晰时省略。所有解释性代码注释必须使用中文，且只说明“为什么”或关键业务约束，不重复代码本身。注释示例：

```python
# 评估失败不能写入 fetches，否则会把模型错误误判为抓取失败。
```

## 测试规范

测试框架为 `pytest`，`pyproject.toml` 已配置 `tests/` 和 `src/` 路径。测试文件命名使用 `test_<area>.py`，例如 `test_fetch.py`、`test_e2e.py`。新增功能应优先补充基于 `tests/fixtures/` 的确定性离线测试，不要依赖真实网络请求或真实 AI 返回。

## 提交与 Pull Request 规范

Git 提交历史采用 Conventional Commits 风格，当前常见前缀包括 `feat:`、`docs:`、`test:`。请沿用这一格式，标题应具体，例如 `feat: add localized prompt fallback`。PR 需要说明行为变化、配置项或数据库结构影响；若改动影响发布结果、评估输出或 CLI 行为，建议附上示例命令和关键输出路径。

## 配置与数据注意事项

运行时配置主要来自环境变量，例如 `OPENAI_API_KEY`、`TAC_MODEL`、`TAC_STATE_DB`、`TAC_PUBLIC_DIR`。不要提交本地数据库、生成的 `public/` 内容或任何密钥。如果新增配置项，请同步更新 `README.md`，并为默认行为补充测试覆盖。
