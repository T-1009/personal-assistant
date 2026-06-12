# ADR-015: OBS + CDN 路径分发避免网关 CORS OPTIONS 预检拦截

> 状态：Accepted | 日期：2026-06-12 | 关联文档：[`ADR-014`](./ADR-014-netlify-edge-function-auth-proxy.md)、[`frontend_architecture.md`](../frontend_architecture.md)

---

## 背景

在个人助手（Personal Assistant）项目的生产环境部署规划中：
1. **前端 (Client)** 部署在华为云 OBS 静态网站托管。
2. **后端 (Service)** FastAPI 部署在华为云 AgentArts Runtime 容器上，通过 AgentArts Gateway 暴露。

为了实现端到端安全，AgentArts Gateway 启用了 API 密钥/JWT 校验（`authorizer_type: API_KEY / CUSTOM_JWT`）。

当浏览器从 OBS 域名直接向 Gateway 域名发送跨域 API 请求时，会产生以下两个硬冲突：
1. **CORS 预检拦截**：浏览器在发起非简单请求（如 `POST /invocations` 携带自定义 header）之前，会自动发送一个不携带身份凭证（无 Token、无 API-Key 签名）的 `OPTIONS` 预检请求。
2. **网关安全防御**：AgentArts Gateway 会严格拦截和校验所有入站请求。由于 `OPTIONS` 预检请求不携带任何认证凭据，**会被网关视为非法请求并直接返回 401 Unauthorized / 403 Forbidden**。

这导致浏览器端会因 `OPTIONS` 请求被网关阻断，而根本无法成功发起后续的真实业务请求（如大模型流式对话），直接卡死跨域方案。

---

## 决策

**生产环境不采用后端 CORS 跨域修补方案，全面采用“OBS + CDN 路径分发回源”架构，实现前后端同源（Same-Origin）部署。**

```mermaid
flowchart TD
    Browser["用户浏览器<br/>(访问同一域名 chat.resource-governance.cloud)"] -->|HTTPS 请求| CDN["华为云 CDN 节点"]
    
    CDN -->|路径匹配 /*| OBS["OBS 静态托管<br/>(前端 React 静态文件)"]
    CDN -->|路径匹配 /api/*| GW["AgentArts Gateway<br/>(后端 FastAPI 容器)"]

    Note over CDN: 统一分流规则：<br/>/api/* 转发至 API 网关<br/>其他 /* 转发至 OBS Bucket
```

选择依据与对比：

| 维度 | 方案 A：OBS + CDN 路径分发 (采纳) | 方案 B：FastAPI 跨域 + CORS (拒绝) | 方案 C：前端加 Node.js BFF 代理 (拒绝) |
|---|---|---|---|
| **对 CORS OPTIONS 的影响** | **无**（同源请求，浏览器不发起 OPTIONS 预检，彻底绕过网关大坑） | **致命**（网关拦截无凭证 OPTIONS 预检，业务请求无法发起） | **无**（通过 BFF 同源，但带来额外运维成本） |
| **安全机制** | ✅ 完美保留网关安全验证防线 | ❌ 需要在网关前放行 OPTIONS（破坏安全基线） | ✅ 完美保留网关验证防线 |
| **Cookie & Auth** | ✅ 天然共享同源 Cookie (Lax)，最安全 | ⚠️ 需配置 `SameSite=None; Secure` 且强制 HTTPS | ✅ 完美支持 Cookie 传递 |
| **前端配置复杂度** | ✅ 极简（API Base URL 设为相对路径 `/api`） | ❌ 繁琐（需配环境变量适配各种不同的跨域 API 域名） | ❌ 繁琐（需要编写代理中转路由） |
| **基础设施成本** | ✅ 极低（华为云 CDN 按流量计费，个人开发几乎免费） | ✅ 极低（无额外组件） | ❌ 高（在华为云上多部署一套 Node.js 容器，IaC 复杂度加倍） |

---

## 拒绝的方案

### 方案 A：在 FastAPI 中通过 `CORSMiddleware` 跨域支持

**拒绝理由**：
虽然在 FastAPI 后端配置 `CORSMiddleware` 是解决跨域最省事的办法（已在本地开发阶段和临时 Netlify 部署中作为过渡方案采用）。但在生产环境中：
1. 华为云 AgentArts Gateway 是平台内置且无法由容器直接修改的安全网关，其优先于容器处理请求。
2. Gateway 对不带认证 of `OPTIONS` 请求进行默认阻断（安全防护规则）。
3. 试图在网关层“特赦”不带认证的 `OPTIONS` 会给整体安全体系开一个漏洞，属于不安全的实践。

### 方案 B：新增 Node.js 后端（BFF 模式，引入 Passport.js 等）

**拒绝理由**：
1. **过度设计**：项目本身是单 React 前端 + 单 FastAPI 后端的轻量级 AI Agent。引入 Node.js BFF 层仅为了解决跨域 and 代理，性价比极低。
2. **多层流代理开销**：流式对话（SSE）本需要高响应速度，如果经过 `FastAPI -> Node.js BFF -> 浏览器` 两次流代理，在没有对 Node.js 做好高并发及数据块透传调优时，极易造成 Stream 积压延迟。
3. **IaC 复杂度倍增**：我们需要用 OpenTofu 额外定义 Node.js 容器、公网 EIP、域名解析、容器监控与日志，严重违反“简单够用”的决策原则。

---

## 影响

### 1. 前端（Client）开发
*   **API 基准路径**：代码中不需要硬编码后端公网域名，将 API Base URL 设为 `/api` 相对路径即可。
*   **Cookie 交互**：前端在进行 Microsoft OAuth 认证成功后，浏览器会自动存储和携带后端下发的 `session_id` HttpOnly Cookie，前端无需任何特殊跨域 Cookie 配置（不用配 `credentials: 'include'`）。

### 2. 基础设施即代码（IaC / OpenTofu）
*   **引入 CDN 资源**：需要在 `personal-assistant-infra` 下新增 CDN 域名及源站、回源路径分发规则的 HCL 定义（优先级 P2 任务）。
*   **域名绑定**：将自定义域名 `chat.resource-governance.cloud` CNAME 指向 CDN 加速域名，而不是直连 OBS 静态网站域名。

### 3. API 安全与鉴权
*   FastAPI 容器端在 CDN 路径分发就绪后，可以**完全关掉公网 CORS**（移除 CORS 中间件或仅保留 localhost 用于本地调试），只接受同源请求，从而将系统受到跨域安全攻击（如 CSRF）的风险降到最低。
