# ADR-010: Astral 生态工具链（uv + ruff）

> 状态：Accepted | 日期：2026-06-05

---

## 背景

personal-assistant-service 即将进入编码阶段。项目需要确定 Python 开发工具链：包管理器、虚拟环境管理、linting 和 formatting。传统方案（pip + virtualenv + flake8 + black + isort）功能完备但工具分散、配置零散、速度较慢。近年 [Astral](https://astral.sh/) 推出的 **uv** 和 **ruff** 已成为 Python 社区快速收敛的标准工具链——Rust 实现，速度提升 10-100 倍，且作为单一工具覆盖多个传统工具的职责。

核心问题：**用传统工具链各自独立管理，还是统一迁移到 Astral 生态？**

## 决策

**全面采用 Astral 生态：uv 管理包和虚拟环境，ruff 负责 linting 和 formatting。**

选择依据：

| 因素 | uv + ruff (Astral) | pip + venv + flake8 + black + isort (传统) |
|------|---------------------|------------------------------------------|
| **速度** | Rust 实现，resolve 和 install 比 pip 快 10-100 倍；ruff lint 比 flake8 快 10-50 倍 | Python 实现，依赖解析慢，大量文件时 lint 等待明显 |
| **单一工具覆盖** | uv 替代 pip/pip-tools/virtualenv/pipx；ruff 替代 flake8/black/isort/pyflakes/pydocstyle | 至少 5 个工具，各自独立配置（setup.cfg / .flake8 / pyproject.toml 多处分散） |
| **锁文件** | `uv.lock` 原生支持确定性构建，跨平台 resolution | `pip freeze > requirements.txt` 无跨平台确定性，需 pip-tools 补充 |
| **Python 版本管理** | `uv python install 3.12` 内置下载管理 | 需额外 pyenv 或手动管理 |
| **生态兼容** | 完整兼容 PyPI，可读 requirements.txt / pyproject.toml；ruff 兼容 flake8 插件生态（规则映射） | 传统生态，无需迁移学习 |
| **VS Code 集成** | ruff 官方扩展成熟，uv 通过终端使用 | 各工具均有扩展但零散 |
| **社区 momentum** | uv 月下载量超 2000 万，ruff 超 1 亿；Anthropic、OpenAI、LangChain 等主流项目已迁移 | 稳定但增长停滞，新项目越来越少选择传统组合 |
| **维护方** | Astral（Charlie Marsh 团队），专注 Python 工具链，商业支持（ruff 有 VSCode 付费扩展） | 社区维护，black 长期无新功能，flake8 缓慢 |

### uv 具体使用方式

```bash
# 不再使用 pip install -r requirements.txt + source venv/bin/activate
# 项目根目录 pyproject.toml 声明依赖

uv sync                          # 自动创建 .venv + 安装依赖
uv add deepagents                # 添加依赖并写入 pyproject.toml + uv.lock
uv run uvicorn app.main:app      # 直接用项目 venv 运行命令
uv lock                          # 锁定依赖版本
```

### ruff 具体使用方式

```toml
# pyproject.toml 中统一配置
[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM"]
# E/F = pyflakes + pycodestyle
# I = isort
# N = pep8-naming
# UP = pyupgrade
# B = flake8-bugbear
# C4 = flake8-comprehensions
# SIM = flake8-simplify

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

```bash
ruff check .          # lint
ruff check --fix .    # lint + auto-fix
ruff format .         # format (替代 black)
```

## 拒绝的方案

### pip + virtualenv + flake8 + black + isort（传统组合）

- 功能完备，可工作
- **拒绝理由**：工具分散（至少 5 个独立工具），配置分散（setup.cfg / .flake8 / pyproject.toml），lint 大项目速度慢，pip 无 lockfile 支持。uv + ruff 是同质替代，零功能损失，大幅提升 DX 和速度

### Poetry

- 比 pip 更好的依赖管理和 lockfile，早于 uv 出现
- **拒绝理由**：uv 出现后 Poetry 的优势被追平甚至超越（速度、PEP 621 兼容、Python 版本管理）。Astral 生态 momentum 更强，uv + ruff 是同一个团队维护的互补工具，无须引入第三方生态

### PDM

- PEP 621 兼容，类似 Poetry
- **拒绝理由**：同上，uv 在速度、社区 momentum 上全面领先。且 PDM 不与 ruff 同生态

## 影响

- 项目不再使用 `requirements.txt`，改为 `pyproject.toml` 中的 `[project.dependencies]` + `uv.lock`
- `agentarts_config.yaml` 中 build command 需调整：从 `pip install -r requirements.txt` 改为 `uv sync --frozen`
- Dockerfile 基础镜像需预装 uv（官方提供 `ghcr.io/astral-sh/uv:python3.12-bookworm` 或通过 curl 安装）
- 本地开发环境安装 uv 和 ruff：`brew install uv ruff`（macOS）/ `pip install uv ruff`
- 后端架构文档 `backend_architecture.md` 中项目结构示例需更新：`requirements.txt` → `pyproject.toml`，增加 `uv.lock`
- CI/CD pipeline 中 lint 步骤改为 `ruff check . && ruff format --check .`
- `.vscode/settings.json` 推荐配置：ruff 作为默认 formatter，formatOnSave
- 项目根 AGENTS.md 中技术栈表需增加此行

## 参考

- [uv 官方文档](https://docs.astral.sh/uv/)
- [ruff 官方文档](https://docs.astral.sh/ruff/)
- [Astral 公司](https://astral.sh/)
- [uv: Python packaging in Rust](https://astral.sh/blog/uv)
- ADR-001: Python 3.12 作为运行时（uv 内置 Python 版本管理与 3.12 配合）
- ADR-009: deepagents 替代 LangGraph 裸用（uv 管理的依赖之一）
