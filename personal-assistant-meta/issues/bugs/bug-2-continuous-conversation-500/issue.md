---
status: todo
related:
  - feature-session-checkpoint
---

# Bug 2: 连续会话触发 500 Internal Server Error

线上 Netlify 部署（`agentarts-personal-assistant.netlify.app`）在使用前端聊天界面连续对话时，`POST /invocations` 返回 **500 Internal Server Error**。直连 AgentArts Gateway 的 curl 测试正常。

## 现象

```
POST https://agentarts-personal-assistant.netlify.app/invocations 500 (Internal Server Error)
Uncaught (in promise) Error: Chat API error: 500
```

**复现条件**：
- ✅ 前端聊天界面：首条消息正常，第 2 条消息 → 500
- ❌ curl 直连 Gateway：连续多条均正常（`curl -N -X POST https://defaultgw-.../invocations`）

## 根因：Netlify Edge Function 的 Orphaned Connection 导致 Gateway 连接超限

### 故障链路

```
Time 1: 用户发消息 1
  Browser ──POST──▶ Edge Function ──fetch()──▶ Gateway ──SSE stream──▶ Container
                                                         ✅ 连接建立，SSE 数据流回

Time 2: 用户发消息 2（assistant-ui 先 abort 消息 1）
  abortController.abort()
  Browser ──断开──▶ Edge Function  (下游连接关闭)
  
  但是！Edge Function 到 Gateway 的 fetch() 连接仍然是活跃的：
  Edge Function ──SSE stream still open──▶ Gateway  ← ⚠️ ORPHANED
  
  Gateway 仍然持有这条 SSE 连接，占用一个 concurrency slot

Time 3: Edge Function 发消息 2
  Edge Function ──新 fetch()──▶ Gateway
  Gateway 检测：已有 1 条活跃 SSE 连接（orphaned）+ 新连接
  AgentArts Runtime 可能限制单容器并发流式连接数
  → Gateway 返回 500
```

### 为什么不走 Edge Function 时没问题

curl 直连 Gateway 时：
- 没有 `abortController` 机制
- 每条 curl 命令独立运行，前一条结束后才发下一条（或不同终端窗口）
- 不存在 "abort 旧连接 → 立即建立新连接" 的时序窗口
- → 永远不会产生 orphaned connection

### 涉及组件

| 组件 | 问题 | 严重度 |
|------|------|:------:|
| **invocations.ts (Edge Function)** | `fetch()` 未传 `signal`，browser abort 时上游 Gateway 连接不能随之关闭 → orphaned | 🔴 **ROOT CAUSE** |
| **invocations.ts (Edge Function)** | `body: request.body` (ReadableStream) 脆弱，丢 `Content-Length` | 🟡 Amplifier |
| `main.py:108-113` | `event_generator()` 无 try/except → 异常穿透到 Starlette → 500 | 🟡 Amplifier |
| `chat-adapter.ts` | `reader.releaseLock()` 在 abort 后有 TDZ bug（`ReferenceError`） | 🟢 混淆调试 |

---

## 修复方案

### Fix 1（🔴 核心修复）：Edge Function 透传 abort signal

**文件**: `netlify/edge-functions/invocations.ts`

```typescript
const response = await fetch(gatewayUrl, {
    method: "POST",
    headers: { ... },
    body: request.body,
    signal: request.signal,  // ← 关键：浏览器 abort → Gateway 连接也关闭
});
```

当浏览器 abort 消息 1 时，`request.signal` 触发 → Deno 的 `fetch()` 也会 abort → 上游 Gateway SSE 连接被干净关闭 → 不产生 orphaned connection。

### Fix 2（🟡 加固）：Buffer 请求体，避免 ReadableStream 问题

**文件**: `netlify/edge-functions/invocations.ts`

```typescript
// 先读取完整的请求体（对于聊天消息，body 很小，不会有内存问题）
const bodyText = await request.text();
const bodyBytes = new TextEncoder().encode(bodyText);

const response = await fetch(gatewayUrl, {
    method: "POST",
    headers: {
        "Content-Type": request.headers.get("content-type") || "application/json",
        "Accept": request.headers.get("accept") || "text/event-stream",
        "Authorization": `Bearer ${apiKey}`,
        "x-hw-agentarts-session-id": sessionId,
        "Content-Length": String(bodyBytes.length),  // ← 补上 Content-Length
    },
    body: bodyText,
    signal: request.signal,
});
```

优点：避免 ReadableStream passthrough 的潜在问题，保证 `Content-Length` header 正确。

### Fix 3（🟡 防御）：event_generator() 加 try/except

**文件**: `personal-assistant-service/app/main.py`

```python
async def event_generator():
    try:
        async for sse_data in handler.handle_stream(
            message=message, user_id=user_id,
        ):
            yield sse_data
    except Exception as e:
        logger.error(f"Stream generator error: {e}", exc_info=True)
        yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"
```

### Fix 4（🟢 客户端）：修复 chat-adapter.ts 的 reader TDZ bug

**文件**: `personal-assistant-client/src/lib/chat-adapter.ts`

```typescript
let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
try {
    const response = await fetch(...);
    if (!response.ok) throw new Error(...);
    reader = response.body?.getReader();
    if (!reader) throw new Error("No response body");
    // ... SSE reading ...
} finally {
    reader?.releaseLock();  // ← 安全：abort 后 reader 为 undefined
}
```

---

## 范围

### Phase 1 — 核心修复（解决 500）

- [fix] `invocations.ts`: `fetch()` 添加 `signal: request.signal`
- [fix] `invocations.ts`: Buffer 请求体 + 添加 `Content-Length`
- [fix] `main.py`: `event_generator()` 添加 try/except
- [fix] `chat-adapter.ts`: 修复 `reader.releaseLock()` TDZ

### Phase 2 — Session 治本（修复多轮对话）

> 注：Fix 1 解决的是 500 错误，但多轮对话仍然是"无状态"的——Agent 不记得前序消息。Phase 2 通过 LangGraph Checkpointer 解决此问题。

- [feat] `agent_handler.py`: 注入 `MemorySaver` checkpointer
- [feat] `agent_handler.py`: 传递 `config={"configurable": {"thread_id": ...}}`
- [feat] `main.py`: 透传 `session_id` 到 `handle_stream()`
- [feat] `invocations.ts`: 稳定 session ID（cookie 持久化替代每请求随机 UUID）

### 不涉及

- Token Bucket 限流器（DeepSeek API 无此瓶颈）
- MaaS Provider 配置
- OAuth 登录

---

## 验收标准

### AC1：连续 5 条消息无 500（核心）

- [ ] Netlify 前端连续发送 5 条消息（快速连续，触发 abort）
- [ ] 所有请求返回 200，SSE 流正常
- [ ] 无 500 Internal Server Error

### AC2：Abort 场景正常

- [ ] 发送消息 1，在 SSE 流进行中发送消息 2
- [ ] 消息 1 被正常 abort，消息 2 正常返回
- [ ] 浏览器 console 无异常（无 `ReferenceError: Cannot access 'reader' before initialization`）

### AC3：异常降级

- [ ] 模拟后端异常时，流式请求返回 SSE error 事件而非 500
- [ ] 全局 exception handler 覆盖未处理异常

### AC4：Session 内多轮上下文（Phase 2）

- [ ] 同一 session 内 Agent 能回忆前序对话

---

## 四问闸门（Four-Question Gate）

| 问题 | 答案 | 说明 |
|------|:----:|------|
| **Is it best practice?** | **Yes** | 透传 `AbortSignal` 是 Web API 标准实践，确保资源在不再需要时被释放（resource cleanup / Defense in Depth）。try/except 是基本防御性编程。`?.` optional chaining 是安全的空值处理方式。 |
| **Is it de facto standard?** | **Yes** | `fetch(url, { signal: request.signal })` 是 Deno/浏览器/Node.js 的标准用法，被 Next.js Edge Middleware、Cloudflare Workers 等平台广泛采用。 |
| **Is it conventional?** | **Yes** | 任何熟悉 Edge/Serverless 的开发者见到 SSE proxy 模式，第一反应就是需要透传 abort signal。这是标准的 proxy 实现模式。 |
| **Is it modern?** | **Yes** | `AbortSignal` / `AbortController` 是现代 Web API 标准（2019+），被所有主流运行时原生支持。Deno Deploy（Netlify Edge Function 底层）完全支持。 |

---

## 风险与缓解

| 风险 | 严重度 | 缓解措施 |
|------|:------:|----------|
| **`signal: request.signal` 在某些 Netlify 版本不支持** | 🟢 Low | Deno Deploy 原生支持。若遇兼容问题，回退方案：在 abort 时手动 `new AbortController()` + 维护连接映射表 |
| **Buffer body 增加延迟**（`await request.text()`） | 🟢 Low | 聊天消息 body 极小（<1KB），同步读取耗时 <1ms |
| **Gateway 并发限制仍被触发**（极端并发场景） | 🟡 Medium | Fix 1 清理 orphaned connection 是治本；若仍有问题需联系 AgentArts 确认限制配额 |
| **MemorySaver 重启丢失**（Phase 2） | 🟡 Medium | 短期可接受；提供 `SQLITE_DB_PATH` 切换 SqliteSaver |

---

## 受影响的架构文档

| 文档 | 更新内容 |
|------|----------|
| `architecture/backend_architecture.md` §3 | 增加 `event_generator()` try/except + exception handler |

---

## 依赖

- `feature-session-checkpoint/issue.md` — Phase 2 实现其核心内容

---

## 参考

- [MDN: AbortSignal](https://developer.mozilla.org/en-US/docs/Web/API/AbortSignal)
- [Deno Deploy: fetch with signal](https://docs.deno.com/deploy/api/runtime-fetch)
- `netlify/edge-functions/invocations.ts:27-36` — 当前 `fetch()` 缺少 `signal`
- `app/main.py:108-113` — `event_generator()` 缺少 try/except
- `src/lib/chat-adapter.ts:46-100` — `reader.releaseLock()` TDZ bug
- `local-thread-runtime-core.ts:308-310` — assistant-ui 的 abort 逻辑
