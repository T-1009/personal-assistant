"""Tests for app.tools.github_tools."""

from __future__ import annotations

import base64

import pytest

from app.identity import AuthorizationRequired
from app.tools.github_tools import (
    get_file_content,
    list_repo_contents,
    list_repositories,
    search_code,
)


@pytest.mark.asyncio
async def test_list_repositories_returns_structure(monkeypatch):
    async def fake_request(method, path, *, params=None):
        assert method == "GET"
        assert path == "/user/repos"
        return [
            {
                "name": "repo-a",
                "full_name": "alice/repo-a",
                "private": True,
                "default_branch": "main",
            }
        ]

    monkeypatch.setattr("app.tools.github_tools._github_request", fake_request)

    result = await list_repositories()
    assert isinstance(result, list)
    assert result[0]["full_name"] == "alice/repo-a"
    assert result[0]["private"] is True


@pytest.mark.asyncio
async def test_list_repo_contents_encodes_path(monkeypatch):
    async def fake_request(method, path, *, params=None):
        assert path == "/repos/alice/repo/contents/src/app"
        return [{"path": "src/app", "type": "dir", "name": "app"}]

    monkeypatch.setattr("app.tools.github_tools._github_request", fake_request)

    result = await list_repo_contents("alice", "repo", "src/app")
    assert isinstance(result, list)
    assert result[0]["path"] == "src/app"


@pytest.mark.asyncio
async def test_get_file_content_decodes_base64(monkeypatch):
    encoded = base64.b64encode(b"hello world").decode()

    async def fake_request(method, path, *, params=None):
        return {
            "path": "README.md",
            "type": "file",
            "encoding": "base64",
            "content": encoded,
        }

    monkeypatch.setattr("app.tools.github_tools._github_request", fake_request)

    result = await get_file_content("alice", "repo", "README.md")
    assert result["content"] == "hello world"


@pytest.mark.asyncio
async def test_search_code_returns_items(monkeypatch):
    async def fake_request(method, path, *, params=None):
        assert path == "/search/code"
        assert params == {"q": "print('x')"}
        return {"items": [{"name": "main.py"}]}

    monkeypatch.setattr("app.tools.github_tools._github_request", fake_request)

    result = await search_code("print('x')")
    assert isinstance(result, list)
    assert result[0]["name"] == "main.py"


@pytest.mark.asyncio
async def test_authorization_required_returns_structured_error(monkeypatch):
    async def fake_request(method, path, *, params=None):
        raise AuthorizationRequired(
            provider_name="github-provider",
            authorization_url="https://example.test/auth",
            message="authorization required",
        )

    monkeypatch.setattr("app.tools.github_tools._github_request", fake_request)

    result = await list_repositories()
    assert isinstance(result, dict)
    assert result["ok"] is False
    assert result["provider_name"] == "github-provider"
    assert result["authorization_url"] == "https://example.test/auth"
