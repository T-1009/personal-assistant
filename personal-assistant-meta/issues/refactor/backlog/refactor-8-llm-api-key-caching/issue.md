---
status: backlog
---

# Refactor 8: 减少 LLM API Key 的重复获取开销

每次调用 `get_model()` 都通过 `@require_api_key` 装饰器从 AgentArts Identity SDK 获取 API Key，可能产生不必要的重复 IPC 调用开销。后续计划在确认 SDK 行为、Key rotation 要求和安全边界后，引入应用层复用机制。

> 关联 ADR：[ADR-016：Secretless Credential Injection via AgentArts Identity](../../architecture/ADR/ADR-016-secretless-credential-injection.md)
>
> 历史实现参考：commit `57312f64875d088dea84f4123bf79df6058ab655`。该实现已由 commit `64107194ea7868fd86b3d1ef7ebbd20c455c76dc` 回退，不代表最终方案，也不应直接 cherry-pick 恢复。

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

`get_model()` 每次创建模型实例时都会调用此函数。若 AgentArts SDK 未在合适的生命周期内完成复用，每一轮对话（包括 tool 调用后的模型再调用）都可能触发一次 SDK IPC。需要通过 profiling 或 SDK 文档确认实际调用次数与延迟，避免仅根据旧实现中的估算作设计。潜在问题包括：

1. **延迟**：重复 IPC 会增加模型调用前的固定开销
2. **不确定依赖**：依赖 SDK 内部实现细节，SDK 升级可能改变缓存策略
3. **生命周期不清**：应用当前没有显式定义 Key 的复用、失效和 rotation 语义

### 历史实现与回退

2026-06-17 的 commit `57312f6` 曾实现以下三层读取顺序：

1. 模块级 `_API_KEY_CACHE`
2. `os.environ`
3. AgentArts Identity SDK

该实现还将 SDK 返回的明文 Key 写入 `os.environ`，并假设 Key rotation 通过 container restart 完成。代码随后在 commit `6410719` 中回退。后续方案应吸收“避免重复 IPC”的目标，但必须重新评估：

- 是否需要同时维护字典和 `os.environ` 两层可变状态
- 将 SDK 返回的明文 Key 写入 `os.environ` 是否符合最小暴露原则
- 多 worker / 多进程部署下缓存的作用域和一致性
- Key rotation、失效、SDK 异常与重试语义
- SDK 是否已经提供可配置且满足需求的缓存能力

---

## 范围

### 8.1 基线测量与约束确认

- [ ] 确认 `@require_api_key` 的官方缓存和刷新语义
- [ ] 测量一次请求及连续请求中的 SDK 调用次数与耗时
- [ ] 明确 Key rotation、失效和 container 生命周期约束

### 8.2 设计并实现复用机制

- [ ] 选择单一、可测试的缓存或复用入口，避免重复状态源
- [ ] 按 `credential_provider_name` 隔离不同 provider 的 Key
- [ ] 定义 cache miss、空 Key、SDK 异常和 rotation 后的行为
- [ ] 排查 Service 中其他直接获取 LLM Key 的路径并统一策略

### 8.3 测试

- [ ] 新增测试：首次调用触发 SDK，第二次调用命中缓存（mock SDK 验证调用次数）
- [ ] 新增测试：不同 provider 的 Key 分别缓存，互不干扰
- [ ] 新增测试：空 Key 和 SDK 异常不会污染缓存
- [ ] 根据最终失效策略覆盖 rotation / invalidation 场景

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
| `personal-assistant-service/app/llm_config.py` | 预计增加 API Key 复用机制；具体数据结构由 Meta 阶段确定 |
| `personal-assistant-service/tests/test_llm_config.py` | 新增复用、隔离、异常与失效测试 |
| `personal-assistant-meta/architecture/ADR/ADR-016-secretless-credential-injection.md` | 根据最终决策同步 credential 生命周期与安全约束 |

### 行为变化

- **首次调用**：行为不变，仍通过 SDK 获取 Key
- **后续调用**：在已定义的有效期内复用 Key，减少 SDK IPC
- **Key 更新**：按最终确定的 rotation / invalidation 策略生效，不预设只能依赖 container restart

---

## 任务拆解

### 8.1 调研与设计
- [ ] 验证实际性能问题及 SDK 现有能力
- [ ] 在 Implementation Plan 中比较 SDK cache、进程内 cache、模型实例复用等方案
- [ ] 明确安全边界、生命周期和可观测指标

### 8.2 测试
- [ ] 测试首次调用走 SDK
- [ ] 测试第二次调用命中缓存、不触发 SDK
- [ ] 测试多 provider 缓存隔离
- [ ] 测试异常不缓存及 Key 失效策略

### 8.3 文档
- [ ] ADR-016 更新最终采用的复用和 rotation 策略
- [ ] `llm_config.py` 模块 docstring 说明最终生命周期

---

## 验收条件

- [ ] 有 profiling 或可重复测试证明重复 credential 获取路径及优化收益
- [ ] 正常请求在有效期内不会重复触发不必要的 SDK IPC
- [ ] 不同 provider 的 credential 状态互相隔离
- [ ] 空 Key、SDK 异常和失效事件不会留下错误缓存
- [ ] 明文 Key 不被写入超出必要范围的状态载体；若使用 `os.environ`，需在 Implementation Plan 中记录理由与 trade-off
- [ ] Unit Tests、Integration Tests 和相关 E2E 验证通过
- [ ] ADR-016 与实际实现保持一致

---

## 依赖

- Feature 1.3（多 LLM Provider 可配置）— `config.yaml` + `llm_config.py` 已存在
- ADR-016（Secretless Credential Injection）— 本 issue 是 ADR-016 中记录的优化项

---

## 参考

- [ADR-016：Secretless Credential Injection via AgentArts Identity](../../architecture/ADR/ADR-016-secretless-credential-injection.md)
- [ADR-011：多 LLM Provider 可配置架构](../../architecture/ADR/ADR-011-multi-llm-provider.md)
- [AWS Lambda 最佳实践：在 handler 外初始化以复用连接](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
