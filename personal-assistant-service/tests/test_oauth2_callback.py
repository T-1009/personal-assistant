"""Tests for Calendar OAuth2 backend-owned callback completion."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.main import app
from app.oauth2_state import (
    clear_oauth2_state_active,
    create_oauth2_state,
    mark_oauth2_state_active,
    verify_oauth2_state,
)
from app.settings import Settings


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def calendar_settings():
    return Settings(
        m365_calendar_provider_name="m365-calendar-provider",
    )


def _state(settings: Settings, user_id: str = "user-1") -> str:
    return create_oauth2_state(
        settings=settings,
        user_id=user_id,
        session_id="session-1",
        provider=settings.m365_calendar_provider_name,
    )


class _IdentityPermissionError(Exception):
    status_code = 403

    def __str__(self) -> str:
        return (
            "ClientRequestException - {status_code:403,"
            "error_code:AgentIdentityTokenVault.1007,"
            "error_msg:not authorized to perform: "
            "agentIdentity::completeResourceTokenAuth}"
        )


def test_backend_callback_openapi_documents_html_and_json():
    operation = app.openapi()["paths"]["/auth/oauth2/callback/m365-calendar"]["get"]
    content = operation["responses"]["200"]["content"]

    assert set(content) == {"text/html", "application/json"}
    assert content["text/html"]["schema"] == {"type": "string"}
    assert content["application/json"]["schema"]["properties"]["status"] == {
        "description": "Backend-owned OAuth2 completion status.",
        "enum": ["complete", "failed", "pending"],
        "title": "Status",
        "type": "string",
    }


@pytest.mark.asyncio
async def test_backend_callback_completes_identity_with_state_user_id(
    client,
    calendar_settings,
):
    identity_client = MagicMock()
    state = _state(calendar_settings, user_id="state-user")

    with (
        patch("app.main.get_settings", return_value=calendar_settings),
        patch("app.main.IdentityClient", return_value=identity_client),
    ):
        response = await client.get(
            "/auth/oauth2/callback/m365-calendar",
            params={
                "session_uri": "urn:uuid:test",
                "state": state,
            },
        )

    assert response.status_code == 200
    assert "授权完成" in response.text
    assert "m365-calendar-auth" in response.text
    identity_client.complete_resource_token_auth.assert_called_once()
    kwargs = identity_client.complete_resource_token_auth.call_args.kwargs
    assert kwargs["session_uri"] == "urn:uuid:test"
    assert kwargs["user_identifier"].user_id == "state-user"


@pytest.mark.asyncio
async def test_backend_callback_returns_json_for_react_shell(
    client,
    calendar_settings,
):
    identity_client = MagicMock()
    state = _state(calendar_settings, user_id="state-user")

    with (
        patch("app.main.get_settings", return_value=calendar_settings),
        patch("app.main.IdentityClient", return_value=identity_client),
    ):
        response = await client.get(
            "/auth/oauth2/callback/m365-calendar",
            params={
                "session_uri": "urn:uuid:test",
                "state": state,
            },
            headers={"Accept": "application/json"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "type": "m365-calendar-auth",
        "requestId": state,
        "provider": "m365-calendar-provider",
        "status": "complete",
        "message": "日历授权已完成，可以关闭此窗口并重试刚才的问题。",
        "state": state,
    }


@pytest.mark.asyncio
async def test_backend_callback_rejects_invalid_state(client, calendar_settings):
    identity_client = MagicMock()

    with (
        patch("app.main.get_settings", return_value=calendar_settings),
        patch("app.main.IdentityClient", return_value=identity_client),
    ):
        response = await client.get(
            "/auth/oauth2/callback/m365-calendar",
            params={
                "session_uri": "urn:uuid:test",
                "state": "not-a-valid-state",
            },
        )

    assert response.status_code == 200
    assert "授权失败" in response.text
    assert "授权状态无效或已过期" in response.text
    identity_client.complete_resource_token_auth.assert_not_called()


@pytest.mark.asyncio
async def test_backend_callback_replay_does_not_call_identity_twice(
    client,
    calendar_settings,
):
    identity_client = MagicMock()
    state = _state(calendar_settings, user_id="state-user")

    with (
        patch("app.main.get_settings", return_value=calendar_settings),
        patch("app.main.IdentityClient", return_value=identity_client),
    ):
        first = await client.get(
            "/auth/oauth2/callback/m365-calendar",
            params={
                "session_uri": "urn:uuid:test",
                "state": state,
            },
        )
        second = await client.get(
            "/auth/oauth2/callback/m365-calendar",
            params={
                "session_uri": "urn:uuid:test",
                "state": state,
            },
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert "授权完成" in second.text
    identity_client.complete_resource_token_auth.assert_called_once()


@pytest.mark.asyncio
async def test_backend_callback_active_duplicate_does_not_call_identity(
    client,
    calendar_settings,
):
    identity_client = MagicMock()
    state = _state(calendar_settings, user_id="state-user")
    claims = verify_oauth2_state(
        state,
        settings=calendar_settings,
        expected_provider=calendar_settings.m365_calendar_provider_name,
    )
    assert mark_oauth2_state_active(claims)

    try:
        with (
            patch("app.main.get_settings", return_value=calendar_settings),
            patch("app.main.IdentityClient", return_value=identity_client),
        ):
            response = await client.get(
                "/auth/oauth2/callback/m365-calendar",
                params={
                    "session_uri": "urn:uuid:test",
                    "state": state,
                },
            )
    finally:
        clear_oauth2_state_active(claims)

    assert response.status_code == 200
    assert "授权处理中" in response.text
    identity_client.complete_resource_token_auth.assert_not_called()


@pytest.mark.asyncio
async def test_backend_callback_reports_oauth_error(client, calendar_settings):
    identity_client = MagicMock()

    with (
        patch("app.main.get_settings", return_value=calendar_settings),
        patch("app.main.IdentityClient", return_value=identity_client),
    ):
        response = await client.get(
            "/auth/oauth2/callback/m365-calendar",
            params={
                "error": "access_denied",
                "error_description": "用户取消授权",
                "state": "signed-state",
            },
        )

    assert response.status_code == 200
    assert "授权失败" in response.text
    assert "用户取消授权" in response.text
    identity_client.complete_resource_token_auth.assert_not_called()


@pytest.mark.asyncio
async def test_backend_callback_reports_identity_permission_error(
    client,
    calendar_settings,
):
    identity_client = MagicMock()
    identity_client.complete_resource_token_auth.side_effect = (
        _IdentityPermissionError()
    )
    state = _state(calendar_settings, user_id="state-user")

    with (
        patch("app.main.get_settings", return_value=calendar_settings),
        patch("app.main.IdentityClient", return_value=identity_client),
    ):
        response = await client.get(
            "/auth/oauth2/callback/m365-calendar",
            params={
                "session_uri": "urn:uuid:test",
                "state": state,
            },
        )

    assert response.status_code == 200
    assert "授权失败" in response.text
    assert "日历授权服务权限尚未配置完成" in response.text
