---
status: backlog
---

# Feature 1.3: 多 LLM Provider 可配置

引入多 LLM Provider 声明式配置架构，使 Agent 支持 MaaS（默认）和 DeepSeek 官方两个 provider，按需切换。本 Feature 在 Feature 1（Agent 骨架）完成后执行，依赖 1.6（MaaS 模型连接）已跑通。

---

## 背景

ADR-005 确定了 MaaS 作为 LLM 推理平台。随着项目演进，出现两个新需求：

1. **开发灵活性**：在家办公或无 VPN 时 MaaS 不可达，需要公网可达的 provider 作为备选
2. **多 Provider 共存**：不同任务适合不同 provider（MaaS 生产、DeepSeek 低成本长尾任务）

两个 provider 均使用 OpenAI-compatible API，切换成本极低——只需换 `base_url` 和 `api_key`。

详见 [ADR-011](../../architecture/ADR/ADR-011-multi-llm-provider.md)。

## 范围

- 新增 `config.yaml`（项目根目录），声明 `llm.providers` 及 `llm.default`
- 新增 `app/llm_config.py`：配置加载模块，暴露 `get_model(provider: str = None) -> BaseChatModel`
- 修改 `app/agent_handler.py`：`init_chat_model()` 硬编码调用改为 `llm_config.get_model()`
- 修改 `agentarts_config.yaml`：新增 `DEEPSEEK_API_KEY` env var；保留 `MODEL_URL` / `MODEL_API_KEY` / `MODEL_NAME` 作为 `maas` provider 的 fallback
- 更新相关架构/规格文档

## 不涉及

- 非 OpenAI-compatible 协议的 provider（如 Anthropic、Gemini）
- 运行时动态路由（按任务类型自动选 provider）
- Provider 健康检查 / 故障切换

## 任务拆解

### 1.3.1 config.yaml 配置文件

- [ ] 项目根目录新增 `config.yaml`
- [ ] 结构：`llm.default` + `llm.providers.<name>.{base_url, api_key_env, model}`
- [ ] 声明两个 provider：
  - `maas`：base_url `https://api.modelarts-maas.com/openai/v1`，api_key_env `MAAS_API_KEY`，model `deepseek-v4-pro`
  - `deepseek`：base_url `https://api.deepseek.com`，api_key_env `DEEPSEEK_API_KEY`，model `deepseek-chat`

### 1.3.2 llm_config.py 配置加载模块

- [ ] 新增 `app/llm_config.py`
- [ ] 读取 `config.yaml` + 对应环境变量
- [ ] 暴露 `get_model(provider: str = None) -> BaseChatModel`
  - `provider=None` 时使用 `llm.default`
  - 从 provider 配置中取 `base_url`、`api_key`（通过 `api_key_env` 对应的环境变量）、`model`
  - 调用 `init_chat_model()` 返回 LangChain BaseChatModel

### 1.3.3 agent_handler.py 改造

- [ ] `create_deep_agent()` 中的 `init_chat_model()` 硬编码调用替换为 `llm_config.get_model()`
- [ ] 默认不传 `provider` 参数，使用 `llm.default`（即 MaaS）

### 1.3.4 agentarts_config.yaml 更新

- [ ] 新增 `DEEPSEEK_API_KEY` env var 声明
- [ ] `MODEL_URL` / `MODEL_API_KEY` / `MODEL_NAME` 保持声明，作为 `maas` provider 未配置 `config.yaml` 时的 fallback

### 1.3.5 架构/规格文档更新

- [ ] `architecture/overall_architecture.md`：技术选型表 LLM 行更新
- [ ] `architecture/backend_architecture.md`：Agent 处理逻辑代码示例更新
- [ ] `specs/overall_specifications.md`：新增 LLM Provider 小节
- [ ] `specs/dictionary.md`：新增 LLM Provider 术语

### 1.3.6 开发环境文档更新

- [ ] `architecture/devops/local-development.md`：环境变量一览增加 DeepSeek 配置

### 1.3.7 验证

- [ ] 默认 provider（MaaS）对话正常
- [ ] 切到 DeepSeek 官方 provider 对话正常
- [ ] `config.yaml` 未配置时，fallback 到 `MODEL_URL` / `MODEL_API_KEY` / `MODEL_NAME` 仍可工作
- [ ] 多轮对话在两个 provider 下均不崩溃

## 依赖

- Feature 1（Agent 骨架）：`agent_handler.py`、`agentarts_config.yaml` 已存在，MaaS 连接已验证

## 参考

- [ADR-011: 多 LLM Provider 可配置架构](../../architecture/ADR/ADR-011-multi-llm-provider.md)
- [ADR-005: MaaS LLM 推理平台](../../architecture/ADR/ADR-005-maas-llm-platform.md)
- [DeepSeek API 文档](https://api-docs.deepseek.com/)
- [12-Factor App: Config](https://12factor.net/config)
