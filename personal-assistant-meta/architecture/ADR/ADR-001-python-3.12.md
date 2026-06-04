# ADR-001: Python 3.12 作为运行时

> 状态：Accepted | 日期：2026-06-03

---

## 背景

Personal Assistant 项目需要选择一个 Python 版本作为容器基础镜像和本地开发环境。候选版本：Python 3.10、3.11、3.12。

Python 3.10 的 EOL（End of Life）是 **2026 年 10 月**，距今不足 5 个月。新项目不应从即将终止支持的版本起步。

## 决策

**使用 Python 3.12。**

选择依据：

| 因素 | Python 3.10 | Python 3.12 |
|------|-------------|-------------|
| **EOL** | 2026-10 | 2028-10 |
| **性能** | 基准 | CPython 3.11+ 提速 10-60%（Faster CPython），3.12 进一步优化 |
| **asyncio** | 基础支持 | TaskGroup、改进的异常处理、更低的调度延迟 |
| **类型系统** | PEP 604 (`X \| Y`) | 新增 PEP 695（类型形参语法 `type X[T]`），更好的泛型支持 |
| **生态兼容** | ✅ | ✅ FastAPI、LangGraph、httpx、langchain 均完整支持 |
| **AgentArts** | 平台最低要求 ≥3.10 | 满足（3.12 ≥ 3.10） |

## 拒绝的方案

### Python 3.10

- 即将 EOL，不符合"新项目用 LTS 版本"的原则
- 无法享受 3.11/3.12 的性能提升（对 LLM Agent 场景中的 I/O 密集任务有实质帮助）

### Python 3.11

- 性能提升显著（Faster CPython 首版），但中间版本
- 3.12 相比 3.11 新增了 TaskGroup、更好的异常组支持，对异步 Agent 代码质量有帮助

### Python 3.13

- 太新（2024-10 发布），部分依赖可能未完全适配
- AgentArts 平台未声明 3.13 兼容性

## 影响

- `agentarts_config.yaml` 中 `base_image` 从 `python:3.10-slim` 改为 `python:3.12-slim`
- `Dockerfile` 基础镜像同步更新
- 本地开发环境建议使用 Python 3.12
- 可以利用 `asyncio.TaskGroup` 实现更健壮的并发工具调用

## 参考

- [Python 3.12 发布说明](https://docs.python.org/3.12/whatsnew/3.12.html)
- [PEP 695 — Type Parameter Syntax](https://peps.python.org/pep-0695/)
- AgentArts 平台要求 Python ≥3.10
