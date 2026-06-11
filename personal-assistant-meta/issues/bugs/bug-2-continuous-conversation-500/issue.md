---
status: todo
related:
  - feature-session-checkpoint
---

# Bug 2: 连续会话触发 500 Internal Server Error

线上 Netlify 部署（`agentarts-personal-assistant.netlify.app`）在连续对话时，浏览器 `POST /invocations` 返回 **500 Internal Server Error**，导致多轮对话中断。

## 现象

```
POST https://agentarts-personal-assistant.netlify.app/invocations 500 (Internal Server Error)
Uncaught (in promise) Error: Chat API error: 500
```

复现规律：首条消息正常，第 2 条消息开始返回 500。

## 线上环境确认

| 项目 | 实际值 |
|------|--------|
| **LLM Provider** | DeepSeek 直连（未配置 `MAAS_API_KEY`，`llm_config.py` 的 auto-fallback 机制自动切换到 deepseek provider） |
| **Base URL** | `https://api.deepseek.com` |
| **Model** | `deepseek-chat` |
| **MaaS 3 RPM 限流** | **不适用**（DeepSeek API 数百 RPM，无此瓶颈） |
| **deepagents checkpointer** | `None`（默认值，无内置 MemorySaver） |
| **每轮 LLM 调用次数** | 1-2 次（一次主调用 + LangGraph agent loop 的二次 model iteration） |
| **请求间状态累积** | 无（无 checkpointer，每次 `astream_events` 为全新 StateBackend） |

> **⚠️ 前期分析纠正**：初始分析错误地将 MaaS 3 RPM 硬限流认定为主因，但线上实际使用 DeepSeek 直连 API，该假设不成立。

## 根因分析（待验证假说）

### 已知事实

1. **流式路径有错误捕获**：`handle_stream()` 的 `try/except Exception` 包裹整个 `astream_events` 调用，异常时应 yield SSE 错误事件（HTTP 200）
2. **500 说明错误穿透了这层 try/except**，或发生在更上层（Gateway/Starlette 层）
3. **首条成功、后续失败**：暗示存在某种跨请求的"副作用"，而非纯随机的瞬时故障
4. **Netlify Edge Function 每请求生成新 UUID**：`crypto.randomUUID()` → Gateway 每个请求都是新 session

### 待排查假说（按可能性排序）

#### 假说 A：AgentArts Gateway 的 Streaming 响应处理问题 🔴 可能性最高

```
请求 1: Edge Function → Gateway → 容器 → SSE stream 正常 → 200
请求 2: Edge Function → Gateway → 容器开始 SSE → Gateway 在流中间
        检测到某种异常（超时？连接断开？）→ remap 为 500
```

**排查方向**：
- 查看 AgentArts Gateway 日志，确认 500 是否由 Gateway 主动返回
- 确认 Gateway 对 SSE streaming 的超时配置
- 检查容器在第二个请求时是否仍然存活（`/ping` endpoint）

#### 假说 B：异常在 async generator 首个 yield 前抛出 🟡

虽然 `handle_stream` 有 `try/except`，但如果 `deepagents` 的 agent loop 在首次 `yield` 前抛出非 `Exception` 类型的错误（如 `asyncio.CancelledError`、`GeneratorExit`、或 LangGraph 的特定错误类型），`except Exception` 不会捕获。

另外，`event_generator()` 在 `main.py:108-113` **没有任何 try/except**——如果 `handle_stream` 以任何方式泄漏异常，会直接传播到 Starlette：

```python
async def event_generator():
    async for sse_data in handler.handle_stream(  # ← 无 try/except!
        message=message, user_id=user_id,
    ):
        yield sse_data
```

**排查方向**：
- 检查容器日志中是否有 unhandled exception traceback
- 确认 deepagents/LangGraph 是否可能抛出 `BaseException` 子类

#### 假说 C：容器在两次请求间状态异常 🟡

AgentArts Runtime 容器可能在某种条件下在请求间进入异常状态：
- 内存压力导致 OOM kill（第二个请求触发）
- 容器健康检查失败导致 Gateway 拒绝后续请求（但 `/ping` 仍可用？）
- 并发限制（AgentArts 可能限制单容器并发连接数）

**排查方向**：
- 容器内存/CPU 监控
- AgentArts Runtime 事件日志
- 两次请求之间 `/ping` 是否正常

#### 假说 D：deepagents/DeepSeek API 特定行为 🟢

某些 DeepSeek API 响应或 deepagents 中间件行为在第二次调用时触发不同代码路径：
- `SummarizationMiddleware` 在两次调用后 token count 跨越阈值？
- `AnthropicPromptCachingMiddleware` 在非 Anthropic 模型上有副作用？
- DeepSeek API 返回特殊响应导致 ChatOpenAI 解析异常？

**排查方向**：
- 比对第 1 次和第 2 次请求的请求体（是否包含额外上下文？）
- 抓取第 2 次请求时的完整 response body

---

## 排查行动计划

### Step 1：定位 500 来源（最高优先级）

```bash
# 1. 绕开 Netlify Edge Function，直连 Gateway 测试
curl -N -X POST \
  "https://defaultgw-ha3wenzqga.cn-southwest-2.huaweicloud-agentarts.com/runtimes/personal-assistant/invocations" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -H "Authorization: Bearer <api-key>" \
  -H "x-hw-agentarts-session-id: test-session-001" \
  -d '{"message":"你好","stream":true}'

# 2. 同一 session ID 发第二条消息（模拟连续会话）
curl -N -X POST \
  "https://defaultgw-ha3wenzqga.../runtimes/personal-assistant/invocations" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -H "Authorization: Bearer <api-key>" \
  -H "x-hw-agentarts-session-id: test-session-001" \
  -d '{"message":"我刚才说了什么？","stream":true}'
```

### Step 2：查看容器日志

- AgentArts Console → Runtime → personal-assistant → Logs
- 查找关键词：`ERROR`、`Traceback`、`exception`、`500`
- 确认每次请求是否有对应的 uvicorn access log

### Step 3：确认 DeepSeek API 可达性

```bash
curl https://api.deepseek.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
  -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"hi"}]}'
```

---

## 防御性修复（无论根因如何，都应实施）

以下修复不依赖根因确认，属于生产系统应有的防御能力：

### 修复 1：为 event_generator() 添加 try/except（`app/main.py`）

```python
async def event_generator():
    try:
        async for sse_data in handler.handle_stream(
            message=message, user_id=user_id, session_id=session_id
        ):
            yield sse_data
    except Exception as e:
        logger.error(f"Stream generator error: {e}", exc_info=True)
        yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"
```

### 修复 2：添加全局 Exception Handler（`app/main.py`）

```python
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )
```

### 修复 3：传递 session_id 到 handle_stream + agent config（`app/agent_handler.py`）

```python
async def handle_stream(self, message, user_id="anonymous", session_id=None):
    thread_id = f"{user_id}:{session_id}" if session_id else f"anonymous:{uuid.uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}
    try:
        async for event in self.agent.astream_events(
            {"messages": [{"role": "user", "content": message}]},
            version="v2",
            config=config,  # ← 至少传入 config，即便暂不启用 checkpoint
        ):
            ...
```

### 修复 4：注入 MemorySaver checkpointer（`app/agent_handler.py`）

按 `feature-session-checkpoint/issue.md` 设计，传入 `checkpointer=MemorySaver()` 启用真正的 session 内多轮上下文：

```python
from langgraph.checkpoint.memory import MemorySaver

self.agent = create_deep_agent(
    model=self.model,
    system_prompt=SYSTEM_PROMPT,
    tools=[],
    checkpointer=MemorySaver(),  # ← 启用 session 隔离
)
```

---

## 范围

### Phase 1 — 防御性加固（无论根因如何都做）

- [fix] `app/main.py`: `event_generator()` 添加 try/except
- [fix] `app/main.py`: 注册全局 `@app.exception_handler(Exception)`
- [fix] `app/agent_handler.py`: `handle_stream()` 签名添加 `session_id` 参数
- [fix] `app/main.py`: 流式路由中透传 `session_id` 到 `handle_stream()`
- [fix] `app/agent_handler.py`: agent 调用中传入 `config={"configurable": {"thread_id": ...}}`

### Phase 2 — Session 治本（修复多轮对话）

- [feat] `app/agent_handler.py`: 注入 `MemorySaver` checkpointer
- [feat] `personal-assistant-client/netlify/edge-functions/invocations.ts`: 稳定 session ID（cookie 持久化）

### 不涉及

- Token Bucket 限流器（DeepSeek API 无 3 RPM 瓶颈，不需要）
- MaaS Provider 相关改动
- OAuth 登录（Feature 4）
- PostgresSaver 生产持久化（后续独立 issue）

---

## 验收标准

### AC1：连续 5 条消息无 500 错误

- [ ] 在 Netlify 部署环境连续发送 5 条消息
- [ ] 所有请求返回 200（流式正常）
- [ ] 无 500 Internal Server Error

### AC2：异常降级为 SSE 错误事件

- [ ] 模拟 LLM API 故障时，流式请求返回 SSE error 而非 500
- [ ] error 包含可读的错误描述

### AC3：全局 Exception Handler 覆盖

- [ ] 模拟 handler 抛出未知异常 → 返回 `{"error": "Internal server error", "detail": "..."}`
- [ ] 服务端日志完整记录 traceback

### AC4：Session 内多轮上下文保持（Phase 2）

- [ ] 同一 session ID，第 1 轮设定事实，第 2 轮 Agent 能回忆前序对话

---

## 四问闸门（Four-Question Gate）

| 问题 | 答案 | 说明 |
|------|:----:|------|
| **Is it best practice?** | **Yes** | 全局 exception handler + async generator try/except 是 Defense in Depth 的基础实践。LangGraph Checkpointer 将状态存储与 Agent 逻辑解耦（Separation of Concerns）。 |
| **Is it de facto standard?** | **Yes** | FastAPI 官方文档推荐 `@app.exception_handler(Exception)`。LangGraph Checkpointer + `thread_id` 是 LangChain 生产部署的标准模式。 |
| **Is it conventional?** | **Yes** | 任何 FastAPI 开发者都预期有全局错误处理。任何 LangGraph 开发者都预期通过 `thread_id` 管理会话。 |
| **Is it modern?** | **Yes** | LangGraph 1.0+ 将 Checkpoint 作为一等公民。deepagents 0.6.8 (2026-06) 为当前最新封装。异步生成器的 try/except 防护是 async Python 的成熟模式。 |

---

## 风险与缓解

| 风险 | 严重度 | 缓解措施 |
|------|:------:|----------|
| **修复 1-3 不完全解决 500**：根因在 Gateway/容器层 | 🟡 Medium | Step 1-3 排查行动确认根因后再针对性修复 |
| **MemorySaver 重启丢失所有 session** | 🟡 Medium | 短期可接受。提供 `SQLITE_DB_PATH` 切换 SqliteSaver |
| **同一 session 并发 checkpoint 写冲突** | 🟡 Medium | AgentHandler 按 `thread_id` 加 `asyncio.Lock` |
| **Global exception handler 遮蔽可操作错误** | 🟡 Medium | 返回前完整记录 traceback；AgentArts 可观测性捕获 |

---

## 受影响的架构文档

| 文档 | 更新内容 |
|------|----------|
| `architecture/backend_architecture.md` §3 | 增加 exception handler + Checkpointer + config 传递说明 |

---

## 依赖

- `feature-session-checkpoint/issue.md` — Phase 2 实现其核心内容
- `app/agent_handler.py` + `app/main.py` — 修改目标文件

---

## 参考

- `config.yaml` — 线上 fallback 到 deepseek provider（非 MaaS）
- `app/llm_config.py:87-99` — auto-fallback 机制
- `feature-session-checkpoint/issue.md` — LangGraph Checkpointer 集成设计
- `app/main.py:108-113` — `event_generator()` 缺少 try/except
- `app/agent_handler.py:65-85` — `handle_stream()` 有 try/except 但缺 session_id 参数
- deepagents 0.6.8 源码：`checkpointer: Checkporter \| None = None`（`.venv/.../deepagents/graph.py:250`）
- [LangGraph Persistence Docs](https://langchain-ai.github.io/langgraph/how-tos/persistence/)
