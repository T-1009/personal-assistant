from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

import app.invocations.service as invocation_service
from app.invocations.models import AgentEventType, AgentStreamEvent, InvocationRequest
from app.invocations.service import InvocationExecution


class BlockingAgentHandler:
    def __init__(self) -> None:
        self.release = asyncio.Event()
        self.cancelled = asyncio.Event()

    async def handle_stream(
        self,
        message: str,
        user_id: str,
        conversation_id: str,
    ):
        del message, user_id, conversation_id
        try:
            await self.release.wait()
            yield AgentStreamEvent(type=AgentEventType.TOKEN, token="done")
        except asyncio.CancelledError:
            self.cancelled.set()
            raise


def _execution(
    handler: BlockingAgentHandler,
) -> tuple[InvocationExecution, AsyncMock, AsyncMock, AsyncMock]:
    insert_assistant = AsyncMock()
    verify_lease = AsyncMock()
    exit_lock = AsyncMock(return_value=None)
    execution = InvocationExecution(
        store=SimpleNamespace(insert_assistant_message=insert_assistant),
        handler=handler,
        request=InvocationRequest(
            conversation_id=uuid4(),
            client_message_id=uuid4(),
            message="write a monthly report",
            stream=True,
        ),
        user_id="user-1",
        conversation_pk=1,
        user_message=SimpleNamespace(id=uuid4()),
        lock_context=SimpleNamespace(__aexit__=exit_lock),
        lock_lease=SimpleNamespace(verify=verify_lease),
    )
    return execution, insert_assistant, verify_lease, exit_lock


def _payload(event: str) -> dict[str, object]:
    return json.loads(event.removeprefix("data: "))


@pytest.mark.asyncio
async def test_silent_agent_emits_heartbeats_without_cancelling_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(invocation_service, "_SSE_HEARTBEAT_INTERVAL_SECONDS", 0.01)
    handler = BlockingAgentHandler()
    execution, insert_assistant, verify_lease, exit_lock = _execution(handler)
    stream = execution.stream_sse()

    assert await asyncio.wait_for(anext(stream), timeout=0.5) == ": heartbeat\n\n"
    assert await asyncio.wait_for(anext(stream), timeout=0.5) == ": heartbeat\n\n"
    assert not handler.cancelled.is_set()

    handler.release.set()
    assert _payload(await asyncio.wait_for(anext(stream), timeout=0.5)) == {
        "token": "done",
        "done": False,
    }
    assert _payload(await asyncio.wait_for(anext(stream), timeout=0.5)) == {
        "token": "",
        "done": True,
    }
    with pytest.raises(StopAsyncIteration):
        await anext(stream)

    insert_assistant.assert_awaited_once()
    verify_lease.assert_awaited_once_with()
    exit_lock.assert_awaited_once_with(None, None, None)
    assert execution.status == "success"


@pytest.mark.asyncio
async def test_closing_silent_stream_cancels_pending_agent_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(invocation_service, "_SSE_HEARTBEAT_INTERVAL_SECONDS", 0.01)
    handler = BlockingAgentHandler()
    execution, insert_assistant, verify_lease, exit_lock = _execution(handler)
    stream = execution.stream_sse()

    assert await asyncio.wait_for(anext(stream), timeout=0.5) == ": heartbeat\n\n"
    await stream.aclose()

    assert handler.cancelled.is_set()
    insert_assistant.assert_not_awaited()
    verify_lease.assert_not_awaited()
    exit_lock.assert_awaited_once_with(None, None, None)
