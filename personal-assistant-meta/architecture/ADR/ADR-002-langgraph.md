# ADR-002: LangGraph 作为 Agent 编排框架

> 状态：Superseded by [ADR-009](ADR-009-deepagents.md) | 日期：2026-06-03

---

## 背景

Personal Assistant Agent 需要实现以下编排模式：

```
agent（LLM 推理）→ tools（工具调用）→ agent → ... → finalize（返回）
```

这是一个标准的 ReAct 循环（Reasoning + Acting），有两种实现路径：

1. **手写 ReAct loop**：用纯 Python 控制流实现，零额外依赖
2. **框架方案**：LangGraph、CrewAI、AutoGen 等

## 决策

**使用 LangGraph (Python)。**

选择依据：

| 因素 | 手写 Loop | LangGraph |
|------|-----------|-----------|
| **复杂度匹配** | 当前场景完全够用 | 支持未来扩展到多分支、条件路由 |
| **可观测性** | 需要自建 Trace/Log | 内置节点级 Tracing、状态快照 |
| **状态管理** | 手动管理 messages 列表 | StateGraph + Checkpointer，支持中断恢复 |
| **行业认知度** | — | LangChain 生态的核心组件，简历价值高 |
| **华为云生态** | — | AgentArts SDK 与 LangGraph 有官方集成示例 |
| **学习成本** | 零 | 中等（StateGraph、Checkpointer、ConditionalEdge） |
| **依赖体积** | 零 | langgraph + langchain-core，约 50MB |

## 拒绝的方案

### 手写 ReAct Loop

- 简单场景下完全可行，代码更清晰
- 但本项目目标之一是**展示 Agent 工程能力**，LangGraph 是业界主流方案，使用它本身是合理的技术展示
- 当未来需要 Human-in-the-loop、条件路由、多 Agent 协作时，手写 loop 的维护成本会急剧上升

### CrewAI / AutoGen

- 面向多 Agent 协作场景，当前不需要
- 概念模型（Agent / Task / Crew）与我们的简单编排模式不匹配

## 影响

- 项目依赖增加 `langgraph` 和 `langchain-core`
- 需要在 `graph.py` 中定义 StateGraph 结构（agent → tools → agent → finalize）
- 初期仅使用基础能力（StateGraph + ToolNode），暂不引入 Checkpointer（持久化状态）和 Human-in-the-loop

## 参考

- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
- AgentArts SDK 中的 LangGraph 集成示例
