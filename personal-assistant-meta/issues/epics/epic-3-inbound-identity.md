---
status: backlog
---

# Epic 3: Inbound Identity 认证

本 Phase 配置 AgentArts Identity 的 Inbound 认证，使用户通过 Google OAuth（Custom JWT）或 API Key 登录后访问 Agent。同时接入 Web Chat 渠道的 SSE 流式对话和 OAuth 回调。

---

## 背景

当前 `/invocations` 是无认证的。本 Phase 配置 AgentArts Identity，使 AgentArts Runtime 层自动完成用户身份验证，并在 Request Header 中注入 `X-AgentArts-User-Id`。同时为 Web Chat 渠道增加 OAuth 登录流程和 SSE 流式对话。

## 范围

- 配置 `agentarts_config.yaml` 中的 `identity_configuration`
- 创建 Google OAuth 应用（获取 client_id / client_secret）
- FastAPI 新增路由：`/auth/callback`（OAuth 回调）、`/chat/stream`（SSE 流式）
- AgentHandler 从 Request Header 读取 `X-AgentArts-User-Id`
- OAuth 流程：登录 → 获取 Google ID Token → 设置 Cookie → 后续请求携带
- 验证：不同认证方式的用户均可访问 Agent

## 不涉及

- Outbound 认证（Phase 4-6）
- 飞书渠道的认证（飞书有自己的 Token 验证机制）
- 多 IdP 支持（先只做 Google OAuth + API Key）

## 任务拆解

### 3.1 Google OAuth 应用

- [ ] 在 Google Cloud Console 创建 OAuth 2.0 应用
- [ ] 配置 Authorized redirect URI: `https://<runtime-domain>/auth/callback`
- [ ] 获取 client_id 和 client_secret

### 3.2 Identity 配置

- [ ] 更新 `agentarts_config.yaml`
  - `authorizer_type: CUSTOM_JWT`
  - `discovery_url: https://accounts.google.com/.well-known/openid-configuration`
  - `allowed_audience` / `allowed_clients` / `allowed_scopes` 配置
  - `key_auth` 配置（开发调试用 API Key）

### 3.3 OAuth 回调路由

- [ ] `app/oauth.py` — Google OAuth 流程
  - `exchange_google_code(code)` → 用 code 换 id_token + access_token
  - `verify_google_id_token(id_token)` → 验证 token 并提取用户信息
- [ ] `app/main.py` — `GET /auth/callback`
  - 接收 `?code=xxx`
  - 调 `exchange_google_code()` 获取 id_token
  - 302 重定向到 `/chat`，同时 Set-Cookie（session=id_token）

### 3.4 SSE 流式对话

- [ ] `app/main.py` — `GET /chat/stream`
  - 从 Cookie 中提取用户身份
  - 调用 `agent_handler.handle_stream()`
  - 返回 `StreamingResponse`，media_type=`text/event-stream`
- [ ] `app/agent_handler.py` — `handle_stream()` 方法
  - 调用 `graph.astream()` 逐 token yield
  - 格式：`data: {"token": "..."}\n\n`

### 3.5 AgentHandler 身份读取

- [ ] `handle()` 和 `handle_stream()` 中，`user_id` 从以下来源获取：
  - AgentArts Runtime 注入的 `X-AgentArts-User-Id` header（生产环境）
  - 手动传入的 user_id（本地开发）
  - Cookie 中的 id_token（Web Chat）

### 3.6 Web Chat 前端页面

- [ ] 最小可行 Web Chat 页面（`web/index.html`）
  - 登录按钮 → 跳转 Google OAuth
  - 对话输入框 + 消息列表
  - 连接 `/chat/stream` 的 SSE，逐 token 渲染
- [ ] 前端独立部署（放到 OBS 静态托管或同容器 serve）

### 3.7 验证

- [ ] API Key 方式：`curl -H "X-AgentArts-User-Id: dev-user" /invocations` → 正常响应
- [ ] Google OAuth 方式：浏览器打开 /chat → 跳转 Google 登录 → 回到 Chat 页面 → 发消息正常
- [ ] SSE 流式：消息逐 token 出现在页面上

## 依赖

- Epic 1（Agent 骨架）完成
- Epic 2（Memory）完成（user_id 需要关联 Memory）

## 参考

- ADR-003: AgentArts 平台
- ADR-004: FastAPI 替代 AgentArtsRuntimeApp
- `architecture/overall_architecture.md` #3 认证流、#4 Identity 设计
- `architecture/frontend_architecture.md` #2.1 Web Chat
