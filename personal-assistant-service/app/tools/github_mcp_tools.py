"""Internal GitHub MCP activity data source functions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

from langchain_core.tools import tool as lc_tool

from app.mcp.gateway_client import (
    MCPGatewayClient,
    MCPGatewayError,
    MCPToolInfo,
    run_with_github_mcp_sts,
)

GitHubActivityType = Literal[
    "commit",
    "pull_request",
    "issue",
    "review",
    "comment",
]

_DEFAULT_EVENT_TYPES: tuple[GitHubActivityType, ...] = (
    "commit",
    "pull_request",
    "issue",
    "review",
    "comment",
)

_ISSUE_READ_METHODS = (
    "get",
    "get_comments",
    "get_sub_issues",
    "get_parent",
    "get_labels",
)

_ISSUE_DETAIL_KEYS = {
    "get": "issue",
    "get_comments": "comments",
    "get_sub_issues": "sub_issues",
    "get_parent": "parent",
    "get_labels": "labels",
}

_READ_TOOL_SUFFIXES = frozenset(
    {
        "get_me",
        "search_repositories",
        "list_commits",
        "get_commit",
        "list_pull_requests",
        "search_pull_requests",
        "get_pull_request",
        "pull_request_read",
        "get_pull_request_comments",
        "get_pull_request_files",
        "get_pull_request_reviews",
        "list_issues",
        "search_issues",
        "get_issue",
        "issue_read",
        "get_issue_comments",
    }
)

_SENSITIVE_WORDS = frozenset(
    {
        "access_token",
        "api_key",
        "authorization",
        "bearer",
        "secret",
        "security_token",
        "x_security_token",
        "x_sdk_date",
        "sts",
    }
)


@dataclass(slots=True)
class GitHubActivityEvent:
    provider: str
    event_type: GitHubActivityType
    repository: str
    external_id: str
    title: str
    parent_external_id: str | None = None
    url: str | None = None
    actor: str | None = None
    state: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    summary: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class GitHubMCPWarning:
    ok: bool
    warning_type: str
    message: str
    retryable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _warning(
    warning_type: str,
    message: str,
    *,
    retryable: bool = False,
) -> GitHubMCPWarning:
    return GitHubMCPWarning(
        ok=False,
        warning_type=warning_type,
        message=message,
        retryable=retryable,
    )


def _warning_from_error(error: Exception) -> GitHubMCPWarning:
    if isinstance(error, MCPGatewayError):
        return _warning(
            error.warning_type,
            str(error),
            retryable=error.retryable,
        )
    return _warning(
        "mcp_error",
        "GitHub MCP activity source failed.",
        retryable=False,
    )


def _normalize_tool_name(name: str) -> str:
    return name.replace("-", "_").lower()


def _matches_tool_suffix(tool_name: str, suffix: str) -> bool:
    normalized = _normalize_tool_name(tool_name)
    normalized_suffix = _normalize_tool_name(suffix)
    return normalized == normalized_suffix or normalized.endswith(
        f"_{normalized_suffix}"
    )


def is_read_only_activity_tool(tool_name: str) -> bool:
    """Return whether a remote GitHub MCP tool is in the activity allowlist."""
    return any(
        _matches_tool_suffix(tool_name, suffix) for suffix in _READ_TOOL_SUFFIXES
    )


def _build_tool_index(tools: list[MCPToolInfo]) -> dict[str, MCPToolInfo]:
    return {tool.name: tool for tool in tools if is_read_only_activity_tool(tool.name)}


def _find_tool(
    tools: dict[str, MCPToolInfo],
    suffixes: tuple[str, ...],
) -> MCPToolInfo:
    for suffix in suffixes:
        for tool in tools.values():
            if _matches_tool_suffix(tool.name, suffix):
                return tool
    raise MCPGatewayError(
        "capability_missing",
        "GitHub MCP Gateway does not expose the required read-only tool.",
        retryable=False,
    )


def _find_optional_tool(
    tools: dict[str, MCPToolInfo],
    suffixes: tuple[str, ...],
) -> MCPToolInfo | None:
    try:
        return _find_tool(tools, suffixes)
    except MCPGatewayError:
        return None


def _schema_properties(tool: MCPToolInfo) -> dict[str, Any]:
    properties = tool.input_schema.get("properties")
    return properties if isinstance(properties, dict) else {}


def _candidate_names(name: str) -> tuple[str, ...]:
    if "_" not in name:
        return (name,)
    parts = name.split("_")
    camel = parts[0] + "".join(part.title() for part in parts[1:])
    return (name, camel)


def _argument_name(tool: MCPToolInfo, *candidates: str) -> str | None:
    properties = _schema_properties(tool)
    if not properties:
        return candidates[0] if candidates else None

    for candidate in candidates:
        for expanded in _candidate_names(candidate):
            if expanded in properties:
                return expanded
    return None


def _set_arg(
    args: dict[str, Any],
    tool: MCPToolInfo,
    value: Any,
    *candidates: str,
    required: bool = False,
) -> None:
    if value is None:
        return
    name = _argument_name(tool, *candidates)
    if name is None:
        if not required:
            return
        name = candidates[0]
    args[name] = value


def _repo_parts(repository: str) -> tuple[str, str]:
    owner, separator, repo = repository.strip().partition("/")
    if not owner or not separator or not repo:
        raise ValueError("repository must use owner/repo format")
    return owner, repo


def _get_nested(item: Any, *keys: str) -> Any:
    current = item
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
    return current


def _first_text(value: str | None, *, limit: int = 160) -> str:
    if not value:
        return ""
    text = " ".join(value.strip().split())
    return text[:limit]


def _coerce_items(payload: Any, *keys: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    for key in ("items", "repositories", "commits", "pull_requests", "issues"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return [payload]


def _parse_datetime(value: str | datetime | None, timezone: str) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(timezone))
    return parsed.astimezone(UTC)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _timestamp_in_window(
    value: str | None,
    *,
    start_at: datetime,
    end_at: datetime,
    timezone: str,
) -> bool:
    parsed = _parse_datetime(value, timezone)
    if parsed is None:
        return True
    return start_at <= parsed <= end_at


def _actor_matches(actor: str | None, expected: str | None) -> bool:
    return expected is None or actor == expected


def _event_matches(
    event: GitHubActivityEvent,
    *,
    start_at: datetime,
    end_at: datetime,
    timezone: str,
    actor: str | None,
) -> bool:
    event_time = event.updated_at or event.created_at
    return _actor_matches(event.actor, actor) and _timestamp_in_window(
        event_time,
        start_at=start_at,
        end_at=end_at,
        timezone=timezone,
    )


def _login_from_payload(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    login = payload.get("login")
    if isinstance(login, str) and login:
        return login
    user = payload.get("user")
    if isinstance(user, dict) and isinstance(user.get("login"), str):
        return user["login"]
    return None


def _commit_to_event(item: dict[str, Any], repository: str) -> GitHubActivityEvent:
    commit = item.get("commit") if isinstance(item.get("commit"), dict) else {}
    author = _get_nested(item, "author", "login") or _get_nested(
        commit, "author", "name"
    )
    message = _get_nested(commit, "message")
    title = _first_text(message).split("\\n", maxsplit=1)[0]
    created_at = _get_nested(commit, "author", "date") or _get_nested(
        commit, "committer", "date"
    )
    sha = str(item.get("sha") or item.get("node_id") or "")
    stats = item.get("stats") if isinstance(item.get("stats"), dict) else {}
    return GitHubActivityEvent(
        provider="github",
        event_type="commit",
        repository=repository,
        external_id=sha,
        title=title or sha[:12],
        url=item.get("html_url"),
        actor=author,
        state=None,
        created_at=created_at,
        updated_at=created_at,
        summary=title or None,
        metrics={
            key: stats[key]
            for key in ("additions", "deletions", "total")
            if key in stats
        },
    )


def _pull_request_to_event(
    item: dict[str, Any],
    repository: str,
) -> GitHubActivityEvent:
    number = item.get("number") or item.get("pull_number") or item.get("id")
    merged_at = item.get("merged_at")
    state = "merged" if merged_at else item.get("state")
    title = str(item.get("title") or f"Pull request {number}")
    return GitHubActivityEvent(
        provider="github",
        event_type="pull_request",
        repository=repository,
        external_id=str(number or ""),
        title=title,
        url=item.get("html_url") or item.get("url"),
        actor=_get_nested(item, "user", "login") or item.get("author"),
        state=state,
        created_at=item.get("created_at"),
        updated_at=item.get("updated_at") or merged_at,
        summary=title,
        metrics={
            key: item[key]
            for key in ("additions", "deletions", "changed_files", "comments")
            if key in item
        },
    )


def _issue_to_event(item: dict[str, Any], repository: str) -> GitHubActivityEvent:
    number = item.get("number") or item.get("id")
    title = str(item.get("title") or f"Issue {number}")
    return GitHubActivityEvent(
        provider="github",
        event_type="issue",
        repository=repository,
        external_id=str(number or ""),
        title=title,
        url=item.get("html_url") or item.get("url"),
        actor=_get_nested(item, "user", "login") or item.get("author"),
        state=item.get("state"),
        created_at=item.get("created_at"),
        updated_at=item.get("updated_at") or item.get("closed_at"),
        summary=title,
        metrics={
            key: item[key]
            for key in ("comments", "reactions")
            if key in item and not isinstance(item[key], dict)
        },
    )


def _comment_to_event(
    item: dict[str, Any],
    repository: str,
    *,
    parent_external_id: str,
    title_prefix: str,
) -> GitHubActivityEvent:
    body = _first_text(item.get("body"))
    external_id = item.get("id") or item.get("node_id")
    return GitHubActivityEvent(
        provider="github",
        event_type="comment",
        repository=repository,
        external_id=str(external_id or ""),
        title=f"{title_prefix}: {body}" if body else title_prefix,
        parent_external_id=parent_external_id,
        url=item.get("html_url") or item.get("url"),
        actor=_get_nested(item, "user", "login") or item.get("author"),
        state=None,
        created_at=item.get("created_at"),
        updated_at=item.get("updated_at") or item.get("created_at"),
        summary=body or None,
    )


def _review_to_event(
    item: dict[str, Any],
    repository: str,
    *,
    parent_external_id: str,
) -> GitHubActivityEvent:
    external_id = item.get("id") or item.get("node_id")
    body = _first_text(item.get("body"))
    state = item.get("state")
    return GitHubActivityEvent(
        provider="github",
        event_type="review",
        repository=repository,
        external_id=str(external_id or ""),
        title=f"Pull request review {state or ''}".strip(),
        parent_external_id=parent_external_id,
        url=item.get("html_url") or item.get("url"),
        actor=_get_nested(item, "user", "login") or item.get("author"),
        state=state,
        created_at=item.get("submitted_at") or item.get("created_at"),
        updated_at=item.get("submitted_at") or item.get("updated_at"),
        summary=body or state,
    )


async def _tool_index(client: MCPGatewayClient) -> dict[str, MCPToolInfo]:
    return _build_tool_index(await client.list_tools())


async def _call(
    client: MCPGatewayClient,
    tools: dict[str, MCPToolInfo],
    suffixes: tuple[str, ...],
    arguments: dict[str, Any],
) -> Any:
    tool = _find_tool(tools, suffixes)
    return await client.call_tool(tool.name, arguments)


async def _resolve_identity_with_tools(
    client: MCPGatewayClient,
    tools: dict[str, MCPToolInfo],
) -> dict[str, Any]:
    payload = await _call(client, tools, ("get_me",), {})
    return payload if isinstance(payload, dict) else {}


async def github_mcp_resolve_identity() -> dict[str, Any] | GitHubMCPWarning:
    """Return the platform GitHub account used by the MCP Target."""

    async def _operation(client: MCPGatewayClient) -> dict[str, Any]:
        tools = await _tool_index(client)
        return await _resolve_identity_with_tools(client, tools)

    try:
        return await run_with_github_mcp_sts(_operation)
    except Exception as exc:
        return _warning_from_error(exc)


async def _list_repositories_with_tools(
    client: MCPGatewayClient,
    tools: dict[str, MCPToolInfo],
    *,
    query: str | None,
    limit: int,
    include_archived: bool,
) -> list[dict[str, Any]]:
    identity = await _resolve_identity_with_tools(client, tools)
    login = _login_from_payload(identity)
    search_query = query or (f"user:{login}" if login else "sort:updated-desc")
    limit = min(max(limit, 1), 100)
    tool = _find_tool(tools, ("search_repositories",))
    args: dict[str, Any] = {}
    _set_arg(args, tool, search_query, "query", "q", required=True)
    _set_arg(args, tool, limit, "per_page", "perPage", "limit")
    payload = await client.call_tool(tool.name, args)
    repositories = _coerce_items(payload, "repositories", "items")
    if include_archived:
        return repositories[:limit]
    return [repo for repo in repositories if not repo.get("archived")][:limit]


async def github_mcp_list_repositories(
    *,
    query: str | None = None,
    limit: int = 30,
    include_archived: bool = False,
) -> list[dict[str, Any]] | GitHubMCPWarning:
    """List repositories visible to the platform GitHub MCP account."""

    async def _operation(client: MCPGatewayClient) -> list[dict[str, Any]]:
        tools = await _tool_index(client)
        return await _list_repositories_with_tools(
            client,
            tools,
            query=query,
            limit=limit,
            include_archived=include_archived,
        )

    try:
        return await run_with_github_mcp_sts(_operation)
    except Exception as exc:
        return _warning_from_error(exc)


async def _collect_commits(
    client: MCPGatewayClient,
    tools: dict[str, MCPToolInfo],
    *,
    repository: str,
    start_at: datetime,
    end_at: datetime,
    timezone: str,
    actor: str | None,
    limit: int,
) -> list[GitHubActivityEvent]:
    owner, repo = _repo_parts(repository)
    tool = _find_optional_tool(tools, ("list_commits",))
    if tool is None:
        return []

    args: dict[str, Any] = {}
    _set_arg(args, tool, owner, "owner", required=True)
    _set_arg(args, tool, repo, "repo", "repository", required=True)
    _set_arg(args, tool, _iso_utc(start_at), "since")
    _set_arg(args, tool, _iso_utc(end_at), "until")
    _set_arg(args, tool, limit, "per_page", "perPage", "limit")
    payload = await client.call_tool(tool.name, args)
    events = [_commit_to_event(item, repository) for item in _coerce_items(payload)]
    return [
        event
        for event in events
        if _event_matches(
            event,
            start_at=start_at,
            end_at=end_at,
            timezone=timezone,
            actor=actor,
        )
    ]


async def _collect_pull_requests(
    client: MCPGatewayClient,
    tools: dict[str, MCPToolInfo],
    *,
    repository: str,
    start_at: datetime,
    end_at: datetime,
    timezone: str,
    actor: str | None,
    limit: int,
) -> list[GitHubActivityEvent]:
    owner, repo = _repo_parts(repository)
    tool = _find_optional_tool(tools, ("list_pull_requests",))
    if tool is None:
        return []

    args: dict[str, Any] = {}
    _set_arg(args, tool, owner, "owner", required=True)
    _set_arg(args, tool, repo, "repo", "repository", required=True)
    _set_arg(args, tool, "all", "state")
    _set_arg(args, tool, "updated", "sort")
    _set_arg(args, tool, "desc", "direction")
    _set_arg(args, tool, limit, "per_page", "perPage", "limit")
    payload = await client.call_tool(tool.name, args)
    events = [
        _pull_request_to_event(item, repository) for item in _coerce_items(payload)
    ]
    return [
        event
        for event in events
        if _event_matches(
            event,
            start_at=start_at,
            end_at=end_at,
            timezone=timezone,
            actor=actor,
        )
    ]


async def _collect_issues(
    client: MCPGatewayClient,
    tools: dict[str, MCPToolInfo],
    *,
    repository: str,
    start_at: datetime,
    end_at: datetime,
    timezone: str,
    actor: str | None,
    limit: int,
) -> list[GitHubActivityEvent]:
    owner, repo = _repo_parts(repository)
    tool = _find_optional_tool(tools, ("list_issues",))
    if tool is None:
        return []

    args: dict[str, Any] = {}
    _set_arg(args, tool, owner, "owner", required=True)
    _set_arg(args, tool, repo, "repo", "repository", required=True)
    _set_arg(args, tool, "all", "state")
    _set_arg(args, tool, _iso_utc(start_at), "since")
    _set_arg(args, tool, limit, "per_page", "perPage", "limit")
    payload = await client.call_tool(tool.name, args)
    events = [
        _issue_to_event(item, repository)
        for item in _coerce_items(payload)
        if not item.get("pull_request")
    ]
    return [
        event
        for event in events
        if _event_matches(
            event,
            start_at=start_at,
            end_at=end_at,
            timezone=timezone,
            actor=actor,
        )
    ]


async def _collect_issue_comments(
    client: MCPGatewayClient,
    tools: dict[str, MCPToolInfo],
    *,
    repository: str,
    issue_number: str,
    start_at: datetime,
    end_at: datetime,
    timezone: str,
    actor: str | None,
) -> list[GitHubActivityEvent]:
    owner, repo = _repo_parts(repository)
    tool = _find_optional_tool(tools, ("get_issue_comments",))
    if tool is None:
        return []

    args: dict[str, Any] = {}
    _set_arg(args, tool, owner, "owner", required=True)
    _set_arg(args, tool, repo, "repo", "repository", required=True)
    _set_arg(
        args,
        tool,
        int(issue_number),
        "issue_number",
        "issueNumber",
        required=True,
    )
    payload = await client.call_tool(tool.name, args)
    events = [
        _comment_to_event(
            item,
            repository,
            parent_external_id=issue_number,
            title_prefix=f"Issue #{issue_number} comment",
        )
        for item in _coerce_items(payload, "comments")
    ]
    return [
        event
        for event in events
        if _event_matches(
            event,
            start_at=start_at,
            end_at=end_at,
            timezone=timezone,
            actor=actor,
        )
    ]


async def _collect_pull_request_reviews(
    client: MCPGatewayClient,
    tools: dict[str, MCPToolInfo],
    *,
    repository: str,
    pull_number: str,
    start_at: datetime,
    end_at: datetime,
    timezone: str,
    actor: str | None,
) -> list[GitHubActivityEvent]:
    owner, repo = _repo_parts(repository)
    tool = _find_optional_tool(tools, ("get_pull_request_reviews",))
    if tool is None:
        return []

    args: dict[str, Any] = {}
    _set_arg(args, tool, owner, "owner", required=True)
    _set_arg(args, tool, repo, "repo", "repository", required=True)
    _set_arg(
        args,
        tool,
        int(pull_number),
        "pull_number",
        "pullNumber",
        required=True,
    )
    payload = await client.call_tool(tool.name, args)
    events = [
        _review_to_event(
            item,
            repository,
            parent_external_id=pull_number,
        )
        for item in _coerce_items(payload)
    ]
    return [
        event
        for event in events
        if _event_matches(
            event,
            start_at=start_at,
            end_at=end_at,
            timezone=timezone,
            actor=actor,
        )
    ]


async def github_mcp_search_activity(
    *,
    start_at: str | datetime,
    end_at: str | datetime,
    timezone: str = "Asia/Shanghai",
    provider: str = "github",
    repositories: list[str] | None = None,
    actor: str | None = "platform",
    event_types: list[GitHubActivityType] | None = None,
    limit: int = 100,
    cursor: str | None = None,
) -> list[GitHubActivityEvent] | GitHubMCPWarning:
    """Search GitHub engineering activity through the MCP data source."""
    del cursor

    if provider != "github":
        return _warning("configuration_error", "Only provider='github' is supported.")
    start = _parse_datetime(start_at, timezone)
    end = _parse_datetime(end_at, timezone)
    if start is None or end is None or start > end:
        return _warning("configuration_error", "Invalid activity time window.")

    selected_types = tuple(event_types or _DEFAULT_EVENT_TYPES)
    capped_limit = min(max(limit, 1), 100)

    async def _operation(client: MCPGatewayClient) -> list[GitHubActivityEvent]:
        tools = await _tool_index(client)
        platform_login: str | None = None
        if actor == "platform":
            identity = await _resolve_identity_with_tools(client, tools)
            platform_login = _login_from_payload(identity)

        repo_names = repositories
        if not repo_names:
            repo_items = await _list_repositories_with_tools(
                client,
                tools,
                query=None,
                limit=min(capped_limit, 30),
                include_archived=False,
            )
            repo_names = [
                str(item.get("full_name") or item.get("name"))
                for item in repo_items
                if item.get("full_name") or item.get("name")
            ]

        events: list[GitHubActivityEvent] = []
        for repository in repo_names or []:
            remaining = capped_limit - len(events)
            if remaining <= 0:
                break
            if "commit" in selected_types:
                events.extend(
                    await _collect_commits(
                        client,
                        tools,
                        repository=repository,
                        start_at=start,
                        end_at=end,
                        timezone=timezone,
                        actor=platform_login,
                        limit=remaining,
                    )
                )
            if "pull_request" in selected_types:
                events.extend(
                    await _collect_pull_requests(
                        client,
                        tools,
                        repository=repository,
                        start_at=start,
                        end_at=end,
                        timezone=timezone,
                        actor=platform_login,
                        limit=remaining,
                    )
                )
            if "issue" in selected_types:
                events.extend(
                    await _collect_issues(
                        client,
                        tools,
                        repository=repository,
                        start_at=start,
                        end_at=end,
                        timezone=timezone,
                        actor=platform_login,
                        limit=remaining,
                    )
                )
            if {"comment", "review"} & set(selected_types):
                seeds = [
                    event
                    for event in events
                    if event.repository == repository
                    and event.event_type in {"issue", "pull_request"}
                ]
                for seed in seeds[:remaining]:
                    if "comment" in selected_types and seed.event_type == "issue":
                        events.extend(
                            await _collect_issue_comments(
                                client,
                                tools,
                                repository=repository,
                                issue_number=seed.external_id,
                                start_at=start,
                                end_at=end,
                                timezone=timezone,
                                actor=platform_login,
                            )
                        )
                    if "review" in selected_types and seed.event_type == "pull_request":
                        events.extend(
                            await _collect_pull_request_reviews(
                                client,
                                tools,
                                repository=repository,
                                pull_number=seed.external_id,
                                start_at=start,
                                end_at=end,
                                timezone=timezone,
                                actor=platform_login,
                            )
                        )

        events.sort(key=lambda item: item.updated_at or item.created_at or "")
        return events[:capped_limit]

    try:
        return await run_with_github_mcp_sts(_operation)
    except Exception as exc:
        return _warning_from_error(exc)


def _supported_issue_read_methods(tool: MCPToolInfo) -> tuple[str, ...]:
    method_schema = _schema_properties(tool).get("method")
    if not isinstance(method_schema, dict):
        return ("get",)

    enum = method_schema.get("enum")
    if not isinstance(enum, list):
        return ("get",)

    supported = tuple(method for method in _ISSUE_READ_METHODS if method in enum)
    if "get" not in supported:
        return ("get", *supported)
    return supported


def _issue_read_arguments(
    tool: MCPToolInfo,
    *,
    method: str,
    owner: str,
    repo: str,
    issue_number: int,
) -> dict[str, Any]:
    args: dict[str, Any] = {}
    _set_arg(args, tool, method, "method", required=True)
    _set_arg(args, tool, owner, "owner", required=True)
    _set_arg(args, tool, repo, "repo", "repository", required=True)
    _set_arg(
        args,
        tool,
        issue_number,
        "issue_number",
        "issueNumber",
        "number",
        required=True,
    )
    return args


def _detail_item_by_external_id(
    payload: Any,
    external_id: str,
    *collection_keys: str,
) -> dict[str, Any]:
    for item in _coerce_items(payload, *collection_keys):
        item_id = next(
            (
                item.get(key)
                for key in ("id", "node_id", "review_id", "comment_id")
                if item.get(key) is not None
            ),
            None,
        )
        if item_id is not None and str(item_id) == external_id:
            return item

    raise MCPGatewayError(
        "mcp_error",
        "GitHub MCP activity detail item was not found.",
        retryable=False,
    )


async def github_mcp_get_detail(
    *,
    event_type: GitHubActivityType,
    repository: str,
    external_id: str,
    parent_external_id: str | None = None,
) -> GitHubActivityEvent | GitHubMCPWarning:
    """Fetch details for one GitHub activity event."""

    parent_number: int | None = None
    if event_type in {"review", "comment"}:
        if not parent_external_id:
            return _warning(
                "configuration_error",
                f"{event_type} detail requires parent_external_id.",
            )
        try:
            parent_number = int(parent_external_id)
        except ValueError:
            return _warning(
                "configuration_error",
                "parent_external_id must be a PR or issue number.",
            )
        if parent_number < 1:
            return _warning(
                "configuration_error",
                "parent_external_id must be a positive PR or issue number.",
            )

    async def _operation(client: MCPGatewayClient) -> GitHubActivityEvent:
        tools = await _tool_index(client)
        owner, repo = _repo_parts(repository)
        if event_type == "commit":
            tool = _find_tool(tools, ("get_commit",))
            args: dict[str, Any] = {}
            _set_arg(args, tool, owner, "owner", required=True)
            _set_arg(args, tool, repo, "repo", "repository", required=True)
            _set_arg(args, tool, external_id, "sha", "ref", required=True)
            payload = await client.call_tool(tool.name, args)
            items = _coerce_items(payload)
            return _commit_to_event(items[0] if items else {}, repository)

        if event_type == "pull_request":
            tool = _find_tool(tools, ("get_pull_request", "pull_request_read"))
            args = {}
            if _matches_tool_suffix(tool.name, "pull_request_read"):
                _set_arg(args, tool, "get", "method", required=True)
            _set_arg(args, tool, owner, "owner", required=True)
            _set_arg(args, tool, repo, "repo", "repository", required=True)
            _set_arg(
                args,
                tool,
                int(external_id),
                "pull_number",
                "pullNumber",
                "number",
                required=True,
            )
            payload = await client.call_tool(tool.name, args)
            items = _coerce_items(payload)
            return _pull_request_to_event(items[0] if items else {}, repository)

        if event_type == "issue":
            tool = _find_tool(tools, ("issue_read", "get_issue"))
            if _matches_tool_suffix(tool.name, "issue_read"):
                payloads: dict[str, Any] = {}
                for method in _supported_issue_read_methods(tool):
                    args = _issue_read_arguments(
                        tool,
                        method=method,
                        owner=owner,
                        repo=repo,
                        issue_number=int(external_id),
                    )
                    payloads[method] = await client.call_tool(tool.name, args)

                payload = payloads["get"]
                items = _coerce_items(payload)
                event = _issue_to_event(items[0] if items else {}, repository)
                event.details = {
                    _ISSUE_DETAIL_KEYS[method]: value
                    for method, value in payloads.items()
                }
                return event

            args = {}
            _set_arg(args, tool, owner, "owner", required=True)
            _set_arg(args, tool, repo, "repo", "repository", required=True)
            _set_arg(
                args,
                tool,
                int(external_id),
                "issue_number",
                "issueNumber",
                "number",
                required=True,
            )
            payload = await client.call_tool(tool.name, args)
            items = _coerce_items(payload)
            return _issue_to_event(items[0] if items else {}, repository)

        if event_type == "review":
            tool = _find_tool(
                tools,
                ("get_pull_request_reviews", "pull_request_read"),
            )
            args = {}
            if _matches_tool_suffix(tool.name, "pull_request_read"):
                _set_arg(args, tool, "get_reviews", "method", required=True)
            _set_arg(args, tool, owner, "owner", required=True)
            _set_arg(args, tool, repo, "repo", "repository", required=True)
            _set_arg(
                args,
                tool,
                parent_number,
                "pull_number",
                "pullNumber",
                "number",
                required=True,
            )
            payload = await client.call_tool(tool.name, args)
            item = _detail_item_by_external_id(payload, external_id, "reviews")
            event = _review_to_event(
                item,
                repository,
                parent_external_id=str(parent_number),
            )
            event.details = {"review": item}
            return event

        if event_type == "comment":
            tool = _find_tool(tools, ("get_issue_comments", "issue_read"))
            args = {}
            if _matches_tool_suffix(tool.name, "issue_read"):
                _set_arg(args, tool, "get_comments", "method", required=True)
            _set_arg(args, tool, owner, "owner", required=True)
            _set_arg(args, tool, repo, "repo", "repository", required=True)
            _set_arg(
                args,
                tool,
                parent_number,
                "issue_number",
                "issueNumber",
                "number",
                required=True,
            )
            payload = await client.call_tool(tool.name, args)
            item = _detail_item_by_external_id(payload, external_id, "comments")
            event = _comment_to_event(
                item,
                repository,
                parent_external_id=str(parent_number),
                title_prefix=f"Issue or pull request #{parent_number} comment",
            )
            event.details = {"comment": item}
            return event

        raise MCPGatewayError(
            "capability_missing",
            "Detail lookup supports commit, pull_request, and issue events.",
            retryable=False,
        )

    try:
        return await run_with_github_mcp_sts(_operation)
    except Exception as exc:
        return _warning_from_error(exc)


def github_mcp_public_schema_is_secret_free() -> bool:
    """Return whether internal source function signatures avoid credential names."""
    import inspect

    for func in (
        github_mcp_resolve_identity,
        github_mcp_list_repositories,
        github_mcp_search_activity,
        github_mcp_get_detail,
    ):
        names = {name.lower() for name in inspect.signature(func).parameters}
        if any(secret in name for name in names for secret in _SENSITIVE_WORDS):
            return False
    return True


def _serialize_activity_value(value: Any) -> Any:
    if isinstance(value, GitHubActivityEvent | GitHubMCPWarning):
        return value.to_dict()
    if isinstance(value, list):
        return [_serialize_activity_value(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize_activity_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize_activity_value(item) for key, item in value.items()}
    return value


def _chat_warning_result(value: GitHubMCPWarning) -> dict[str, Any]:
    return value.to_dict()


async def chat_github_mcp_resolve_identity() -> dict[str, Any]:
    """Resolve the platform GitHub account configured on the MCP Target."""
    result = await github_mcp_resolve_identity()
    if isinstance(result, GitHubMCPWarning):
        return _chat_warning_result(result)
    return {"ok": True, "identity": _serialize_activity_value(result)}


async def chat_github_mcp_list_repositories(
    query: str | None = None,
    limit: int = 30,
    include_archived: bool = False,
) -> dict[str, Any]:
    """List repositories visible to the platform GitHub MCP account."""
    result = await github_mcp_list_repositories(
        query=query,
        limit=limit,
        include_archived=include_archived,
    )
    if isinstance(result, GitHubMCPWarning):
        return _chat_warning_result(result)
    repositories = _serialize_activity_value(result)
    return {
        "ok": True,
        "repositories": repositories,
        "count": len(repositories) if isinstance(repositories, list) else 0,
    }


async def chat_github_mcp_search_activity(
    start_at: str,
    end_at: str,
    repositories: list[str] | None = None,
    event_types: list[GitHubActivityType] | None = None,
    limit: int = 30,
    timezone: str = "Asia/Shanghai",
) -> dict[str, Any]:
    """Search read-only GitHub engineering activity through MCP Gateway."""
    result = await github_mcp_search_activity(
        start_at=start_at,
        end_at=end_at,
        timezone=timezone,
        repositories=repositories,
        event_types=event_types,
        limit=limit,
    )
    if isinstance(result, GitHubMCPWarning):
        return _chat_warning_result(result)
    events = _serialize_activity_value(result)
    return {
        "ok": True,
        "events": events,
        "count": len(events) if isinstance(events, list) else 0,
        "start_at": start_at,
        "end_at": end_at,
        "timezone": timezone,
    }


async def chat_github_mcp_get_detail(
    event_type: GitHubActivityType,
    repository: str,
    external_id: str,
    parent_external_id: str | None = None,
) -> dict[str, Any]:
    """Fetch one GitHub activity detail through the read-only MCP Gateway."""
    result = await github_mcp_get_detail(
        event_type=event_type,
        repository=repository,
        external_id=external_id,
        parent_external_id=parent_external_id,
    )
    if isinstance(result, GitHubMCPWarning):
        return _chat_warning_result(result)
    return {"ok": True, "event": _serialize_activity_value(result)}


GITHUB_MCP_CHAT_TOOLS = [
    lc_tool(
        "github_mcp_resolve_identity",
        description=(
            "Read-only debug tool for Feature 17. Resolve the platform GitHub "
            "account configured on the AgentArts MCP Gateway Target. It does "
            "not use or reveal end-user OAuth tokens, PATs, STS credentials, "
            "or signed headers."
        ),
    )(chat_github_mcp_resolve_identity),
    lc_tool(
        "github_mcp_list_repositories",
        description=(
            "Read-only debug tool for Feature 17. List repositories visible to "
            "the platform GitHub MCP account. Optional query uses GitHub search "
            "syntax; limit is capped by the internal source."
        ),
    )(chat_github_mcp_list_repositories),
    lc_tool(
        "github_mcp_search_activity",
        description=(
            "Read-only debug tool for Feature 17. Search commits, pull "
            "requests, issues, reviews, and comments via AgentArts MCP Gateway. "
            "Use repository names like 'T-1009/personal-assistant' and ISO "
            "datetime strings such as '2026-07-01T00:00:00+08:00'."
        ),
    )(chat_github_mcp_search_activity),
    lc_tool(
        "github_mcp_get_detail",
        description=(
            "Read-only debug tool for Feature 17. Fetch detail for one activity "
            "event. Supported event_type values are commit, pull_request, issue, "
            "review, and comment. For review or comment, pass the parent PR or "
            "issue number as parent_external_id."
        ),
    )(chat_github_mcp_get_detail),
]
