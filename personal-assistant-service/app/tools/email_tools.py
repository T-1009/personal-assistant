import asyncio
import functools
import logging
import os
from typing import Any

import httpx
from agentarts.sdk import IdentityClient, require_access_token
from agentarts.sdk.identity.types import OAuth2Vendor

logger = logging.getLogger(__name__)

_PROVIDER_INITIALIZED = False
_provider_lock = asyncio.Lock()

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0/me"

_client: httpx.AsyncClient | None = None


def _handle_provider_error(fn):
    """Wrap a tool function to gracefully handle provider-not-found errors.

    The @require_access_token decorator fires BEFORE the function body,
    so a missing provider throws ClientRequestException before our code runs.
    This wrapper catches that and returns a user-friendly error message
    instead of crashing the frontend.
    """

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except Exception as e:
            error_msg = str(e)
            if "m365-provider" in error_msg or "Resource not found" in error_msg:
                logger.error("Email tool failed — m365-provider not found: %s", e)
                return {
                    "error": (
                        "邮件功能暂不可用：M365 Provider 未配置。"
                        "请设置环境变量 M365_CLIENT_ID, M365_CLIENT_SECRET, M365_TENANT_ID，"
                        "并确保 AgentArts Identity 服务可用。"
                    ),
                    "setup_required": True,
                }
            raise

    return wrapper


def _get_client() -> httpx.AsyncClient:
    """Return a shared httpx.AsyncClient with connection pooling.

    Created lazily on first call, reused across all tool invocations.
    """
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
    return _client


async def _ensure_provider():
    """Ensure the m365-provider exists in AgentArts Identity Service.

    Called lazily on first tool invocation, NOT at module import time.
    Reads M365_CLIENT_ID, M365_CLIENT_SECRET, M365_TENANT_ID from env.
    Thread-safe via double-checked locking with asyncio.Lock.
    Only sets _PROVIDER_INITIALIZED = True on successful creation.
    """
    global _PROVIDER_INITIALIZED
    if _PROVIDER_INITIALIZED:
        return
    async with _provider_lock:
        if _PROVIDER_INITIALIZED:
            return
        client_id = os.environ.get("M365_CLIENT_ID")
        client_secret = os.environ.get("M365_CLIENT_SECRET")
        tenant_id = os.environ.get("M365_TENANT_ID")
        if not all([client_id, client_secret, tenant_id]):
            logger.warning(
                "M365_CLIENT_ID, M365_CLIENT_SECRET, or M365_TENANT_ID not set. "
                "Email tools will be registered but may fail at runtime."
            )
            return
        try:
            region = os.environ.get("AGENTARTS_REGION", "cn-southwest-2")
            client = IdentityClient(region=region)
            client.create_oauth2_credential_provider(
                name="m365-provider",
                vendor=OAuth2Vendor.MICROSOFTOAUTH2,
                client_id=client_id,
                client_secret=client_secret,
                tenant_id=tenant_id,
            )
            logger.info("m365-provider created successfully.")
            _PROVIDER_INITIALIZED = True
        except Exception as e:
            logger.error(f"Failed to create m365-provider: {e}")


# ── 1. list_emails ──

@_handle_provider_error
@require_access_token(
    provider_name="m365-provider",
    scopes=["https://graph.microsoft.com/Mail.Read"],
    auth_flow="USER_FEDERATION",
)
async def list_emails(
    folder: str = "inbox",
    limit: int = 10,
    access_token: str | None = None,
) -> dict[str, Any]:
    """列出指定文件夹中的邮件。

    Args:
        folder: 邮件文件夹名（inbox, sentitems, drafts 等），默认为 inbox
        limit: 返回邮件数量上限，默认 10
        access_token: AgentArts Identity SDK 自动注入的 Microsoft Graph access token

    Returns:
        dict with keys: emails (list of {id, subject, from, receivedDateTime,
        isRead, importance}), count (int), folder (str)
    """
    await _ensure_provider()
    client = _get_client()
    resp = await client.get(
        f"{GRAPH_BASE_URL}/mailFolders/{folder}/messages",
        headers={"Authorization": f"Bearer {access_token}"},
        params={
            "$top": limit,
            "$select": (
                "id,subject,from,receivedDateTime,isRead,importance,bodyPreview"
            ),
            "$orderby": "receivedDateTime desc",
        },
    )
    resp.raise_for_status()
    data = resp.json()
    emails = [
        {
            "id": m.get("id"),
            "subject": m.get("subject"),
            "from": (
                (m.get("from") or {})
                .get("emailAddress", {})
                .get("name", "Unknown")
            ),
            "receivedDateTime": m.get("receivedDateTime"),
            "isRead": m.get("isRead"),
            "importance": m.get("importance", "normal"),
            "bodyPreview": m.get("bodyPreview", ""),
        }
        for m in data.get("value", [])
    ]
    return {"emails": emails, "count": len(emails), "folder": folder}


# ── 2. get_email ──

@_handle_provider_error
@require_access_token(
    provider_name="m365-provider",
    scopes=["https://graph.microsoft.com/Mail.Read"],
    auth_flow="USER_FEDERATION",
)
async def get_email(
    email_id: str,
    access_token: str | None = None,
) -> dict[str, Any]:
    """获取单封邮件的完整详情。

    Args:
        email_id: Microsoft Graph 邮件 ID
        access_token: AgentArts Identity SDK 自动注入

    Returns:
        dict with: id, subject, body (plain text), from, toRecipients,
        ccRecipients, receivedDateTime, attachments (list of {name, size, contentType})
    """
    await _ensure_provider()
    client = _get_client()
    resp = await client.get(
        f"{GRAPH_BASE_URL}/messages/{email_id}",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Prefer": 'outlook.body-content-type="text"',
        },
        params={
            "$select": (
                "id,subject,body,from,toRecipients,ccRecipients,receivedDateTime"
            ),
            "$expand": "attachments($select=name,contentType,size)",
        },
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        "id": data.get("id"),
        "subject": data.get("subject"),
        "body": data.get("body", {}).get("content", ""),
        "from": (data.get("from") or {}).get("emailAddress", {}),
        "toRecipients": [
            r.get("emailAddress", {})
            for r in data.get("toRecipients", [])
        ],
        "ccRecipients": [
            r.get("emailAddress", {})
            for r in data.get("ccRecipients", [])
        ],
        "receivedDateTime": data.get("receivedDateTime"),
        "attachments": [
            {
                "name": a.get("name"),
                "size": a.get("size"),
                "contentType": a.get("contentType"),
            }
            for a in data.get("attachments", [])
        ] if data.get("hasAttachments") else [],
    }


# ── 3. search_emails ──

@_handle_provider_error
@require_access_token(
    provider_name="m365-provider",
    scopes=["https://graph.microsoft.com/Mail.Read"],
    auth_flow="USER_FEDERATION",
)
async def search_emails(
    query: str,
    limit: int = 10,
    access_token: str | None = None,
) -> dict[str, Any]:
    """按关键词搜索邮件。

    使用 Microsoft Graph API $search 参数进行全文搜索。

    Args:
        query: 搜索关键词（支持 KQL 语法）
        limit: 返回结果数量上限，默认 10
        access_token: AgentArts Identity SDK 自动注入

    Returns:
        dict with keys: results (list of {id, subject, from, receivedDateTime, isRead}),
        count (int), query (str)
    """
    await _ensure_provider()
    escaped_query = query.replace('"', '\\"')
    client = _get_client()
    resp = await client.get(
        f"{GRAPH_BASE_URL}/messages",
        headers={"Authorization": f"Bearer {access_token}"},
        params={
            "$search": f'"{escaped_query}"',
            "$top": limit,
            "$select": "id,subject,from,receivedDateTime,isRead,bodyPreview",
        },
    )
    resp.raise_for_status()
    data = resp.json()
    results = [
        {
            "id": m.get("id"),
            "subject": m.get("subject"),
            "from": (
                (m.get("from") or {})
                .get("emailAddress", {})
                .get("name", "Unknown")
            ),
            "receivedDateTime": m.get("receivedDateTime"),
            "isRead": m.get("isRead"),
            "bodyPreview": m.get("bodyPreview", ""),
        }
        for m in data.get("value", [])
    ]
    return {"results": results, "count": len(results), "query": query}


# ── 4. send_email (Guard protected) ──

@_handle_provider_error
@require_access_token(
    provider_name="m365-provider",
    scopes=["https://graph.microsoft.com/Mail.Send"],
    auth_flow="USER_FEDERATION",
)
async def send_email(
    to: list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    confirm: bool = False,
    access_token: str | None = None,
) -> dict[str, Any]:
    """发送邮件。

    此操作为敏感写操作，调用前 Agent 应通过 Guard 机制向用户展示预览
    并等待 explicit 确认。设置 confirm=False（默认）时返回预览而不发送，
    confirm=True 时才实际发送邮件。

    Args:
        to: 收件人邮箱地址列表
        subject: 邮件主题
        body: 邮件正文（纯文本）
        cc: 抄送邮箱地址列表，可选
        confirm: 是否已获得用户确认，默认 False（返回预览）
        access_token: AgentArts Identity SDK 自动注入

    Returns:
        dict with: sent (bool), message_id (str or None), error (str or None),
        requires_confirmation (bool) when confirm=False, preview (dict) when
        confirm=False
    """
    if not to:
        return {
            "sent": False,
            "message_id": None,
            "error": "At least one recipient is required",
        }
    if not confirm:
        return {
            "sent": False,
            "requires_confirmation": True,
            "preview": {
                "to": to,
                "subject": subject,
                "body_preview": body[:200],
            },
            "error": "请确认收件人、主题和正文后再发送。调用时设置 confirm=True。",
        }
    await _ensure_provider()
    message: dict[str, Any] = {
        "subject": subject,
        "body": {
            "contentType": "Text",
            "content": body,
        },
        "toRecipients": [
            {"emailAddress": {"address": addr}} for addr in to
        ],
    }
    if cc:
        message["ccRecipients"] = [
            {"emailAddress": {"address": addr}} for addr in cc
        ]

    client = _get_client()
    resp = await client.post(
        f"{GRAPH_BASE_URL}/sendMail",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={"message": message, "saveToSentItems": True},
    )
    if resp.status_code == 202:
        return {"sent": True, "message_id": None, "error": None}
    error_detail = resp.text
    return {"sent": False, "message_id": None, "error": error_detail}


# ── 5. reply_to_email ──

@_handle_provider_error
@require_access_token(
    provider_name="m365-provider",
    scopes=["https://graph.microsoft.com/Mail.Send"],
    auth_flow="USER_FEDERATION",
)
async def reply_to_email(
    email_id: str,
    body: str,
    confirm: bool = False,
    access_token: str | None = None,
) -> dict[str, Any]:
    """直接回复邮件 — 使用 Graph API POST /messages/{id}/reply 发送回复。

    此 API 立即发送回复（不创建草稿）。设置 confirm=False（默认）时
    返回预览而不发送，confirm=True 时才实际发送回复。

    Args:
        email_id: 要回复的原始邮件 ID
        body: 回复正文（纯文本），将插入原邮件内容上方
        confirm: 是否已获得用户确认，默认 False（返回预览）
        access_token: AgentArts Identity SDK 自动注入

    Returns:
        dict with: sent (bool), error (str or None),
        requires_confirmation (bool) when confirm=False, preview (dict) when
        confirm=False
    """
    if not email_id or not email_id.strip():
        return {"sent": False, "error": "email_id is required for reply_to_email"}
    if not body or not body.strip():
        return {"sent": False, "error": "reply body is required"}
    if not confirm:
        return {
            "sent": False,
            "requires_confirmation": True,
            "preview": {
                "email_id": email_id,
                "body_preview": body[:200],
            },
            "error": "请确认回复内容后再发送。调用时设置 confirm=True。",
        }
    await _ensure_provider()
    client = _get_client()
    resp = await client.post(
        f"{GRAPH_BASE_URL}/messages/{email_id}/reply",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={"message": {"body": {"contentType": "Text", "content": body}}},
    )
    if resp.status_code == 202:
        return {"sent": True, "error": None}
    return {"sent": False, "error": resp.text}


# ── Module-level tool list (no side-effects at import time) ──

EMAIL_TOOLS = [
    list_emails,
    get_email,
    search_emails,
    send_email,
    reply_to_email,
]
