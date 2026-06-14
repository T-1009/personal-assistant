# Service Implementation Plan — Feature 10a: Outbound Email（Microsoft 365 邮件处理）

> 状态：Draft | 目标分支：`feat/feature-10-outbound-email-obs`
> 
> 关联架构：`backend_architecture.md` §5.2, §7 | 关联 spec：`overall_specifications.md` §3.1, §4.2

---

## 变更概述

本 Phase 引入 AgentArts Python SDK，创建 `m365-provider` OAuth2 Credential Provider，实现 5 个 Microsoft Graph API 邮件工具函数，并通过 `build_tools()` 工厂注册到 LangGraph ToolNode。Agent 以 User Federation 模式代表用户调用 Outlook 邮件 API，支持邮件列表、详情、搜索、草拟回复和发送。

**核心依赖**：Feature 4（Microsoft Entra ID OAuth）已完成，`agentarts-sdk v0.1.3` 提供 `@require_access_token` 装饰器和 `IdentityClient`。

---

## 1. API Changes

### 1.1 Route 层 — 无变更

本 Feature **不新增也不修改任何 FastAPI 路由**。所有邮件工具函数通过现有 `POST /invocations` 路由的 deepagents ReAct loop 内 `ToolNode` 自动调用：

- 用户通过对话自然描述需求 → Agent 推理决定调哪个 tool → ToolNode 执行 → 结果喂回 Agent
- `@require_access_token` 装饰器在 tool 执行前自动从 AgentArts Identity Service 获取 access_token 并注入

### 1.2 OpenAPI Spec 影响

- `openapi.json` **无需手动修改** — 本 Feature 不涉及路由层变更
- 工具函数的 Pydantic schema 由 LangChain `@tool` 装饰器自动生成（argument schema），不暴露在 FastAPI OpenAPI 路径中
- **注意**：后续 `personal-assistant-meta-service-dev`（API 接口更新 agent）会检查是否需要在 OpenAPI spec 中声明 tool 相关 schema — 本 plan 判断为不需要

### 1.3 Environment Variables

| 变量 | 用途 | 必填 |
|------|------|------|
| `M365_CLIENT_ID` | Microsoft Entra ID 应用注册 Client ID（用于创建 `m365-provider`） | ✅ |
| `M365_CLIENT_SECRET` | Microsoft Entra ID 应用注册 Client Secret | ✅ |
| `M365_TENANT_ID` | Azure AD Tenant ID | ✅ |

这些变量由 `app/tools/email_tools.py` 的 module-level `_provider_init()` 函数读取，用于调用 `IdentityClient.create_oauth2_credential_provider()`。

---

## 2. Service Tasks

### 2.1 Task 1: 添加 `agentarts-sdk` 依赖

**文件**：`personal-assistant-service/pyproject.toml`

**操作**：在 `[project].dependencies` 列表中追加一行：

```toml
"agentarts-sdk>=0.1.3",
```

**验证**：执行 `uv sync` 确认依赖解析成功。

---

### 2.2 Task 2: 创建 `app/tools/` 目录和 `app/tools/__init__.py`

**文件**：`personal-assistant-service/app/tools/__init__.py`（新建）

**内容**：

```python
"""Tools package — factory for building the LangGraph ToolNode with registered tools.

This module provides build_tools(), called by AgentHandler.__init__() to
dynamically assemble the tool list. Each sub-module (email_tools.py, etc.)
registers its tools via a module-level TOOLS list.
"""

from typing import Any


def build_tools() -> list[Any]:
    """Build the list of tools for deepagents/LangGraph ToolNode.

    Collects tools from all registered sub-modules. Each sub-module
    must expose a module-level TOOLS list of callable tool functions.
    """
    tools: list[Any] = []

    # ── Email tools (Feature 10a) ──
    try:
        from app.tools.email_tools import EMAIL_TOOLS

        tools.extend(EMAIL_TOOLS)
    except ImportError:
        pass  # module not yet created — graceful degradation

    # ── Future tool modules go here ──
    # try:
    #     from app.tools.github_tools import GITHUB_TOOLS
    #     tools.extend(GITHUB_TOOLS)
    # except ImportError:
    #     pass

    return tools
```

**设计说明**：
- 使用 `try/except ImportError` 确保每个 tool module 独立加载，不因某个 module 缺少依赖导致整个 Agent 启动失败
- `build_tools()` 返回 `list[Any]`（而非 `list[BaseTool]`），因为 `@require_access_token` 装饰器在未激活时返回原始 callable，类型签名暂不严格

---

### 2.3 Task 3: 创建 `app/tools/email_tools.py`

**文件**：`personal-assistant-service/app/tools/email_tools.py`（新建）

**Microsoft Graph API 约定**：
- Base URL：`https://graph.microsoft.com/v1.0/me`
- 所有 HTTP 调用使用 `httpx.AsyncClient`（已在 `pyproject.toml` 的 dependencies 中）
- 认证：`Authorization: Bearer {access_token}` header

**GLOBAL PROVIDER INIT**：在 module scope 创建 `m365-provider`（如未存在），使用 module-level `_provider_initialized` flag 确保只初始化一次。

```python
import logging
import os
from typing import Any

import httpx
from agentarts.sdk import IdentityClient, require_access_token
from agentarts.sdk.identity import OAuth2Vendor

logger = logging.getLogger(__name__)

_PROVIDER_INITIALIZED = False

def _init_provider():
    """Ensure the m365-provider exists in AgentArts Identity Service.
    
    Reads M365_CLIENT_ID, M365_CLIENT_SECRET, M365_TENANT_ID from env.
    Idempotent — skips if already initialized this process lifetime.
    """
    global _PROVIDER_INITIALIZED
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
        _PROVIDER_INITIALIZED = True
        return
    try:
        client = IdentityClient(region=os.environ.get("AGENTARTS_REGION", "cn-southwest-2"))
        client.create_oauth2_credential_provider(
            name="m365-provider",
            vendor=OAuth2Vendor.MICROSOFTOAUTH2,
            client_id=client_id,
            client_secret=client_secret,
            tenant_id=tenant_id,
        )
        logger.info("m365-provider created successfully.")
    except Exception as e:
        logger.error(f"Failed to create m365-provider: {e}")
    _PROVIDER_INITIALIZED = True

# ── Tool Functions ──

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0/me"

# ── 3a. list_emails ──

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
        dict with keys: emails (list of {id, subject, from, receivedDateTime, isRead, importance}),
        count (int), folder (str)
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GRAPH_BASE_URL}/mailFolders/{folder}/messages",
            headers={"Authorization": f"Bearer {access_token}"},
            params={
                "$top": limit,
                "$select": "id,subject,from,receivedDateTime,isRead,importance,bodyPreview",
                "$orderby": "receivedDateTime desc",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        emails = [
            {
                "id": m.get("id"),
                "subject": m.get("subject"),
                "from": m.get("from", {}).get("emailAddress", {}).get("name", "Unknown"),
                "receivedDateTime": m.get("receivedDateTime"),
                "isRead": m.get("isRead"),
                "importance": m.get("importance", "normal"),
                "bodyPreview": m.get("bodyPreview", ""),
            }
            for m in data.get("value", [])
        ]
        return {"emails": emails, "count": len(emails), "folder": folder}

# ── 3b. get_email ──

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
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GRAPH_BASE_URL}/messages/{email_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"$select": "id,subject,body,from,toRecipients,ccRecipients,receivedDateTime,hasAttachments,attachments"},
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "id": data.get("id"),
            "subject": data.get("subject"),
            "body": data.get("body", {}).get("content", ""),
            "from": data.get("from", {}).get("emailAddress", {}),
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

# ── 3c. search_emails ──

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
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GRAPH_BASE_URL}/messages",
            headers={"Authorization": f"Bearer {access_token}"},
            params={
                "$search": f'"{query}"',
                "$top": limit,
                "$select": "id,subject,from,receivedDateTime,isRead,bodyPreview",
                "$orderby": "receivedDateTime desc",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        results = [
            {
                "id": m.get("id"),
                "subject": m.get("subject"),
                "from": m.get("from", {}).get("emailAddress", {}).get("name", "Unknown"),
                "receivedDateTime": m.get("receivedDateTime"),
                "isRead": m.get("isRead"),
                "bodyPreview": m.get("bodyPreview", ""),
            }
            for m in data.get("value", [])
        ]
        return {"results": results, "count": len(results), "query": query}

# ── 3d. send_email (Guard 保护) ──

@require_access_token(
    provider_name="m365-provider",
    scopes=[
        "https://graph.microsoft.com/Mail.ReadWrite",
        "https://graph.microsoft.com/Mail.Send",
    ],
    auth_flow="USER_FEDERATION",
)
async def send_email(
    to: list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    access_token: str | None = None,
) -> dict[str, Any]:
    """发送邮件。

    此操作为敏感写操作，调用前 Agent 应通过 Guard 机制向用户展示预览
    并等待 explicit 确认。本函数不做 confirmation 检查 — 由 Agent 层处理。

    Args:
        to: 收件人邮箱地址列表
        subject: 邮件主题
        body: 邮件正文（纯文本）
        cc: 抄送邮箱地址列表，可选
        access_token: AgentArts Identity SDK 自动注入

    Returns:
        dict with: sent (bool), message_id (str or None), error (str or None)
    """
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

    async with httpx.AsyncClient() as client:
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

# ── 3e. draft_reply ──

@require_access_token(
    provider_name="m365-provider",
    scopes=["https://graph.microsoft.com/Mail.ReadWrite"],
    auth_flow="USER_FEDERATION",
)
async def draft_reply(
    email_id: str,
    body: str,
    access_token: str | None = None,
) -> dict[str, Any]:
    """草拟回复 — 创建回复草稿并返回供用户确认。

    注意：本函数创建草稿（Draft），不直接发送。Agent 应在返回后展示
    草稿内容给用户，用户确认后通过 send_email 发送。

    Args:
        email_id: 要回复的原始邮件 ID
        body: 回复正文（纯文本）
        access_token: AgentArts Identity SDK 自动注入

    Returns:
        dict with: draft_id (str or None), subject (str), body (str),
        toRecipients (list), error (str or None)
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GRAPH_BASE_URL}/messages/{email_id}/createReply",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={"message": {"body": {"contentType": "Text", "content": body}}},
        )
        if resp.status_code == 201:
            data = resp.json()
            return {
                "draft_id": data.get("id"),
                "subject": data.get("subject"),
                "body": data.get("body", {}).get("content", body),
                "toRecipients": [
                    r.get("emailAddress", {})
                    for r in data.get("toRecipients", [])
                ],
                "error": None,
            }
        return {
            "draft_id": None,
            "subject": "",
            "body": body,
            "toRecipients": [],
            "error": resp.text,
        }

# ── Module-level tool list (populated at import time) ──

_init_provider()

EMAIL_TOOLS = [
    list_emails,
    get_email,
    search_emails,
    send_email,
    draft_reply,
]
```

**关键设计决策**：

| 决策点 | 选择 | 原因 |
|--------|------|------|
| `_init_provider()` 在 import 时调用 | Module-level 函数调用，非 `__init__.py` | 避免循环导入，每个 tool module 自管理 provider 注册 |
| `email_id` 类型 | `str` | Microsoft Graph API 的 message ID 为 opaque string |
| `body` 格式 | 纯文本（`contentType: "Text"`） | MVP 阶段简单可靠，后续可扩展 HTML |
| `send_email` 不内置 Guard | 由 Agent system prompt + deepagents skills 控制 | 保持工具函数纯净，Guard 逻辑属于编排层 |

---

### 2.4 Task 4: 修改 `app/agent_handler.py` — 集成 ToolNode 和更新 System Prompt

**文件**：`personal-assistant-service/app/agent_handler.py`（修改）

**变更点 1**：修改 `SYSTEM_PROMPT` 常量（替换全文）

```python
SYSTEM_PROMPT = """\
你是 Personal Assistant，一个智能个人助手。
帮助用户管理日程、邮件、笔记和任务。

## 核心能力

### 邮件处理 ✅
你可以帮用户处理 Microsoft 365 (Outlook) 邮件，包括：
- **list_emails**: 列出收件箱或指定文件夹（如 sentitems、drafts）中的邮件
- **get_email**: 获取单封邮件的完整内容（正文、发件人、收件人、附件列表）
- **search_emails**: 按关键词搜索邮件，快速定位特定主题或发送者的邮件
- **send_email**: 发送邮件（⚠️ 敏感操作 — 必须先向用户展示预览并获得 explicit 确认）
- **draft_reply**: 草拟回复某封邮件的内容，供用户审阅后确认发送

使用邮件功能时：
1. 当用户询问收件箱情况时，优先使用 list_emails 获取邮件列表
2. 当用户想搜索特定内容时，使用 search_emails
3. 当用户想查看某封邮件详情时，使用 get_email
4. 当用户想回复邮件时，先用 draft_reply 生成草稿展示给用户，确认后再用 send_email 发送
5. ⚠️ 发送邮件前必须先展示预览（收件人、主题、正文）并等待用户 explicit 确认

### 日程管理（即将上线）
- 创建、查询、修改和取消日程

### 笔记和任务（即将上线）
- 创建和检索个人笔记
- 管理待办事项和项目进度

## 行为准则
- 使用中文回复
- 保持友好、专业、乐于助人的语调
- 不清楚的事情坦诚说明，不要编造
- 回复简洁有力，避免冗长
- 涉及邮件发送等敏感操作时，必须先确认再执行"""
```

**变更点 2**：修改 `AgentHandler.__init__()` 中的 `tools` 参数

原有代码：
```python
self.agent = create_deep_agent(
    model=self.model,
    system_prompt=SYSTEM_PROMPT,
    tools=[],  # TODO: Feature 10a
    checkpointer=self.checkpointer,
)
```

改为：
```python
from app.tools import build_tools

# ... inside __init__ ...
self.agent = create_deep_agent(
    model=self.model,
    system_prompt=SYSTEM_PROMPT,
    tools=build_tools(),
    checkpointer=self.checkpointer,
)
```

**注意**：移除 `tools=[]` 旁的 `# TODO: Feature 10a` 注释，替换为实际调用。

---

### 2.5 Task 5: Guard Mechanism — `send_email` 二次确认

Guard 机制**不在工具函数内部实现**，而是通过 deepagents 的 **skills 系统** 实现：

**实现方式**：
- 在 `SYSTEM_PROMPT` 中明确声明 `send_email` 为敏感操作（见 §2.4）
- 在 Agent 的 SKILL.md 文件中（`personal-assistant-service/.files/` 或 deepagents 的 skills 目录）描述邮件发送流程：Agent 在决定调用 `send_email` 之前，必须先在对话中向用户展示邮件预览（收件人、主题、正文），并等待用户明确回复"确认"或"发送"后才能执行
- **不需要**在 email_tools.py 中为 `send_email` 添加 `requires_confirmation` 标记 — deepagents/human-in-the-loop 机制由 Agent 层 system prompt 控制

**备选方案**（如 deepagents 支持 tool-level confirmation）：
- 如果 deepagents 后续版本支持 tool-level `requires_confirmation=True` 属性，可以在 `send_email` 返回值中携带 `requires_confirmation: True`
- 当前版本通过 system prompt 描述行为约束

---

### 2.6 Task 6: Unit Test 设计

#### 测试文件结构

```
personal-assistant-service/tests/
├── test_tools_init.py         # 新建 — 测试 build_tools() 工厂
├── test_email_tools.py        # 新建 — 测试所有 5 个 email 工具函数
├── test_agent_handler.py      # 修改 — 验证 tools 已注入
```

#### 6.1 `tests/test_tools_init.py` — 新建

测试 `app.tools.build_tools()` 工厂函数：

| 测试场景 | 说明 |
|----------|------|
| `test_build_tools_returns_list` | 验证返回类型为 list |
| `test_build_tools_includes_email_tools` | 验证 EMAIL_TOOLS 中的 5 个函数都在返回列表中 |
| `test_build_tools_graceful_import_error` | 模拟 `email_tools` import 失败时的行为 — 不应抛异常 |

#### 6.2 `tests/test_email_tools.py` — 新建

每个 tool function 的单元测试（mock httpx + mock require_access_token）：

| 测试场景 | 说明 |
|----------|------|
| **list_emails** | |
| `test_list_emails_returns_formatted_list` | 验证返回 `{emails, count, folder}` 结构 |
| `test_list_emails_default_folder_inbox` | 不传 folder 参数时默认 `"inbox"` |
| `test_list_emails_custom_folder` | 传入 `folder="sentitems"` 时 URL 正确 |
| `test_list_emails_limit_parameter` | `limit=5` 时 Graph API 参数 `$top=5` |
| `test_list_emails_empty_inbox` | Graph API 返回空 value 数组时应返回 `count: 0` |
| `test_list_emails_http_error` | Graph API 返回 4xx/5xx 时 propagate 异常 |
| **get_email** | |
| `test_get_email_returns_full_detail` | 验证返回完整字段（id, subject, body, from, toRecipients, ccRecipients, attachments） |
| `test_get_email_with_attachments` | `hasAttachments=true` 时返回附件列表 |
| `test_get_email_without_attachments` | `hasAttachments=false` 时返回空附件列表 |
| `test_get_email_not_found` | 404 时应 propagate 异常 |
| **search_emails** | |
| `test_search_emails_returns_results` | 验证 `{results, count, query}` 结构 |
| `test_search_emails_empty_results` | 无匹配结果时返回 `count: 0` |
| `test_search_emails_uses_search_param` | 验证 Graph API 调用使用了 `$search` 参数 |
| **send_email** | |
| `test_send_email_success` | 202 响应 → 返回 `{sent: True}` |
| `test_send_email_with_cc` | 包含 cc 参数时 Graph API payload 包含 ccRecipients |
| `test_send_email_failure` | 非 202 响应 → 返回 `{sent: False, error: ...}` |
| `test_send_email_formats_recipients` | 验证 to 和 cc 数组正确格式化为 emailAddress 结构 |
| **draft_reply** | |
| `test_draft_reply_returns_draft_info` | 201 响应 → 返回 `{draft_id, subject, body, toRecipients}` |
| `test_draft_reply_failure` | 非 201 响应 → 返回 `{draft_id: None, error: ...}` |
| **Provider 初始化** | |
| `test_provider_init_skips_if_env_vars_missing` | M365_CLIENT_ID 等未设置时不抛异常，仅 warning |
| `test_provider_init_with_valid_env` | 环境变量齐全时调用 IdentityClient（mock） |

#### 6.3 Mock 策略

**`@require_access_token` 装饰器 mock**：
- 在测试中将 `require_access_token` 替换为简单的 passthrough — 直接将被装饰函数原样返回，`access_token` 参数由测试显式传入
- 或者在测试级别 mock 掉 decorator：`patch("app.tools.email_tools.require_access_token", lambda **kw: lambda fn: fn)`

**`httpx.AsyncClient` mock**：
- 使用 `unittest.mock.AsyncMock` + `patch` 替换 `httpx.AsyncClient`
- 预定义 Graph API JSON 响应 fixture，模拟真实 Microsoft Graph API 返回结构

**`IdentityClient` mock**：
- 测试 provider 初始化逻辑时 mock `agentarts.sdk.IdentityClient`

#### 6.4 修改 `tests/test_agent_handler.py`

**变更**：

| 测试场景 | 说明 |
|----------|------|
| `test_agent_created_with_tools_from_build_tools` | 验证 `create_deep_agent` 的 `tools` kwarg 不为空列表 — 调用了 `build_tools()` |
| `test_system_prompt_mentions_email_capabilities` | 验证 `SYSTEM_PROMPT` 包含 `list_emails`、`send_email` 等关键词 |

**注意**：由于 `build_tools()` 会 import `email_tools.py`，而 `email_tools.py` 的 module-level 会调用 `_init_provider()` → `IdentityClient(...)`，在 CI 测试环境（无真实 AgentArts Identity Service）中需要 mock `IdentityClient` 或确保 env vars 未设置时走 warning 路径不抛异常。

---

## 3. 后端测试汇总

```
Test File                           New / Modified   Test Cases
─────────────────────────────────────────────────────────────────
tests/test_tools_init.py            NEW              3
tests/test_email_tools.py           NEW              ~18
tests/test_agent_handler.py         MODIFIED         2
─────────────────────────────────────────────────────────────────
Total (new tests)                                     23
```

---

## 4. Sequence Diagram

### 邮件查询流程（list_emails）

```mermaid
sequenceDiagram
    actor User as 用户
    participant Agent as deepagents Agent
    participant ToolNode as LangGraph ToolNode
    participant Decorator as @require_access_token
    participant IdSvc as AgentArts Identity Service
    participant GraphAPI as Microsoft Graph API

    User->>Agent: "帮我看看收件箱"
    Agent->>Agent: LLM 推理 → 决定调用 list_emails(folder="inbox", limit=10)
    Agent->>ToolNode: tool_call: list_emails(folder="inbox", limit=10)
    ToolNode->>Decorator: 执行 @require_access_token 包裹的函数
    Decorator->>IdSvc: get_resource_oauth2_token(provider="m365-provider", scopes=["Mail.Read"], agent_identity_token=...)
    IdSvc-->>Decorator: access_token (JWT)
    Decorator->>ToolNode: 调用原始 async fn → access_token 注入
    ToolNode->>GraphAPI: GET /me/mailFolders/inbox/messages?$top=10&$select=...&$orderby=receivedDateTime desc
    GraphAPI-->>ToolNode: 200 OK: {value: [{id, subject, from, ...}, ...]}
    ToolNode-->>Agent: tool result: {emails: [...], count: 3, folder: "inbox"}
    Agent->>Agent: LLM 推理 → 生成自然语言回复
    Agent-->>User: "你最近有 3 封邮件：1. 张三 — 项目进度..."
```

### 邮件发送流程（send_email + Guard）

```mermaid
sequenceDiagram
    actor User as 用户
    participant Agent as deepagents Agent
    participant ToolNode as LangGraph ToolNode
    participant IdSvc as AgentArts Identity Service
    participant GraphAPI as Microsoft Graph API

    User->>Agent: "帮张三回邮件说下周 meeting 改周三"
    Agent->>Agent: LLM 推理 → 先调 get_email 获取原始邮件上下文
    Agent->>ToolNode: tool_call: get_email(email_id="...")
    ToolNode->>GraphAPI: GET /me/messages/{id}
    GraphAPI-->>ToolNode: 邮件详情
    ToolNode-->>Agent: {subject, body, from, ...}
    Agent->>Agent: LLM 推理 → 生成回复草稿
    Agent-->>User: "草拟如下：收件人：张三，主题：Re: ..., 正文：... 需要发送吗？"
    User->>Agent: "发送"
    Agent->>Agent: ✅ Guard: 用户 explicit 确认
    Agent->>ToolNode: tool_call: send_email(to=["zhangsan@..."], subject="Re: ...", body="...")
    ToolNode->>IdSvc: get_resource_oauth2_token(provider="m365-provider", scopes=["Mail.ReadWrite", "Mail.Send"])
    IdSvc-->>ToolNode: access_token (JWT)
    ToolNode->>GraphAPI: POST /me/sendMail {message: {...}, saveToSentItems: true}
    GraphAPI-->>ToolNode: 202 Accepted
    ToolNode-->>Agent: {sent: true}
    Agent-->>User: "邮件已发送给张三 ✅"
```

---

## 5. 文件变更清单

```
personal-assistant-service/
├── pyproject.toml                    # MODIFIED  — 添加 agentarts-sdk>=0.1.3
├── app/
│   ├── tools/
│   │   ├── __init__.py               # NEW       — build_tools() 工厂函数
│   │   └── email_tools.py            # NEW       — 5 个邮件工具函数
│   └── agent_handler.py              # MODIFIED  — 导入 build_tools(), 更新 SYSTEM_PROMPT, tools=build_tools()
├── tests/
│   ├── test_tools_init.py            # NEW       — build_tools() 测试
│   ├── test_email_tools.py           # NEW       — email_tools 各函数测试
│   └── test_agent_handler.py         # MODIFIED  — 验证 tools 注入 + system prompt 内容
```

**文件数量**：新建 3 个文件，修改 2 个文件。

---

## 6. Implementation Order（推荐实现顺序）

| Step | Task | 依赖 | 验证方式 |
|------|------|------|----------|
| 1 | `pyproject.toml` 添加 `agentarts-sdk` | 无 | `uv sync` |
| 2 | `app/tools/__init__.py` 创建 `build_tools()` | Step 1 | `python -c "from app.tools import build_tools; print(build_tools())"` |
| 3 | `app/tools/email_tools.py` 创建 5 个工具函数 | Step 2 | 见 §6.2 测试 |
| 4 | `app/agent_handler.py` 集成 `build_tools()` 和更新 prompt | Step 2, 3 | `python -c "from app.agent_handler import AgentHandler; h = AgentHandler()"` 启动不报错 |
| 5 | `tests/test_tools_init.py` 编写 | Step 2 | `pytest tests/test_tools_init.py -v` |
| 6 | `tests/test_email_tools.py` 编写 | Step 3 | `pytest tests/test_email_tools.py -v` |
| 7 | `tests/test_agent_handler.py` 更新 | Step 4 | `pytest tests/test_agent_handler.py -v` |
| 8 | 全量测试 | 全部 | `pytest tests/ -v` |

---

## 7. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `agentarts-sdk` v0.1.3 尚未发布到 PyPI 或版本不兼容 | 依赖安装失败 | 先验证 PyPI 可用性；如不可用，使用本地 path 安装 (`uv add /path/to/agentarts-sdk-python`) |
| IdentityClient 创建 provider 在测试环境不可用 | 测试无法 import email_tools | 通过 env var guard（`M365_CLIENT_ID` 未设置时 skip 初始化）确保 import 不阻塞 |
| Graph API 响应格式变更 | 工具返回 dict 字段丢失 | 使用 `.get()` 安全访问 + 默认值，工具函数不假定必选字段存在 |
| `httpx.AsyncClient` 在 AgentArts 容器内网络策略限制 | 无法访问 `graph.microsoft.com` | AgentArts Runtime PUBLIC network_mode 应支持出站 HTTPS，需部署后验证 |
