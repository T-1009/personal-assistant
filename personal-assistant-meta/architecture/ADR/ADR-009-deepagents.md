# ADR-009: deepagents 替代 LangGraph 裸用

> 状态：Accepted | 日期：2026-06-05

---

## 背景

ADR-002 决定使用 LangGraph 作为 Agent 编排框架，在其上直接定义 StateGraph（agent → tools → agent → finalize）。该方案可行但需要手写约 50-100 行图编排样板代码。

LangChain 推出了 [deepagents](https://github.com/langchain-ai/deepagents)，一个基于 LangGraph 的 "batteries-included agent harness"——它封装了标准 ReAct loop，附带 conversation summarization、planning tool、skills 系统等预置能力。底层就是 LangGraph，API 兼容。

核心问题：**从零开始写 LangGraph 样板 vs 用 deepagents 封装，选哪个？**

## 决策

**使用 deepagents 替代裸写 LangGraph StateGraph。**

选择依据：

| 因素 | 裸写 LangGraph | deepagents |
|------|---------------|-----------|
| **底层** | LangGraph StateGraph | LangGraph StateGraph（完全一致） |
| **代码量** | ~50-100 行 graph.py 样板 | `create_deep_agent(model=..., tools=..., system_prompt=...)` |
| **Identity SDK 兼容** | 工具照常注册到 ToolNode | 工具照常传给 `tools=` 参数 |
| **conversation summarization** | 需要自己实现 | 内置 compact_conversation |
| **skills 系统** | 无 | SKILL.md 文件驱动，按需加载 |
| **planning tool** | 无（手写 system prompt） | 内置 write_todos，可关闭 |
| **sub-agents** | 需要自己实现 | 内置 task tool（本项目不需要，不碍事） |
| **依赖体积** | langgraph + langchain-core | deepagents（依赖 langgraph + langchain-core） |
| **版本稳定性** | LangGraph 稳定版 | deepagents 0.6.8，API 趋于稳定 |

## 拒绝的方案

### 裸写 LangGraph StateGraph（原方案）

- 可行，且 ADR-002 的分析仍然成立
- 但 deepagents 就是 LangGraph 的封装，不引入额外风险——底层完全一致，工具注册方式不变
- deepagents 节省样板代码，附赠 summarization/skills，用不上也不碍事
- **拒绝理由：无意义的样板代码不写，deepagents 提供了同质替代**

### CrewAI / AutoGen

- 已在 ADR-002 中拒绝，理由不变

## 影响

- `requirements.txt` 增加 `deepagents`（替代 `langgraph`，后者作为传递依赖仍在）
- 不再需要 `app/graph.py`（StateGraph 定义被 `create_deep_agent()` 替代）
- `app/agent_handler.py` 中直接调 `create_deep_agent()` 创建 agent，调 `.invoke()` / `.astream()` 执行
- `app/tools/` 目录不变，工具函数直接传给 deepagents 的 `tools=` 参数
- ADR-002 状态改为 Superseded
- 根 `AGENTS.md` 中的技术选型表需更新
- 架构文档中 "LangGraph 编排" 替换为 "deepagents 编排"

## 参考

- [deepagents 文档](https://docs.langchain.com/oss/python/deepagents/overview)
- [deepagents GitHub](https://github.com/langchain-ai/deepagents)
- [deepagents PyPI](https://pypi.org/project/deepagents/) (v0.6.8)
- ADR-002: LangGraph 作为 Agent 编排框架（Superseded）
