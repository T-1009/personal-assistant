---
status: backlog
---

# Bug 16: Auth Card system_message 重复出现在聊天气泡中

`system_message` 既渲染了 Auth Card 组件，又被追加到聊天流 `fullText`，导致用户在同一条消息中看到同一段授权文字出现两次。

---

## 背景

Auth Card 的设计目标是用专用 UI 卡片替代 inline markdown 链接展示授权 URL。但当后端通过 `get_stream_writer()` 推送 `auth_required` / `auth_complete` 自定义事件时，`chat-adapter.ts` 在渲染 Auth Card 的同时，也将 `system_message` 无条件追加到了 `fullText`：

```typescript
// chat-adapter.ts:213
fullText += parsed.system_message;
```

这意味着 M365 邮件工具触发的 "邮件功能需要您的授权。请点击该链接进行授权：" 和 "授权已完成 ✅" 既出现在 Auth Card 中，又以普通聊天文本重复出现在助理消息气泡里。

## 复现步骤

1. 未授权状态下请求邮件操作（如"查看收件箱"）
2. 观察助理回复：
   - Auth Card 中显示 "邮件功能需要您的授权。请点击该链接进行授权："
   - 同一消息气泡正文中同样出现该文字

## 根因

`chat-adapter.ts:209-228` —— `system_message` 到达时的逻辑没有区分 auth 事件和普通 system 消息。auth 事件已有专属的 AuthCard 渲染通道，不应再写入聊天流。

## 范围

### In Scope

- `personal-assistant-client/src/lib/chat-adapter.ts`：auth 事件的 `system_message` 跳过 `fullText` 追加

### Out of Scope

- Auth Card UI 样式调整
- 后端 `system_message` 内容修改
- GitHub/Gitee 工具接入 Auth Card 通道（那是 feature 的事）

## 影响

| 文件 | 变更 |
|------|------|
| `personal-assistant-client/src/lib/chat-adapter.ts` | 在 `parsed.auth_required` 或 `parsed.auth_complete` 为 true 时，跳过 `fullText += parsed.system_message`，只操作 `useAuthCardStore` |

## 验收标准

- [ ] M365 邮件工具触发授权时，Auth Card 正常显示，但聊天气泡正文**不包含** `system_message` 的文字
- [ ] 授权完成后 Auth Card 正常转绿，聊天气泡正文**不包含** "授权已完成 ✅"
- [ ] 非 auth 的 `system_message` 不受影响，依然正常追加到聊天流
- [ ] `npm run test` 通过

## 参考

| 文档 | 路径 |
|------|------|
| Auth Card 组件 | `personal-assistant-client/src/components/chat/AuthCard.tsx` |
| Auth Card Store | `personal-assistant-client/src/stores/auth-card-store.ts` |
| Chat Adapter | `personal-assistant-client/src/lib/chat-adapter.ts` |
| 邮件工具 (handle_auth_url) | `personal-assistant-service/app/tools/email_tools.py` |
| Agent Handler (SSE 路由) | `personal-assistant-service/app/agent_handler.py` |
| SSE Event 类型定义 | `personal-assistant-client/src/types/chat.ts` |
