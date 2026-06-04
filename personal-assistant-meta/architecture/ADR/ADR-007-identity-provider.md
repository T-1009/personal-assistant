# ADR-007: Inbound Identity Provider 选型

> 状态：Accepted | 日期：2026-06-03

---

## 背景

Inbound 认证（用户 → Agent）当前架构文档中默认使用 Google OAuth 作为 Custom JWT 的 Identity Provider。但 Google 服务（accounts.google.com、OAuth 端点）在国内被 GFW 阻断：

- Google OIDC Discovery URL（`https://accounts.google.com/.well-known/openid-configuration`）不可达
- Google OAuth 授权页面不可达
- 终端用户无法完成登录流程

需要选择一个在国内网络环境下稳定可用的 OIDC Identity Provider。

## 决策

**不使用 Google OAuth。采用以下 Provider 优先级：**

| 优先级 | Provider | OIDC 兼容 | 国内可达 | 适用场景 |
|--------|----------|-----------|----------|----------|
| 1 | **Microsoft Entra ID**（Azure AD） | ✅ | ✅ | 企业员工（华为内部使用 Microsoft 365） |
| 2 | **GitHub OAuth** | ⚠️ OpenID 非标准 | ✅（偶尔慢，不阻断） | 开发者用户，同时用于 Outbound GitHub 工具 |
| 3 | **飞书 / 阿里云 IDaaS / 自建 OIDC** | ✅ | ✅ | 国内用户、无 Microsoft 365 企业 |

### 首选：Microsoft Entra ID

选择依据：

| 因素 | Microsoft Entra ID | Google OAuth |
|------|-------------------|--------------|
| **OIDC 标准** | ✅ 完整 OIDC 支持 | ✅ 完整 OIDC 支持 |
| **国内可达** | ✅ login.microsoftonline.com 可达 | ❌ accounts.google.com 被阻断 |
| **华为内网** | ✅ 可能是已使用的 IdP（Office 365 体系） | ❌ |
| **个人用户** | ⚠️ 需要 Azure AD 租户 | ✅ 个人 Outlook 账号即可 |

OIDC Discovery URL：`https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration`

如果华为内部已有 Microsoft 365 / Azure AD 租户，直接复用现有体系。否则创建一个 Azure AD 租户即可。

### 备选：GitHub OAuth

GitHub OAuth 非完整 OIDC 实现（用户信息端点 `/user` 而非标准 `/userinfo`），但 AgentArts Custom JWT 模式下可以适配：

- 授权端点：`https://github.com/login/oauth/authorize`
- Token 端点：`https://github.com/login/oauth/access_token`
- 用户信息：`https://api.github.com/user`

适合开发者用户群体。github.com 在国内偶尔慢但不会被阻断。

### 备选：国内 IdP 方案

如果 Microsoft 和 GitHub 都不适用，可以使用国内方案：

| 方案 | 说明 |
|------|------|
| **阿里云 IDaaS (EIAM)** | 企业级身份认证服务，支持 OIDC、SAML，国内部署 |
| **飞书 IdP** | 华为内部大量使用飞书，可配置为 OIDC Provider |
| **华为云 IAM** | 用 IAM 账号直接认证（`authorizer_type: IAM`），不需要 OIDC |
| **自建 OIDC** | 部署 Keycloak 或 Ory Hydra，完全自主可控 |
| **钉钉 / 企业微信** | 如果未来面向外部用户，可用这些作为登录入口 |

## 拒绝的方案

### Google OAuth

- GFW 阻断，终端用户无法完成登录
- 错误信息不明显（页面打不开 vs 授权失败），用户体验差
- 未登录用户完全无法使用 Agent

### Auth0 / Okta（海外版）

- 国内访问不稳定
- 同样受 GFW 影响
- 额外成本（SaaS 订阅费）

## 影响

### 架构文档更新

需要将架构文档中的 Google OAuth 引用替换为 Microsoft Entra ID：

| 文件 | 改动 |
|------|------|
| `overall_architecture.md` | Identity 配置中 `discovery_url` 改为 Microsoft OIDC |
| `backend_architecture.md` | `/auth/callback` 改为适配 Microsoft OAuth |
| `frontend_architecture.md` | Web Chat 登录流程改为 Microsoft OAuth |
| `overall_specifications.md` | 认证矩阵中 "Google 用户" → "Microsoft 用户" |

### 代码变更

- `app/oauth.py` — OAuth 流程适配 Microsoft（验证签名用 Microsoft 公钥，而非 Google）
- `agentarts_config.yaml` — `discovery_url` 改为 Microsoft OIDC 端点
- Web Chat 登录按钮 — "Sign in with Google" → "Sign in with Microsoft"

### Epic 4 调整

Epic 4（Inbound Identity）的任务 "创建 Google OAuth 应用" 替换为 "配置 Microsoft Entra ID 应用注册"。

## 参考

- [Microsoft Entra ID OIDC 文档](https://learn.microsoft.com/en-us/entra/identity-platform/v2-protocols-oidc)
- [华为云 AgentArts Identity Custom JWT 配置](https://support.huaweicloud.com/highcode-agentarts/agentarts_10_044.html)
- [GitHub OAuth 文档](https://docs.github.com/en/apps/oauth-apps)
