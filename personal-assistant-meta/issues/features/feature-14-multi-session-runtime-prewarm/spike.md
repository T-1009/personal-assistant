# Feature 14 Spike: Runtime Session、Cookie 与提前唤醒

> 日期：2026-07-13
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
- No Control Plane placement, BFF service credential, background cleanup worker or lifecycle state
  machine is required.
- `sessions-start` knowledge remains documented for future experiments without contaminating the
  production contract.
