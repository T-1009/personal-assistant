"""Tests for app.tools.gitee_tools."""

from __future__ import annotations

import pytest

from app.identity import AuthorizationRequired
from app.tools.gitee_tools import list_repositories


@pytest.mark.asyncio
async def test_list_repositories_returns_structure(monkeypatch):
    async def fake_request(method, path, *, params=None):
        assert method == "GET"
        assert path == "/user/repos"
        assert params["visibility"] == "all"
        assert params["sort"] == "full_name"
        assert params["page"] == 1
        assert params["per_page"] == 20
        return [
            {
                "name": "repo-a",
                "full_name": "alice/repo-a",
                "private": True,
                "human_name": "Repo A",
                "namespace": {"path": "alice"},
                "html_url": "https://gitee.com/alice/repo-a",
            }
        ]

    monkeypatch.setattr("app.tools.gitee_tools._gitee_request", fake_request)

    result = await list_repositories()
    assert result["ok"] is True
    assert result["count"] == 1
    repo = result["repositories"][0]
    assert repo["full_name"] == "alice/repo-a"
    assert repo["namespace"] == "alice"
    assert repo["private"] is True


@pytest.mark.asyncio
async def test_list_repositories_clamps_pagination(monkeypatch):
    async def fake_request(method, path, *, params=None):
        assert params["page"] == 1
        assert params["per_page"] == 100
        return []

    monkeypatch.setattr("app.tools.gitee_tools._gitee_request", fake_request)

    result = await list_repositories(page=0, per_page=200)
    assert result["ok"] is True
    assert result["count"] == 0


@pytest.mark.asyncio
async def test_list_repositories_rejects_conflicting_filters(monkeypatch):
    async def fake_request(method, path, *, params=None):
        raise AssertionError("validation should happen before Gitee request")

    monkeypatch.setattr("app.tools.gitee_tools._gitee_request", fake_request)

    result = await list_repositories(visibility="private", repo_type="owner")
    assert result["ok"] is False
    assert "repo_type cannot be combined" in result["message"]


@pytest.mark.asyncio
async def test_authorization_required_returns_structured_error(monkeypatch):
    async def fake_request(method, path, *, params=None):
        raise AuthorizationRequired(
            provider_name="gitee-provider",
            authorization_url="https://example.test/gitee-auth",
            message="authorization required",
        )

    monkeypatch.setattr("app.tools.gitee_tools._gitee_request", fake_request)

    result = await list_repositories()
    assert result["ok"] is False
    assert result["provider_name"] == "gitee-provider"
    assert result["authorization_url"] == "https://example.test/gitee-auth"
