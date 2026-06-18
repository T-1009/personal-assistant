---
|status: resolved
related: []
---

# Bug 14: 邮件工具对 B2B Guest 用户（MSA 个人账号）返回 401 Unauthorized

在使用 Microsoft Graph API 调用邮件相关工具（如 `send_email`, `list_emails` 等）时，对于被邀请为 B2B Guest 的个人微软账号（MSA，如 outlook.com/live.com），接口返回 401 Unauthorized 且 body 为空，导致邮件发送失败并可能引发无限重授权循环。

## 现象

1. 用户（以 B2B Guest 身份，`idp: "live.com"` 登录）触发 `send_email` 工具。
2. AgentArts SDK (`@require_access_token`) 成功通过 `USER_FEDERATION` 获取了 Access Token，且 Token 未过期。
3. 请求 `https://graph.microsoft.com/v1.0/me/sendMail` 时，Graph API 返回 `401 Unauthorized`，且响应体为空。
4. 后端日志显示：
   ```text
   [DEBUG] app.tools.email_tools: send_email access_token: eyJ0e...
   [ERROR] app.tools.email_tools: send_email failed — status=401, body=(empty)
   ```
5. `email_tools.py` 捕获到 401 错误，将其格式化为：`{"error": "授权已过期，请重新授权。"}`。
6. LLM 收到此错误后，可能会不断引导用户重新点击授权链接，形成死循环。

## 根因分析

1. **Token 租户作用域限制**：
   当前 AgentArts 的 Identity Provider 和 `.agentarts_config.yaml` 均配置为特定的 Entra ID 租户（`2a1d3739-88c5-4314-b921-acbeac0abbfa`）。Guest 用户通过 `USER_FEDERATION` 获取的 Graph Token 是由该特定租户签发的（`iss` 包含该 tenant ID，`tid` 也是该 tenant ID）。
2. **Mailbox 归属问题**：
   B2B Guest（MSA 个人账号）在该资源租户下**没有** Exchange Online 邮箱。他们的个人邮箱位于 Consumer 侧（`common` / `consumers`）。
3. **Graph API 拒绝访问**：
   当携带特定租户签发的 Token 访问 `/me/...` 邮件接口时，Graph API 尝试在该租户内寻找用户的邮箱。由于邮箱不存在，Graph API 直接在网关层拒绝了请求，返回 401 Unauthorized 及空 body，而不是标准的 JSON 错误信息。
4. **错误的异常提示**：
   `app.tools.email_tools._format_tool_error` 中，硬编码了 `status == 401` 时返回 `"授权已过期，请重新授权。"`。实际上，因为 AgentArts SDK 已经具备 Token 自动刷新能力，到达这里的 401 大概率是因为权限结构性问题（如 Guest 跨租户邮箱），导致 LLM 给出错误的引导。

## 解决方案

### 1. 客户端与服务端错误提示修复（短期/应用层）

修改 `_format_tool_error` 中的 401 错误提示。由于 SDK 会处理真正的过期（并在必要时要求重新授权），工具内部抛出的 401 应被视为权限不足或账号类型不支持。

- 将 `"授权已过期，请重新授权。"` 修改为类似于 `"邮件功能未授权或当前账号不支持（访客/个人账号无法使用此租户的邮件功能）。"`，阻断 LLM 的无限重试逻辑。

### 2. 账号体系与提供方配置调整（长期/平台层）

若产品目标是支持任意微软账号（包括个人账号）的邮件功能：
- 需要将 Azure AD 应用注册修改为 **多租户和个人 Microsoft 账户（Multitenant and personal accounts）**。
- AgentArts 平台上的 `m365-provider` 配置以及前端/后端的 `discovery_url` 应使用 `common` 端点，而非写死特定的 Tenant ID。
- 在此之前，向用户明确说明当前仅支持组织内（Member）账号使用邮件代理功能。

## 实施任务

- [ ] 修改 `personal-assistant-service/app/tools/email_tools.py` 中的 `_format_tool_error` 函数，优化 401 状态码的错误文案。
- [ ] 验证普通 Member 账号邮箱功能是否正常。
- [ ] 更新 `personal-assistant-meta/issues/bugs/README.md`，添加 Bug 14。
- [ ] （可选）在 README 或产品文档中补充 "目前邮件功能不支持 B2B Guest/个人账号" 的已知限制说明。

## 四问闸门（Four-Question Gate）

| 维度 | 评估结果 | 说明 |
|------|:---:|------|
| **Is it best practice?** | **Yes** | 区分 "Token 失效" 与 "业务权限拒绝（401/403）" 是 API 错误处理的最佳实践。避免误导 Agent 重试。 |
| **Is it industry standard?** | **Yes** | Microsoft Graph 对 B2B Guest 访问 Exchange 的限制是标准的云厂商架构设计。明确提示限制也是业界通用做法。 |
| **Is it conventional?** | **Yes** | 对于确定的跨租户限制，在业务层给予明确的话术拦截，而不是交由底层统一处理为 token 过期。 |
| **Is it modern?** | **Yes** | 结合大模型交互，提供清晰明确不可重试的 error message 可以有效避免 Agent 的无效推理（幻觉重试）。 |
