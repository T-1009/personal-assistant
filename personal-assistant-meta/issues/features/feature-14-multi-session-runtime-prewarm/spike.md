# Feature 14 Spike: Runtime Session、Cookie 与提前唤醒

> 日期：2026-07-14
> 状态：文档与代码静态验证完成；Gateway trust、custom path 和 latency 仍需 deployed probe

## 结论摘要

1. **AgentArts 官方 API 文档没有定义 pre-warm/warm-up API。**
   `sessions-start` 的官方语义是创建 Runtime Session；文档没有 readiness、TTL 或
   首条 Invocation latency guarantee。
2. **`sessions-start` 不接收调用者提供的 Session ID。**
   请求无 body，成功后由平台返回 `data.session_id`。因此它不能启动 BFF 预先生成的
   Cookie ID。
3. **Invocation 隐式创建已满足正确性。**
   应用可直接使用合法自生成 ID；底层 instance 被自动回收后，同一个 ID 可再次触发
   创建，无需 replacement ID。
4. **选择 random HttpOnly Cookie，而不是数据库 Runtime lease。**
   Cloudflare BFF 生成 opaque routing key、写 Cookie并覆盖 upstream Session header。
   Runtime ID 不代表用户身份，不写 DB。
5. **Conversation API 放在现有 FastAPI Service。**
   请求经显式 Pages Function 和 AgentArts Gateway custom path 进入 Runtime；不创建
   独立 Control Plane，也没有 BFF-only internal API。
6. **进入 Chat 的 Conversation list 是 application-level warm-up。**
   它本来就是产品需要的请求，同时会隐式启动 Runtime。是否降低第一条消息延迟仍需
   benchmark，失败不影响直接 Invocation。
7. **BFF 不校验 JWT。**
   AgentArts Gateway 负责验证；FastAPI 在 Gateway 后从已验证 token 派生 `user_id`。
   该方案以 Gateway 转发 Authorization 且 Runtime 无 public bypass 为 blocking 前提。
8. **Feature 14 不建立 `invocation_runs`，也不自动重试 Invocation。**
   Message row 自身记录 `in_progress/completed/failed/interrupted`；重复
   `client_message_id` 返回 409，用户主动重发使用新 ID。
9. **Conversation Store 只实现 PostgreSQL。**
   in-memory fake 用于纯 Unit Test；Store/migration/lock/local integration 使用真实
   PostgreSQL；SQLite 不作为 PostgreSQL 语义替身。
10. **Delete 是同步永久删除。**
    当前锁定依赖中的 `AsyncPostgresSaver` 已确认提供 `adelete_thread()`；messages 通过
    PostgreSQL `ON DELETE CASCADE` 删除，不设计 soft delete 或后台 purge。
11. **跨 Runtime 并发使用 PostgreSQL session-level Advisory Lock。**
    Invocation 与 Delete 使用同一 lock key；`pg_try_advisory_lock` 拿不到就返回 409，
    不无限等待、不自动重试。

## Spike 问题

本次 spike 回答：

1. AgentArts 是否存在文档化的预热 API？
2. `sessions-start` 是否允许指定已有 Session ID？
3. 自生成 Session ID 是否可直接用于 Invocation 和自动重建？
4. Runtime ID 应由 browser、BFF、Service 还是 AgentArts 生成？
5. 为了复用 Runtime，是否必须持久化 lease？
6. Conversation API 是否必须部署在 Gateway 前？
7. 不让 BFF 校验 JWT 时，业务身份如何可信？
8. 如何用可观测实验判断提前请求是否真的改善 latency？
9. 是否需要 Invocation Run ledger 和自动 retry？
10. Feature 14 的本地/集成测试应使用 SQLite、PostgreSQL 还是 in-memory？
11. Delete 应当 soft delete 还是立即永久删除？
12. 多 Runtime instance 如何避免同一 Conversation 并发执行或边执行边删除？

## AgentArts PDF 证据

PDF：`personal-assistant-meta/architecture/cloud-service/huaweicloud/agentarts-api-pdf.pdf`

### `StartRuntimeSession`

- Section：4.7.1.1
- URI：`POST /runtimes/{runtime_name}/sessions-start`
- Required header：`Authorization`
- Optional header：`X-Sdk-Content-Sha256`（IAM auth）
- 文档没有 request body，也没有 caller-supplied Session ID 参数
- 200 response：`code`、`message`、`data.session_id`
- `data.session_id`：英文字母、数字、`-`、`_`，最长 64 字符
- PDF 的 request example 在该 section 中误写了 `sessions-stop`；URI 和参数表应作为
  文档依据，live probe 仍需防御该文档问题

文档未给出：

- `ready` flag 或 readiness query；
- `expires_at`、`ttl`、`session_timeout`；
- start latency 或 first-invocation latency guarantee；
- caller-selected ID；
- repeated start idempotency；
- “pre-warm”或“warm-up”术语。

因此，`sessions-start` 可以被应用尝试用于提前创建，但不能被写成平台承诺的预热 API。

### `ExecuteRuntimeWithPrefix`

- Section：4.7.1.2
- URI：`POST /runtimes/{runtime_name}/invocations/{custom_path}`
- Runtime access 必须配置 `url_match_type=PREFIX_MATCH`
- `custom_path` 不以 `/` 开头
- Required headers：`X-Hw-Agentarts-Session-Id`、`Authorization`
- `X-Hw-Agentgateway-User-Id` 在平台文档中为 optional

PDF 以 POST 描述该接口，但项目 Calendar callback 设计还需要 GET custom path；Feature 14
的 Conversation API 还需要 GET/PATCH/DELETE。因此 method pass-through 必须做 deployed
contract probe，不能只从 FastAPI route 能力推断 Gateway 行为。

### `ExecuteRuntime`

- Section：4.7.1.3
- URI：`POST /runtimes/{runtime_name}/invocations`
- Required headers：`X-Hw-Agentarts-Session-Id`、`Authorization`
- 当前 Web Chat 已使用该 path

### `StopRuntimeSession`

- Section：4.7.1.7
- URI：`POST /runtimes/{runtime_name}/sessions-stop`
- Required headers：`X-Hw-Agentarts-Session-Id`、`Authorization`
- 官方用途：销毁该 Session 对应的 instance

Feature 14 不接入该 API，因为没有后台 service credential 模型，也不需要 stop 才能保证
Conversation correctness。登出只丢弃 Cookie，底层 instance 由平台自动回收。

### API 预热结论

AgentArts 产品材料提到低冷启动延迟，但产品能力描述不等于 API contract。当前 API PDF
没有独立 pre-warm endpoint，也没有把 `sessions-start` 与“ready for first message”绑定。

结论用语固定为：

> AgentArts 提供 Runtime Session lifecycle API；Personal Assistant 使用业务初始化请求
> 实现 application-level warm-up。性能收益必须实测，不属于平台 API 保证。

## 已确认的 Runtime 复用行为

项目已确认：

- 合法的 application-generated `runtime_session_id` 可直接用于 Invocation；
- 底层 Runtime execution instance 被平台自动回收后，同一 ID 仍可继续使用；
- 下一次 Invocation 会为该逻辑 ID 隐式创建 instance；
- 应用无需仅因自动回收生成 replacement ID；
- 相同 ID 不保证物理 instance identity；
- 平台自动回收后的复用不等同于显式 `sessions-stop` 后的复用，后者没有成为本 Feature
  的依赖。

## 当前代码静态检查

### Client/BFF Runtime ID

Current path：

```text
src/lib/chat/session.ts
  -> browser localStorage generates agentarts-session-id
src/lib/chat/chat-api-client.ts
  -> sends x-hw-agentarts-session-id
functions/_shared/agentarts-proxy.js
  -> forwards caller header unchanged
```

Target path：

```text
functions/_shared/runtime-session.js
  -> reads/generates pa_runtime_session HttpOnly Cookie
functions/_shared/agentarts-proxy.js
  -> drops caller header and injects Cookie value
src/lib/chat/chat-api-client.ts
  -> no Runtime Session header
```

UUID v4 contains only hexadecimal digits and `-`, length 36, so it fits the documented AgentArts
character and length limits.

### Current identity weakness

Current production flow is:

```text
Browser decodes JWT without signature verification
  -> sends X-HW-AgentGateway-User-Id
BFF forwards it unchanged
FastAPI trusts it as verified identity
```

AgentArts project documentation records that CUSTOM_JWT Gateway validates JWT but does not itself
inject that user header. A valid user could therefore change only the header and attempt to select
another user's DB rows once Feature 14 adds Conversation APIs.

Target flow removes the header as ownership source:

```text
Browser -> Authorization JWT
BFF -> forwards JWT, no validation
Gateway -> validates JWT
FastAPI -> parses validated token sub, authorizes DB query
```

This is safe only when the FastAPI request is guaranteed to have passed Gateway. The deployed probe
must verify that trust assumption before Conversation data is exposed.

### OAuth callback coupling

`functions/_shared/callback-context.js` currently reads
`x-hw-agentarts-session-id` from the browser request to create
`pa_oauth2_callback_session`. Once Client stops sending that header, the snapshot would disappear.

Required change: `proxyInvocationsRequest()` passes the BFF-resolved Session ID explicitly into the
callback helper. Add a regression where the main Runtime Cookie rotates after authorization starts;
the callback must still use the captured Session context and signed state.

## Alternatives Evaluated

| Alternative | Result | Reason |
|-------------|--------|--------|
| Browser localStorage ID | Reject | JS-readable/caller-controlled; mixes product and routing identity |
| Deterministic ID derived from `user_id` | Reject | BFF would need trusted identity or token validation; stable identifiers leak correlation and complicate rotation |
| Service-owned Control Plane + DB lease | Reject | new deployment/auth/DB/lifecycle worker for an optimization; no platform ready/TTL state to mirror |
| BFF direct PostgreSQL/Hyperdrive | Reject | puts ownership and DB logic at edge, duplicates Service business boundary |
| `sessions-start` then save returned ID in Cookie | Defer | technically possible but no documented warm-up benefit; adds lifecycle call and alternate ID source |
| Random BFF HttpOnly Cookie + implicit Invocation | **Choose** | opaque, simple, no DB state, same-tab sharing, works with confirmed implicit recreation |
| `invocation_runs` + automatic retry/replay | Reject | current product does not require transparent retry; adds failed/interrupted/replay state machine and request fingerprinting |
| No automatic Invocation retry + Message status | **Choose** | duplicate id returns 409; network ambiguity is resolved by history refresh or deliberate new send |
| SQLite Conversation Store | Reject | does not validate PostgreSQL JSONB, cascade, migration, concurrency or Advisory Lock behavior |
| In-memory production/local Store | Reject | process-scoped and non-durable; retain only as a Unit Test fake |
| PostgreSQL Store in local/integration/production | **Choose** | one schema and one concurrency model across environments |
| Soft delete + retention/purge worker | Reject | no Trash, legal hold or retention requirement in Feature 14 |
| Immediate Checkpoint + cascade hard delete | **Choose** | matches user-visible Delete semantics and avoids lifecycle state |
| `asyncio.Lock` | Reject | cannot coordinate different Runtime instances/devices |
| Long `SELECT FOR UPDATE` transaction | Reject | would hold a database transaction for the whole LLM/SSE duration |
| Redis/distributed lease | Reject | new infrastructure and TTL/ownership complexity are unnecessary |
| PostgreSQL session-level Advisory Lock | **Choose** | cross-instance mutual exclusion, no long transaction, automatic release on connection loss |

## Message、Delete 与并发验证

### Checkpointer 删除能力

在当前锁定依赖中检查 `AsyncPostgresSaver` 和 `BaseCheckpointSaver`，两者均提供
`adelete_thread(thread_id)`。其 PostgreSQL 实现删除该 thread 的 `checkpoints`、
`checkpoint_blobs` 和 `checkpoint_writes`。因此 Feature 14 可以调用 library public API，
不需要解析或直接依赖 LangGraph 内部表结构。

### 为什么不用 Run ledger

浏览器 `fetch`、BFF 和 Service 都可以明确禁止自动重放 `POST /invocations`。网络断开时：

- 若 assistant commit 已完成，刷新 history 可以恢复答案；
- 若未完成，user message 显示 failed/interrupted；
- 用户主动重新发送会生成新的 `client_message_id`，表示新操作；
- 相同 ID 再次到达只返回 `409 duplicate_message`。

这已经满足当前正确性要求，不需要记录每次 Agent attempt 或设计 replay transport。

### Advisory Lock 选择

同一个用户可以从不同设备、不同 Runtime Session ID 同时访问一条 Conversation，因此
进程锁不够。目标实现使用：

- stable Conversation -> signed 64-bit lock key helper；
- session-level `pg_try_advisory_lock`；
- Invocation 和 Delete 共用同一 key；
- dedicated lock connection pool，普通 CRUD 使用另一个 query pool；
- `finally` unlock，pool reset 执行 `pg_advisory_unlock_all()`；
- bounded process admission；Conversation busy 返回 409，server capacity busy 返回 429。

锁只提供互斥，不提供 retry、ownership 或 durable status。

## Why No Lease Store

A durable lease is useful when multiple workers must coordinate exclusive ownership, renewal,
takeover or cleanup. Feature 14 needs none of those for correctness:

- Cookie provides routing-key reuse;
- Gateway JWT + Service ownership protects business data;
- Runtime auto-recreation handles platform recycle;
- no service credential means a background stop worker would be fictional;
- no platform TTL/readiness means local status would drift;
- an initial two-Tab duplicate only consumes temporary resources.

The lease store would create more state than it observes. It is therefore removed rather than
simplified.

## Live Probe Status

The previous environment had HuaweiCloud AK/SK but the deployed Runtime used CUSTOM_JWT. Attempts to
call lifecycle endpoints with the available credential returned authentication failure, so no live
claim is made about successful `sessions-start` response timing or repeated-start behavior.

This no longer blocks Feature 14 because production does not call lifecycle endpoints.

Still required deployed probes:

| Probe | Expected evidence |
|-------|-------------------|
| Valid JWT root Invocation | Gateway accepts and FastAPI can read Authorization |
| Forged/expired JWT custom path | Gateway rejects before FastAPI |
| Valid JWT + forged user header | Service-derived user remains token `sub` |
| Direct Runtime/container access attempt | no production public bypass |
| GET/POST/PATCH/DELETE custom paths | method/path reach intended FastAPI routes |
| Same Session ID after platform recycle | request succeeds and durable Conversation restores |

## Warm-up Benchmark Design

### Hypothesis

Calling `GET /api/conversations` with a fresh Runtime Session ID before the first chat Invocation may
move Runtime cold start and Service initialization outside the first-message critical path.

### Cohorts

1. **Baseline**: fresh ID -> `POST /invocations`.
2. **Application warm-up**: fresh ID -> `GET /api/conversations` -> same-ID Invocation.
3. **Optional lifecycle**: valid auth -> `sessions-start` -> returned-ID Invocation.

### Measurements

- warm-up request duration;
- Invocation time to first SSE byte;
- time to first model token when distinguishable;
- total response time;
- failure/timeout count;
- p50 and p95 over repeated fresh IDs;
- Runtime version, region and observation timestamp.

Do not compare one warm request with one cold request. Do not publish a “ready” state because an HTTP
200 from Conversation list only proves that request completed; it does not define future platform TTL.

### Decision rule

- Conversation list remains required regardless of latency outcome.
- If first-token latency improves, describe the behavior as measured application warm-up.
- If it does not improve, remove pre-warm performance claims while keeping the simpler Cookie/session
  architecture.
- Do not add `sessions-start` unless the optional cohort shows repeatable material benefit and a new
  design supplies auth, error and lifecycle ownership.

## Remaining Questions

Blocking before implementation:

- Does Gateway forward the validated original Authorization header to all custom paths?
- Can production Runtime be reached by any route that bypasses Gateway auth?
- Does PREFIX_MATCH preserve GET/PATCH/DELETE in the deployed configuration?

Non-blocking research:

- Does `sessions-start` provide measurable first-token benefit over useful-work warm-up?
- What happens when reusing an ID after an explicit `sessions-stop`?
- Does AgentArts expose future official readiness/TTL metadata?

## Design Consequences

- `runtime_session_id` cardinality is browser-session-scoped, not strictly user-scoped.
- Same user on multiple devices may consume multiple temporary Runtime instances.
- Runtime ID never appears in browser JavaScript or PostgreSQL.
- Conversation state and ownership remain stable across Runtime ID rotation.
- Only `conversations` and `conversation_messages` are added as Feature 14 business tables.
- Invocation has no automatic retry or Run ledger.
- Local/integration Store tests use PostgreSQL; in-memory is Unit-Test-only and SQLite is not a
  Conversation Store backend.
- Delete is immediate and permanent: `adelete_thread()` plus message cascade.
- Invocation and Delete share a bounded PostgreSQL Advisory Lock.
- BFF rollout is dual-mode until legacy Client header usage reaches zero, then becomes Cookie-only.
- No Control Plane placement, BFF service credential, background cleanup worker or lifecycle state
  machine is required.
- `sessions-start` knowledge remains documented for future experiments without contaminating the
  production contract.
