# feature-13-reset-session: 添加"重置 Session ID"按钮

## 动机

当前 Session ID 长期绑定在 `localStorage` 的 `agentarts-session-id` key 中（`chat-adapter.ts:57`），导致同一浏览器上的所有对话共享同一个 LangGraph thread——对话上下文无限累积，用户无法主动"清零"对话上下文以开始全新会话。

用户需要一个简单的方式开始全新对话。所有主流 AI Chat 产品（ChatGPT、Claude、Gemini）均提供类似 "New Chat" / "New Conversation" 功能。

## 影响范围

| 系统 | 影响 |
|------|------|
| `personal-assistant-client` | 修改 2 个现有文件 + 新增 1 个组件文件 |
| `personal-assistant-service` | **无需修改** |
| `personal-assistant-meta` | 本 issue |
| `personal-assistant-e2e` | 需新增 E2E 测试用例 |
| `personal-assistant-infra` | 无需修改 |

## 预期结果

用户点击 header 中的 Reset 按钮 → 弹出确认对话框 → 确认后：

1. `localStorage` 中 `agentarts-session-id` key 被删除
2. 聊天界面回到空白 welcome 状态（`ThreadWelcome` 组件显示）
3. 输入框内容被清空
4. 下一条消息请求中包含全新的 UUID（`x-hw-agentarts-session-id` header 值变更）
5. 服务端自动创建新 `thread_id`，对话上下文隔离

## 验收标准

- [ ] 点击 Reset 按钮弹出确认对话框（"取消" + "确认"两个按钮）
- [ ] 确认后 `localStorage` 中 `agentarts-session-id` key 被删除
- [ ] 确认后聊天界面回到空白 welcome 状态
- [ ] 确认后输入框内容被清空
- [ ] 确认后发送的下一条消息请求中包含全新的 UUID
- [ ] streaming 进行中时 Reset 按钮处于 `disabled` 状态
- [ ] 隐私模式 / localStorage 不可用时，点击 Reset 不抛异常
- [ ] 按钮样式符合 Apple 风格设计语言
- [ ] 已登录和未登录状态下均可正常使用

## Panel Review Summary

全体专家一致通过（Four-Question Gate: Yes × 4），详见 panel chair 综合报告。

## 关联文档

- `personal-assistant-client/src/lib/chat-adapter.ts` — Session ID 管理
- `personal-assistant-client/src/components/chat/ChatPage.tsx` — 聊天页面布局
- `personal-assistant-service/app/agent_handler.py` — 服务端 thread_id 构造
- `personal-assistant-client/DESIGN.md` — Apple 风格设计约束
