---
status: backlog
---

# Refactor 8: LLM API Key 进程级缓存（os.environ）

每次调用 `get_model()` 都通过 `@require_api_key` 装饰器从 AgentArts Identity SDK 获取 API Key，存在不必要的重复 IPC 调用开销。应改为首次获取后缓存到 `os.environ`，后续直接读取环境变量。

> 关联 ADR：[ADR-016：Secretless Credential Injection via AgentArts Identity](../../architecture/ADR/ADR-016-secretless-credential-injection.md)

---

## 背景

当前 `llm_config.py` 的 `_get_api_key_from_identity()` 实现：

```python
def _get_api_key_from_identity(credential_provider_name: str) -> str:
    @require_api_key(provider_name=credential_provider_name, into="api_key")
    def _fetch(api_key: str | None = None) -> str:
        if not api_key:
            raise ValueError(...)
        return api_key
    return _fetch()
```

`get_model()` 每次创建模型实例时都会调用此函数，导致每一轮对话（包括 tool 调用后的模型再调用）都触发一次 AgentArts SDK 的 IPC 调用。虽然 SDK 内部可能有短时缓存，但：

1. **延迟**：IPC 调用有 10-50ms 的固定开销
2. **不确定依赖**：依赖 SDK 内部实现细节，SDK 升级可能改变缓存策略
3. **语义不清**：API Key 在进程生命周期内不变，不应每次重新获取

### 为什么不用 `@require_api_key` 装饰器本身的缓存？

`@require_api_key` 是通用装饰器——它不知道调用方是"每次对话获取 LLM Key"还是"偶尔获取某个低频 API 的 Key"。它有默认定时缓存（TTL-based），但缓存策略是 SDK 内部实现，不应在应用层假设其行为。

应用层明确知道：**LLM API Key 在进程生命周期内不会变化**（换 Key 需要重启容器，AgentArts Runtime 会在 `agentarts launch` 时重建容器）。因此进程级缓存（`os.environ`）是最合适的策略。

---

## 范围

### 8.1 `llm_config.py` 增加进程级缓存

- [ ] 新增 `_API_KEY_CACHE: dict[str, str] = {}` 模块级字典
- [ ] `_get_api_key_from_identity()` 改为先查缓存，miss 时才调 SDK，获取后写入 `os.environ` 和 `_API_KEY_CACHE`
- [ ] 缓存 key 为 `credential_provider_name`（支持多 provider 各自缓存）

### 8.2 `agent_handler.py` 复用缓存的 Key

当前 `agent_handler.py` 中也可能存在独立的 `@require_api_key` 调用，应统一走 `llm_config` 的缓存出口。

- [ ] 排查 `agent_handler.py` 和 `tools/` 下是否有直接调 `@require_api_key` 获取 LLM Key 的代码

### 8.3 测试

- [ ] 新增测试：首次调用触发 SDK，第二次调用命中缓存（mock SDK 验证调用次数）
- [ ] 新增测试：不同 provider 的 Key 分别缓存，互不干扰

---

## 不涉及

- OAuth2 Access Token 缓存 — Token 有过期时间，缓存策略不同，属于独立优化
- STS Token 缓存 — 同理，临时凭证有自己的生命周期管理
- `@require_api_key` 装饰器本身的实现修改 — 那是 AgentArts SDK 的职责

---

## 影响

### 修改文件

| 文件 | 改动 |
|------|------|
| `personal-assistant-service/app/llm_config.py` | `_get_api_key_from_identity()` 加缓存逻辑；新增 `_API_KEY_CACHE` 字典 |
| `personal-assistant-service/tests/test_llm_config.py` | 新增缓存命中/未命中测试 |

### 行为变化

- **首次调用**：行为不变，仍通过 SDK 获取 Key
- **后续调用**：直接从 `os.environ` 读取，不再触发 SDK IPC 调用
- **Key 更新**：需重启容器（`agentarts launch` 重建容器），与当前"修改环境变量后重启"的运维习惯一致

---

## 任务拆解

### 8.1 实现缓存
- [ ] `llm_config.py`：新增 `_API_KEY_CACHE` 字典
- [ ] `llm_config.py`：`_get_api_key_from_identity()` 改为先查缓存
- [ ] 获取后同时写入 `os.environ`（LangChain 底层会自动读环境变量）

### 8.2 测试
- [ ] 测试首次调用走 SDK
- [ ] 测试第二次调用命中缓存、不触发 SDK
- [ ] 测试多 provider 缓存隔离

### 8.3 文档
- [ ] ADR-016 更新：标注"已通过进程级缓存优化"
- [ ] `llm_config.py` 模块 docstring 说明缓存策略

---

## 依赖

- Feature 1.3（多 LLM Provider 可配置）— `config.yaml` + `llm_config.py` 已存在
- ADR-016（Secretless Credential Injection）— 本 issue 是 ADR-016 中记录的优化项

---

## 参考

- [ADR-016：Secretless Credential Injection via AgentArts Identity](../../architecture/ADR/ADR-016-secretless-credential-injection.md)
- [ADR-011：多 LLM Provider 可配置架构](../../architecture/ADR/ADR-011-multi-llm-provider.md)
- [AWS Lambda 最佳实践：在 handler 外初始化以复用连接](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
