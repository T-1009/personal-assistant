"""Helpers for outbound AgentArts Identity integrations."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

from agentarts.sdk.runtime.context import AgentArtsRuntimeContext
from agentarts.sdk.service.identity.polling.token_poller import TokenPoller

DEFAULT_GITHUB_SCOPES = ("repo", "read:user")
GITHUB_PROVIDER_NAME = "github-provider"

_GITHUB_AUTHORIZATION_URL: ContextVar[str | None] = ContextVar(
    "github_authorization_url",
    default=None,
)


@dataclass(slots=True)
class AuthorizationRequired(Exception):  # noqa: N818
    """Signal that end-user consent is required before an access token exists."""

    provider_name: str
    authorization_url: str | None = None
    message: str = "GitHub authorization is required"

    def __post_init__(self) -> None:
        Exception.__init__(self, self.message)


def capture_github_authorization_url(url: str) -> None:
    """Store the latest GitHub authorization URL in this request context."""
    _GITHUB_AUTHORIZATION_URL.set(url)


@dataclass(slots=True)
class GitHubAuthorizationRequiredPoller(TokenPoller):
    """Stop SDK polling and ask the agent to show the authorization URL."""

    provider_name: str = GITHUB_PROVIDER_NAME

    async def poll_for_token(self) -> str:
        raise AuthorizationRequired(
            provider_name=self.provider_name,
            authorization_url=_GITHUB_AUTHORIZATION_URL.get(),
        )


def get_runtime_user_id() -> str | None:
    return AgentArtsRuntimeContext.get_user_id()


def get_runtime_session_id() -> str | None:
    return AgentArtsRuntimeContext.get_session_id()
