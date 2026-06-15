"""Tests for Huawei Cloud IAM tools."""

from __future__ import annotations

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
            "id": "user-id",
            "name": "alice",
            "domain_id": "domain-id",
            "enabled": True,
            "access_mode": "default",
        }
    )

    assert item.id == "user-id"
    assert item.name == "alice"
    assert item.domain_id == "domain-id"
    assert item.enabled is True
    assert item.access_mode == "default"


@pytest.mark.asyncio
async def test_list_iam_users_uses_sdk_future_result(monkeypatch):
    captured = {}

    class FakeFuture:
        def result(self):
            return SimpleNamespace(users=[])

    class FakeClient:
        def keystone_list_users_async(self, request):
            captured["request"] = request
            return FakeFuture()

    sts = SimpleNamespace(
        access_key_id="ak",
        secret_access_key="sk",
        security_token="token",
    )
    monkeypatch.setattr("app.tools.iam_tools._build_iam_client", lambda _: FakeClient())

    response = await _list_iam_users.__wrapped__(
        domain_id="domain-id",
        enabled=False,
        name="bob",
        password_expires_at="lt:2026-12-01T00:00:00Z",
        sts_credentials=sts,
    )

    assert response.users == []
    request = captured["request"]
    assert request.domain_id == "domain-id"
    assert request.enabled is False
    assert request.name == "bob"
    assert request.password_expires_at == "lt:2026-12-01T00:00:00Z"


@pytest.mark.asyncio
async def test_list_iam_users_returns_structure(monkeypatch):
    async def fake_list_users(**kwargs):
        assert kwargs == {
            "domain_id": "domain-id",
            "enabled": True,
            "name": "alice",
            "password_expires_at": None,
        }
        return SimpleNamespace(
            users=[
                SimpleNamespace(
                    id="user-id",
                    name="alice",
                    domain_id="domain-id",
                    enabled=True,
                    description="dev user",
                    access_mode="programmatic",
                    pwd_status=False,
                    pwd_strength="high",
                    password_expires_at=None,
                    last_project_id="project-id",
                )
            ]
        )

    monkeypatch.setattr("app.tools.iam_tools._list_iam_users", fake_list_users)

    result = await list_iam_users(domain_id="domain-id", enabled=True, name="alice")

    assert result["ok"] is True
    assert result["provider_name"] == "iam-users-readonly"
    assert result["count"] == 1
    user = result["users"][0]
    assert user["id"] == "user-id"
    assert user["name"] == "alice"
    assert user["access_mode"] == "programmatic"


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
