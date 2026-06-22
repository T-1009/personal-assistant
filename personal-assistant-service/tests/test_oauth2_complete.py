"""Tests for Calendar OAuth2 complete flow."""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from agentarts.sdk.runtime.model import USER_ID_HEADER

from app.main import app
from app.oauth2_state import create_oauth2_state
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
        oauth2_state_secret="test-secret",
    )


def _state(settings: Settings, user_id: str = "user-1") -> str:
    return create_oauth2_state(
        settings=settings,
        user_id=user_id,
        session_id="sess-1",
        provider=settings.m365_calendar_provider_name,
    )


@pytest.mark.asyncio
async def test_complete_requires_trusted_user_header(client, calendar_settings):
    state = _state(calendar_settings)
    with patch("app.main.get_settings", return_value=calendar_settings):
        response = await client.post(
            "/invocations/auth/oauth2/complete",
            json={
                "provider": "m365-calendar-provider",
                "session_uri": "urn:uuid:test",
                "state": state,
            },
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_complete_rejects_forged_user_id(client, calendar_settings):
    state = _state(calendar_settings, user_id="real-user")
    with patch("app.main.get_settings", return_value=calendar_settings):
        response = await client.post(
            "/invocations/auth/oauth2/complete",
            json={
                "provider": "m365-calendar-provider",
                "session_uri": "urn:uuid:test",
                "state": state,
                "user_id": "attacker",
            },
            headers={USER_ID_HEADER: "attacker"},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "invalid OAuth2 state"


@pytest.mark.asyncio
async def test_complete_calls_identity_client(client, calendar_settings):
    state = _state(calendar_settings)
    identity_client = MagicMock()

    with (
        patch("app.main.get_settings", return_value=calendar_settings),
        patch("app.main.IdentityClient", return_value=identity_client),
    ):
        response = await client.post(
            "/invocations/auth/oauth2/complete",
            json={
                "provider": "m365-calendar-provider",
                "session_uri": "urn:uuid:test",
                "state": state,
            },
            headers={USER_ID_HEADER: "user-1"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "complete"
    identity_client.complete_resource_token_auth.assert_called_once()
    kwargs = identity_client.complete_resource_token_auth.call_args.kwargs
    assert kwargs["session_uri"] == "urn:uuid:test"
    assert kwargs["user_identifier"].user_id == "user-1"


@pytest.mark.asyncio
async def test_complete_rejects_oauth_error(client, calendar_settings):
    state = _state(calendar_settings)
    with patch("app.main.get_settings", return_value=calendar_settings):
        response = await client.post(
            "/invocations/auth/oauth2/complete",
            json={
                "provider": "m365-calendar-provider",
                "session_uri": "urn:uuid:test",
                "state": state,
                "error": "access_denied",
            },
            headers={USER_ID_HEADER: "user-1"},
        )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Calendar authorization failed. Please try again."
    )
