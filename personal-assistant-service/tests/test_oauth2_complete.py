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
    )


def _state(settings: Settings, user_id: str = "user-1") -> str:
    return create_oauth2_state(
        settings=settings,
        user_id=user_id,
        session_id="session-1",
        provider=settings.m365_calendar_provider_name,
    )


@pytest.mark.asyncio
async def test_complete_requires_trusted_user_header(client, calendar_settings):
    with patch("app.main.get_settings", return_value=calendar_settings):
        response = await client.post(
            "/invocations/auth/oauth2/complete",
            json={
                "provider": "m365-calendar-provider",
                "session_uri": "urn:uuid:test",
            },
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_complete_rejects_unsupported_provider(client, calendar_settings):
    with patch("app.main.get_settings", return_value=calendar_settings):
        response = await client.post(
            "/invocations/auth/oauth2/complete",
            json={
                "provider": "other-provider",
                "session_uri": "urn:uuid:test",
            },
            headers={USER_ID_HEADER: "user-1"},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "unsupported OAuth2 provider"


@pytest.mark.asyncio
async def test_complete_calls_identity_client(client, calendar_settings):
    identity_client = MagicMock()
    state = _state(calendar_settings)

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
async def test_complete_requires_state(client, calendar_settings):
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
            },
            headers={USER_ID_HEADER: "user-1"},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "state is required"
    identity_client.complete_resource_token_auth.assert_not_called()


@pytest.mark.asyncio
async def test_complete_rejects_invalid_state(client, calendar_settings):
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
                "state": "not-a-valid-state",
            },
            headers={USER_ID_HEADER: "user-1"},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "invalid OAuth2 state"
    identity_client.complete_resource_token_auth.assert_not_called()


@pytest.mark.asyncio
async def test_complete_rejects_oauth_error(client, calendar_settings):
    with patch("app.main.get_settings", return_value=calendar_settings):
        response = await client.post(
            "/invocations/auth/oauth2/complete",
            json={
                "provider": "m365-calendar-provider",
                "session_uri": "urn:uuid:test",
                "error": "access_denied",
            },
            headers={USER_ID_HEADER: "user-1"},
        )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Calendar authorization failed. Please try again."
    )
