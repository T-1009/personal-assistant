# Feature-17 GitHub MCP Gateway IAM 签名 401 排查

> 记录时间：2026-07-15
> 区域：`cn-southwest-2`
> 结论：AgentArts MCP Gateway 底层基于 APIC（API Connect），使用非标准域名
> `*.huaweicloud-agentarts.com`。华为云 SDK 默认使用 SDK-HMAC-SHA256 签名算法，
> 但 APIC 只认 V11-HMAC-SHA256。需要通过 `with_derived_predicate()` 将签名算法
> 从 SDK-HMAC-SHA256 切换到 V11-HMAC-SHA256，并通过 `_process_derived_auth_params("apic", ...)`
> 将服务名指定为 `apic`。此外，`HuaweiCloudIAMAuth` 的 `requires_request_body = True`
> 导致 body-less 请求（MCP Session 终止 DELETE）跳过签名，需移除该标志。

## 症状

Feature-17 的 GitHub MCP 工具调用失败，返回：

```text
GitHub MCP Gateway IAM authentication failed.
```

对应日志中出现 HTTP 401，MCP 初始化请求被 Gateway 拒绝。

## 诊断过程

### 第一步：定位签名算法 — V11-HMAC-SHA256 vs SDK-HMAC-SHA256

排查起点是检查签名头 `Authorization` 的格式。

标准华为云服务（`*.myhuaweicloud.com`）接受 SDK-HMAC-SHA256 签名的请求头，格式为：

```text
Authorization: SDK-HMAC-SHA256 Credential=...
```

但 AgentArts MCP Gateway 底层跑在 **APIC（华为云 API Connect）** 上，使用非标准域名
`*.huaweicloud-agentarts.com`。APIC 是华为云较早的 API 网关产品，只兼容早期的
**V11-HMAC-SHA256** 签名协议。

对照验证：

| 维度 | 标准华为云服务 | AgentArts MCP Gateway |
|------|-------------|---------------------|
| 域名 | `*.myhuaweicloud.com` | `*.huaweicloud-agentarts.com` |
| 签名算法 | SDK-HMAC-SHA256（SDK 默认） | **V11-HMAC-SHA256**（APIC 旧协议） |
| 服务名 | 各服务自识别 | `apic`（API Connect） |
| 区域 | 各区域自动匹配 | 合并到 `apic` 服务的区域参数中 |

华为云 SDK 的 `GlobalCredentials` 默认使用 SDK-HMAC-SHA256 签名。如果不做任何处理直接用
SDK 的 `sign_request()` 签名，生成的 `Authorization` 头格式与 APIC 期望不匹配，Gateway
直接返回 401。

### 第二步：理解派生签名（Derived Signing）

签名算法的切换通过 `GlobalCredentials.with_derived_predicate()` 完成。

对应代码：[gateway_client.py:145-148](personal-assistant-service/app/mcp/gateway_client.py#L145-L148)

```python
credentials = _credentials_to_global_credentials(sts_credentials)
# AgentArts Gateway uses huaweicloud-agentarts.com which is a non-standard
# endpoint → requires V11-HMAC-SHA256 derived signing (not SDK-HMAC-SHA256).
credentials.with_derived_predicate(
    GlobalCredentials.get_default_derived_predicate()
)
```

`with_derived_predicate()` 的作用是将签名算法从默认的 SDK-HMAC-SHA256 切换到
SDK 内置的"派生签名算法"（即 V11-HMAC-SHA256）。传入的 predicate 是一个判断函数：
当 predicate 返回 `True` 时使用派生算法，`False` 时使用默认算法。
`get_default_derived_predicate()` 返回的默认实现总是 `True`，即无条件使用派生签名。

### 第三步：指定服务名和区域

切换签名算法后，还需要指定正确的服务名。APIC 在签名时使用的服务标识是 `apic`，
而不是标准服务名（如 `iam`、`ecs`）。

对应代码：[gateway_client.py:148](personal-assistant-service/app/mcp/gateway_client.py#L148)

```python
credentials._process_derived_auth_params("apic", "cn-southwest-2")
```

`_process_derived_auth_params(service_name, region)` 将服务名和区域嵌入 V11-HMAC-SHA256
签名计算中的 `SignedHeaders` 和 `CanonicalRequest` 部分。缺少这步调用会导致
签名计算中服务名缺失或不正确，签名校验失败。

### 第四步：验证签名头格式

测试用例中明确了签名头的期望格式：[test_mcp_gateway_auth.py:37-42](personal-assistant-service/tests/test_mcp_gateway_auth.py#L37-L42)

```python
headers = sign_httpx_request(request, sts)

assert headers["Authorization"].startswith("V11-HMAC-SHA256")
assert "Credential=test-ak/" in headers["Authorization"]
assert "test-sk" not in headers["Authorization"]   # SK 不能出现在签名头中
assert headers["X-Security-Token"] == "test-security-token"
assert headers["X-Sdk-Content-Sha256"] == "UNSIGNED-PAYLOAD"
```

关键验证点：

- `Authorization` 必须以 `V11-HMAC-SHA256` 开头，确认使用了派生签名算法
- `X-Security-Token` 携带 STS 返回的临时 security token
- `X-Sdk-Content-Sha256` 固定为 `UNSIGNED-PAYLOAD`（不对 body 做 SHA256 哈希，APIC 接受此值）
- `X-Sdk-Content-Sha256` 必须参与 Canonical Request 计算

### 第五步：发现 DELETE 请求漏签名（次生问题）

主签名算法修复后，仍偶发 401。排查发现 MCP 协议生命周期中有一个特殊的请求被遗漏：

MCP Streamable HTTP 协议在 session 结束时发送 **DELETE 请求** 以终止服务端 session。
对应 MCP 库代码：[streamable_http.py:579-593](personal-assistant-service/.venv/Lib/site-packages/mcp/client/streamable_http.py#L579-L593)

```python
async def terminate_session(self, client: httpx.AsyncClient) -> None:
    if not self.session_id:
        return
    response = await client.delete(self.url, headers=headers)
```

`HuaweiCloudIAMAuth` 继承了 `httpx.Auth`，并设置了 `requires_request_body = True`。
在 httpx 中，`requires_request_body = True` 的含义是"需要请求体才能生成认证头"。
对于 DELETE 请求（body 为 `b""`），httpx 会跳过 `auth_flow()`，请求以**未签名**状态发出。

完整生命周期分析：

```
① POST /mcp  (initialize)  → IAM 签名 ✓（有 body）
② POST /mcp  (tools/list)  → IAM 签名 ✓（有 body）
③ POST /mcp  (tools/call)  → IAM 签名 ✓（有 body）
④ DELETE /mcp (terminate)  → IAM 签名 ✗（无 body → requires_request_body=True 跳过）
                            → 401 仅记 warning 不抛异常
```

对应修复：移除 `requires_request_body = True`，使 DELETE 请求同样经过 `auth_flow()`。

## 故障树总结

```
401 Unauthorized
│
├─ 签名算法错误（主因）
│   问题：AgentArts Gateway 底层是 APIC，期望 V11-HMAC-SHA256，
│         SDK 默认使用 SDK-HMAC-SHA256
│   根因：非标准域名 *.huaweicloud-agentarts.com 不走标准服务签名路径
│   定位：对比 Authorization 头格式，确认 Gateway 要求 V11-HMAC-SHA256
│   修复：with_derived_predicate()                              — 切换签名算法
│         _process_derived_auth_params("apic", "cn-southwest-2") — 指定 APIC 服务名
│
├─ DELETE 请求漏签名（次生）
│   问题：requires_request_body=True 跳过 body-less 请求的 auth_flow()
│   定位：追踪 MCP session 生命周期，发现 terminate_session 发 DELETE
│   修复：移除 requires_request_body
│
└─ Sandbox 配额耗尽（放大因子）
    每次连接创建新 sandbox，DELETE 未签名导致 sandbox 泄漏
    修复：固定 mcp-session-id 复用 sandbox
```

## 修复代码

签名函数最终形态：[gateway_client.py:132-159](personal-assistant-service/app/mcp/gateway_client.py#L132-L159)

```python
def sign_httpx_request(request, sts_credentials):
    parsed = urlsplit(str(request.url))
    credentials = _credentials_to_global_credentials(sts_credentials)
    # 切换签名算法：SDK-HMAC-SHA256 → V11-HMAC-SHA256
    credentials.with_derived_predicate(
        GlobalCredentials.get_default_derived_predicate()
    )
    # 指定 APIC 服务名和区域
    credentials._process_derived_auth_params("apic", "cn-southwest-2")
    sdk_request = SdkRequest(
        method=request.method,
        schema=parsed.scheme,
        host=_host_with_port(parsed),
        resource_path=parsed.path or "/",
        query_params=list(request.url.params.multi_items()),
        header_params=_request_headers_for_signing(request),
        body=request.content,
    )
    signed_request = credentials.sign_request(sdk_request)
    return dict(signed_request.header_params)
```

## 验证方法

### 单元测试验证

```bash
cd personal-assistant-service
uv run pytest tests/test_mcp_gateway_auth.py::test_sign_httpx_request_uses_sts_credentials_without_secret_leak -v
```

期望：
- `Authorization` 头以 `V11-HMAC-SHA256` 开头
- `Credential=<access_key_id>/` 存在于 Authorization 中
- `secret_access_key` 不出现在 Authorization 中
- `X-Security-Token` 等于 STS 返回的 security_token

### 端到端验证

启动 Service 后，调用一次 GitHub MCP 工具（如 `github_mcp_resolve_identity`），观察日志：

```bash
# 期望日志中没有 401 或 authentication_error
# IAM signing 成功 → 正常返回 identity 信息
```

可进一步抓包或开启 SDK debug 日志，确认发送的 Authorization 头以 `V11-HMAC-SHA256` 开头。

## 关联代码引用

| 文件 | 行号 | 内容 |
|------|------|------|
| `gateway_client.py` | 70-86 | `HuaweiCloudIAMAuth` — httpx Auth 实现 |
| `gateway_client.py` | 132-159 | `sign_httpx_request` — V11-HMAC-SHA256 签名 |
| `gateway_client.py` | 117-129 | `_request_headers_for_signing` — 签名用 header 构建 |
| `gateway_client.py` | 26-30 | `_DEFAULT_MCP_HEADERS` — 固定 mcp-session-id |
| `test_mcp_gateway_auth.py` | 19-42 | 签名格式单元测试 |
| `streamable_http.py` | 148-163 | MCP 库 `_prepare_headers()` |
| `streamable_http.py` | 579-593 | MCP 库 `terminate_session()` — DELETE 请求 |
