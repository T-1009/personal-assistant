"""Tests for internal GitHub MCP activity source functions."""

from __future__ import annotations

from typing import Any

import pytest

import app.tools.github_mcp_tools as gmt
from app.mcp.gateway_client import MCPGatewayError, MCPToolInfo


class FakeMCPClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def list_tools(self) -> list[MCPToolInfo]:
        return [
            MCPToolInfo("target-github-mcp_get_me", "Get me", {}),
            MCPToolInfo(
                "target-github-mcp_search_repositories",
                "Search repositories",
                {"properties": {"query": {}, "perPage": {}}},
            ),
            MCPToolInfo(
                "target-github-mcp_list_commits",
                "List commits",
                {
                    "properties": {
                        "owner": {},
                        "repo": {},
                        "since": {},
                        "until": {},
                        "perPage": {},
                    }
                },
            ),
            MCPToolInfo(
                "target-github-mcp_list_pull_requests",
                "List pull requests",
                {
                    "properties": {
                        "owner": {},
                        "repo": {},
                        "state": {},
                        "perPage": {},
                    }
                },
            ),
            MCPToolInfo(
                "target-github-mcp_list_issues",
                "List issues",
                {
                    "properties": {
                        "owner": {},
                        "repo": {},
                        "state": {},
                        "since": {},
                        "perPage": {},
                    }
                },
            ),
            MCPToolInfo(
                "target-github-mcp_get_issue_comments",
                "Get issue comments",
                {
                    "properties": {
                        "owner": {},
                        "repo": {},
                        "issueNumber": {},
                    }
                },
            ),
            MCPToolInfo(
                "target-github-mcp_create_issue",
                "Create issue",
                {"properties": {"owner": {}, "repo": {}, "title": {}}},
            ),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((name, arguments))
        if name.endswith("get_me"):
            return {"login": "T-1009"}
        if name.endswith("search_repositories"):
            return {
                "repositories": [
                    {
                        "name": "personal-assistant",
                        "full_name": "T-1009/personal-assistant",
                        "archived": False,
                    }
                ]
            }
        if name.endswith("list_commits"):
            return [
                {
                    "sha": "abcdef123456",
                    "html_url": "https://github.com/T-1009/personal-assistant/commit/abcdef",
                    "author": {"login": "T-1009"},
                    "commit": {
                        "message": "Implement feature 17",
                        "author": {"date": "2026-07-10T12:00:00Z"},
                    },
                    "stats": {"additions": 10, "deletions": 2},
                }
            ]
        if name.endswith("list_pull_requests"):
            return [
                {
                    "number": 17,
                    "title": "Feature 17",
                    "html_url": "https://github.com/T-1009/personal-assistant/pull/17",
                    "user": {"login": "T-1009"},
                    "state": "open",
                    "created_at": "2026-07-11T12:00:00Z",
                    "updated_at": "2026-07-12T12:00:00Z",
                    "comments": 1,
                }
            ]
        if name.endswith("list_issues"):
            return [
                {
                    "number": 99,
                    "title": "Track MCP smoke",
                    "html_url": "https://github.com/T-1009/personal-assistant/issues/99",
                    "user": {"login": "T-1009"},
                    "state": "open",
                    "created_at": "2026-07-09T12:00:00Z",
                    "updated_at": "2026-07-09T13:00:00Z",
                    "comments": 1,
                },
                {
                    "number": 17,
                    "pull_request": {},
                    "title": "PR issue shadow",
                },
            ]
        if name.endswith("get_issue_comments"):
            return {
                "comments": [
                    {
                        "id": 1,
                        "body": "Looks good",
                        "html_url": "https://github.com/T-1009/personal-assistant/issues/99#issuecomment-1",
                        "user": {"login": "T-1009"},
                        "created_at": "2026-07-09T14:00:00Z",
                    }
                ]
            }
        raise AssertionError(f"Unexpected tool: {name}")


class DetailMCPClient:
    def __init__(
        self,
        tool_name: str,
        number_argument: str,
        payload: dict[str, Any],
    ) -> None:
        self.tool_name = tool_name
        self.number_argument = number_argument
        self.payload = payload
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def list_tools(self) -> list[MCPToolInfo]:
        return [
            MCPToolInfo(
                self.tool_name,
                "Read activity detail",
                {
                    "properties": {
                        "method": {},
                        "owner": {},
                        "repo": {},
                        self.number_argument: {},
                    }
                },
            )
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((name, arguments))
        return self.payload


class CompleteIssueReadMCPClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.payloads = {
            "get": {"number": 17, "title": "Feature 17 issue", "state": "open"},
            "get_comments": [{"id": 1, "body": "First comment"}],
            "get_sub_issues": {"sub_issues": [{"number": 18}]},
            "get_parent": {"number": 10, "title": "Parent issue"},
            "get_labels": [{"name": "feature"}],
        }

    async def list_tools(self) -> list[MCPToolInfo]:
        return [
            MCPToolInfo(
                "target-github-mcp_issue_read",
                "Read issue data",
                {
                    "properties": {
                        "method": {"enum": list(self.payloads)},
                        "owner": {},
                        "repo": {},
                        "issue_number": {},
                    }
                },
            ),
            MCPToolInfo(
                "target-github-mcp_get_issue",
                "Get issue",
                {
                    "properties": {
                        "owner": {},
                        "repo": {},
                        "issue_number": {},
                    }
                },
            ),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        assert name == "target-github-mcp_issue_read"
        self.calls.append((name, arguments))
        return self.payloads[arguments["method"]]


class ReviewCommentDetailMCPClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.reviews = [
            {"id": 700, "state": "COMMENTED", "body": "Other review"},
            {"id": 701, "state": "APPROVED", "body": "Approved"},
        ]
        self.comments = {
            "comments": [
                {"id": 800, "body": "Other comment"},
                {"id": 801, "body": "Target comment"},
            ]
        }

    async def list_tools(self) -> list[MCPToolInfo]:
        return [
            MCPToolInfo(
                "target-github-mcp_pull_request_read",
                "Read pull request data",
                {
                    "properties": {
                        "method": {"enum": ["get_reviews"]},
                        "owner": {},
                        "repo": {},
                        "pullNumber": {},
                    }
                },
            ),
            MCPToolInfo(
                "target-github-mcp_issue_read",
                "Read issue data",
                {
                    "properties": {
                        "method": {"enum": ["get_comments"]},
                        "owner": {},
                        "repo": {},
                        "issue_number": {},
                    }
                },
            ),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((name, arguments))
        if name.endswith("pull_request_read"):
            return self.reviews
        if name.endswith("issue_read"):
            return self.comments
        raise AssertionError(f"Unexpected tool: {name}")


@pytest.fixture
def fake_client(monkeypatch):
    client = FakeMCPClient()

    async def fake_run(operation):
        return await operation(client)

    monkeypatch.setattr(gmt, "run_with_github_mcp_sts", fake_run)
    return client


def test_github_mcp_public_schema_is_secret_free():
    assert gmt.github_mcp_public_schema_is_secret_free() is True


def test_github_mcp_chat_tools_are_registered_without_credential_args():
    names = {tool.name for tool in gmt.GITHUB_MCP_CHAT_TOOLS}
    assert names == {
        "github_mcp_resolve_identity",
        "github_mcp_list_repositories",
        "github_mcp_search_activity",
        "github_mcp_get_detail",
    }

    for chat_tool in gmt.GITHUB_MCP_CHAT_TOOLS:
        fields = getattr(chat_tool.args_schema, "model_fields", {})
        assert {
            "access_token",
            "api_key",
            "authorization",
            "sts",
        }.isdisjoint(fields)


def test_read_only_activity_tool_allowlist_blocks_writes():
    assert gmt.is_read_only_activity_tool("target-github-mcp_get_me") is True
    assert gmt.is_read_only_activity_tool("target-github-mcp_create_issue") is False
    assert gmt.is_read_only_activity_tool("target-github-mcp_delete_file") is False


@pytest.mark.asyncio
async def test_resolve_identity_returns_platform_account(fake_client):
    result = await gmt.github_mcp_resolve_identity()

    assert result == {"login": "T-1009"}
    assert fake_client.calls[0] == ("target-github-mcp_get_me", {})


@pytest.mark.asyncio
async def test_list_repositories_uses_search_repositories(fake_client):
    result = await gmt.github_mcp_list_repositories(limit=5)

    assert isinstance(result, list)
    assert result[0]["full_name"] == "T-1009/personal-assistant"
    search_call = fake_client.calls[-1]
    assert search_call[0] == "target-github-mcp_search_repositories"
    assert search_call[1]["query"] == "user:T-1009"


@pytest.mark.asyncio
async def test_search_activity_normalizes_events(fake_client):
    result = await gmt.github_mcp_search_activity(
        start_at="2026-07-01T00:00:00+08:00",
        end_at="2026-07-13T23:59:59+08:00",
        repositories=["T-1009/personal-assistant"],
        event_types=["commit", "pull_request", "issue", "comment"],
        limit=10,
    )

    assert isinstance(result, list)
    event_types = {event.event_type for event in result}
    assert event_types == {"commit", "pull_request", "issue", "comment"}
    commit = next(event for event in result if event.event_type == "commit")
    assert commit.external_id == "abcdef123456"
    assert commit.metrics["additions"] == 10
    issue = next(event for event in result if event.event_type == "issue")
    assert issue.external_id == "99"


@pytest.mark.asyncio
async def test_chat_search_activity_returns_json_safe_result(fake_client):
    result = await gmt.chat_github_mcp_search_activity(
        start_at="2026-07-01T00:00:00+08:00",
        end_at="2026-07-13T23:59:59+08:00",
        repositories=["T-1009/personal-assistant"],
        event_types=["commit"],
        limit=10,
    )

    assert result["ok"] is True
    assert result["count"] == 1
    assert result["events"][0]["event_type"] == "commit"
    assert result["events"][0]["repository"] == "T-1009/personal-assistant"


@pytest.mark.asyncio
async def test_search_activity_maps_gateway_error_to_warning(monkeypatch):
    async def fake_run(operation):
        raise MCPGatewayError(
            "permission_denied",
            "GitHub MCP Gateway rejected the caller permissions.",
        )

    monkeypatch.setattr(gmt, "run_with_github_mcp_sts", fake_run)

    result = await gmt.github_mcp_search_activity(
        start_at="2026-07-01T00:00:00+08:00",
        end_at="2026-07-13T23:59:59+08:00",
    )

    assert isinstance(result, gmt.GitHubMCPWarning)
    assert result.warning_type == "permission_denied"
    assert "permissions" in result.message


@pytest.mark.parametrize(
    ("event_type", "tool_name", "number_argument", "payload"),
    [
        (
            "pull_request",
            "target-github-mcp_pull_request_read",
            "pullNumber",
            {"number": 17, "title": "Feature 17", "state": "open"},
        ),
        (
            "issue",
            "target-github-mcp_issue_read",
            "issue_number",
            {"number": 17, "title": "Feature 17 issue", "state": "open"},
        ),
    ],
)
@pytest.mark.asyncio
async def test_get_detail_sets_get_method_for_aggregate_read_tools(
    monkeypatch,
    event_type,
    tool_name,
    number_argument,
    payload,
):
    client = DetailMCPClient(tool_name, number_argument, payload)

    async def fake_run(operation):
        return await operation(client)

    monkeypatch.setattr(gmt, "run_with_github_mcp_sts", fake_run)

    result = await gmt.github_mcp_get_detail(
        event_type=event_type,
        repository="T-1009/personal-assistant",
        external_id="17",
    )

    assert isinstance(result, gmt.GitHubActivityEvent)
    assert client.calls == [
        (
            tool_name,
            {
                "method": "get",
                "owner": "T-1009",
                "repo": "personal-assistant",
                number_argument: 17,
            },
        )
    ]


@pytest.mark.asyncio
async def test_get_issue_detail_calls_every_supported_issue_read_method(monkeypatch):
    client = CompleteIssueReadMCPClient()

    async def fake_run(operation):
        return await operation(client)

    monkeypatch.setattr(gmt, "run_with_github_mcp_sts", fake_run)

    result = await gmt.github_mcp_get_detail(
        event_type="issue",
        repository="T-1009/personal-assistant",
        external_id="17",
    )

    assert isinstance(result, gmt.GitHubActivityEvent)
    assert [arguments["method"] for _, arguments in client.calls] == [
        "get",
        "get_comments",
        "get_sub_issues",
        "get_parent",
        "get_labels",
    ]
    assert all(
        arguments["owner"] == "T-1009"
        and arguments["repo"] == "personal-assistant"
        and arguments["issue_number"] == 17
        for _, arguments in client.calls
    )
    assert result.details == {
        "issue": client.payloads["get"],
        "comments": client.payloads["get_comments"],
        "sub_issues": client.payloads["get_sub_issues"],
        "parent": client.payloads["get_parent"],
        "labels": client.payloads["get_labels"],
    }


@pytest.mark.asyncio
async def test_search_comment_event_includes_parent_external_id(fake_client):
    result = await gmt.github_mcp_search_activity(
        start_at="2026-07-01T00:00:00+08:00",
        end_at="2026-07-13T23:59:59+08:00",
        repositories=["T-1009/personal-assistant"],
        event_types=["issue", "comment"],
        limit=10,
    )

    assert isinstance(result, list)
    comment = next(event for event in result if event.event_type == "comment")
    assert comment.external_id == "1"
    assert comment.parent_external_id == "99"


@pytest.mark.parametrize(
    (
        "event_type",
        "external_id",
        "parent_external_id",
        "method",
        "number_argument",
        "detail_key",
    ),
    [
        ("review", "701", "17", "get_reviews", "pullNumber", "review"),
        ("comment", "801", "99", "get_comments", "issue_number", "comment"),
    ],
)
@pytest.mark.asyncio
async def test_get_detail_supports_review_and_comment(
    monkeypatch,
    event_type,
    external_id,
    parent_external_id,
    method,
    number_argument,
    detail_key,
):
    client = ReviewCommentDetailMCPClient()

    async def fake_run(operation):
        return await operation(client)

    monkeypatch.setattr(gmt, "run_with_github_mcp_sts", fake_run)

    result = await gmt.github_mcp_get_detail(
        event_type=event_type,
        repository="T-1009/personal-assistant",
        external_id=external_id,
        parent_external_id=parent_external_id,
    )

    assert isinstance(result, gmt.GitHubActivityEvent)
    assert result.event_type == event_type
    assert result.external_id == external_id
    assert result.parent_external_id == parent_external_id
    assert result.details[detail_key]["id"] == int(external_id)
    assert client.calls == [
        (
            client.calls[0][0],
            {
                "method": method,
                "owner": "T-1009",
                "repo": "personal-assistant",
                number_argument: int(parent_external_id),
            },
        )
    ]


@pytest.mark.parametrize("event_type", ["review", "comment"])
@pytest.mark.asyncio
async def test_get_detail_requires_parent_external_id(event_type):
    result = await gmt.github_mcp_get_detail(
        event_type=event_type,
        repository="T-1009/personal-assistant",
        external_id="123",
    )

    assert isinstance(result, gmt.GitHubMCPWarning)
    assert result.warning_type == "configuration_error"
    assert "parent_external_id" in result.message


def test_get_detail_chat_schema_includes_parent_external_id():
    detail_tool = next(
        tool
        for tool in gmt.GITHUB_MCP_CHAT_TOOLS
        if tool.name == "github_mcp_get_detail"
    )
    schema = detail_tool.args_schema.model_json_schema()

    assert "parent_external_id" in schema["properties"]
    assert set(schema["properties"]["event_type"]["enum"]) == {
        "commit",
        "pull_request",
        "issue",
        "review",
        "comment",
    }
