---
status: backlog
---

# Refactor 5: LLM Provider 动态路由选择

引入运行时动态路由机制：根据任务特征（如是否需要 vision、reasoning）自动选择最合适的 LLM Provider，支持故障切换和成本优化路由。

> 依赖 [Refactor 3](../refactor-3-llm-provider-config/issue.md) 中 `capabilities` / `weight` 静态配置字段完成后才能实施。

---

## 背景

Feature 1.3 引入的多 LLM Provider 架构已支持静态声明多个 provider，但当前 `agent_handler.py` 初始化时调用 `get_model()` 不带 `provider` 参数，整个 Agent 生命周期绑定单一 provider。无法实现：

- **按任务类型选 provider**：简单闲聊用便宜的 DeepSeek，复杂推理/vision 用更强的模型
- **故障切换（fallover）**：主 provider 不可用时自动降级到备用
- **成本优化路由**：根据预估 token 消耗选择最经济的 provider

当前 `llm_config.py` 有一个跨 provider API key fallback（当 default provider 的 key 未设置时扫描其他 provider），但这只是**初始化时的一次性回退**，不是运行时的动态路由。

---

## 范围

### 动态路由模块

- [ ] 新增 `personal-assistant-service/app/llm_router.py`：动态路由模块
  - 输入：任务需求（capabilities required）
  - 输出：选中的 provider name
  - 策略：基于 `capabilities` 匹配 + `weight` 加权随机（简单有效，不引入外部依赖）
- [ ] 修改 `personal-assistant-service/app/agent_handler.py`：每次 `handle()` 调用时根据任务特征动态选 provider，而非初始化时固定
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

### 不涉及

- 多模态自动分流（自动判断是否需要 vision 模型）— 本次只做基于 `capabilities` 的显式路由，自动意图识别后续 feature
- Provider 健康检查独立服务 — 简单 call 失败 → fallback 即可，不需要独立的 health check probe
- 运行时动态添加/删除 provider（reload config）— 后续 feature
- 非 OpenAI-compatible 协议的 provider（Anthropic、Gemini 等）

---

## 影响

### 修改文件

| 文件 | 改动 |
|------|------|
| `personal-assistant-service/app/llm_router.py` | **新增**：动态路由模块 |
| `personal-assistant-service/app/agent_handler.py` | `AgentHandler` 支持每次调用时动态选 provider |
| `personal-assistant-service/config.yaml` | 新增 `llm.routing` 配置段 |

### 测试影响

- 新增 `llm_router.py` 单测：capability 匹配、fallback、权重随机
- `agent_handler.py` 测试：验证动态路由集成

---

## 任务拆解

### 5.1 动态路由模块
- [ ] 新增 `app/llm_router.py`：`route(config, requirements) -> provider_name` 函数
- [ ] `config.yaml` 新增 `llm.routing` 配置段
- [ ] 单测：capability 匹配正确、fallback 逻辑正确、无匹配时 fallback 到 default

### 5.2 AgentHandler 动态选择
- [ ] `agent_handler.py`：`__init__()` 不再绑定单一 model；`handle()` / `handle_stream()` 中按需调用 `llm_router.route()` + `get_model(provider)`
- [ ] 确保 SSE 流式响应正常工作（model 切换不影响 stream 事件结构）

### 5.3 验证
- [ ] 动态路由：vision 任务选 doubao，其他选 deepseek（capability match）
- [ ] Provider 故障时自动 fallback 到备用 provider

---

## 依赖

- [Refactor 3: LLM Provider 静态配置重构](../refactor-3-llm-provider-config/issue.md) — 提供 `capabilities` / `weight` / `default` 等静态配置基础
- Feature 1.3（多 LLM Provider 可配置）— 已 resolved

---

## 参考

- [ADR-011: 多 LLM Provider 可配置架构](../../architecture/ADR/ADR-011-multi-llm-provider.md)
- [Feature 1.3 issue](../features/resolved/feature-1.3-multi-llm-provider/issue.md)
