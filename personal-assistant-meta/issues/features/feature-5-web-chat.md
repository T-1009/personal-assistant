---
status: backlog
---

# Feature 5: Web Chat 渠道

本 Phase 实现 Web Chat 前端 + SSE 流式对话，完成三种接入渠道的最后一块拼图。这是最重的渠道，放在最后因为依赖 OAuth（Feature 4），且飞书和 OfficeClaw 已经覆盖了日常使用场景。

---

## 背景

飞书和 OfficeClaw 覆盖了企业内部 IM 场景，但没有独立的 Web 界面用于对外 Demo 和 OAuth 登录体验。本 Phase 实现一个最小可行的 Web Chat 页面，通过 SSE 接收流式响应。

## 范围

- `app/agent_handler.py` — `handle_stream()` 流式方法
- `GET /chat/stream` SSE 路由
- `web/` 前端页面（登录 + 对话界面 + SSE 渲染）
- 前端部署（OBS 静态托管或同容器 serve）

## 不涉及

- 复杂前端功能（Markdown 渲染、文件上传、对话历史列表）
- 移动端适配

## 任务拆解

### 5.1 SSE 流式对话

- [ ] `app/agent_handler.py` — `handle_stream(message, user_id)`
  - 调用 `graph.astream()` 逐 token yield
  - 格式：`data: {"token":"..."}\n\n`
- [ ] `GET /chat/stream?q=...`
  - 从 Cookie 提取用户身份
  - 返回 `StreamingResponse`，media_type=`text/event-stream`

### 5.2 Web Chat 前端

- [ ] `web/index.html` — 单页应用
  - 未登录 → 显示 "使用 Google 登录" 按钮（跳转 OAuth）
  - 已登录 → 对话输入框 + 消息列表
  - 连接 SSE，逐 token 渲染消息
- [ ] 登录流程：按钮 → Google OAuth → `/auth/callback` → 回到 Chat

### 5.3 前端部署

- [ ] 选项 A：同容器 serve（FastAPI `StaticFiles` mount `web/`）
- [ ] 选项 B：OBS 静态托管（需额外配置，见 Layer 3 IaC）

### 5.4 验证

- [ ] 浏览器打开 /chat → 跳转 Google 登录 → 回到 Chat
- [ ] 发消息 → 逐 token 流式出现
- [ ] 飞书 / OfficeClaw 渠道不受影响

## 依赖

- Feature 1（Agent 骨架 + 飞书）
- Feature 4（Inbound Identity）

## 参考

- ADR-004: FastAPI
- ADR-006: IaC（前端 OBS 托管）
- `architecture/frontend_architecture.md` #2.1 Web Chat
