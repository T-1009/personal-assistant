---
status: backlog
---

# Epic 1: Agent 骨架搭建

本 Phase 搭建 Personal Assistant 的最小可运行骨架：FastAPI 应用 + LangGraph 编排 + MaaS 模型调用，能够在本地完成一轮对话。

---

## 背景

这是整个项目的起点。在本 Phase 结束时，你可以在终端里 `curl /invocations` 发一条消息，Agent 调用 MaaS 上的 DeepSeek-V4-Pro 推理并返回结果。不涉及 Memory、Identity、任何外部工具。

## 范围

- FastAPI 应用入口（`app/main.py`）
- Agent 处理逻辑（`app/agent_handler.py`）
- LangGraph 编排（`app/graph.py`）— agent → tools → finalize 的 StateGraph
- MaaS 模型连接（通过 `langchain-openai` 的 `ChatOpenAI`）
- `agentarts_config.yaml` 基础配置
- Dockerfile（ARM64）
- 本地开发环境验证

## 不涉及

- Memory 集成（Phase 2）
- 用户认证（Phase 3）
- 任何外部工具（Phase 4-6）
- 飞书 / OfficeClaw 渠道（仅 `/ping` + `/invocations`）
- 流式响应（SSE 放 Phase 3 或后续）

## 任务拆解

### 1.1 项目初始化

- [ ] 创建项目目录结构（`app/`、`app/tools/`）
- [ ] 创建 `requirements.txt`（fastapi、uvicorn、langgraph、langchain-openai、agentarts-sdk）
- [ ] 创建 `Dockerfile`（`FROM python:3.12-slim`、linux/arm64）
- [ ] 创建 `.agentarts_config.yaml` 基础配置
- [ ] 配置本地开发环境变量（MODEL_API_KEY、MODEL_NAME、MODEL_URL）

### 1.2 FastAPI 入口

- [ ] `app/main.py` — FastAPI 应用，`/ping` 返回 `{"status": "ok"}`
- [ ] `app/main.py` — `/invocations` 接受 JSON payload，调用 AgentHandler
- [ ] 本地 `uvicorn` 启动验证

### 1.3 Agent 处理逻辑

- [ ] `app/agent_handler.py` — AgentHandler 类
  - `handle(message, user_id, session_id)` → 非流式处理
  - 从 `graph.py` 导入编译好的 LangGraph app
  - 构造初始 State（messages + context）并调用 `graph.ainvoke()`

### 1.4 LangGraph 编排

- [ ] `app/graph.py` — StateGraph 定义
  - AgentState 类型（messages、query、context、response）
  - **agent_node**：注入 system prompt → 调 LLM → 判断是否有 tool_calls
  - **tools_node**：ToolNode（此时无工具，但结构先搭好）
  - **finalize_node**：提取最终响应，写入 AgentState
  - 条件边：有 tool_calls → tools，无 → finalize
  - 编译并导出 `graph` 对象
- [ ] system prompt 设计（角色定义 + 基本行为规范）

### 1.5 MaaS 模型连接

- [ ] 在 graph.py 中用 `ChatOpenAI` 连接 MaaS
  - base_url: `https://api.modelarts-maas.com/openai/v1`
  - model: 从 `MODEL_NAME` 环境变量读取
  - api_key: 从 `MODEL_API_KEY` 环境变量读取
- [ ] 验证 LLM 调用成功（本地对话返回合理结果）

### 1.6 验证

- [ ] `curl /ping` → 200
- [ ] `curl /invocations -d '{"message": "你好"}'` → 返回 Agent 响应
- [ ] 多轮对话不崩溃
- [ ] 容器内 `uvicorn` 启动正常

## 依赖

无。本 Phase 不依赖任何前置 Phase。

## 参考

- ADR-001: Python 3.12
- ADR-002: LangGraph
- ADR-004: FastAPI 替代 AgentArtsRuntimeApp
- ADR-005: MaaS 作为 LLM 推理平台
- `architecture/devops/local-development.md`
