import logging

from agentarts.sdk import IdentityClient
from agentarts.sdk.runtime.context import AgentArtsRuntimeContext
from agentarts.sdk.runtime.model import (
    ACCESS_TOKEN_HEADER,
    SESSION_HEADER,
    USER_ID_HEADER,
)
from agentarts.sdk.utils.constant import get_region
from fastapi import HTTPException, Request

from app.settings import get_settings

logger = logging.getLogger(__name__)


def extract_authorization_user_token(request: Request) -> str:
    """Extract the JWT from the Authorization header for AgentArts Identity."""
    authorization = request.headers.get("authorization", "").strip()
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header",
        )
    if authorization.lower() == "bearer":
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header",
        )

    scheme, separator, token = authorization.partition(" ")
    if not separator:
        return authorization
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header",
        )
    return token.strip()


def extract_gateway_user_id(request: Request) -> str:
    """Extract verified user_id from AgentArts Gateway injected header.

    Production (CUSTOM_JWT): Gateway validates JWT then injects
    this header. It is guaranteed to be present and trustworthy.
    Development (key_auth or no Gateway): Manually inject this
    header to simulate identity.

    Raises:
        HTTPException(401): Fail-closed when header is missing.
    """
    user_id = request.headers.get(USER_ID_HEADER, "").strip()
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail=f"Missing {USER_ID_HEADER} header",
        )
    AgentArtsRuntimeContext.set_user_id(user_id)
    return user_id


def extract_gateway_session_id(request: Request) -> str:
    """Extract session_id from AgentArts Gateway injected header.

    Raises:
        HTTPException(400): Fail-closed when header is missing.
    """
    session_id = request.headers.get(SESSION_HEADER, "").strip()
    if not session_id:
        raise HTTPException(
            status_code=400,
            detail=f"{SESSION_HEADER} header is required",
        )
    AgentArtsRuntimeContext.set_session_id(session_id)
    return session_id


def ensure_jwt_workload_access_token(
    request: Request,
    *,
    required: bool,
) -> str | None:
    """Ensure Runtime Context has a JWT-bound AgentArts workload token.

    Production requests receive a Gateway-injected workload token that is
    already bound to the inbound JWT identity. Local Calendar OAuth2 requests
    must create the same JWT-mode token from the inbound Authorization token
    before AgentArts SDK decorators can fall back to user_id mode.
    """
    gateway_token = request.headers.get(ACCESS_TOKEN_HEADER, "").strip()
    if gateway_token:
        AgentArtsRuntimeContext.set_workload_access_token(gateway_token)
        logger.info("JWT-mode WAT ready source=gateway_wat identity_mode=jwt")
        return gateway_token

    try:
        user_token = extract_authorization_user_token(request)
    except HTTPException as e:
        AgentArtsRuntimeContext.set_workload_access_token(None)
        logger.info(
            "JWT-mode WAT unavailable source=missing_authorization_user_token "
            "identity_mode=jwt required=%s",
            required,
        )
        if required:
            raise HTTPException(
                status_code=401,
                detail="Local Calendar OAuth2 requires an Authorization user token",
            ) from e
        return None

    settings = get_settings()
    client = IdentityClient(region=get_region())
    workload_token = client.create_workload_access_token(
        settings.agent_identity_workload_name,
        user_token=user_token,
    )
    AgentArtsRuntimeContext.set_workload_access_token(workload_token)
    logger.info(
        "JWT-mode WAT ready source=local_jwt_wat identity_mode=jwt workload_name=%s",
        settings.agent_identity_workload_name,
    )
    return workload_token


def extract_workload_access_token(request: Request) -> None:
    """Backward-compatible Gateway/local JWT WAT preparation helper."""
    ensure_jwt_workload_access_token(request, required=False)
