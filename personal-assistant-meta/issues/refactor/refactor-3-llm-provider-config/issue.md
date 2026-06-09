---
status: backlog
---

# Refactor 3: 重构 LLM Provider 静态配置体系

对 Feature 1.3 引入的 LLM Provider 配置进行系统性重构，解决配置碎片化问题：建立 Provider 静态配置规范、扩展缺失的生产级字段、切换默认 Provider 为 DeepSeek、淘汰旧版不合理环境变量。

> 动态路由选择机制拆至 [Refactor 5](../refactor-5-llm-dynamic-routing/issue.md)，本次聚焦静态配置层面。

---

## 背景

Feature 1.3（[issue](../features/resolved/feature-1.3-multi-llm-provider/issue.md)）引入了多 LLM Provider 可配置架构（[ADR-011](../../architecture/ADR/ADR-011-multi-llm-provider.md)），实现了 `config.yaml` + `llm_config.py` 的声明式配置体系。但当前实现存在三个问题：

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
| `capabilities` | 无法标记 provider 能力（vision、tools、streaming、reasoning），后续动态路由依赖此字段 |
| `weight` | 无法控制多 provider 间的负载分配优先级，后续动态路由依赖此字段 |
| `extra_headers` | 无法注入自定义请求头（某些 provider 需要） |

### 问题 2：默认 Provider 不合理

当前 `llm.default: maas`。MaaS 需要华为内网/VPN 才能访问，作为默认 provider 导致：
- 无 VPN 环境下服务启动即失败（API key 未设置 → fallback 扫描 → 报错）
- 本地开发必须配置 VPN，增加开发环境搭建成本
- DeepSeek 公网可达、API 兼容、价格低廉，更适合作为默认选项

### 问题 3：旧版环境变量未彻底淘汰

Feature 1.3 设计为 `config.yaml` 存在时优先使用声明式配置，不存在时 fallback 到旧版三个环境变量（`MODEL_API_KEY`、`MODEL_NAME`、`MODEL_URL`）。这导致：

| 位置 | 残留 | 问题 |
|------|------|------|
| `llm_config.py:108-125` | fallback 逻辑 | 两套代码路径，增加维护负担和测试复杂度 |
| `.agentarts_config.yaml:48-55` | `MODEL_API_KEY` / `MODEL_NAME` / `MODEL_URL` env var | 部署时注入无用环境变量；且缺少 `MAAS_API_KEY`（config.yaml maas provider 实际引用的 env var），导致删除 fallback 后 maas provider 在 AgentArts Runtime 上不可用 |
| `.env.example:12-14` | 旧版兼容变量注释 | 新开发者可能误以为这些变量仍在使用 |

现在 `config.yaml` 已经稳定使用，旧版 fallback 可以安全移除。

---

## 范围

### 3.1 静态配置字段扩展

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
| `capabilities` | list[str] | `[]` | 能力标签：`vision`、`tools`、`streaming`、`reasoning`（供动态路由使用） |
| `weight` | int | `1` | 动态路由权重（越大越优先，供动态路由使用） |
| `extra_headers` | dict | `{}` | 自定义 HTTP 请求头 |

- [ ] `llm_config.py` 的 `get_model()` 读取并使用以上新字段，传递给 `init_chat_model()` 的对应参数

### 3.2 默认 Provider 切换为 DeepSeek

- [ ] `config.yaml`：`llm.default` 从 `maas` 改为 `deepseek`
- [ ] `architecture/overall_architecture.md` 技术选型表：LLM 默认行更新
- [ ] `specs/overall_specifications.md` §6.1 场景表：默认推荐 provider 更新

### 3.3 淘汰旧版配置

- [ ] `llm_config.py`：删除第 108-125 行的 fallback 代码路径（`MODEL_URL` / `MODEL_API_KEY` / `MODEL_NAME` 环境变量读取逻辑）
  - 简化 `get_model()`：`config.yaml` 不存在时直接抛 `ValueError`（而非静默 fallback），引导新开发者正确配置
- [ ] `.agentarts_config.yaml`：**删除** `MODEL_API_KEY`、`MODEL_NAME`、`MODEL_URL` 三个旧版 environment_variables 条目（第 50-55 行）；**新增** `MAAS_API_KEY` 条目（config.yaml 中 maas provider 的 `api_key_env` 对应值），确保 AgentArts Runtime 部署后 maas provider 仍可用
- [ ] `.env.example`：删除第 11-14 行旧版兼容变量段
- [ ] 确保所有 CI/部署流程已切换到新配置方式，不受删除影响

---

## 不涉及

- **动态路由选择机制** — 拆至 [Refactor 5](../refactor-5-llm-dynamic-routing/issue.md)。本次仅建立静态配置基础（`capabilities` / `weight` 字段）
- 非 OpenAI-compatible 协议的 provider（Anthropic、Gemini 等）— 不属于本次重构范围
- MaaS provider 删除 — 保留配置，仅切换默认值

---

## 影响

### 修改文件

| 文件 | 改动 |
|------|------|
| `personal-assistant-service/config.yaml` | 扩展 provider 字段 + `default` 改为 `deepseek` |
| `personal-assistant-service/app/llm_config.py` | `get_model()` 读取新字段传给 `init_chat_model()`；删除旧版 fallback |
| `personal-assistant-service/.agentarts_config.yaml` | 删除旧版 `MODEL_API_KEY` / `MODEL_NAME` / `MODEL_URL` env var；新增 `MAAS_API_KEY` env var |
| `personal-assistant-service/.env.example` | 删除旧版兼容变量段 |
| `personal-assistant-meta/architecture/overall_architecture.md` | §6 LLM Provider 配置更新 |
| `personal-assistant-meta/specs/overall_specifications.md` | §6 LLM Provider 管理更新 |
| `personal-assistant-meta/specs/dictionary.md` | 更新 LLM Provider 术语 |
| `personal-assistant-meta/architecture/ADR/ADR-011-multi-llm-provider.md` | 标注 amend：默认 provider 变更 + 旧版 env var 移除 |

### 测试影响

- `llm_config.py` 单测：扩展测试用例覆盖新字段、删除 fallback 路径测试

---

## 任务拆解

### 3.1 静态配置字段扩展
- [ ] `config.yaml`：每个 provider 增加 `temperature`、`top_p`、`max_tokens`、`timeout`、`capabilities`、`weight`、`extra_headers` 可选字段
- [ ] `llm_config.py`：`get_model()` 读取新字段并传给 `init_chat_model()`
- [ ] 单元测试：覆盖新字段读取和传递

### 3.2 默认 Provider 切换
- [ ] `config.yaml`：`llm.default: deepseek`
- [ ] 架构/规格文档同步更新

### 3.3 淘汰旧版环境变量
- [ ] `llm_config.py`：删除 fallback 代码路径（第 108-125 行）
- [ ] `.agentarts_config.yaml`：删除 `MODEL_API_KEY` / `MODEL_NAME` / `MODEL_URL`，新增 `MAAS_API_KEY`（对齐 config.yaml 中 maas provider 的 `api_key_env`）
- [ ] `.env.example`：删除旧版兼容变量段

### 3.4 文档更新
- [ ] `overall_architecture.md` §6 更新
- [ ] `overall_specifications.md` §6 更新
- [ ] `dictionary.md` 更新
- [ ] `ADR-011` amend 标注

### 3.5 验证
- [ ] 默认 DeepSeek provider 对话正常
- [ ] 显式指定 maas provider 对话正常（VPN 环境）
- [ ] `config.yaml` 缺失时明确报错（不静默 fallback）
- [ ] 旧版 `MODEL_API_KEY` 等 env var 设值后不再生效
- [ ] `.agentarts_config.yaml` 仅包含 `DEEPSEEK_API_KEY` 和 `MAAS_API_KEY` 两个 env var（与 config.yaml provider `api_key_env` 一一对应，不含旧版变量）

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
- [Refactor 5: LLM Provider 动态路由选择](../refactor-5-llm-dynamic-routing/issue.md) — 本次建立的 `capabilities` / `weight` 字段为后续动态路由提供基础
