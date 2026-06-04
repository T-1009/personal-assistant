# Architecture Decision Records (ADR)

Personal Assistant 项目的架构决策记录。采用 [Michael Nygard 的 ADR 格式](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)。

## 决策列表

| 编号 | 标题 | 状态 | 决策 |
|------|------|------|------|
| [ADR-001](ADR-001-python-3.12.md) | Python 3.12 作为运行时 | Accepted | 使用 Python 3.12 替代即将 EOL 的 3.10 |
| [ADR-002](ADR-002-langgraph.md) | LangGraph 作为 Agent 编排框架 | Accepted | 使用 LangGraph StateGraph 实现 Agent 推理循环 |
| [ADR-003](ADR-003-agentarts-platform.md) | AgentArts 平台作为基础设施 | Accepted | 全面采用 AgentArts（Memory/Identity/Gateway/Sandbox） |
| [ADR-004](ADR-004-fastapi-over-agentarts-runtime-app.md) | FastAPI 替代 AgentArtsRuntimeApp | Accepted | 标准 FastAPI 获取更多路由自由度 |
| [ADR-005](ADR-005-maas-llm-platform.md) | 华为云 MaaS 作为 LLM 推理平台 | Accepted | MaaS 平台 + DeepSeek-V4-Pro，模型可替换 |
| [ADR-006](ADR-006-iac-cdktf-typescript.md) | 基础设施即代码（IaC）工具选型 | Accepted | AgentArts 层用 agentarts_config.yaml，基础资源层用 CDKTF (TypeScript) |

## 决策原则

1. **平台优先** — 优先使用 AgentArts 和华为云原生能力，展示平台完整链路
2. **可展示性** — 选型需体现 Agent 工程最佳实践，具简历展示价值
3. **简单够用** — 不引入超出当前需求的复杂度，保持架构清晰
