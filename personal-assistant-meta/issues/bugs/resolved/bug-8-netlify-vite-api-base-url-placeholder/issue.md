# Bug 8: Netlify 部署聊天失败 — VITE_API_BASE_URL 未替换占位符

## Motivation

部署到 `https://agentarts-personal-assistant.netlify.app/` 后，用户发送聊天消息时浏览器报错：

```
Failed to execute 'fetch' on 'Window': Failed to parse URL from https://<runtime-domain>/invocations/stream?q=today
```

**直接原因**：Netlify 构建时 `VITE_API_BASE_URL` 环境变量未配置，Vite 回退到 `.env.production` 中的占位符 `https://<runtime-domain>`，将其原样嵌入生产 JS bundle，导致浏览器无法解析该 URL。

**深层原因**：构建流程缺少校验机制——即使 `VITE_API_BASE_URL` 是无效占位符，构建依然成功并通过部署，没有任何 fail-fast 保护。

Feature 12（Netlify 部署）的 issue 文档中已明确要求 "在 Netlify Site Settings → Environment variables 中设置 `VITE_API_BASE_URL`"，但该步骤在部署时被遗漏。

## Scope

### 修复（必须）

- [ ] 在 Netlify Site Settings → Environment variables 中设置 `VITE_API_BASE_URL` 为 AgentArts Runtime 实际域名（如 `https://xxx.agentarts.cn-southwest-2.myhuaweicloud.com`）
- [ ] 触发 Netlify 重新构建并部署
- [ ] 验证聊天功能正常：SSE 流式回复可用，浏览器 Network 面板请求指向真实 Runtime 域名

### 构建时校验（预防复发）

- [ ] 在 `personal-assistant-client/vite.config.ts` 中添加 `production` 模式下的构建时校验：若 `VITE_API_BASE_URL` 未设置、为空、或包含 `<runtime-domain>` 等占位符，构建失败并给出明确错误提示
- [ ] 移除 `personal-assistant-client/.env.production` 中的占位符默认值（改为空值或删除该文件），防止任何部署目标在未设置环境变量时静默构建出包含占位符的 bundle

### 后端 CORS 配置（确保联调成功）

- [ ] 确认 AgentArts Runtime 的 `CORS_ALLOWED_ORIGINS` 环境变量包含 Netlify 生产域名 `https://agentarts-personal-assistant.netlify.app`
- [ ] 若尚未配置，在 Runtime 环境变量中添加（注意：该变量支持逗号分隔多个 origin）

### 文档更新

- [ ] 更新 `personal-assistant-meta/architecture/devops/agentarts-deploy-runbook.md` §9.2，新增 **Netlify 部署专属** 的环境变量配置说明（Netlify UI 操作步骤，区别于 OBS 的命令行 export 方式）

### 不涉及

- Netlify proxy rewrites（`/invocations/*` → 后端）。Proxy 会缓冲 SSE 流式响应并受 26 秒超时限制，与当前直连架构不兼容。
- OBS 部署流程的任何变更
- 硬编码 Runtime 域名到源码或 `.env.production`

## Acceptance Criteria

1. **功能恢复**：`https://agentarts-personal-assistant.netlify.app/` 发送聊天消息 → SSE 流式回复正常，浏览器 Network 请求指向真实 Runtime URL
2. **构建失败校验**：本地执行 `VITE_API_BASE_URL="https://<runtime-domain>" npm run build` 必须失败并报告明确错误
3. **构建成功校验**：本地执行 `VITE_API_BASE_URL="https://valid-domain.example.com" npm run build` 必须成功
4. **无 CORS 错误**：Netlify 部署后浏览器 DevTools Console 无 CORS 相关报错
5. **文档更新完成**：deploy runbook §9.2 包含 Netlify 环境变量配置步骤

## Affected Architecture Docs

- `personal-assistant-meta/architecture/devops/agentarts-deploy-runbook.md` — §9.2 新增 Netlify 环境变量配置说明
- `personal-assistant-meta/issues/features/feature-12-netlify-deployment/issue.md` — 本 bug 作为该 feature 的部署遗漏问题，需在本 issue 中引用

## Notes

### 技术背景

1. **`VITE_API_BASE_URL` 是构建时变量**：Vite 在 `vite build` 时静态替换 `import.meta.env.VITE_API_BASE_URL` 为环境变量值，嵌入 JS bundle。更改该值需要重新触发 Netlify 构建，无法运行时更改。

2. **为什么不用 Netlify Proxy**：Netlify 的 `[[redirects]]` proxy rewrite 对 SSE 流式响应存在两个致命问题：
   - **缓冲响应**：Netlify CDN 会缓冲 chunked transfer encoding，导致 token-by-token 流式输出变成一次性延迟返回，用户看不到逐字打字效果
   - **26 秒超时**：Netlify proxy connection 最多维持 26 秒，长 LLM 推理或复杂 multi-tool 调用会触发 HTTP 502/504

3. **`VITE_API_BASE_URL` 是公开变量**：所有 `VITE_` 前缀的环境变量会被 Vite 暴露到客户端 JS bundle 中，可被用户查看。Runtime 域名本身即为公开信息，这符合预期。

4. **CORS 配置**：后端 `CORS_ALLOWED_ORIGINS` 已于 Feature 12 中改造为环境变量驱动，支持逗号分隔多域名。若 Netlify 域名尚未加入，需在 Runtime 环境变量中更新。

### 与现有 Issues 的关系

| Issue | 关系 |
|-------|------|
| `feature-12-netlify-deployment` | 本 bug 是该 feature 的部署执行遗漏 —— env var 配置步骤被文档记录了但未执行 |
| `chore-1-agentarts-deploy` | deploy runbook 需在本 bug 中更新，补充 Netlify 专属配置说明 |

### 咨询顾问综合建议

本 issue 的范围和方案基于 DeepSeek、Gemini、GPT 三位 AI 顾问的并行分析综合得出。三方一致认为：
- 根因是部署流程遗漏（非代码 bug），Netlify env var 未配置
- 最佳修复是直接设置 env var + 添加构建时校验防止复发
- Netlify proxy rewrite 不适用于 SSE 流式场景（缓冲 + 超时）
- 不应硬编码 Runtime 域名
- CORS 配置需同步确认，确保联调成功
