# refactor-email-auth-normal-control-flow

## 动机

当前 `email_tools.py` 使用 **exceptional control flow**（异常控制流）处理 OAuth2 鉴权 URL 的呈现：

1. `handle_auth_url` 回调抛出 `AuthUrlRequired` 异常
2. `@_handle_provider_error` 装饰器捕获该异常，构造错误响应 dict
3. LLM 看到 dict 后向用户呈现鉴权 URL

这种方式将异常用于正常业务逻辑，违反了软件工程最佳实践。参考 `agent-identity-dev-sdk/examples/langgraph_chainlit_agent/tools.py` 的模式：
- `handle_auth_url` 直接向用户呈现鉴权 URL（正常控制流，不抛异常）
- 每个 tool function 检查 `if not access_token` 后正常返回
- 无需装饰器包装

## 核心设计挑战

**`handle_auth_url` 运行在 `@require_access_token` 装饰器内部，早于 tool function body 执行，且位于 LLM 的 SSE token stream 之外。** 当前架构中：

- SSE stream 仅传输 LLM token（`on_chat_model_stream` 事件）
- 无 event bus / WebSocket / shared queue 等 out-of-band 通信机制
- tool 返回值仅由 LLM 消费，不直接推送给用户

因此需要设计一个机制，使 `handle_auth_url` 能够在 LLM stream 之外向用户推送鉴权 URL。

## 期望变更

### 1. 删除异常控制流

- 删除 `@_handle_provider_error` 装饰器（~80 行）
- 删除 `AuthUrlRequired` 异常类
- 删除 `import functools`

### 2. 设计 `handle_auth_url` 主动呈现机制

`handle_auth_url(auth_url: str)` 需要能够向聊天用户呈现鉴权 URL。可能的方案包括但不限于：

- 扩展 SSE stream 支持 `tool_message` / `system_message` 事件类型
- 使用 LangChain Core 提供的 `adispatch_custom_event`，通过 LangGraph 的 `on_custom_event` 事件直接穿透阻塞，将消息下发
- 在 `handle_stream` 的事件循环中拦截该 custom event，并作为 `system_message` SSE payload 推送给客户端

### 3. 各 tool function 使用正常控制流

每个 tool function body 顶部添加 `if not access_token: return _auth_required_response()`

## 影响的文件

| 文件 | 变更 |
|------|------|
| `personal-assistant-service/app/tools/email_tools.py` | 删除装饰器/异常类，改写 `handle_auth_url` 使用 `adispatch_custom_event`，添加 `if not access_token` guard |
| `personal-assistant-service/app/agent_handler.py` | 在 `handle_stream()` 中捕获 `on_custom_event` 并推送 SSE |
| `personal-assistant-client/src/lib/chat-adapter.ts` | 可能需要支持新的 SSE event type |
| `personal-assistant-client/src/types/chat.ts` | 扩展 `SSEEvent` 类型 |
| `personal-assistant-meta/architecture/backend_architecture.md` | 更新 SSE streaming / message flow 架构文档 |

## 预期结果

- `handle_auth_url` 不再抛异常，使用正常控制流向用户呈现鉴权 URL
- `email_tools.py` 不再有装饰器包装的异常处理
- 鉴权 URL 能在工具调用过程中实时呈现给用户（而非等待 LLM 总结 tool result）
