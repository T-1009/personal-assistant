---
status: backlog
---

# Refactor 2: 移除 Web Chat 同容器静态文件 serve

移除 FastAPI 容器中 Web Chat 前端构建产物的 `StaticFiles` mount，后端回归纯 API + Chainlit Playground。Web Chat 前端直接走 OBS 独立部署。

## 背景

Phase 1 部署策略中，Web Chat 的 Vite build 产物通过 `StaticFiles` mount 在 FastAPI 容器根路径 `/` 上 serve，实现同容器前后端一体化。Feature 1.4 引入 Chainlit Playground（`/playground`）后，同容器已有 Python 原生的调试/对话 UI，不再需要 Web Chat 前端也打包进容器：

- **Chainlit** 覆盖了同容器的对话 UI 需求（开发调试、Agent 链路验证、运维访问）
- **Web Chat** 维护同容器 serve 中间态带来不必要的耦合——测试依赖 `dist/` 目录存在、Dockerfile 需 COPY 前端构建产物、后端代码被迫感知前端路径
- Web Chat 的最终部署目标是 OBS + CDN（Phase 2/3），跳过 Phase 1 中间态消除冗余

## 范围

- `personal-assistant-service/app/main.py`：移除 `StaticFiles` mount + `SPAFallbackMiddleware` + `STATIC_DIR` 解析逻辑
- `personal-assistant-service/Dockerfile`：移除 `COPY personal-assistant-client/dist/ ./dist/`
- `personal-assistant-service/tests/test_main.py`：移除 `TestStaticFileDualPathDiscovery` 测试类（8 个依赖 `dist/` 的用例）
- `personal-assistant-meta/architecture/backend_architecture.md`：Container 路由图移除静态文件 serve
- `personal-assistant-meta/architecture/frontend_architecture.md`：§6.2 Phase 1 改为 Chainlit-only，移除 Web Chat 同容器 serve 描述
- `personal-assistant-meta/architecture/overall_architecture.md`：如有引用需同步更新

## 不涉及

- Chainlit Playground (`/playground`) — 保持不变，继续作为同容器调试 UI
- Web Chat 前端代码 (`personal-assistant-client/`) — 不受影响，独立构建部署
- API 路由 (`/ping`, `/invocations`, `/chat/stream`, `/auth/callback`, `/feishu/webhook`) — 不受影响

## 影响

- 后端不再依赖前端构建产物，消除测试与 `dist/` 目录的耦合
- Docker 镜像体积减小（不再包含 Vite build 产物）
- 本地开发时前端通过 `npm run dev` 独立启动，后端通过 `uvicorn` 独立启动，互不依赖
- FastAPI 容器路由简化为 API + Chainlit，不再 mount 前端静态文件

## 关联文档

- [Feature 1.4 Chainlit Playground](../features/resolved/feature-1.4-chainlit-playground/issue.md)
- [Feature 1.1 Web Chat 前端工程化](../features/resolved/feature-1.1-web-chat-frontend/issue.md)
- [前端架构 §6.2 部署拓扑](../../architecture/frontend_architecture.md)
- [后端架构 §1-2](../../architecture/backend_architecture.md)
