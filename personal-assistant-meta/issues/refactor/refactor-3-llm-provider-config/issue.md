---
status: backlog
---

# Refactor 3: 重构 LLM Provider 配置体系

对 Feature 1.3 引入的 LLM Provider 配置进行系统性重构，解决配置碎片化问题：建立 Provider 静态配置规范、引入动态路由选择机制、切换默认 Provider 为 DeepSeek、淘汰旧版不合理环境变量。

---

## 背景

Feature 1.3（[issue](../features/resolved/feature-1.3-multi-llm-provider/issue.md)）引入了多 LLM Provider 可配置架构（[ADR-011](../../architecture/ADR/ADR-011-multi-llm-provider.md)），实现了 `config.yaml` + `llm_config.py` 的声明式配置体系。但当前实现存在四个问题：

### 问题 1：静态配置不完整

当前 `config.yaml` 的 provider 定义只包含 `base_url`、`api_key_env`、`model` 三个字段，缺少生产级必需的配置项：

```yaml
# 现状 — 仅三个字段
llm:
  providers:
    deepseek:
      base_url: https://api.deepseek.com
      api_key_env: DEEPSEEK_API_KEY
      model: deepseek-chat
```

缺失的关键字段：

| 字段 | 缺失影响 |
|------|----------|
| `temperature` / `top_p` | 无法按 provider 调参 |
| `max_tokens` | 无法限制 token 消耗 |
| `timeout` | 无法控制请求超时 |
| `capabilities` | 无法标记 provider 能力（vision、tools、streaming），导致动态路由无法决策 |
| `weight` | 无法控制多 provider 间的负载分配优先级 |
| `extra_headers` | 无法注入自定义请求头（某些 provider 需要） |

### 问题 2：无动态选择机制

`agent_handler.py` 初始化时调用 `get_model()` 不带 `provider` 参数，整个 Agent 生命周期绑定单一 provider。无法实现：

- **按任务类型选 provider**：简单闲聊用便宜的 DeepSeek，复杂推理/vision 用更强的模型
- **故障切换（failover）**：主 provider 不可用时自动降级到备用
- **成本优化路由**：根据预估 token 消耗选择最经济的 provider

当前 `llm_config.py` 有一个跨 provider API key fallback（当 default provider 的 key 未设置时扫描其他 provider），但这只是**初始化时的一次性回退**，不是运行时的动态路由。

### 问题 3：默认 Provider 不合理

当前 `llm.default: maas`。MaaS 需要华为内网/VPN 才能访问，作为默认 provider 导致：
- 无 VPN 环境下服务启动即失败（API key 未设置 → fallback 扫描 → 报错）
- 本地开发必须配置 VPN，增加开发环境搭建成本
- DeepSeek 公网可达、API 兼容、价格低廉，更适合作为默认选项

### 问题 4：旧版环境变量未彻底淘汰

Feature 1.3 设计为 `config.yaml` 存在时优先使用声明式配置，不存在时 fallback 到旧版三个环境变量（`MODEL_API_KEY`、`MODEL_NAME`、`MODEL_URL`）。这导致：

| 位置 | 残留 | 问题 |
|------|------|------|
| `llm_config.py:108-125` | fallback 逻辑 | 两套代码路径，增加维护负担和测试复杂度 |
| `.agentarts_config.yaml:33-38` | `MODEL_API_KEY` / `MODEL_NAME` / `MODEL_URL` env var | 部署时注入无用环境变量，占位值含硬编码 API key 明文 |
| `.env.example:12-14` | 旧版兼容变量注释 | 新开发者可能误以为这些变量仍在使用 |

现在 `config.yaml` 已经稳定使用，旧版 fallback 可以安全移除。

---

## 范围

### 4.1 静态配置增强

- [ ] `config.yaml` provider 定义扩展以下字段（均为可选，有合理默认值）：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `base_url` | str | **必填** | OpenAI-compatible API 端点 |
| `api_key_env` | str | **必填** | API key 对应的环境变量名 |
| `model` | str | **必填** | 模型名称 |
| `temperature` | float | `0.7` | 采样温度 |
| `top_p` | float | `1.0` | nucleus sampling |
| `max_tokens` | int | `4096` | 最大输出 token 数 |
| `timeout` | int | `60` | 请求超时（秒） |
| `capabilities` | list[str] | `[]` | 能力标签：`vision`、`tools`、`streaming`、`reasoning` |
| `weight` | int | `1` | 动态路由权重（越大越优先） |
| `extra_headers` | dict | `{}` | 自定义 HTTP 请求头 |

- [ ] `llm_config.py` 的 `get_model()` 读取并使用以上新字段，传递给 `init_chat_model()` 的对应参数

### 4.2 动态选择机制

- [ ] 新增 `app/llm_router.py`：动态路由模块
  - 输入：任务需求（capabilities required）
  - 输出：选中的 provider name
  - 策略：基于 `capabilities` 匹配 + `weight` 加权随机（简单有效，不引入外部依赖）
- [ ] 修改 `agent_handler.py`：每次 `handle()` 调用时根据任务特征动态选 provider，而非初始化时固定
  - 短期：基于简单启发式（如消息中是否包含图片/文件 → vision capability）
  - 长期：可扩展为意图识别后路由
- [ ] 新增 `config.yaml` 的 `llm.routing` 配置段，定义路由策略

```yaml
llm:
  default: deepseek
  routing:
    strategy: capability_match    # capability_match | weighted_random | fixed
    fallback_on_error: true       # 主 provider 报错时自动切换
  providers:
    deepseek:
      capabilities: [tools, streaming, reasoning]
      weight: 10
    doubao:
      capabilities: [vision, tools, streaming]
      weight: 5
```

### 4.3 默认 Provider 切换为 DeepSeek

- [ ] `config.yaml`：`llm.default` 从 `maas` 改为 `deepseek`
- [ ] `architecture/overall_architecture.md` 技术选型表：LLM 默认行更新
- [ ] `specs/overall_specifications.md` §6.1 场景表：默认推荐 provider 更新

### 4.4 淘汰旧版配置

- [ ] `llm_config.py`：删除第 108-125 行的 fallback 代码路径（`MODEL_URL` / `MODEL_API_KEY` / `MODEL_NAME` 环境变量读取逻辑）
  - 简化 `get_model()`：`config.yaml` 不存在时直接抛 `ValueError`（而非静默 fallback），引导新开发者正确配置
- [ ] `.agentarts_config.yaml`：删除 `MODEL_API_KEY`、`MODEL_NAME`、`MODEL_URL` 三个 environment_variables 条目（第 33-38 行）
- [ ] `.env.example`：删除第 11-14 行旧版兼容变量段
- [ ] 确保所有 CI/部署流程已切换到新配置方式，不受删除影响

---

## 不涉及

- 非 OpenAI-compatible 协议的 provider（Anthropic、Gemini 等）— 不属于本次重构范围
- Provider 健康检查独立服务 — 简单 call 失败 → fallback 即可，不需要独立的 health check probe
- 运行时动态添加/删除 provider（reload config）— 后续 feature
- 多模态自动分流（自动判断是否需要 vision 模型）— 后续 feature，本次只建基础设施（`capabilities` 字段）
- MaaS provider 删除 — 保留配置，仅切换默认值

---

## 影响

### 修改文件

| 文件 | 改动 |
|------|------|
| `personal-assistant-service/config.yaml` | 扩展 provider 字段 + 新增 `routing` 段 + `default` 改为 `deepseek` |
| `personal-assistant-service/app/llm_config.py` | `get_model()` 读取新字段传给 `init_chat_model()`；删除旧版 fallback |
| `personal-assistant-service/app/llm_router.py` | **新增**：动态路由模块 |
| `personal-assistant-service/app/agent_handler.py` | `AgentHandler` 支持每次调用时动态选 provider |
| `personal-assistant-service/.agentarts_config.yaml` | 删除 `MODEL_API_KEY` / `MODEL_NAME` / `MODEL_URL` 三个 env var |
| `personal-assistant-service/.env.example` | 删除旧版兼容变量段 |
| `personal-assistant-meta/architecture/overall_architecture.md` | §6 LLM Provider 配置更新 |
| `personal-assistant-meta/architecture/backend_architecture.md` | Agent 处理逻辑更新（动态路由） |
| `personal-assistant-meta/specs/overall_specifications.md` | §6 LLM Provider 管理更新 |
| `personal-assistant-meta/specs/dictionary.md` | 更新 LLM Provider 术语、新增路由相关术语 |
| `personal-assistant-meta/architecture/ADR/ADR-011-multi-llm-provider.md` | 标注 amend：默认 provider 变更 + 旧版 env var 移除 |

### 测试影响

- `llm_config.py` 单测：扩展测试用例覆盖新字段、删除 fallback 路径测试
- 新增 `llm_router.py` 单测：capability 匹配、fallback、权重随机
- `agent_handler.py` 测试：验证动态路由集成

---

## 任务拆解

### 3.1 静态配置字段扩展
- [ ] `config.yaml`：每个 provider 增加 `temperature`、`top_p`、`max_tokens`、`timeout`、`capabilities`、`weight`、`extra_headers` 可选字段
- [ ] `llm_config.py`：`get_model()` 读取新字段并传给 `init_chat_model()`
- [ ] 单元测试：覆盖新字段读取和传递

### 3.2 动态路由模块
- [ ] 新增 `app/llm_router.py`：`route(config, requirements) -> provider_name` 函数
- [ ] `config.yaml` 新增 `llm.routing` 配置段
- [ ] 单测：capability 匹配正确、fallback 逻辑正确、无匹配时 fallback 到 default

### 3.3 AgentHandler 动态选择
- [ ] `agent_handler.py`：`__init__()` 不再绑定单一 model；`handle()` / `handle_stream()` 中按需调用 `llm_router.route()` + `get_model(provider)`
- [ ] 确保 SSE 流式响应正常工作（model 切换不影响 stream 事件结构）

### 3.4 默认 Provider 切换
- [ ] `config.yaml`：`llm.default: deepseek`
- [ ] 架构/规格文档同步更新

### 3.5 淘汰旧版环境变量
- [ ] `llm_config.py`：删除 fallback 代码路径（第 108-125 行）
- [ ] `.agentarts_config.yaml`：删除 `MODEL_API_KEY` / `MODEL_NAME` / `MODEL_URL`
- [ ] `.env.example`：删除旧版兼容变量段

### 3.6 文档更新
- [ ] `overall_architecture.md` §6 更新
- [ ] `backend_architecture.md` 更新
- [ ] `overall_specifications.md` §6 更新
- [ ] `dictionary.md` 更新
- [ ] `ADR-011` amend 标注

### 3.7 验证
- [ ] 默认 DeepSeek provider 对话正常
- [ ] 显式指定 maas provider 对话正常（VPN 环境）
- [ ] `config.yaml` 缺失时明确报错（不静默 fallback）
- [ ] 旧版 `MODEL_API_KEY` 等 env var 设值后不再生效
- [ ] 动态路由：vision 任务选 doubao，其他选 deepseek（capability match）
- [ ] Provider 故障时自动 fallback 到备用 provider

---

## 依赖

- Feature 1.3（多 LLM Provider 可配置）— 已 resolved，`config.yaml` + `llm_config.py` 已存在
- Feature 1（Agent 骨架）— `agent_handler.py` 已存在

---

## 参考

- [ADR-011: 多 LLM Provider 可配置架构](../../architecture/ADR/ADR-011-multi-llm-provider.md) — 本次重构对此 ADR 进行 amend
- [ADR-005: MaaS LLM 推理平台](../../architecture/ADR/ADR-005-maas-llm-platform.md)
- [Feature 1.3 issue](../features/resolved/feature-1.3-multi-llm-provider/issue.md)
- [12-Factor App: Config](https://12factor.net/config)
- [langchain-openai `init_chat_model()`](https://python.langchain.com/docs/integrations/chat/)
