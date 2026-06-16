# refactor-migrate-frontend-to-zeabur

## 动机

当前 Web Chat 前端部署在 Netlify（`agentarts-personal-assistant.netlify.app`），通过 Edge Function 注入 `Authorization` header 后转发 API 请求到 AgentArts Gateway。迁移到 Zeabur 主要解决两个核心问题：

### 问题 1：避免国内域名备案（ICP 备案）

- 使用国内服务器或 CDN（如华为云 OBS + CDN）绑定自定义域名，必须完成 ICP 备案，流程通常 20+ 工作日，且需要国内主体资质
- Netlify 默认域名不可绑自定义域名，OAuth Cookie 跨域不可用
- **Zeabur 提供海外节点 + 自定义域名支持**，无需 ICP 备案即可绑定自己的域名，同时通过 Caddy reverse proxy 实现前后端同源部署（零跨域、零预检拦截、Cookie 天然共享）

### 问题 2：Netlify 504 超时

- Netlify Edge Function 有执行超时限制（免费套餐 ~10s），Agent 推理 + SSE 流式响应时，长请求被 Netlify 强行截断返回 504
- 用户等待 Agent 推理结果时看到 504 错误，体验极差
- **Zeabur 的 Caddy reverse proxy 无强制超时限制**，SSE 长连接可保持至 Agent 推理自然结束

### 附加收益

| 维度 | Netlify（当前） | OBS + CDN（原目标） | Zeabur |
|------|:---:|:---:|:---:|
| 域名备案 | 不需要（海外） | **需要 ICP 备案** | 不需要（海外） |
| 超时限制 | **504 ~10s** | 无 | 无 |
| 自定义域名 | 不支持 | 支持（需备案 + CDN） | 支持 |
| 同源部署 | 否 | 是（CDN 路径分流） | 是（Caddy reverse proxy） |
| CI/CD | 自动推送部署 | 手动 obsutil 上传 | 自动推送部署 |
| API 认证注入 | Edge Function | CDN 回源 | Caddyfile `header_up` |
| SPA fallback | ✅ | ✅ | ✅ |
| 平台统一 | 前端独立 | 前端独立 | 未来可后端也迁入 |

> **注意**：本次 refactor 仅涉及前端部署迁移。后端仍运行在 AgentArts Runtime（华为云），不在 Zeabur 上部署。

## 核心设计挑战

### 1. API 认证代理（替代 Netlify Edge Function）

当前 Netlify Edge Function (`netlify/edge-functions/invocations.ts`) 负责：
- 拦截 `POST /invocations` 请求
- 注入 `Authorization: Bearer <api-key>` 和 `x-hw-agentarts-session-id`
- 转发到 AgentArts Gateway

在 Zeabur 静态站点中，使用 **Caddyfile** 实现等效功能：

```caddyfile
# 自定义 Caddy 配置 — 在 Zeabur Config Editor 中设置
# 或通过 /etc/caddy/Caddyfile 路径挂载

@apiPath {
    path /invocations
}
reverse_proxy @apiPath https://defaultgw-xxx.cn-southwest-2.huaweicloud-agentarts.com/runtimes/personal-assistant/invocations {
    header_up Authorization "Bearer {$AGENTARTS_API_KEY}"
    header_up x-hw-agentarts-session-id {http.request.uuid}
}
```

> Caddy 的 `reverse_proxy` + `header_up` 在服务端注入认证 header，API Key 不出现在浏览器中，与 Netlify Edge Function 方案安全等价。

### 2. SPA 路由回退

Zeabur 静态站点内置 Caddy `try_files` 逻辑，默认支持 SPA（找不到文件时返回 `index.html`）。无需额外配置。若需定制，可通过 Caddyfile 调整。

### 3. Monorepo 子目录构建

当前仓库为 monorepo，前端代码在 `personal-assistant-client/` 子目录。Zeabur 需要通过以下方式指定构建上下文：

**方案 A：`zbpack.json`**（推荐，无需修改仓库结构）

在仓库根目录添加：

```json
{
    "root_dir": "personal-assistant-client",
    "output_dir": "dist"
}
```

**方案 B：环境变量**

在 Zeabur 服务配置中设置：
```
ZBPACK_OUTPUT_DIR=dist
```
并在 Zeabur Dashboard 中设置 Root Directory 为 `personal-assistant-client`。

> Zeabur 自动检测 Vite 项目（`vite.config.ts` 存在），后续 `git push` 自动触发 `npm install && npm run build`。

## 期望变更

### 1. 添加 Zeabur 部署配置

| 新增文件 | 说明 |
|----------|------|
| `zbpack.json`（仓库根目录） | 指定 monorepo 子目录 `root_dir: personal-assistant-client` 和 `output_dir: dist` |
| `personal-assistant-client/Caddyfile` | Caddy 反向代理配置，注入 `Authorization` header 后转发 `/invocations` 到 AgentArts Gateway |

`Caddyfile` 内容：

```caddyfile
# AgentArts Gateway proxy — inject auth headers server-side
@api {
    path /invocations
}
reverse_proxy @api https://defaultgw-xxx.cn-southwest-2.huaweicloud-agentarts.com/runtimes/personal-assistant/invocations {
    header_up Authorization "Bearer {env.AGENTARTS_API_KEY}"
}
```

> `{env.AGENTARTS_API_KEY}` 引用 Zeabur 环境变量，API Key 不进入代码仓库。

### 2. 移除或保留 Netlify 配置

| 文件 | 处理方式 |
|------|----------|
| `personal-assistant-client/netlify.toml` | 保留，作为备选回退方案。Zeabur 部署成功后通过 follow-up PR 移除 |
| `personal-assistant-client/netlify/edge-functions/invocations.ts` | 保留，同上 |

### 3. 环境变量配置

Zeabur Dashboard 中配置以下环境变量（与 Netlify 当前配置对齐）：

| 变量 | 值 | 说明 |
|------|-----|------|
| `AGENTARTS_API_KEY` | `<production-api-key>` | AgentArts Gateway API Key，供 Caddy 注入 `Authorization` header |
| `VITE_ENTRA_CLIENT_ID` | 同 `.env.production` | MSAL 认证 |
| `VITE_ENTRA_TENANT_ID` | 同 `.env.production` | MSAL 认证 |

### 4. 更新架构文档

| 文件 | 变更 |
|------|------|
| `personal-assistant-meta/architecture/frontend_architecture.md` §6 | 更新部署拓扑：当前部署从 Netlify 改为 Zeabur；目标部署（OBS+CDN）保留为未来选项 |
| `personal-assistant-meta/architecture/overall_architecture.md` | 更新部署相关引用 |

### 5. 创建 ADR（可选）

若 Zeabur 选型需要正式决策记录，新建 `ADR-016-zeabur-frontend-hosting.md`，记录方案对比和选型理由。

## 影响的文件

| 文件 | 变更 |
|------|------|
| `zbpack.json`（仓库根） | **新增** — Zeabur monorepo 构建配置 |
| `personal-assistant-client/Caddyfile` | **新增** — API 认证代理 + SPA fallback |
| `personal-assistant-client/netlify.toml` | 保留（后续移除） |
| `personal-assistant-client/netlify/edge-functions/invocations.ts` | 保留（后续移除） |
| `personal-assistant-meta/architecture/frontend_architecture.md` | 更新 §6 部署拓扑 |
| `personal-assistant-meta/architecture/overall_architecture.md` | 更新部署引用 |
| `personal-assistant-meta/architecture/ADR/ADR-016-zeabur-frontend-hosting.md` | **新增**（可选）— 选型决策记录 |

## 预期结果

- Web Chat 前端通过 Zeabur 自定义域名访问，与后端 AgentArts Gateway 通过 Caddy reverse proxy 实现同源部署（零跨域、零预检拦截）
- API Key 仅存在于 Zeabur 服务端环境变量和 Caddyfile 中，不出现在浏览器
- `git push` 后 Zeabur 自动构建并部署，无需手动 `obsutil cp` 或 Netlify CI
- Netlify 配置保留作为备用回退，Zeabur 稳定运行后可移除
