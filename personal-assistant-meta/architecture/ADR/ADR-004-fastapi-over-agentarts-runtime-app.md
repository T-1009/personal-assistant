# ADR-004: FastAPI 替代 AgentArtsRuntimeApp

> 状态：Accepted | 日期：2026-06-03

---

## 背景

AgentArts 平台提供了 `AgentArtsRuntimeApp` 作为推荐的 Agent 应用基类。使用它时，开发者只需定义 `@app.entrypoint` 处理函数，框架自动暴露 `/ping` 和 `/invocations` 两个端点。

但 Personal Assistant 需要额外的路由：OAuth 回调、SSE 流式对话、飞书 Webhook。这些是 `AgentArtsRuntimeApp` 无法支持的。

## 决策

**使用标准 FastAPI 应用替代 AgentArtsRuntimeApp。**

选择依据：

| 因素 | AgentArtsRuntimeApp | FastAPI |
|------|---------------------|---------|
| **路由自由度** | 仅 `/ping` + `/invocations` | 无限制（可添加任意路由） |
| **OAuth 回调** | ❌ 不支持 | ✅ `/auth/callback` |
| **SSE 流式** | ❌ 不支持 | ✅ `/chat/stream`（StreamingResponse） |
| **飞书 Webhook** | ❌ 不支持 | ✅ `/feishu/webhook` |
| **平台兼容性** | ✅ 原生 | ✅ AgentArts 只看 :8080 的 `/ping` + `/invocations`，不限制 HTTP 框架 |
| **OpenAPI 文档** | 有限 | ✅ 自动生成 Swagger/ReDoc |
| **中间件生态** | 有限 | ✅ CORS、限流、日志等丰富中间件 |

核心原理：AgentArts Runtime 只要求容器在 `:8080` 端口提供 `/ping`（健康检查）和 `/invocations`（调用入口），不关心底层 HTTP 框架。FastAPI 可以完全替代 `AgentArtsRuntimeApp`，同时提供更大的路由灵活性。

## 拒绝的方案

### 使用 AgentArtsRuntimeApp + 额外的 HTTP Server

- 启动两个 HTTP Server（一个 AgentArtsRuntimeApp，一个额外的 FastAPI/Flask）
- 增加复杂度，端口管理、进程管理都更麻烦

### 使用 AgentArtsRuntimeApp + 中间件 hack

- 尝试通过 monkey-patch 或中间件扩展 AgentArtsRuntimeApp
- 不可靠，框架升级可能破坏 hack

## 影响

- `app/main.py` 使用标准 `FastAPI()` 初始化，不依赖 `agentarts.sdk.runtime`
- 必须保留 `/ping`（返回 `{"status": "ok"}`）和 `/invocations`（接受 JSON payload），确保 AgentArts 平台兼容
- 所有额外路由（`/auth/callback`、`/chat/stream`、`/feishu/webhook`）在同一个 FastAPI 实例中管理
- `agentarts launch` 部署命令不受影响，因为平台不关心 HTTP 框架

## 参考

- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- AgentArts Runtime 协议：容器需在 :8080 提供 `/ping` + `/invocations`
