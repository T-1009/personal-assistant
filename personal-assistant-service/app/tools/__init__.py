"""Tools package — factory for building the LangGraph ToolNode with registered tools.

This module provides build_tools(), called by AgentHandler.__init__() to
dynamically assemble the tool list. Each sub-module (email_tools.py, etc.)
registers its tools via a module-level TOOLS list.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def build_tools() -> list[Any]:
    """Build the list of tools for deepagents/LangGraph ToolNode.

    Collects tools from all registered sub-modules. Each sub-module
    must expose a module-level TOOLS list of callable tool functions.
    """
    tools: list[Any] = []

    # ── GitHub tools (Feature 6) — always register ──
    try:
        from app.tools.github_tools import GITHUB_TOOLS

        tools.extend(GITHUB_TOOLS)
        logger.info("GitHub tools registered (%d tools).", len(GITHUB_TOOLS))
    except ImportError as e:
        logger.warning(
            "GitHub tools not available (import failed): %s. "
            "GitHub functionality will be disabled for this session.",
            e,
            exc_info=True,
        )

    # ── Gitee tools — always register ──
    try:
        from app.tools.gitee_tools import GITEE_TOOLS

        tools.extend(GITEE_TOOLS)
        logger.info("Gitee tools registered (%d tools).", len(GITEE_TOOLS))
    except ImportError as e:
        logger.warning(
            "Gitee tools not available (import failed): %s. "
            "Gitee functionality will be disabled for this session.",
            e,
            exc_info=True,
        )

    # Huawei Cloud IAM tools -- always register
    try:
        from app.tools.iam_tools import IAM_TOOLS

        tools.extend(IAM_TOOLS)
        logger.info("Huawei Cloud IAM tools registered (%d tools).", len(IAM_TOOLS))
    except ImportError as e:
        logger.warning(
            "Huawei Cloud IAM tools not available (import failed): %s. "
            "IAM functionality will be disabled for this session.",
            e,
            exc_info=True,
        )

    # ── Email tools (Feature 10a) — always register ──
    try:
        from app.tools.email_tools import EMAIL_TOOLS, ensure_provider_sync

        tools.extend(EMAIL_TOOLS)
        logger.info("Email tools registered (%d tools).", len(EMAIL_TOOLS))

        # Pre-create the OAuth2 credential provider on AgentArts Identity.
        # Don't gate tool registration on this — tools are always available
        # to the LLM. If provider creation fails, the _handle_provider_error
        # wrapper on each tool catches it and returns a user-friendly error
        # instead of crashing.
        ensure_provider_sync()
    except ImportError as e:
        logger.warning(
            "Email tools not available (import failed): %s. "
            "Email functionality will be disabled for this session.",
            e,
            exc_info=True,
        )

    return tools
