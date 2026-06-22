"""Unit tests for Microsoft 365 Calendar tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.tools.calendar_tools as ct


@pytest.fixture(autouse=True)
def unwrap_calendar_tools():
    saved = {}
    for name in [
        "list_calendar_events",
        "get_calendar_event",
        "search_calendar_events",
    ]:
        wrapped = getattr(ct, name)
        saved[name] = wrapped
        raw = wrapped
        while hasattr(raw, "__wrapped__"):
            raw = raw.__wrapped__
        setattr(ct, name, raw)
    yield
    for name, original in saved.items():
        setattr(ct, name, original)


@pytest.fixture(autouse=True)
def reset_shared_client():
    ct._client = None
    yield
    ct._client = None


def _response(json_data: dict, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data
    response.raise_for_status = MagicMock()
    return response


def _mock_client(response: MagicMock) -> AsyncMock:
    client = AsyncMock()
    client.get.return_value = response
    return client


@pytest.mark.asyncio
async def test_list_calendar_events_formats_graph_request_and_response():
    response = _response(
        {
            "value": [
                {
                    "id": "event-1",
                    "subject": "Project Sync",
                    "start": {"dateTime": "2026-06-22T09:00:00", "timeZone": "UTC"},
                    "end": {"dateTime": "2026-06-22T10:00:00", "timeZone": "UTC"},
                    "location": {"displayName": "Room A"},
                    "organizer": {
                        "emailAddress": {
                            "name": "Alice",
                            "address": "alice@example.com",
                        }
                    },
                    "attendees": [],
                    "isOnlineMeeting": True,
                    "onlineMeetingUrl": "https://teams.example/meet",
                    "webLink": "https://outlook.example/event",
                    "bodyPreview": "Weekly sync",
                }
            ]
        }
    )
    client = _mock_client(response)

    with (
        patch("app.tools.calendar_tools._get_client", return_value=client),
        patch("app.tools.calendar_tools._push_auth_complete"),
    ):
        result = await ct.list_calendar_events(
            "2026-06-22T00:00:00",
            "2026-06-23T00:00:00",
            access_token="token",
        )

    assert result["count"] == 1
    assert result["events"][0]["subject"] == "Project Sync"
    assert result["events"][0]["location"] == "Room A"
    client.get.assert_awaited_once()
    args, kwargs = client.get.call_args
    assert args[0] == "https://graph.microsoft.com/v1.0/me/calendarView"
    assert kwargs["headers"]["Authorization"] == "Bearer token"
    assert "outlook.timezone" in kwargs["headers"]["Prefer"]
    assert kwargs["params"]["startDateTime"] == "2026-06-22T00:00:00"
    assert kwargs["params"]["endDateTime"] == "2026-06-23T00:00:00"
    assert kwargs["params"]["$top"] == 20


@pytest.mark.asyncio
async def test_get_calendar_event_uses_calendar_scoped_url_when_calendar_id_given():
    response = _response({"id": "event-1", "subject": "One on One"})
    client = _mock_client(response)

    with (
        patch("app.tools.calendar_tools._get_client", return_value=client),
        patch("app.tools.calendar_tools._push_auth_complete"),
    ):
        result = await ct.get_calendar_event(
            "event-1",
            calendar_id="calendar-1",
            access_token="token",
        )

    assert result["event"]["subject"] == "One on One"
    args, _kwargs = client.get.call_args
    assert (
        args[0]
        == "https://graph.microsoft.com/v1.0/me/calendars/calendar-1/events/event-1"
    )


@pytest.mark.asyncio
async def test_search_calendar_events_with_time_window_filters_locally():
    response = _response(
        {
            "value": [
                {"id": "event-1", "subject": "Design Review"},
                {"id": "event-2", "subject": "Lunch"},
            ]
        }
    )
    client = _mock_client(response)

    with (
        patch("app.tools.calendar_tools._get_client", return_value=client),
        patch("app.tools.calendar_tools._push_auth_complete"),
    ):
        result = await ct.search_calendar_events(
            "design",
            start_time="2026-06-22T00:00:00",
            end_time="2026-06-23T00:00:00",
            access_token="token",
        )

    assert result["count"] == 1
    assert result["events"][0]["subject"] == "Design Review"


@pytest.mark.asyncio
async def test_calendar_tools_return_auth_required_when_sdk_injects_no_token():
    def fake_require_access_token(**_kwargs):
        def decorator(func):
            async def wrapper(*args, **kwargs):
                kwargs["access_token"] = None
                return await func(*args, **kwargs)

            return wrapper

        return decorator

    with patch(
        "app.tools.calendar_tools.require_access_token",
        fake_require_access_token,
    ):
        result = await ct.list_calendar_events(
            "2026-06-22T00:00:00",
            "2026-06-23T00:00:00",
        )

    assert result["auth_required"] is True
