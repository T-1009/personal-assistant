"""Tests for AgentArts MCP Gateway IAM signing."""

from __future__ import annotations

from types import SimpleNamespace

import anyio
import httpx

from app.mcp.gateway_client import (
    MCPGatewayClient,
    MCPGatewayConfig,
    _map_generic_mcp_error,
    extract_mcp_payload,
    sign_httpx_request,
)


def test_sign_httpx_request_uses_sts_credentials_without_secret_leak():
    request = httpx.Request(
        "POST",
        "https://gateway.example.com/mcp?cursor=next",
        headers={
            "Content-Type": "application/json",
            "mcp-session-id": "session-id",
        },
        content=b'{"jsonrpc":"2.0","method":"tools/list"}',
    )
    sts = SimpleNamespace(
        access_key_id="test-ak",
        secret_access_key="test-sk",
        security_token="test-security-token",
    )

    headers = sign_httpx_request(request, sts)

    assert headers["Authorization"].startswith("V11-HMAC-SHA256")
    assert "Credential=test-ak/" in headers["Authorization"]
    assert "test-sk" not in headers["Authorization"]
    assert headers["X-Security-Token"] == "test-security-token"
    assert headers["X-Sdk-Content-Sha256"] == "UNSIGNED-PAYLOAD"
    assert headers["mcp-session-id"] == "session-id"


def test_extract_mcp_payload_prefers_structured_content():
    result = SimpleNamespace(
        structuredContent={"ok": True},
        content=[SimpleNamespace(text='{"ok": false}')],
    )

    assert extract_mcp_payload(result) == {"ok": True}


def test_extract_mcp_payload_parses_json_text_content():
    result = SimpleNamespace(
        structuredContent=None,
        content=[SimpleNamespace(text='{"tools": [{"name": "get_me"}]}')],
    )

    assert extract_mcp_payload(result) == {"tools": [{"name": "get_me"}]}


def test_mcp_http_client_factory_ignores_environment_proxies():
    config = MCPGatewayConfig(
        enabled=True,
        gateway_url="https://gateway.example.com/mcp",
        auth_mode="iam",
        sts_provider_name="github-mcp-gateway",
        sts_agency_session_name="personal-assistant-github-mcp",
        timeout_seconds=30.0,
        tool_prefix="target-github-mcp",
    )
    client = MCPGatewayClient(
        config=config,
        sts_credentials=SimpleNamespace(
            access_key_id="test-ak",
            secret_access_key="test-sk",
            security_token="test-security-token",
        ),
    )

    factory = client._client().connections["github"]["httpx_client_factory"]
    http_client = factory(headers={}, timeout=httpx.Timeout(1.0), auth=None)

    try:
        assert http_client._trust_env is False
    finally:
        anyio.run(http_client.aclose)


def test_generic_mcp_error_maps_nested_remote_disconnect():
    exc = ExceptionGroup(
        "unhandled errors in a TaskGroup",
        [httpx.RemoteProtocolError("Server disconnected without sending a response.")],
    )

    error = _map_generic_mcp_error(exc)

    assert error.warning_type == "gateway_unavailable"
    assert error.retryable is True
