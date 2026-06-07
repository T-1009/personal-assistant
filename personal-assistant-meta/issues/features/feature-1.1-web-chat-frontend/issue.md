---
status: backlog
---

# Feature 1.1: Web Chat 前端工程化

本 Feature 将 Feature 1 的 `web/index.html` 单文件前端升级为工程化前端项目，技术栈按 ADR-008 决策：Vite + React + TypeScript + Tailwind CSS。

---

## 背景

Feature 1 用单 HTML 文件快速验证了 Agent 骨架和 SSE 流式对话链路。该文件具备基本聊天功能（消息列表、文本输入、SSE 流式渲染），但缺少：

- 组件化架构（所有 UI 和逻辑塞在一个文件）
- 工程化工具链（模块打包、HMR、TypeScript）
- 样式系统（内联 CSS，无暗色模式、响应式断点）
- OAuth 登录流程（Feature 4 需要前端配合）
- 多轮对话管理、消息持久化、错误状态 UI

ADR-008 已决策 Vite + React + TypeScript + Tailwind CSS。本 Feature 将该决策落地为 `personal-assistant-client/` 项目，Feature 1 的 `web/index.html` 在本 Feature 完成后移除。

## 范围

- `personal-assistant-client/` 目录初始化（Vite + React + TypeScript + Tailwind CSS）
- 聊天主界面（消息列表 + 输入框 + SSE 流式渲染）
- 消息气泡组件（user/assistant 双色，markdown 渲染）
- 流式 token 逐字动画
- 错误状态处理（连接中断、超时、500 错误提示）
- 构建产物对接 FastAPI `StaticFiles` mount
- 开发模式代理配置（Vite dev server proxy → FastAPI）

## 不涉及

- OAuth 登录 UI（Feature 4 的前端适配，本 Feature 只预留入口）
- 飞书/OfficeClaw 客户端适配（Feature 5/3）
- 消息持久化（Feature 2 Memory 的前端配合）
- OBS/CDN 部署（Feature 9 或后续部署 Feature）

## 任务拆解

### 1.1.1 项目初始化

- [ ] `npm create vite@latest personal-assistant-client -- --template react-ts`
- [ ] 安装依赖：`tailwindcss @tailwindcss/vite`
- [ ] 配置 Tailwind（`tailwind.config.ts`，iOS 风格色板）
- [ ] 配置 Vite 代理（`/api/*` → `localhost:8080`）
- [ ] 目录结构：`src/components/`, `src/hooks/`, `src/types/`

### 1.1.2 核心组件

- [ ] `ChatContainer` — 主布局（header + messages + input）
- [ ] `MessageBubble` — 消息气泡（user 右对齐蓝色，assistant 左对齐灰色）
- [ ] `MessageList` — 消息列表容器（自动滚底、流式追加）
- [ ] `ChatInput` — 输入框（Enter 发送，Shift+Enter 换行，发送中禁用）
- [ ] `StreamingText` — 流式文本渲染（逐 token 追加 + 光标动画）

### 1.1.3 SSE 连接

- [ ] `useChat` hook — 管理 SSE 连接生命周期
  - 发送消息 → 创建 EventSource
  - 接收 token → 追加到当前 assistant 消息
  - 接收 done → 关闭连接，解锁输入
  - 接收 error → 显示错误提示，关闭连接
- [ ] 中断/重连处理（`EventSource.onerror` → 用户提示）
- [ ] 并发保护（发送新消息前关闭已有连接）

### 1.1.4 构建和集成

- [ ] `vite build` → `personal-assistant-client/dist/`
- [ ] FastAPI `StaticFiles` mount 指向 `dist/`（替换原来的 `web/`）
- [ ] 验证：`npm run dev` → 代理到 FastAPI → 聊天正常
- [ ] 验证：`npm run build` → FastAPI serve 静态文件 → 聊天正常

### 1.1.5 清理

- [ ] 删除 Feature 1 的 `personal-assistant-service/web/index.html`
- [ ] 更新 `frontend_architecture.md` 反映新前端项目路径

## 验证

- [ ] `npm run dev` → 浏览器打开 → 看到聊天界面
- [ ] 输入消息 → SSE 流式返回，逐 token 渲染
- [ ] 多轮对话不串消息、不崩溃
- [ ] 断网/服务器宕机 → 界面显示错误提示（不白屏）
- [ ] `npm run build` → FastAPI serve `dist/` → 功能同开发模式

## 依赖

- Feature 1（Agent 骨架 + `/chat/stream` SSE 端点）

## 可并行

- Feature 2（Memory 集成）— 前端和后端独立，无冲突
- Feature DB（PostgreSQL）— 独立基础设施

## 参考

- ADR-008: Web Chat 前端框架选型
- `architecture/frontend_architecture.md` #2.1 Web Chat
- `architecture/frontend_architecture.md` #6.2 部署（Phase 1 同容器 serve）
