# Personal Assistant Service

基于 [AgentArts](https://www.huaweicloud.com/product/agentarts.html) 平台的 AI Agent 后端服务。处理对话逻辑、日程/邮件/笔记/任务管理，支持非流式与 SSE 流式两种对话模式。

## 目录结构

```
personal-assistant-service/
├── app/
│   ├── __init__.py          # Python 包标记
│   ├── main.py              # FastAPI 应用入口 + 路由定义
│   ├── agent_handler.py     # deepagents Agent 编排 + MaaS 模型连接
│   ├── llm_config.py        # LLM 多模型配置管理
│   ├── auth.py              # Inbound 认证中间件（JWT / API Key）
│   └── playground.py        # Chainlit Playground 挂载
├── tests/
│   ├── __init__.py
│   ├── test_main.py         # FastAPI 端点集成测试
│   ├── test_agent_handler.py # AgentHandler 单元测试
│   ├── test_llm_config.py   # LLM 配置管理测试
│   ├── test_auth.py         # 认证中间件测试
│   ├── test_checkpointer.py # Checkpoint 持久化测试
│   └── test_playground.py   # Chainlit Playground 测试
├── scripts/                 # 运维脚本（部署、冒烟测试等）
├── config.yaml              # LLM Provider 配置（多 provider 声明式管理）
├── openapi.json             # OpenAPI 规范（自动生成）
├── pyproject.toml           # 项目元数据 + 依赖 (uv)
├── uv.lock                  # 确定性依赖锁定
├── Dockerfile               # ARM64 容器镜像
├── .agentarts_config.yaml   # AgentArts 平台部署配置
└── .dockerignore
```

## 环境要求

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/)（包管理）
- Docker（可选，容器化部署）

## 快速开始

### 1. 安装依赖

```bash
uv sync
```

### 2. 设置环境变量

```bash
export MAAS_API_KEY="<your-maas-api-key>"
```

> 当 `config.yaml` 存在时，LLM Provider 配置由 `config.yaml` 管理（详见 [ADR-011](../personal-assistant-meta/architecture/ADR/ADR-011-multi-llm-provider.md)），此时需设置 `MAAS_API_KEY`（maas provider）或 `DEEPSEEK_API_KEY`（deepseek provider）。
>
> 若无 `config.yaml`，系统会 fallback 读取旧版环境变量：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MODEL_API_KEY` | **必需**（fallback 模式） | MaaS API Key |
| `MODEL_NAME` | `deepseek-v4-pro` | 模型名称 |
| `MODEL_URL` | `https://api.modelarts-maas.com/openai/v1` | MaaS API 地址 |

### 3. 启动服务

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

### 4. 打开浏览器

访问 `http://localhost:8080/invocations/playground` 进入 Chainlit 调试界面。API 端点见下方。

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/ping` | 健康检查，返回 `{"status":"ok"}` |
| `POST` | `/invocations` | 统一对话入口；不传 `stream` 或 `stream:false` 返回 JSON，`stream:true` 返回 SSE |

### 示例

```bash
# 健康检查
curl http://localhost:8080/ping

# 非流式对话
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"message":"你好"}'

# SSE 流式对话
curl -N -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"message":"你好","stream":true}'
```

### SSE 数据格式

```
data: {"token":"你","done":false}

data: {"token":"好","done":false}

data: {"token":"","done":true}
```

## Docker

### 构建镜像

```bash
docker build --platform linux/arm64 -t personal-assistant:dev .
```

### 运行容器

```bash
docker run --rm -p 8080:8080 -e MODEL_API_KEY="<your-key>" personal-assistant:dev
```

## 在线测试

部署到 AgentArts 后，可通过 `agentarts invoke` 命令直接测试线上 Agent：

```bash
# 通过 IAM 签名认证（AgentArts Gateway 自动处理）
agentarts invoke '{"message":"你好，简单介绍一下你自己"}' --agent personal-assistant

# 或者使用 bearer token 认证（API Key 需替换为实际值）
agentarts invoke '{"message":"hello world"}' --bearer-token <your-bearer-token>
```

> **注意**：`agentarts invoke` 自动带 IAM 签名认证，可直接通过 AgentArts Gateway 调用。裸 `curl` 命令在生产环境不可用。

## 测试

```bash
# 运行全部测试 + 覆盖率
uv run pytest tests/ -v --cov=app --cov-report=term-missing

# Lint 检查
uv run ruff check .

# 格式化检查
uv run ruff format --check .
```

## 技术栈

| 组件 | 技术 |
|------|------|
| Web 框架 | FastAPI |
| Agent 编排 | deepagents（内置 ReAct loop） |
| LLM 连接 | langchain-openai → MaaS (DeepSeek-V4-Pro) |
| 包管理 | uv |
| 代码质量 | ruff |
| 测试 | pytest + pytest-asyncio |

## 架构

```
Browser ──POST /invocations {"stream":true}──→ StreamingResponse
  │
  │  SSE 响应
  │
  │  AgentHandler.handle_stream()
  │
  │  deepagents agent.astream_events(v2)
  │
  │  MaaS LLM (DeepSeek-V4-Pro)
  │
  └── POST /invocations {"stream":false} ──→ AgentHandler.handle() → agent.ainvoke()
```

## 后续 Feature

| Feature | 内容 | 状态 |
|---------|------|------|
| Feature 2 | Memory 集成（跨 Session 记忆） | [Planned — not yet implemented] |
| Feature 3 | OfficeClaw 渠道 | [Planned — not yet implemented] |
| Feature 4 | 用户认证 / OAuth（Inbound Identity） | 已实现 |
| Feature 5 | 飞书 Client Adapter（飞书 Bot 接入） | [Planned — not yet implemented] |
| Feature 6-8 | 外部工具集成（日历/邮件/笔记/任务） | [Planned — not yet implemented] |
