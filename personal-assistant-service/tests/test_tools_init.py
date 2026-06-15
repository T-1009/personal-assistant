"""Unit tests for app.tools — build_tools() factory function.

Feature 10a: Outbound Email — verifies the factory correctly discovers
and collects tools from sub-modules.
"""

import sys
from unittest.mock import patch

from app.tools import build_tools


def _tool_name(tool) -> str:
    return tool.name if hasattr(tool, "name") else tool.__name__


class TestBuildTools:
    """Tests for build_tools() factory function."""

    def test_build_tools_returns_list(self) -> None:
        """UT-TI-01: build_tools() returns a list."""
        with patch("app.tools.email_tools.ensure_provider_sync", return_value=True):
            result = build_tools()
        assert isinstance(result, list)

    def test_build_tools_includes_email_tools(self) -> None:
        """UT-TI-02: build_tools() includes all 5 email tools."""
        with patch("app.tools.email_tools.ensure_provider_sync", return_value=True):
            result = build_tools()

        result_names = [_tool_name(t) for t in result]
        expected = [
            "list_emails",
            "get_email",
            "search_emails",
            "send_email",
            "reply_to_email",
        ]
        for name in expected:
            assert name in result_names, (
                f"Expected {name} in build_tools() result, got {result_names}"
            )

    def test_build_tools_includes_github_tools(self) -> None:
        """UT-TI-05: build_tools() includes all GitHub tools."""
        with patch("app.tools.email_tools.ensure_provider_sync", return_value=True):
            result = build_tools()

        result_names = [_tool_name(t) for t in result]
        expected = [
            "github_list_repositories",
            "github_list_repo_contents",
            "github_get_file_content",
            "github_search_code",
            "github_star_repository",
        ]
        for name in expected:
            assert name in result_names, (
                f"Expected {name} in build_tools() result, got {result_names}"
            )

    def test_build_tools_includes_gitee_tools(self) -> None:
        """UT-TI-06: build_tools() includes Gitee tools."""
        with patch("app.tools.email_tools.ensure_provider_sync", return_value=True):
            result = build_tools()

        result_names = [_tool_name(t) for t in result]
        assert "gitee_list_repositories" in result_names

    def test_build_tools_includes_iam_tools(self) -> None:
        """UT-TI-07: build_tools() includes Huawei Cloud IAM tools."""
        with patch("app.tools.email_tools.ensure_provider_sync", return_value=True):
            result = build_tools()

        result_names = [_tool_name(t) for t in result]
        assert "huaweicloud_list_iam_users" in result_names

    def test_build_tools_graceful_import_error(self) -> None:
        """UT-TI-03: build_tools() does NOT raise when email_tools import fails."""
        # Ensure the module is in sys.modules before we set it to None
        _ = sys.modules.get("app.tools.email_tools")

        with patch.dict(sys.modules, {"app.tools.email_tools": None}):
            result = build_tools()

        # Should return a list (possibly empty) without raising
        assert isinstance(result, list)

    def test_build_tools_deduplicates(self) -> None:
        """UT-TI-04: each tool function appears only once in the result list."""
        with patch("app.tools.email_tools.ensure_provider_sync", return_value=True):
            result = build_tools()

        names = [_tool_name(t) for t in result]
        assert len(names) == len(set(names)), f"Duplicate tool names detected: {names}"
