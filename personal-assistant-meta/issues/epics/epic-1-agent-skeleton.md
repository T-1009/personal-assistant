---
status: backlog
---

# Epic 1: Agent 骨架 + 飞书渠道

本 Phase 搭建 Personal Assistant 的最小可运行骨架并接入飞书渠道。完成后可在飞书客户端 @Bot 完成一轮对话。

---

## 背景

飞书是企业内部最高频的 IM 工具，接入成本低（无需写前端 UI），是验证 Agent 能力的最佳第一个渠道。飞书消息走 Webhook 回调到后端，`/feishu/webhook` 解析消息 → Agent 处理 → 调飞书 API 回复。不需要 Google OAuth、不需要 SSE、不需要前端页面。

## 范围

- FastAPI 应用入口（`app/main.py`）+ `/ping`、`/invocations`、`/feishu/webhook`
- `app/feishu_adapter.py` — 飞书消息解析 + URL 验证 + 回复
- Agent 处理逻辑（`app/agent_handler.py`）
- LangGraph 编排（`app/graph.py`）— agent → tools → finalize
- MaaS 模型连接
- `agentarts_config.yaml` 基础配置
- Dockerfile（ARM64）
- 飞书 Bot 创建 + 配置

## 不涉及

- Memory 集成（Epic 2）
- OfficeClaw（Epic 3）
- 用户认证 / OAuth（Epic 4）
- Web Chat / SSE 流式（Epic 5）
- 任何外部工具（Epic 6-8）

## 任务拆解

### 1.1 项目初始化

- [ ] 创建项目目录结构
- [ ] `requirements.txt`（fastapi、uvicorn、langgraph、langchain-openai、agentarts-sdk、httpx）
- [ ] `Dockerfile`（`FROM python:3.12-slim`、linux/arm64）
- [ ] `.agentarts_config.yaml` 基础配置
- [ ] 本地开发环境变量

### 1.2 FastAPI 入口

- [ ] `app/main.py` — FastAPI 应用
  - `GET /ping` → `{"status": "ok"}`
  - `POST /invocations` → 调 AgentHandler
  - `POST /feishu/webhook` → URL 验证 + 消息处理

### 1.3 飞书适配器

- [ ] `app/feishu_adapter.py`
  - `handle_feishu_webhook(body)` → 解析飞书事件
  - URL 验证（Challenge 模式）：返回 challenge 字段
  - 消息解析：提取消息文本 + user_id + chat_id
  - 消息回复：调飞书发送消息 API

### 1.4 Agent 处理逻辑

- [ ] `app/agent_handler.py` — AgentHandler 类
  - `handle(message, user_id, session_id)` → 非流式处理
  - 构造初始 State + 调 graph.ainvoke()
  - 飞书渠道无需流式（普通文本回复即可）

### 1.5 LangGraph 编排

- [ ] `app/graph.py`
  - AgentState 类型（messages、query、context、response）
  - agent_node：system prompt → LLM 推理 → 判断 tool_calls
  - tools_node：ToolNode（此时无工具，结构先搭好）
  - finalize_node：提取最终响应
  - 条件边：有 tool_calls → tools，无 → finalize
- [ ] system prompt 设计（角色定义 + 基本行为规范）

### 1.6 MaaS 模型连接

- [ ] `ChatOpenAI` 连接 MaaS
  - base_url: `https://api.modelarts-maas.com/openai/v1`
  - model: 环境变量 `MODEL_NAME`
- [ ] 验证 LLM 调用成功

### 1.7 飞书 Bot 创建

- [ ] 飞书开放平台创建自建应用
- [ ] 配置事件订阅：`/feishu/webhook` 作为回调 URL
- [ ] 配置 Bot 权限（获取消息、发送消息）
- [ ] 发布应用

### 1.8 验证

- [ ] `curl /ping` → 200
- [ ] `curl /invocations -d '{"message":"你好"}'` → Agent 响应
- [ ] 飞书 @Bot "你好" → Agent 在飞书回复
- [ ] 多轮对话不崩溃

## 依赖

无。

## 参考

- ADR-001: Python 3.12
- ADR-002: LangGraph
- ADR-004: FastAPI
- ADR-005: MaaS
- `architecture/frontend_architecture.md` #2.2 飞书直连
- `architecture/devops/local-development.md`
