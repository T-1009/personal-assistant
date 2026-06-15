from fastapi import HTTPException, Request

from agentarts.sdk.runtime.context import AgentArtsRuntimeContext
from agentarts.sdk.runtime.model import ACCESS_TOKEN_HEADER


def extract_gateway_user_id(request: Request) -> str:
    """Extract verified user_id from AgentArts Gateway injected header.

    Production (CUSTOM_JWT): Gateway validates JWT then injects this header.
    It is guaranteed to be present and trustworthy.
    Development (key_auth or no Gateway): Manually inject this header to
    simulate identity.

    Raises:
        HTTPException(401): Fail-closed when header is missing in production.
    """
    user_id = request.headers.get("X-HW-AgentGateway-User-Id", "").strip()
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Missing X-HW-AgentGateway-User-Id header",
        )
    return user_id


def extract_workload_access_token(request: Request) -> None:
    """提取并存入 AgentArts Gateway 注入的 Workload Access Token。

    生产环境中，AgentArts Gateway 在转发请求时注入
    X-HW-AgentGateway-Workload-Access-Token header（常量:
    agentarts.sdk.runtime.model.ACCESS_TOKEN_HEADER）。

    提取后存入 AgentArtsRuntimeContext，使 @require_access_token
    等装饰器可以直接使用，跳过本地 .agent_identity.json 的 fallback 流程。

    若 header 不存在或为空（本地开发环境），显式设为 None，
    确保 context 干净。SDK 的 _get_workload_access_token() 自动
    fallback 到本地认证。
    """
    token = request.headers.get(ACCESS_TOKEN_HEADER, "").strip()
    AgentArtsRuntimeContext.set_workload_access_token(token or None)
