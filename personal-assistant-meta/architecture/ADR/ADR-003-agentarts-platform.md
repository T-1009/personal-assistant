# ADR-003: AgentArts 平台作为基础设施

> 状态：Accepted | 日期：2026-06-03

---

## 背景

Personal Assistant 需要以下基础设施能力：

- **Runtime**：容器化部署，ARM64 架构，自动扩缩容
- **Memory**：短期对话记忆 + 长期偏好/事实/情景记忆
- **Identity**：Inbound 用户认证（JWT/API Key） + Outbound 服务认证（OAuth2/M2M/STS）
- **MCP Gateway**：API 定义转 MCP Tool，供 Agent 调用
- **Sandbox**：安全隔离的代码执行环境
- **Observability**：Tracing + Logging + Metrics

有两种路径：自建（开源组件拼装）或使用平台服务。

## 决策

**全面采用 AgentArts 平台（华为云智果）。**

选择依据：

| 因素 | 分析 |
|------|------|
| **战略定位** | 本项目是华为云内部项目，目标是**展示 AgentArts 平台能力**和**华为云技术栈**的端到端应用 |
| **Memory** | AgentArts Memory SDK 提供语义/偏好/情景三种记忆策略，开箱即用，无需自建向量数据库和抽取 Pipeline |
| **Identity** | Inbound 认证（Custom JWT/API Key） + Outbound Federation（OAuth2/M2M/STS）统一管理，降低安全实现复杂度 |
| **MCP Gateway** | API 定义自动转 MCP Tool，减少工具适配代码量 |
| **Observability** | 平台内置 OTEL，无需自建可观测性基础设施 |
| **部署** | `agentarts launch` 一键构建 ARM64 镜像并部署，CI/CD 成本最低 |

### 项目定位声明

> Personal Assistant 是一个 **AgentArts 平台示范项目**。技术选型优先考虑 AgentArts 和华为云原生能力，展示平台从开发到部署的完整链路。

## 拒绝的方案

### 自建（开源组件拼装）

- Memory → ChromaDB/Milvus + 自建抽取 Pipeline
- Identity → Auth0/Keycloak + 自建 Token 管理
- Runtime → K8s/Docker Compose 自运维

拒绝理由：
- 与本项目"展示华为云能力"的定位矛盾
- 运维成本高，偏离 Agent 核心逻辑的开发
- Memory/Identity 的自建方案无法体现平台价值

## 影响

- **平台绑定**：Memory、Identity、Sandbox、MCP Gateway 均依赖 AgentArts。如果未来需要迁移，这些模块需要重写。
- **接受绑定**：这是有意识的选择，不是技术债务。项目定位决定了平台绑定是特点而非缺陷。
- **开发依赖**：本地开发时需要 AgentArts 平台连接（Memory Space、Identity Provider 需预配置）
- 架构文档中保留平台选型说明，明确这是面向 AgentArts 生态的示范项目

## 参考

- AgentArts Runtime 部署文档
- AgentArts Memory SDK 文档
- AgentArts Identity SDK 文档
- AgentArts MCP Gateway 文档
