"""Huawei Cloud IAM tools backed by AgentArts STS credentials."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from typing import Any

from agentarts.sdk import require_sts_token
from agentarts.sdk.identity.types import StsCredentials
from huaweicloudsdkcore.auth.credentials import GlobalCredentials
from huaweicloudsdkiam.v5 import IamAsyncClient, ListUsersV5Request
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
    user_id: str | None = None
    user_name: str | None = None
    enabled: bool | None = None
    description: str | None = None
    is_root_user: bool | None = None
    created_at: str | None = None
    urn: str | None = None


def _get_value(item: Any, key: str) -> Any:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _serialize_value(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _normalize_user_item(item: Any) -> IamUserItem:
    user_id = _get_value(item, "user_id") or _get_value(item, "id")
    user_name = _get_value(item, "user_name") or _get_value(item, "name")
    return IamUserItem(
        id=user_id,
        name=user_name,
        user_id=user_id,
        user_name=user_name,
        enabled=_get_value(item, "enabled"),
        description=_get_value(item, "description"),
        is_root_user=_get_value(item, "is_root_user"),
        created_at=_serialize_value(_get_value(item, "created_at")),
        urn=_get_value(item, "urn"),
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
    limit: int | None = None,
    marker: str | None = None,
    group_id: str | None = None,
    sts_credentials: StsCredentials,
) -> Any:
    client = _build_iam_client(sts_credentials)
    request = ListUsersV5Request(limit=limit, marker=marker, group_id=group_id)
    future_response = client.list_users_v5_async(request)
    return await asyncio.to_thread(future_response.result)


async def list_iam_users(
    limit: int | None = None,
    marker: str | None = None,
    group_id: str | None = None,
) -> dict[str, Any]:
    """List Huawei Cloud IAM users with the IAM V5 API."""
    try:
        response = await _list_iam_users(
            limit=limit,
            marker=marker,
            group_id=group_id,
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
    page_info = getattr(response, "page_info", None)
    return {
        "ok": True,
        "api_version": "v5",
        "provider_name": _IAM_USERS_CONFIG["provider_name"],
        "region": _IAM_USERS_CONFIG["region"],
        "endpoint": _IAM_USERS_CONFIG["endpoint"],
        "count": len(users),
        "page_info": (
            {
                "next_marker": _get_value(page_info, "next_marker"),
                "current_count": _get_value(page_info, "current_count"),
            }
            if page_info is not None
            else None
        ),
        "users": users,
    }


IAM_TOOLS = [
    tool(
        "huaweicloud_list_iam_users",
        description=(
            "List Huawei Cloud IAM users/sub-users visible to the AgentArts "
            "STS credential provider iam-users-readonly using IAM V5. Supports "
            "optional pagination and group filters: limit, marker, and group_id."
        ),
    )(list_iam_users),
]
