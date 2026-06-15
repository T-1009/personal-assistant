"""Tests for Huawei Cloud IAM tools."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.tools.iam_tools import (
    _credentials_to_global_credentials,
    _list_iam_users,
    _normalize_user_item,
    list_iam_users,
)


def test_credentials_to_global_credentials_uses_sts_fields():
    sts = SimpleNamespace(
        access_key_id="ak",
        secret_access_key="sk",
        security_token="token",
    )

    credentials = _credentials_to_global_credentials(sts)

    assert credentials.ak == "ak"
    assert credentials.sk == "sk"
    assert credentials.security_token == "token"


def test_normalize_user_item_accepts_dicts():
    item = _normalize_user_item(
        {
            "user_id": "user-id",
            "user_name": "alice",
            "enabled": True,
            "is_root_user": False,
            "urn": "iam::123:user/alice",
        }
    )

    assert item.id == "user-id"
    assert item.name == "alice"
    assert item.user_id == "user-id"
    assert item.user_name == "alice"
    assert item.enabled is True
    assert item.is_root_user is False
    assert item.urn == "iam::123:user/alice"


@pytest.mark.asyncio
async def test_list_iam_users_uses_sdk_future_result(monkeypatch):
    captured = {}

    class FakeFuture:
        def result(self):
            return SimpleNamespace(users=[])

    class FakeClient:
        def list_users_v5_async(self, request):
            captured["request"] = request
            return FakeFuture()

    sts = SimpleNamespace(
        access_key_id="ak",
        secret_access_key="sk",
        security_token="token",
    )
    monkeypatch.setattr("app.tools.iam_tools._build_iam_client", lambda _: FakeClient())

    response = await _list_iam_users.__wrapped__(
        limit=50,
        marker="next-marker",
        group_id="group-id",
        sts_credentials=sts,
    )

    assert response.users == []
    request = captured["request"]
    assert request.limit == 50
    assert request.marker == "next-marker"
    assert request.group_id == "group-id"


@pytest.mark.asyncio
async def test_list_iam_users_returns_structure(monkeypatch):
    async def fake_list_users(**kwargs):
        assert kwargs == {
            "limit": 100,
            "marker": None,
            "group_id": "group-id",
        }
        return SimpleNamespace(
            users=[
                SimpleNamespace(
                    user_id="user-id",
                    user_name="alice",
                    enabled=True,
                    description="dev user",
                    is_root_user=False,
                    created_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
                    urn="iam::123:user/alice",
                )
            ],
            page_info=SimpleNamespace(
                next_marker="next-marker",
                current_count=1,
            ),
        )

    monkeypatch.setattr("app.tools.iam_tools._list_iam_users", fake_list_users)

    result = await list_iam_users(limit=100, group_id="group-id")

    assert result["ok"] is True
    assert result["api_version"] == "v5"
    assert result["provider_name"] == "iam-users-readonly"
    assert result["count"] == 1
    assert result["page_info"] == {
        "next_marker": "next-marker",
        "current_count": 1,
    }
    user = result["users"][0]
    assert user["id"] == "user-id"
    assert user["name"] == "alice"
    assert user["user_id"] == "user-id"
    assert user["user_name"] == "alice"
    assert user["is_root_user"] is False
    assert user["created_at"] == "2026-01-02T03:04:05+00:00"
    assert user["urn"] == "iam::123:user/alice"


@pytest.mark.asyncio
async def test_list_iam_users_returns_structured_error(monkeypatch):
    async def fake_list_users(**kwargs):
        raise RuntimeError("sts provider unavailable")

    monkeypatch.setattr("app.tools.iam_tools._list_iam_users", fake_list_users)

    result = await list_iam_users()

    assert result["ok"] is False
    assert result["provider_name"] == "iam-users-readonly"
    assert "Failed to list Huawei Cloud IAM users" in result["message"]
    assert "sts provider unavailable" in result["details"]
