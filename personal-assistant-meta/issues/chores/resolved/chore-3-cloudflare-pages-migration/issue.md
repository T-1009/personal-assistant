# Chore 3: Web Chat 迁移到 Cloudflare Pages

## 变更动机

Netlify same-origin Proxy 可绕过 AgentArts Gateway 对 CORS preflight
`OPTIONS` 的 401 拦截，但亚洲用户访问延迟较高。Browser 直接跨域调用
Gateway 又不可用，因此需要一个支持静态前端托管、same-origin Proxy 和 SSE
streaming 的替代入口。

## 影响范围

- `personal-assistant-client`：新增 Cloudflare Pages Function 和 Wrangler 配置。
- `personal-assistant-meta/architecture/frontend_architecture.md`
- `personal-assistant-meta/architecture/backend_architecture.md`
- `personal-assistant-meta/architecture/ADR/ADR-017-cloudflare-pages-proxy.md`

## 预期结果

- Cloudflare Pages 托管 Vite production build。
- Browser 请求 same-origin `/api/invocations`，不产生 CORS preflight。
- Pages Function 将 JWT、session header 和 body 透传到 AgentArts Gateway。
- Gateway response body 以 `ReadableStream` 直接返回，支持 SSE。
- 删除 Netlify deployment configuration。
- GitHub Actions 在 `main` Client 变更后自动执行 tests、build、Wrangler
  deployment 和 production smoke test。
- Wrangler CLI 支持本地 Pages runtime、手动 production deployment、
  deployment list 和 Function log tail。
