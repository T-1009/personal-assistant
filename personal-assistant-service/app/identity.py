"""Helpers for outbound AgentArts Identity integrations."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from agentarts.sdk.runtime.context import AgentArtsRuntimeContext
from agentarts.sdk.service.identity.polling.token_poller import TokenPoller

DEFAULT_GITHUB_SCOPES = ("repo", "read:user")
GITHUB_PROVIDER_NAME = "github-provider"
GITEE_PROVIDER_NAME = "gitee-provider"
IAM_USERS_READONLY_PROVIDER_NAME = "iam-users-readonly"
IAM_USERS_DEFAULT_REGION = "cn-southwest-2"
IAM_USERS_DEFAULT_ENDPOINT = f"https://iam.{IAM_USERS_DEFAULT_REGION}.myhuaweicloud.com"
IAM_USERS_DEFAULT_AGENCY_SESSION_NAME = "personal-assistant-iam-users-readonly"

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config.yaml"
_service_config: dict[str, Any] | None = None

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


def _clean(value: str | None) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _load_service_config() -> dict[str, Any]:
    global _service_config
    if _service_config is None:
        if _CONFIG_PATH.exists():
            with open(_CONFIG_PATH, encoding="utf-8") as f:
                _service_config = yaml.safe_load(f) or {}
        else:
            _service_config = {}
    return _service_config


def get_gitee_provider_name() -> str:
    """Return the configured Gitee OAuth provider name."""
    identity_cfg = _load_service_config().get("identity", {})
    gitee_cfg = identity_cfg.get("gitee", {})
    return _clean(gitee_cfg.get("provider_name")) or GITEE_PROVIDER_NAME


def get_iam_users_readonly_config() -> dict[str, str]:
    """Return outbound IAM Users credential provider settings."""
    identity_cfg = _load_service_config().get("identity", {})
    iam_cfg = identity_cfg.get("iam_users_readonly", {})
    region = _clean(iam_cfg.get("region")) or IAM_USERS_DEFAULT_REGION
    endpoint = (
        _clean(iam_cfg.get("endpoint")) or f"https://iam.{region}.myhuaweicloud.com"
    )
    return {
        "provider_name": (
            _clean(iam_cfg.get("provider_name")) or IAM_USERS_READONLY_PROVIDER_NAME
        ),
        "agency_session_name": (
            _clean(iam_cfg.get("agency_session_name"))
            or IAM_USERS_DEFAULT_AGENCY_SESSION_NAME
        ),
        "region": region,
        "endpoint": endpoint,
    }


@dataclass(slots=True)
class GitHubAuthorizationRequiredPoller(TokenPoller):
    """Stop SDK polling and ask the agent to show the authorization URL."""

    provider_name: str = GITHUB_PROVIDER_NAME

    async def poll_for_token(self) -> str:
        raise AuthorizationRequired(
            provider_name=self.provider_name,
            authorization_url=_GITHUB_AUTHORIZATION_URL.get(),
            message=f"{self.provider_name} authorization is required",
        )


def get_runtime_user_id() -> str | None:
    return AgentArtsRuntimeContext.get_user_id()


def get_runtime_session_id() -> str | None:
    return AgentArtsRuntimeContext.get_session_id()
