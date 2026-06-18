# Personal Assistant Client

Personal Assistant 的 Web Chat 前端应用，负责用户登录、对话界面、SSE 流式消息渲染和 Markdown 内容展示。当前生产主入口为 Web Chat；飞书和 OfficeClaw 渠道仍在规划中。

Vite + React + TypeScript + Tailwind CSS + assistant-ui。支持 OAuth 登录（Microsoft Entra ID）、登录落地页和聊天界面，并在请求后端时传递 `Authorization` 与 `x-hw-agentarts-session-id`，配合 AgentArts Gateway 完成 Inbound Identity。

## 目录结构

```
personal-assistant-client/
├── src/
│   ├── components/
│   │   ├── assistant-ui/             # assistant-ui 组件（thread, markdown-text, reasoning, attachment 等）
│   │   ├── ui/                       # shadcn/ui 基础组件（button, dialog, avatar, tooltip, collapsible）
│   │   ├── landing/                  # 登录落地页组件（LandingPage, LandingHero, FeatureTile 等）
│   │   ├── chat/                     # 聊天界面组件（ChatPage）
│   │   ├── RuntimeProvider.tsx       # assistant-ui RuntimeProvider 包装
│   │   ├── LoginButton.tsx           # OAuth 登录按钮
│   │   └── AuthGuard.tsx             # 认证守卫组件
│   ├── stores/
│   │   └── auth-store.ts            # 认证状态管理（MSAL）
│   ├── lib/
│   │   ├── chat-adapter.ts           # assistant-ui ChatModelAdapter（fetch POST + SSE）
│   │   ├── auth.ts                   # MSAL 认证配置
│   │   └── utils.ts                  # 工具函数（cn 等）
│   ├── types/
│   │   └── chat.ts                   # Message、SSEEvent 类型定义
│   ├── test/
│   │   └── setup.ts                  # Vitest 测试配置
│   ├── App.tsx                       # 根组件
│   ├── main.tsx                      # React 入口
│   ├── index.css                     # Tailwind 入口 + 自定义动画
│   └── vite-env.d.ts                # Vite 类型声明
├── functions/
│   └── api/invocations.js           # Cloudflare Pages Function，透传 JWT + SSE
├── index.html                     # Vite 入口 HTML
├── vite.config.ts                 # Vite 配置（代理 + React 插件 + Tailwind CSS）
├── wrangler.toml                  # Cloudflare Pages 项目配置
├── tsconfig.json                  # TypeScript 配置
├── tsconfig.node.json             # Vite 配置文件 TypeScript 配置
├── package.json                   # 项目依赖与 scripts
├── DESIGN.md                      # 前端设计文档
└── .gitignore
```

## 环境要求

- Node.js >= 18
- npm >= 9

## 快速开始

### 1. 安装依赖

```bash
npm ci
```

### 2. 启动开发服务器

```bash
npm run dev
```

开发服务器默认监听 `http://localhost:5173`，`/api/*` 请求通过 Vite proxy 转发到 FastAPI（`http://localhost:8080`）。

确保后端服务已启动：

```bash
# 在 personal-assistant-service/ 下
uv run uvicorn app.main:app --port 8080 --reload
```

LLM API Key 通过 AgentArts Identity 的 `DEEPSEEK_API_KEY` Credential Provider 注入，不再通过前端或后端环境变量传递。

### 3. 打开浏览器

访问 `http://localhost:5173` 进入 Web Chat 对话界面。

## 构建

### 开发构建

```bash
npm run build
```

产出 `dist/` 目录。生产环境部署至 Cloudflare Pages，不再由 FastAPI
StaticFiles 服务。

### 预览构建产物

```bash
npm run preview
```

### Cloudflare Pages 本地预览

```bash
npm run pages:dev
```

该命令先构建 Vite，再通过 Wrangler 启动静态站点与 Pages Functions。

### Cloudflare Pages 部署

```bash
npx wrangler login
npm run pages:deploy
```

Production deployment 通常由
`.github/workflows/deploy-frontend-to-cloudflare.yml` 自动执行：`main` branch
中的 Client 相关文件变化后，GitHub Actions 会运行 tests、build 和 Wrangler
deployment。Workflow 使用 repository secrets `CLOUDFLARE_API_TOKEN` 与
`CLOUDFLARE_ACCOUNT_ID`。

首次部署后，将实际的
`https://<cloudflare-project>.pages.dev/` 添加到 Microsoft Entra SPA
Redirect URI。

当前 production URL：

```text
https://agentarts-personal-assistant.pages.dev
```

## 测试

```bash
# 运行全部测试
npm test

# watch 模式
npm run test:watch
```

## 技术栈

| 组件 | 技术 |
|------|------|
| 构建工具 | Vite 6 |
| UI 框架 | React 19 + assistant-ui 0.14 |
| 语言 | TypeScript 5.8 (strict) |
| 样式 | Tailwind CSS 4 + shadcn/ui |
| Markdown 渲染 | @assistant-ui/react-markdown |
| 测试 | Vitest + @testing-library/react |

## 架构

```
浏览器 ──GET /──→ Vite Dev Server (:5173) ──proxy /invocations──→ FastAPI (:8080)
  │                    │                                    │
  │  React App         │                                    │
  │  ├─ RuntimeProvider │                                    │
  │  │  └─ Thread       │                                    │
  │  │     └─ assistant-ui markdown / reasoning              │
  │  ├─ LoginPlaceholder│                                    │
  │  └─ assistant-ui runtime ─┘── fetch POST + SSE ───────→ /invocations
  │
  └── 生产模式 ── Cloudflare Pages ── /api/invocations Function ──→ AgentArts Gateway
```

## SSE 协议

前端通过 `fetch` 向 `POST /invocations` 发送 `{"message":"...","stream":true}`，并消费响应体中的 SSE 流：

```
data: {"token":"你","done":false}

data: {"token":"好","done":false}

data: {"token":"","done":true}
```

- `token`：当前 token 文本
- `done`：`true` 表示流结束

## 后续 Feature

| Feature | 内容 | 状态 |
|---------|------|------|
| Feature 4 | OAuth 登录 UI（MSAL + Microsoft Entra ID） | 已实现 |
| Feature 5 | 飞书客户端适配 | [Planned — not yet implemented] |
| Feature 3 | OfficeClaw 客户端适配 | [Planned — not yet implemented] |
