import json
import logging
import time
from contextlib import asynccontextmanager
from json import JSONDecodeError
from pathlib import Path

from app.logging_config import RequestLoggingMiddleware

logger = logging.getLogger("app")

from agentarts.sdk import IdentityClient  # noqa: E402
from agentarts.sdk.runtime.context import AgentArtsRuntimeContext  # noqa: E402
from agentarts.sdk.utils.constant import get_region  # noqa: E402
from chainlit.utils import mount_chainlit  # noqa: E402
from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.responses import (  # noqa: E402
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
)
from huaweicloudsdkagentidentity.v1.model import UserIdentifier  # noqa: E402
from pydantic import BaseModel, Field, StrictBool, ValidationError  # noqa: E402

from app.agent_handler import AgentHandler, get_agent_handler  # noqa: E402
from app.auth import (  # noqa: E402
    extract_gateway_session_id,
    extract_gateway_user_id,
    extract_workload_access_token,
)
from app.oauth2_state import (  # noqa: E402
    OAuth2StateError,
    create_oauth2_state,
    verify_oauth2_state,
)
from app.settings import get_settings  # noqa: E402


class InvocationRequest(BaseModel):
    """Agent invocation request."""

    message: str = Field(description="User message sent to the Agent.")
    stream: StrictBool = Field(
        default=False,
        description="Return a Server-Sent Events stream instead of JSON.",
    )


class InvocationResponse(BaseModel):
    """Successful non-streaming invocation response."""

    response: str


class ErrorResponse(BaseModel):
    """HTTP error response."""

    detail: str


class OAuth2CompleteRequest(BaseModel):
    """OAuth2 Resource Token Auth completion request."""

    provider: str = Field(description="AgentArts resource credential provider name.")
    session_uri: str = Field(description="AgentArts Resource Token Auth session URI.")
    state: str | None = Field(
        default=None,
        description="OAuth2 state returned by the callback, if present.",
    )
    error: str | None = Field(default=None, description="OAuth2 callback error code.")
    error_description: str | None = Field(
        default=None,
        description="OAuth2 callback error description.",
    )


class OAuth2CompleteResponse(BaseModel):
    """OAuth2 completion response."""

    status: str
    provider: str
    message: str


def _parse_invocation_request(body: object) -> InvocationRequest:
    """Validate an invocation body while preserving the public 400 contract."""
    try:
        invocation = InvocationRequest.model_validate(body)
    except ValidationError as e:
        errors = e.errors()
        if any(
            error["loc"] == ("message",) and error["type"] == "missing"
            for error in errors
        ):
            detail = "message is required"
        elif any(error["loc"] == ("message",) for error in errors):
            detail = "message must be a string"
        elif any(error["loc"] == ("stream",) for error in errors):
            detail = "stream must be a boolean"
        else:
            detail = "invalid request body"
        raise HTTPException(status_code=400, detail=detail) from e

    if not invocation.message.strip():
        raise HTTPException(status_code=400, detail="message is required")
    return invocation


def _parse_oauth2_complete_request(body: object) -> OAuth2CompleteRequest:
    try:
        complete_request = OAuth2CompleteRequest.model_validate(body)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail="invalid request body") from e

    if not complete_request.provider.strip():
        raise HTTPException(status_code=400, detail="provider is required")
    if not complete_request.session_uri.strip():
        raise HTTPException(status_code=400, detail="session_uri is required")
    return complete_request


def _accepts_media_type(accept: str | None, media_type: str) -> bool:
    """Return whether an Accept header permits the selected response type."""
    if not accept:
        return True

    expected_type, expected_subtype = media_type.lower().split("/", maxsplit=1)
    for entry in accept.split(","):
        parts = [part.strip() for part in entry.split(";")]
        accepted_type = parts[0].lower()
        if "/" not in accepted_type:
            continue

        quality = 1.0
        for parameter in parts[1:]:
            name, separator, value = parameter.partition("=")
            if separator and name.strip().lower() == "q":
                try:
                    quality = float(value)
                except ValueError:
                    quality = 0.0
        if quality <= 0:
            continue

        accepted_main, accepted_subtype = accepted_type.split("/", maxsplit=1)
        if accepted_main in {"*", expected_type} and accepted_subtype in {
            "*",
            expected_subtype,
        }:
            return True
    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle for the FastAPI application."""
    # Validate LLM provider metadata. The Agent Bundle is built lazily after
    # the first request places the Gateway workload token in Runtime Context.
    from app.llm_config import validate_model_config

    try:
        validate_model_config()
    except ValueError as e:
        raise RuntimeError(f"LLM 配置错误: {e}") from e

    # Initialize the shared handler and persistent Checkpointer before serving.
    handler = get_agent_handler()
    await handler.startup()
    app.state.agent_handler = handler

    try:
        yield
    finally:
        await handler.shutdown()


app = FastAPI(
    title="Personal Assistant",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(RequestLoggingMiddleware)


@app.get("/ping")
async def ping():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post(
    "/invocations",
    response_model=InvocationResponse,
    responses={
        200: {
            "description": (
                "JSON response when stream is false, or a Server-Sent Events "
                "stream when stream is true."
            ),
            "content": {
                "text/event-stream": {
                    "schema": {
                        "type": "string",
                        "description": "Server-Sent Events stream.",
                    },
                    "example": (
                        'data: {"token":"你","done":false}\n\n'
                        'data: {"token":"","done":true}\n\n'
                    ),
                }
            },
        },
        400: {
            "model": ErrorResponse,
            "description": "Invalid JSON or invocation request.",
        },
        406: {
            "model": ErrorResponse,
            "description": "The Accept header excludes the selected response type.",
        },
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": InvocationRequest.model_json_schema(),
                }
            },
        }
    },
)
async def invocations(request: Request):
    """Agent invocation endpoint, supporting sync JSON and SSE streaming."""
    try:
        body = await request.json()
    except JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="invalid JSON body") from e

    invocation = _parse_invocation_request(body)
    message = invocation.message
    stream = invocation.stream
    user_id = extract_gateway_user_id(request)
    session_id = extract_gateway_session_id(request)
    extract_workload_access_token(request)
    settings = get_settings()
    AgentArtsRuntimeContext.set_oauth2_custom_state(
        create_oauth2_state(
            settings=settings,
            user_id=user_id,
            session_id=session_id,
            provider=settings.m365_calendar_provider_name,
        )
    )

    mode = "stream" if stream else "sync"
    response_media_type = "text/event-stream" if stream else "application/json"
    if not _accepts_media_type(request.headers.get("accept"), response_media_type):
        raise HTTPException(
            status_code=406,
            detail=f"Accept header must allow {response_media_type}",
        )

    handler: AgentHandler = request.app.state.agent_handler
    started_at = time.perf_counter()
    logger.info("Invocation started mode=%s", mode)

    if stream:

        async def event_generator():
            status = "cancelled"
            try:
                async for sse_data in handler.handle_stream(
                    message=message,
                    user_id=user_id,
                    session_id=session_id,
                ):
                    yield sse_data
                status = "success"
            except Exception as e:
                status = "error"
                logger.error(
                    "Invocation failed mode=stream duration_ms=%.2f: %s",
                    (time.perf_counter() - started_at) * 1000,
                    e,
                    exc_info=True,
                )
                yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"
            finally:
                logger.info(
                    "Invocation completed mode=stream status=%s duration_ms=%.2f",
                    status,
                    (time.perf_counter() - started_at) * 1000,
                )

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    try:
        result = await handler.handle(
            message=message,
            user_id=user_id,
            session_id=session_id,
        )
    except Exception as e:
        logger.error(
            "Invocation failed mode=sync duration_ms=%.2f: %s",
            (time.perf_counter() - started_at) * 1000,
            e,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(e)) from e

    logger.info(
        "Invocation completed mode=sync status=success duration_ms=%.2f",
        (time.perf_counter() - started_at) * 1000,
    )
    return JSONResponse(content=InvocationResponse(response=result).model_dump())


@app.post(
    "/auth/oauth2/complete",
    response_model=OAuth2CompleteResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid callback payload."},
        401: {"model": ErrorResponse, "description": "Missing trusted user header."},
        403: {"model": ErrorResponse, "description": "Invalid OAuth2 state."},
        502: {"model": ErrorResponse, "description": "Identity Service failure."},
    },
)
async def complete_oauth2_auth(request: Request):
    """Complete AgentArts Resource Token Auth for Calendar OAuth2 callbacks."""
    logger.info("Handling OAuth2 complete request")
    try:
        body = await request.json()
    except JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="invalid JSON body") from e

    complete_request = _parse_oauth2_complete_request(body)
    user_id = extract_gateway_user_id(request)
    settings = get_settings()

    if complete_request.error:
        logger.warning(
            "Calendar OAuth2 callback failed provider=%s error=%s",
            complete_request.provider,
            complete_request.error,
        )
        raise HTTPException(
            status_code=400,
            detail="Calendar authorization failed. Please try again.",
        )

    if complete_request.provider != settings.m365_calendar_provider_name:
        raise HTTPException(status_code=400, detail="unsupported OAuth2 provider")

    if not complete_request.state or not complete_request.state.strip():
        raise HTTPException(status_code=400, detail="state is required")

    try:
        verify_oauth2_state(
            complete_request.state,
            settings=settings,
            expected_user_id=user_id,
            expected_provider=complete_request.provider,
        )
    except OAuth2StateError as e:
        logger.warning(
            "Calendar OAuth2 state rejected provider=%s user_id=%s: %s",
            complete_request.provider,
            user_id,
            e,
        )
        raise HTTPException(status_code=403, detail="invalid OAuth2 state") from e

    try:
        client = IdentityClient(region=get_region())
        client.complete_resource_token_auth(
            session_uri=complete_request.session_uri,
            user_identifier=UserIdentifier(user_id=user_id),
        )
    except Exception as e:
        logger.warning(
            "Calendar OAuth2 complete failed provider=%s user_id=%s: %s",
            complete_request.provider,
            user_id,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=502,
            detail="Calendar authorization could not be completed.",
        ) from e

    logger.info(
        "Calendar OAuth2 complete succeeded provider=%s user_id=%s",
        complete_request.provider,
        user_id,
    )
    return OAuth2CompleteResponse(
        status="complete",
        provider=complete_request.provider,
        message="Calendar authorization completed.",
    )


# === Chainlit Playground（Agent 调试 UI）===


@app.get("/invocations/playground", include_in_schema=False)
async def playground_redirect():
    """Redirect /playground to /playground/ (Chainlit mount requires trailing slash)."""
    return RedirectResponse(url="/invocations/playground/")


mount_chainlit(
    app=app,
    target=str(Path(__file__).parent / "playground.py"),
    path="/invocations/playground",
)
