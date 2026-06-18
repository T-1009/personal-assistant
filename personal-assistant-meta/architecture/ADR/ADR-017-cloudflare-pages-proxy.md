# ADR-017: Cloudflare Pages 托管与 Same-Origin API Proxy

> 状态：Accepted | 日期：2026-06-18 | 关联文档：[`ADR-014`](./ADR-014-netlify-edge-function-auth-proxy.md)

## 背景

AgentArts Gateway 在 `CUSTOM_JWT` 模式下会对 Browser 自动发送且不携带 JWT
的 CORS preflight `OPTIONS` 执行认证并返回 401，因此 Browser 无法跨域直连
Gateway。Netlify Proxy 可以消除 CORS preflight，但亚洲访问延迟不满足当前
需求。

## 决策

Production Web Chat 迁移到 Cloudflare Pages。Cloudflare 同时托管 Vite
静态文件，并通过 Pages Function 提供 same-origin `/api/invocations`：

```text
https://agentarts-personal-assistant.pages.dev
```

```mermaid
flowchart LR
    Browser["Browser<br/>Cloudflare Pages origin"] -->|"POST /api/invocations<br/>JWT + session header"| Function["Pages Function"]
    Function -->|"POST full Runtime path<br/>headers + body"| Gateway["AgentArts Gateway<br/>CUSTOM_JWT"]
    Gateway -->|"SSE ReadableStream"| Function
    Function -->|"SSE ReadableStream"| Browser
```

Browser 只请求 Cloudflare Pages origin，因此不产生 CORS preflight。
Pages Function 不验证或生成 JWT，只透明转发 authentication headers；
AgentArts Gateway 继续承担 JWT validation。

Production Client 配置为：

```bash
VITE_API_BASE_URL=/api
```

Netlify deployment configuration 删除，不作为 fallback 或并行 production
环境保留。

## 约束

- Pages Function 必须使用完整 Runtime path：
  `/runtimes/personal-assistant/invocations`。
- 必须显式复制 `Authorization`、session header 和 request body。
- Response body 必须以 stream 透传，不能调用 `response.text()` 或
  `response.json()` 后重新组装。
- API response 设置 `Cache-Control: no-store`。
- Cloudflare Pages deployment URL 必须加入 Microsoft Entra SPA Redirect
  URI。

## Four-Question Gate

| 问题 | 结论 |
|------|------|
| Is it best practice? | Yes。Browser 使用 same-origin API，Gateway 保持认证职责 |
| Is it industry standard? | Yes。Edge-hosted SPA + serverless reverse proxy 是常见 BFF pattern |
| Is it conventional? | Yes。Frontend 使用相对 `/api` path，部署层负责 upstream routing |
| Is it modern? | Yes。Pages Functions 与 Web Streams 原生支持 edge streaming |
