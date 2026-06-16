import asyncio
import logging
from typing import Any

import httpx
from agentarts.sdk import require_access_token
from langchain_core.callbacks.manager import adispatch_custom_event

logger = logging.getLogger(__name__)


async def handle_auth_url(auth_url: str) -> None:
    """Callback triggered by the SDK when user authentication is required.

    Dispatches a custom event to the LangGraph astream_events loop
    so the SSE stream can present the authorization URL directly to the
    user — no exception, no LLM round-trip.
    """
    logger.info("User authorization required — auth URL: %s", auth_url)
    await adispatch_custom_event(
        "auth_required",
        {
            "type": "system_message",
            "content": (
                "邮件功能需要您的授权。请点击以下链接进行授权：\n\n"
                f"{auth_url}\n\n"
                "授权完成后，请再次告诉我您需要做什么。"
            ),
            "auth_url": auth_url,
            "auth_required": True,
        },
    )


GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0/me"


def _extract_graph_error(resp: httpx.Response) -> str:
    """Extract a human-readable error message from a Microsoft Graph API response.

    Graph errors have a structured JSON body:
        {"error": {"code": "...", "message": "..."}}

    Falls back to HTTP status text or a generic message when the body is
    empty or unparseable.
    """
    status = resp.status_code

    # Try to extract the Graph error message from the JSON body
    try:
        body = resp.json()
        graph_error = body.get("error", {})
        code = graph_error.get("code", "")
        message = graph_error.get("message", "")
        if code or message:
            return f"[{status}] {code}: {message}" if code else f"[{status}] {message}"
    except (ValueError, AttributeError):
        pass

    # Fall back to response text if it's non-empty
    if resp.text and resp.text.strip():
        return f"[{status}] {resp.text[:500]}"

    # Absolute fallback — use the HTTP reason phrase
    return f"[{status}] {resp.reason_phrase or 'Unknown error'}"


def _auth_required_response() -> dict[str, Any]:
    """Return a tool result indicating authorization is pending."""
    return {
        "auth_required": True,
        "error": "Authorization pending. Please follow the authorization link sent to you.",
    }


def _format_tool_error(e: Exception, tool_name: str) -> dict[str, Any]:
    """Convert known exceptions to user-friendly Chinese error dicts."""
    if isinstance(e, httpx.TimeoutException):
        return {"error": f"请求超时，请稍后再试。（{tool_name}）"}
    if isinstance(e, httpx.ConnectError):
        return {"error": f"无法连接到邮件服务器，请检查网络。（{tool_name}）"}
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 429:
            return {"error": "请求过于频繁，请稍后再试。"}
        if status == 503:
            return {"error": "邮件服务暂时不可用，请稍后再试。"}
        if status == 401:
            return {"error": "授权已过期，请重新授权。"}
        return {"error": f"邮件服务返回错误（{status}），请稍后再试。"}
    return {"error": f"操作失败: {tool_name}。如果问题持续，请联系支持。"}


_client: httpx.AsyncClient | None = None


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


# ── 1. list_emails ──

@require_access_token(
    provider_name="m365-provider",
    scopes=[
        "https://graph.microsoft.com/Mail.Read",
        "https://graph.microsoft.com/Mail.ReadWrite",
        "https://graph.microsoft.com/Mail.Send",
    ],
    auth_flow="USER_FEDERATION",
    on_auth_url=handle_auth_url,
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
    logger.debug("list_emails access_token: %s", access_token)
    if not access_token:
        return _auth_required_response()
    try:
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
    except Exception as e:
        logger.exception("list_emails failed")
        return _format_tool_error(e, "list_emails")


# ── 2. get_email ──

@require_access_token(
    provider_name="m365-provider",
    scopes=[
        "https://graph.microsoft.com/Mail.Read",
        "https://graph.microsoft.com/Mail.ReadWrite",
        "https://graph.microsoft.com/Mail.Send",
    ],
    auth_flow="USER_FEDERATION",
    on_auth_url=handle_auth_url,
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
    logger.debug("get_email access_token: %s", access_token)
    if not access_token:
        return _auth_required_response()
    try:
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
    except Exception as e:
        logger.exception("get_email failed")
        return _format_tool_error(e, "get_email")


# ── 3. search_emails ──

@require_access_token(
    provider_name="m365-provider",
    scopes=[
        "https://graph.microsoft.com/Mail.Read",
        "https://graph.microsoft.com/Mail.ReadWrite",
        "https://graph.microsoft.com/Mail.Send",
    ],
    auth_flow="USER_FEDERATION",
    on_auth_url=handle_auth_url,
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
    logger.debug("search_emails access_token: %s", access_token)
    if not access_token:
        return _auth_required_response()
    try:
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
    except Exception as e:
        logger.exception("search_emails failed")
        return _format_tool_error(e, "search_emails")


# ── 4. send_email (Guard protected) ──

@require_access_token(
    provider_name="m365-provider",
    scopes=[
        "https://graph.microsoft.com/Mail.Read",
        "https://graph.microsoft.com/Mail.ReadWrite",
        "https://graph.microsoft.com/Mail.Send",
    ],
    auth_flow="USER_FEDERATION",
    on_auth_url=handle_auth_url,
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
    logger.debug("send_email access_token: %s", access_token)
    if not access_token:
        return _auth_required_response()
    if not to:
        return {
            "sent": False,
            "message_id": None,
            "error": "At least one recipient is required",
        }
    try:
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
            return {
                "sent": True,
                "message_id": None,
                "error": None,
                "status_code": 202,
            }

        # ── Non-202: extract a human-readable error from the Graph API ──
        error_msg = _extract_graph_error(resp)
        logger.error(
            "send_email failed — status=%d, body=%s",
            resp.status_code,
            resp.text[:500] if resp.text else "(empty)",
        )
        return {
            "sent": False,
            "message_id": None,
            "error": error_msg,
            "status_code": resp.status_code,
        }
    except Exception as e:
        logger.exception("send_email failed")
        return _format_tool_error(e, "send_email")


# ── 5. reply_to_email ──

@require_access_token(
    provider_name="m365-provider",
    scopes=[
        "https://graph.microsoft.com/Mail.Read",
        "https://graph.microsoft.com/Mail.ReadWrite",
        "https://graph.microsoft.com/Mail.Send",
    ],
    auth_flow="USER_FEDERATION",
    on_auth_url=handle_auth_url,
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
    logger.debug("reply_to_email access_token: %s", access_token)
    if not access_token:
        return _auth_required_response()
    if not email_id or not email_id.strip():
        return {"sent": False, "error": "email_id is required for reply_to_email"}
    if not body or not body.strip():
        return {"sent": False, "error": "reply body is required"}
    try:
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
            return {"sent": True, "error": None, "status_code": 202}

        error_msg = _extract_graph_error(resp)
        logger.error(
            "reply_to_email failed — status=%d, body=%s",
            resp.status_code,
            resp.text[:500] if resp.text else "(empty)",
        )
        return {
            "sent": False,
            "error": error_msg,
            "status_code": resp.status_code,
        }
    except Exception as e:
        logger.exception("reply_to_email failed")
        return _format_tool_error(e, "reply_to_email")


# ── Module-level tool list (no side-effects at import time) ──

EMAIL_TOOLS = [
    list_emails,
    get_email,
    search_emails,
    send_email,
    reply_to_email,
]
