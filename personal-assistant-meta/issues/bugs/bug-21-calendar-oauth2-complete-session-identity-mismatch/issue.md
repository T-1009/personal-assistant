---
status: todo
related: ["feature-15-calendar-agentarts-full-oauth2"]
---

# Bug 21: Calendar OAuth2 complete 偶发 session identity mismatch

## 现象

Feature 15 Calendar OAuth2 授权流程中，用户在前端授权页面看到绿色成功提示：

> 日历授权已完成，可以关闭此窗口并重试刚才的问题。

但回到 Web Chat 主页面后，聊天页同时出现授权失败提示：

```text
Authorization session failed. The user may have denied access or the session expired.
```

Service 端日志显示 AgentArts Identity Token Vault 在
`complete_resource_token_auth` 阶段返回 400：

```text
2026-06-28T12:29:02.628+00:00 [WARNING] app:
Calendar OAuth2 complete failed
provider=m365-calendar-provider
user_id=JiVQK-iNU4PcnLxBpkFu_oQmC8mWpYTDMNq8LYQDPxc
error_type=ClientRequestException
error=ClientRequestException - {
  status_code:400,
  request_id:e22477bb697ff87f0cdd30c0feda6584,
  error_code:AgentIdentityTokenVault.1002,
  error_msg:The identity in the request does not match the session identity information,
  encoded_authorization_message:None
}
```

该问题为偶发，不是稳定复现。用户体感是“授权页面已经成功，但聊天页认为授权 session
失败或过期”。

## 影响

- 用户无法稳定完成 Calendar Tool 的 Microsoft 365 授权。
- UI 状态出现冲突：callback 页面显示 success，主聊天页显示 failure。
- Calendar Tool 后续重试可能仍无法读取日历，破坏 feature-15 的授权完成闭环。
- 错误文案把 identity mismatch 归因成用户拒绝授权或 session 过期，排障信息不准确。

## 复现线索

该 bug 的关键复现条件：浏览器中必须同时打开多个 Web Chat tab。单 tab 情况下，
callback envelope 只会被原聊天页处理，暂未观察到同类 identity mismatch。

1. 在 Web Chat 中发送日历查询，例如“查看今日 calendar”。
2. 保持至少另一个 Web Chat tab 打开，且该 tab 也会监听 calendar OAuth
   `BroadcastChannel`。
3. 点击 Calendar AuthCard 进入 Microsoft / AgentArts OAuth2 授权页。
4. 完成授权后，callback 页面显示授权成功。
5. 回到主聊天窗口，观察 AuthCard / system message 是否出现
   `Authorization session failed...`。
6. 检查 Service 日志是否存在
   `AgentIdentityTokenVault.1002` 与
   `The identity in the request does not match the session identity information`。

## 已确认排查发现

- Calendar callback 与聊天页之间使用全局 `BroadcastChannel`
  `m365-calendar-auth` 通信；所有同源 Web Chat tab 都会收到同一条
  `m365-calendar-auth-request`。
- `personal-assistant-client/src/App.tsx` 中每个非 callback tab 都会监听该 channel，
  收到 request 后调用 `completeOAuth2Auth()`，因此一次 callback 可能触发多个 chat tab
  同时 POST `/invocations/auth/oauth2/complete`。
- `personal-assistant-service/app/oauth2_state.py` 的 state 绑定了 `user_id`、
  `session_id`、provider 和 nonce；complete endpoint 当前验证了 `user_id` 与
  provider，但客户端 cross-tab 分发仍可能让非发起授权的 tab 使用自己的当前
  id token / session context 发起 complete。
- 这解释了偶发现象：正确 tab 或 callback 页面可能已经得到 success，但另一个 tab
  抢先或重复处理同一 callback，并在 AgentArts Identity
  `complete_resource_token_auth` 阶段触发
  `AgentIdentityTokenVault.1002`。
- 初步客户端修复方向：由于 SDK 下发的 `auth_url` 不保证携带可供前端反查的
  `state` / `custom_state`，不能依赖解析 AuthCard URL 做 ownership 校验。应由前端
  给打开授权窗口的 chat tab 生成 per-tab owner id，将 Calendar AuthCard 的
  `target` 设置为带 owner id 的命名窗口；callback page 通过 `window.name` 取回
  owner id，并随 BroadcastChannel request 一起发送。不匹配 owner id 的 tab 应静默
  忽略，不能调用 complete endpoint，也不能污染 AuthCard 状态。

## 当前行为

```mermaid
sequenceDiagram
    actor User as 用户
    participant UI as Web Chat 原主窗口
    participant OtherUI as 其他 Web Chat tab
    participant CB as Callback Page
    participant API as Service complete endpoint
    participant IdSvc as AgentArts Identity Service

    User->>UI: 请求查看日历
    UI-->>User: 展示 Calendar AuthCard
    User->>CB: 完成 Microsoft OAuth2 授权
    CB-->>User: 显示“授权已完成”
    CB->>UI: BroadcastChannel callback envelope(state, session_uri)
    CB->>OtherUI: 同一 BroadcastChannel envelope
    UI->>API: POST /invocations/auth/oauth2/complete
    OtherUI->>API: 也可能 POST /invocations/auth/oauth2/complete
    API->>IdSvc: complete_resource_token_auth(user_id, session_uri)
    IdSvc-->>API: 可能返回 400 AgentIdentityTokenVault.1002<br/>request identity != session identity
    API-->>OtherUI: auth session failed
    OtherUI-->>User: 错误 tab / stale AuthCard 显示 Authorization session failed
```

## 初步怀疑方向

本 bug 先记录生产现象，不在 issue 阶段锁死根因。Implementation 阶段需重点排查：

- Service complete endpoint 使用的可信 `user_id` 是否与创建 AgentArts OAuth2
  `session_uri` 时的 runtime identity 完全一致。
- `state` / pending auth record 中绑定的 user identity、provider、session 与
  complete request 中的 server-bound user 是否可能跨浏览器窗口、跨 tab、跨登录态或
  reset session 后错配。
- 主聊天窗口 callback coordinator 是否可能处理旧的 callback envelope、重复 callback
  或 stale AuthCard。
- 多个 Web Chat tab 是否因共享 `m365-calendar-auth` BroadcastChannel 而同时处理同一个
  callback envelope；非发起授权的 tab 是否缺少 state/AuthCard ownership 校验。
- callback 页面是否过早展示“授权完成”，没有等待主窗口 complete API 的真实结果。
- AgentArts Gateway / Cloudflare Pages proxy 是否在 complete request 上丢失或替换了
  inbound identity 相关 header。
- 与 Bug 20 的 replay / duplicate callback 场景是否互相放大。

## 预期行为

- callback 页面只有在主窗口 complete API 真正成功后，才展示最终“授权完成”状态。
- Service 调用 `complete_resource_token_auth` 时使用的 identity 必须与创建
  AgentArts OAuth2 session 的 identity 一致。
- 如果 AgentArts 返回 `AgentIdentityTokenVault.1002`，前端应展示准确、可恢复的错误，
  不应误导为用户拒绝授权或普通 session 过期。
- 重复 callback、旧 callback、跨 tab callback 应被识别并返回受控结果，不应污染当前
  AuthCard 状态。
- 非发起授权的 Web Chat tab 即使收到 BroadcastChannel request，也必须因 owner id
  与本 tab 不匹配而忽略，不能调用 complete endpoint。

## 修复范围

### In Scope

- 排查并修复 Calendar OAuth2 complete flow 中 identity / session binding 偶发错配。
- 对 callback 页面与主窗口 AuthCard 的成功/失败状态建立一致语义。
- 增加结构化日志，至少能关联：
  - provider；
  - server-bound user_id；
  - state nonce / pending auth id；
  - session_uri hash；
  - AgentArts request_id；
  - complete result。
- 增加 Service / Client / E2E regression tests，覆盖 identity mismatch、stale callback
  和 duplicate callback 的用户可见状态。
- 增加 Client regression test，覆盖多 chat tab 共享 BroadcastChannel 时，owner id
  不匹配的 tab 不会调用 `completeOAuth2Auth()`。

### Out of Scope

- 重做整个 AgentArts OAuth2 架构。
- 修改 Microsoft Entra App 的权限范围，除非排查证明 provider 配置是根因。
- 在浏览器保存 Microsoft access token 或平台 token。
- 将非 Calendar 工具迁移到 complete flow。

## 验收标准

- [ ] Calendar OAuth2 callback 成功时，callback 页面与 Web Chat 主窗口状态一致。
- [ ] `complete_resource_token_auth` 不再因项目侧 identity/session 错配偶发返回
      `AgentIdentityTokenVault.1002`。
- [ ] 真实 `AgentIdentityTokenVault.1002` 场景有明确日志与用户可恢复提示。
- [ ] stale / duplicate callback 不会把当前 AuthCard 标记为失败。
- [ ] 多 Web Chat tab 场景中，只有 owner id 匹配 callback window 的 tab 会执行
      complete；其他 tab 不发请求、不改 UI 状态。
- [ ] 相关 Service tests、Client tests 和 E2E regression 通过。

## Affected Specs / Architecture Docs

| 文档 | 影响 |
|------|------|
| `personal-assistant-meta/issues/features/feature-15-calendar-agentarts-full-oauth2/issue.md` | 对齐 callback page 与主窗口 complete API 的成功语义 |
| `personal-assistant-meta/issues/features/feature-15-calendar-agentarts-full-oauth2/plan.md` | 补充 identity/session mismatch 排查与回归验证 |
| `personal-assistant-meta/architecture/backend_architecture.md` | 如修复改变 OAuth2 complete endpoint 语义，需要同步 |

## 参考实现 / 排查入口

| 路径 | 关联点 |
|------|--------|
| `personal-assistant-service/app/main.py` | `/invocations/auth/oauth2/complete` complete endpoint |
| `personal-assistant-service/app/oauth2_state.py` | signed state、pending auth、nonce / replay guard |
| `personal-assistant-service/app/tools/calendar_tools.py` | Calendar Tool 与 AgentArts Identity SDK provider 使用 |
| `personal-assistant-client/src/` | AuthCard、callback page、主窗口 callback coordinator |
| `personal-assistant-e2e/tests/` | Calendar OAuth2 授权回归测试 |
