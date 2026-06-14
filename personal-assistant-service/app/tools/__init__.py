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

    # ── Email tools (Feature 10a) ──
    try:
        from app.tools.email_tools import EMAIL_TOOLS, ensure_provider_sync

        # Pre-create the OAuth2 credential provider BEFORE registering tools.
        # The @require_access_token decorator fires before the tool function body,
        # so the provider must already exist on the AgentArts Identity service.
        if ensure_provider_sync():
            tools.extend(EMAIL_TOOLS)
            logger.info("Email tools registered (%d tools).", len(EMAIL_TOOLS))
        else:
            logger.warning(
                "Email tools skipped — failed to create m365-provider. "
                "Check M365_CLIENT_ID, M365_CLIENT_SECRET, M365_TENANT_ID env vars "
                "and AgentArts Identity service availability."
            )
    except ImportError as e:
        logger.warning(
            "Email tools not available (import failed): %s. "
            "Email functionality will be disabled for this session.",
            e,
            exc_info=True,
        )

    # ── Future tool modules go here ──
    # try:
    #     from app.tools.github_tools import GITHUB_TOOLS
    #     tools.extend(GITHUB_TOOLS)
    # except ImportError as e:
    #     logger.warning("GitHub tools not available.", exc_info=True)

    return tools
