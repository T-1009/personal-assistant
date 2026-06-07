---
status: backlog
---

# Feature 1.4: Chainlit Playground 调试工具

在 FastAPI 容器内挂载 Chainlit，作为同容器的 Python 原生 Agent 调试 UI。路径 `/playground`，与 Web Chat（Vite + React）长期共存。

---

## 背景

Feature 1 验证了 Agent 骨架和 SSE 流式对话链路，但调试 Agent 推理过程只能用 curl 看原始 SSE 输出——看不到推理步骤、tool 调用、中间状态。Feature 1.1 的 Vite + React 是面向最终用户的完整 UI，但在开发调试阶段需要一套更轻量的方案：

- **零构建**：不需要 `npm run dev` / `npm run build`，`chainlit run` 即用
- **同语言**：Python 原生，与后端同一进程，共享 `agent_handler`
- **Agent 可观测**：Chainlit 内置 LangChain callback，直接展示每一步推理（think → act → observe）

Chainlit 定位为**调试工具**，不是生产用户界面。挂载路径 `/playground` 避免与 `/chat`（未来 OAuth 登录后的用户入口）冲突。

详见 `architecture/frontend_architecture.md` §2.1.1。

## 范围

- 安装 Chainlit（`chainlit` pip package）
- 创建 `app/playground.py`：Chainlit app，挂接 `agent_handler`
- FastAPI mount：`/playground` → Chainlit app（与 API 路由共存）
- 验证：打开 `/playground` 可对话，观察 Agent 推理步骤

## 不涉及

- Chainlit 自定义 UI/主题（用默认即可）
- Chainlit 认证/授权（容器内部调试，无需 OAuth）
- Chainlit 替代 Web Chat（两者共存，Chainlit 仅调试用）
- `/playground` 暴露到 CDN（仅容器内部直连访问）

## 任务拆解

### 1.4.1 安装 Chainlit

- [ ] `uv add chainlit` 添加到 `pyproject.toml`
- [ ] 验证：`chainlit --version` 正常

### 1.4.2 创建 Chainlit app

- [ ] 新增 `app/playground.py`
- [ ] `@cl.on_chat_start`：初始化 session，注入欢迎消息
- [ ] `@cl.on_message`：调用 `agent_handler.handle()`，通过 `cl.Message.stream_token()` 流式输出
- [ ] 复用 Feature 1 的 `agent_handler`，不重复实现 Agent 逻辑

### 1.4.3 FastAPI mount

- [ ] 修改 `app/main.py`：确保 Chainlit app 挂载在 `/playground`
  - 注意路径优先级：Chainlit 的 websocket 路由不能被子路径拦截
  - 参考 Chainlit 文档的 FastAPI 集成方式

### 1.4.4 验证

- [ ] `uv run chainlit run app/playground.py` → 浏览器打开 → 看到 Chainlit UI
- [ ] 输入消息 → Agent 回复正常，流式渲染正常
- [ ] FastAPI 同容器模式下 `/playground` 可访问，`/ping` 仍正常
- [ ] Web Chat（`/` 和 `/api/chat/stream`）不受影响

## 依赖

- Feature 1（Agent 骨架）：`agent_handler.py` + SSE 链路已验证

## 可并行

- Feature 1.1（Web Chat 前端工程化）
- Feature 1.2（PostgreSQL）
- Feature 1.3（多 LLM Provider）

## 参考

- `architecture/frontend_architecture.md` §2.1.1
- [Chainlit 文档 — FastAPI 集成](https://docs.chainlit.io/deploy/fastapi)
- [Chainlit 文档 — LangChain 集成](https://docs.chainlit.io/integrations/langchain)
