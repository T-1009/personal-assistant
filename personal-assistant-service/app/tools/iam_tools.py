"""Huawei Cloud IAM tools backed by AgentArts STS credentials."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from typing import Any

from agentarts.sdk import require_sts_token
from agentarts.sdk.identity.types import StsCredentials
from huaweicloudsdkcore.auth.credentials import GlobalCredentials
from huaweicloudsdkiam.v3 import IamAsyncClient, KeystoneListUsersRequest
from langchain_core.tools import tool

from app.identity import get_iam_users_readonly_config

_IAM_USERS_CONFIG = get_iam_users_readonly_config()


@dataclass(slots=True)
class IamToolError:
    ok: bool
    message: str
    provider_name: str | None = None
    details: str | None = None


@dataclass(slots=True)
class IamUserItem:
    id: str | None = None
    name: str | None = None
    domain_id: str | None = None
    enabled: bool | None = None
    description: str | None = None
    access_mode: str | None = None
    pwd_status: bool | None = None
    pwd_strength: str | None = None
    password_expires_at: str | None = None
    last_project_id: str | None = None


def _get_value(item: Any, key: str) -> Any:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _normalize_user_item(item: Any) -> IamUserItem:
    return IamUserItem(
        id=_get_value(item, "id"),
        name=_get_value(item, "name"),
        domain_id=_get_value(item, "domain_id"),
        enabled=_get_value(item, "enabled"),
        description=_get_value(item, "description"),
        access_mode=_get_value(item, "access_mode"),
        pwd_status=_get_value(item, "pwd_status"),
        pwd_strength=_get_value(item, "pwd_strength"),
        password_expires_at=_get_value(item, "password_expires_at"),
        last_project_id=_get_value(item, "last_project_id"),
    )


def _user_item_to_dict(item: IamUserItem) -> dict[str, Any]:
    return asdict(item)


def _credentials_to_global_credentials(
    sts_credentials: StsCredentials,
) -> GlobalCredentials:
    return GlobalCredentials(
        sts_credentials.access_key_id,
        sts_credentials.secret_access_key,
    ).with_security_token(sts_credentials.security_token)


def _build_iam_client(sts_credentials: StsCredentials) -> IamAsyncClient:
    return (
        IamAsyncClient.new_builder()
        .with_credentials(_credentials_to_global_credentials(sts_credentials))
        .with_endpoint(_IAM_USERS_CONFIG["endpoint"])
        .build()
    )


@require_sts_token(
    provider_name=_IAM_USERS_CONFIG["provider_name"],
    agency_session_name=_IAM_USERS_CONFIG["agency_session_name"],
    into="sts_credentials",
)
async def _list_iam_users(
    *,
    domain_id: str | None = None,
    enabled: bool | None = None,
    name: str | None = None,
    password_expires_at: str | None = None,
    sts_credentials: StsCredentials,
) -> Any:
    client = _build_iam_client(sts_credentials)
    request = KeystoneListUsersRequest(
        domain_id=domain_id,
        enabled=enabled,
        name=name,
        password_expires_at=password_expires_at,
    )
    future_response = client.keystone_list_users_async(request)
    return await asyncio.to_thread(future_response.result)


async def list_iam_users(
    domain_id: str | None = None,
    enabled: bool | None = None,
    name: str | None = None,
    password_expires_at: str | None = None,
) -> dict[str, Any]:
    """List Huawei Cloud IAM users visible to the readonly STS credential."""
    try:
        response = await _list_iam_users(
            domain_id=domain_id,
            enabled=enabled,
            name=name,
            password_expires_at=password_expires_at,
        )
    except Exception as exc:
        return asdict(
            IamToolError(
                ok=False,
                message="Failed to list Huawei Cloud IAM users.",
                provider_name=_IAM_USERS_CONFIG["provider_name"],
                details=str(exc),
            )
        )

    users = [
        _user_item_to_dict(_normalize_user_item(item))
        for item in (getattr(response, "users", None) or [])
    ]
    return {
        "ok": True,
        "provider_name": _IAM_USERS_CONFIG["provider_name"],
        "region": _IAM_USERS_CONFIG["region"],
        "endpoint": _IAM_USERS_CONFIG["endpoint"],
        "count": len(users),
        "users": users,
    }


IAM_TOOLS = [
    tool(
        "huaweicloud_list_iam_users",
        description=(
            "List Huawei Cloud IAM users/sub-users visible to the AgentArts "
            "STS credential provider iam-users-readonly. Supports optional "
            "filters: domain_id, enabled, name, and password_expires_at."
        ),
    )(list_iam_users),
]
