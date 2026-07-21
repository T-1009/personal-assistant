# Bug 24 Implementation Plan

## 目标

在当前 `conversation_id` + structured Agent event 架构下恢复 stale PostgreSQL
Checkpointer 自愈，同时保持 AgentArts Runtime Session ID、Invocation API 和 Client
行为不变。

## 实现步骤

1. 在 `AgentHandler` 中仅将带已知 idle/closed message 的
   `psycopg.OperationalError` 识别为可恢复 Checkpointer 错误。
2. 复用现有 Agent Bundle lock 串行化 Checkpointer restart，并通过失败时的
   Checkpointer 对象身份避免并发请求重复重启新连接。
3. sync Invocation 遇到可恢复错误时 restart 后重试一次。
4. Streaming Invocation 仅在未输出任何 `AgentStreamEvent` 时 restart 后重试一次；
   已输出 event 后保持原 error path。
5. 更新 Service unit regression tests，覆盖 sync、stream 输出前、stream 输出后和
   非 Checkpointer error。
6. 同步 backend、session state 和 test strategy 文档中的恢复边界。

## 影响范围

| 子系统 | 变更 |
|--------|------|
| Service | `AgentHandler` Checkpointer lifecycle 与 sync/stream retry |
| Service tests | 恢复 Bug 19 regression coverage，并适配 structured event |
| Meta | 记录 Runtime Session 与数据库 connection 生命周期独立 |
| Client / Cloudflare / Gateway | 无变更 |
| API / OpenAPI | 无 route 或 schema 变更，不重新生成 `openapi.json` |

## 风险与控制

| 风险 | 控制 |
|------|------|
| 把 LLM/工具网络错误误判为 Checkpointer 错误 | 同时约束 exception type 和已知 message |
| 并发失败重复关闭刚恢复的 Checkpointer | restart 前比较失败时的 Checkpointer 对象身份 |
| Streaming 重试产生重复内容 | 仅允许首个 event 输出前重试 |
| 影响 Runtime Session continuity | 不读取或修改 Runtime Session ID，继续使用原 `conversation_id` config |

## 验证

```bash
cd personal-assistant-service
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/test_agent_handler.py tests/test_checkpointer.py
uv run pytest tests/

cd ../personal-assistant-e2e
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/full_stack/test_feature_14_conversation_boundary.py
```

不新增 E2E case：stale psycopg connection 属于 Service 内部、可 mock 的 lifecycle
边界；按 E2E 目录规则由 Service unit tests 覆盖。既有 Feature 14 full-stack test 用于确认
SSE、Conversation 与 cancellation contract 未受影响。
