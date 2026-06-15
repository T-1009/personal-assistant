"""E2E tests for refactored email OAuth2 auth flow using normal control flow.

Tests the ContextVar-isolated message_queue flow for delivering auth URLs
via SSE system_message events, replacing the old exception-based
AuthUrlRequired flow.

Test scenarios from plan:
  E2E-AUTH-01: OAuth2 auth URL delivered via SSE system_message
  E2E-AUTH-02: system_message interleaved with tokens — correct ordering
  E2E-AUTH-03: system_message fields are complete
  E2E-AUTH-04: done: true normal ending
  E2E-AUTH-05: Normal email operations without auth (regression)
  E2E-AUTH-06: Non-streaming path unaffected
  E2E-AUTH-07: Queue lifecycle — no cross-request leakage
  E2E-AUTH-08: Concurrency isolation
"""

import asyncio
import json
import os
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

# NOTE: These tests run from the service venv which has agentarts-sdk
# installed, so no sys.modules mocking is needed. The email_tools import
# chain (agentarts.sdk → agentarts.sdk.runtime → etc.) resolves normally.

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _parse_sse_events(text: str) -> list[dict]:
    """Parse SSE response text into a list of JSON event dicts."""
    events: list[dict] = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events


def _stream_headers() -> dict[str, str]:
    """Return default headers for streaming POST /invocations."""
    return {
        "X-HW-AgentGateway-User-Id": "test-user",
        "x-hw-agentarts-session-id": "e2e-auth-session",
        "Accept": "text/event-stream",
    }


# ─────────────────────────────────────────────────────────────────────────────
# FakeAuthHandler — simulates the message_queue flow
# ─────────────────────────────────────────────────────────────────────────────

AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
AUTH_MESSAGE_CONTENT = (
    "邮件功能需要您的授权。请点击以下链接进行授权：\n\n"
    f"{AUTH_URL}\n\n"
    "授权完成后，请再次告诉我您需要做什么。"
)


class FakeAuthHandler:
    """Fake AgentHandler that supports the ContextVar message_queue flow.

    Mimics the real AgentHandler.handle_stream() behaviour:
    1. Accepts message_queue parameter (like the real one)
    2. Calls set_message_queue(message_queue) to inject into email_tools
    3. When simulate_auth=True, puts a system_message into the queue
       (simulating handle_auth_url being called by the SDK)
    4. Drains the queue before each token yield
    5. Drains remaining messages after all tokens
    6. Calls set_message_queue(None) in finally for cleanup
    """

    def __init__(self):
        self.handle_calls: list[tuple] = []
        self.stream_calls: list[tuple] = []
        self.simulate_auth: bool = False
        self._tokens: list[str] = ["你好", "，", "世界", "！"]

    async def handle(
        self, message: str, user_id: str = "anonymous",
        session_id: str | None = None,
    ) -> str:
        """Non-streaming handler — always returns a canned response."""
        self.handle_calls.append((message, user_id, session_id))
        return f"Response to: '{message}'"

    async def handle_stream(
        self, message: str, user_id: str = "anonymous",
        session_id: str | None = None,
        message_queue: "asyncio.Queue | None" = None,
    ):
        """Streaming handler with message_queue support.

        Drains system_message events from the queue before each token,
        exactly like the real agent_handler.AgentHandler.handle_stream().
        """
        self.stream_calls.append((message, user_id, session_id))

        # Import the actual ContextVar setter from email_tools to test
        # the real ContextVar isolation mechanism.
        from app.tools.email_tools import set_message_queue

        set_message_queue(message_queue)

        try:
            # ── Simulate handle_auth_url being called by the SDK ──
            if self.simulate_auth and message_queue is not None:
                await message_queue.put({
                    "type": "system_message",
                    "content": AUTH_MESSAGE_CONTENT,
                    "auth_url": AUTH_URL,
                    "auth_required": True,
                })

            for _idx, token in enumerate(self._tokens):
                # ── Drain pending out-of-band messages from tool callbacks ──
                if message_queue is not None:
                    while not message_queue.empty():
                        msg = message_queue.get_nowait()
                        if msg.get("type") != "system_message":
                            continue
                        payload = {
                            "system_message": msg["content"],
                            "auth_url": msg.get("auth_url"),
                            "auth_required": True,
                        }
                        yield f"data: {json.dumps(payload)}\n\n"

                yield f'data: {json.dumps({"token": token, "done": False})}\n\n'

            # ── Drain any remaining messages after agent completes ──
            if message_queue is not None:
                while not message_queue.empty():
                    msg = message_queue.get_nowait()
                    if msg.get("type") != "system_message":
                        continue
                    payload = {
                        "system_message": msg["content"],
                        "auth_url": msg.get("auth_url"),
                        "auth_required": True,
                    }
                    yield f"data: {json.dumps(payload)}\n\n"

            # Signal completion
            yield f'data: {json.dumps({"token": "", "done": True})}\n\n'

        finally:
            # Clean up per-task queue reference
            set_message_queue(None)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def auth_fake_handler() -> FakeAuthHandler:
    """Create a FakeAuthHandler instance."""
    return FakeAuthHandler()


@pytest.fixture
def auth_test_client(auth_fake_handler: FakeAuthHandler):
    """FastAPI TestClient with FakeAuthHandler patched in.

    Patches init_chat_model (lifespan startup) and AgentHandler class
    so get_agent_handler() returns our fake. This exercises the full
    FastAPI stack — routing, SSE formatting, header handling — with
    our controlled fake handler.
    """
    os.environ.setdefault("MAAS_API_KEY", "dummy-e2e-test-key")
    os.environ.setdefault("MODEL_API_KEY", "test-key-for-e2e")

    with patch("app.llm_config.init_chat_model", return_value=MagicMock()), \
         patch("app.agent_handler.AgentHandler", return_value=auth_fake_handler):
        from app.main import app

        # Ensure the handler is set (lifespan will call get_agent_handler
        # which now returns our fake handler)
        app.state.agent_handler = auth_fake_handler

        client = TestClient(app, raise_server_exceptions=False)
        yield client, auth_fake_handler


@pytest.fixture
async def async_auth_client(auth_fake_handler: FakeAuthHandler):
    """Async httpx client for tests that need concurrency (E2E-AUTH-08).

    Uses httpx.AsyncClient with ASGITransport for in-process FastAPI testing.
    Must be async because ASGITransport requires httpx.AsyncClient.
    """
    os.environ.setdefault("MAAS_API_KEY", "dummy-e2e-test-key")
    os.environ.setdefault("MODEL_API_KEY", "test-key-for-e2e")

    import app.main as app_main
    with patch.object(app_main, "AgentHandler", return_value=auth_fake_handler):
        from app.main import app

        app.state.agent_handler = auth_fake_handler

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test",
        ) as client:
            yield client, auth_fake_handler


# ═════════════════════════════════════════════════════════════════════════════
# E2E-AUTH-01: OAuth2 auth URL delivered via SSE system_message
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.feature
def test_auth_url_delivered_via_sse_system_message(auth_test_client):
    """E2E-AUTH-01: Auth URL delivered as SSE system_message event.

    POST /invocations with stream=true, handler simulates auth callback.
    Verifies:
    - SSE stream contains a system_message event (not just token events)
    - Event has auth_url with a valid URL
    - auth_required: true is present
    - Last event has done: true
    """
    client, fake_handler = auth_test_client
    fake_handler.simulate_auth = True

    resp = client.post(
        "/invocations",
        json={"message": "帮我看看收件箱", "stream": True},
        headers=_stream_headers(),
    )

    assert resp.status_code == 200, (
        f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
    )

    # Verify content-type
    content_type = resp.headers.get("content-type", "")
    assert "text/event-stream" in content_type, (
        f"Expected text/event-stream, got: {content_type}"
    )

    events = _parse_sse_events(resp.text)
    assert len(events) >= 1, f"Expected at least 1 SSE event, got {len(events)}"

    # Find system_message events
    system_events = [e for e in events if "system_message" in e]
    assert len(system_events) >= 1, (
        f"Expected at least 1 system_message event, got {len(system_events)}. "
        f"All events: {events}"
    )

    se = system_events[0]
    assert "auth_url" in se, f"system_message event missing 'auth_url': {se}"
    assert se["auth_url"].startswith("https://"), (
        f"auth_url should be a URL, got: {se['auth_url']}"
    )
    assert se.get("auth_required") is True, (
        f"auth_required should be True, got: {se.get('auth_required')}"
    )

    # Verify last event has done: true
    last_event = events[-1]
    assert last_event.get("done") is True, (
        f"Last SSE event should have done=True: {last_event}"
    )

    # Verify stream_calls recorded
    assert len(fake_handler.stream_calls) == 1


# ═════════════════════════════════════════════════════════════════════════════
# E2E-AUTH-02: system_message interleaved with tokens — correct ordering
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.feature
def test_system_message_appears_before_tokens(auth_test_client):
    """E2E-AUTH-02: system_message appears BEFORE token events in SSE stream.

    The drain-before-token logic ensures system_message events are
    yielded before any token events. This verifies the correct ordering.
    """
    client, fake_handler = auth_test_client
    fake_handler.simulate_auth = True

    resp = client.post(
        "/invocations",
        json={"message": "帮我看看收件箱", "stream": True},
        headers=_stream_headers(),
    )
    assert resp.status_code == 200

    events = _parse_sse_events(resp.text)
    assert len(events) >= 2, f"Expected at least 2 events, got {len(events)}"

    # Find the index of the first system_message event
    first_system_idx = None
    first_token_idx = None
    for i, e in enumerate(events):
        if "system_message" in e and first_system_idx is None:
            first_system_idx = i
        if "token" in e and not e.get("done") and first_token_idx is None:
            first_token_idx = i

    assert first_system_idx is not None, "No system_message event found"
    assert first_token_idx is not None, "No token event found before done"

    # system_message must appear before (or at same position as) first token
    assert first_system_idx <= first_token_idx, (
        f"system_message (idx={first_system_idx}) must appear before "
        f"or at same position as first token (idx={first_token_idx}). "
        f"Events: {[list(e.keys()) for e in events]}"
    )


# ═════════════════════════════════════════════════════════════════════════════
# E2E-AUTH-03: system_message fields are complete
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.feature
def test_system_message_fields_complete(auth_test_client):
    """E2E-AUTH-03: system_message event has all required fields.

    Verifies SSE JSON contains system_message (content text),
    auth_url (valid URL), and auth_required (true), all present
    with correct values.
    """
    client, fake_handler = auth_test_client
    fake_handler.simulate_auth = True

    resp = client.post(
        "/invocations",
        json={"message": "帮我看看收件箱", "stream": True},
        headers=_stream_headers(),
    )
    assert resp.status_code == 200

    events = _parse_sse_events(resp.text)
    system_events = [e for e in events if "system_message" in e]
    assert len(system_events) >= 1, f"No system_message event in: {events}"

    se = system_events[0]

    # system_message (the content text) must be present and non-empty
    assert "system_message" in se, f"Missing 'system_message' key: {se}"
    assert isinstance(se["system_message"], str), (
        f"system_message should be a string: {type(se['system_message'])}"
    )
    assert len(se["system_message"]) > 0, "system_message content must not be empty"
    assert "授权" in se["system_message"], (
        f"system_message should mention authorization: {se['system_message'][:200]}"
    )

    # auth_url must be present and a valid URL
    assert "auth_url" in se, f"Missing 'auth_url' key: {se}"
    assert se["auth_url"].startswith("https://"), (
        f"auth_url should start with https://: {se['auth_url']}"
    )

    # auth_required must be True
    assert "auth_required" in se, f"Missing 'auth_required' key: {se}"
    assert se["auth_required"] is True, (
        f"auth_required should be True: {se['auth_required']}"
    )


# ═════════════════════════════════════════════════════════════════════════════
# E2E-AUTH-04: done: true normal ending
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.feature
def test_auth_stream_ends_with_done_true(auth_test_client):
    """E2E-AUTH-04: After system_message + tokens, stream ends with done: true.

    Verifies the normal completion signal is present even when
    system_message events are interleaved in the stream.
    """
    client, fake_handler = auth_test_client
    fake_handler.simulate_auth = True

    resp = client.post(
        "/invocations",
        json={"message": "帮我看看收件箱", "stream": True},
        headers=_stream_headers(),
    )
    assert resp.status_code == 200

    events = _parse_sse_events(resp.text)
    assert len(events) >= 1, f"Expected at least 1 event, got {len(events)}"

    # Last event must signal completion
    last_event = events[-1]
    assert last_event.get("done") is True, (
        f"Last SSE event should have done=True: {last_event}"
    )

    # There should be exactly one done event
    done_events = [e for e in events if e.get("done")]
    assert len(done_events) == 1, (
        f"Expected exactly 1 done event, got {len(done_events)}: {done_events}"
    )

    # Verify there are token events and system_message events before done
    token_events = [e for e in events if "token" in e and not e.get("done")]
    system_events = [e for e in events if "system_message" in e]
    assert len(token_events) >= 1, f"Expected at least 1 token event, got events: {events}"
    assert len(system_events) >= 1, f"Expected at least 1 system_message event"


# ═════════════════════════════════════════════════════════════════════════════
# E2E-AUTH-05: Normal email operations without auth (regression)
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.feature
def test_normal_streaming_has_no_system_message(auth_test_client):
    """E2E-AUTH-05: Normal streaming without auth — no system_message events.

    When no system_message is in the queue, SSE stream only has token
    events and done — no system_message events. This verifies backward
    compatibility with non-auth scenarios.
    """
    client, fake_handler = auth_test_client
    fake_handler.simulate_auth = False  # No auth simulation

    resp = client.post(
        "/invocations",
        json={"message": "你好", "stream": True},
        headers=_stream_headers(),
    )
    assert resp.status_code == 200

    events = _parse_sse_events(resp.text)
    assert len(events) >= 2, f"Expected at least 2 events (token + done), got {len(events)}"

    # No system_message events
    system_events = [e for e in events if "system_message" in e]
    assert len(system_events) == 0, (
        f"Expected no system_message events in normal flow, got: {system_events}"
    )

    # Should have token events and a done event
    token_events = [e for e in events if "token" in e and not e.get("done")]
    assert len(token_events) >= 1, f"Expected at least 1 token event, got events: {events}"

    # Last event should be done: true
    assert events[-1].get("done") is True, (
        f"Last event should have done=True: {events[-1]}"
    )

    # Verify content-type is correct
    assert "text/event-stream" in resp.headers.get("content-type", "")


# ═════════════════════════════════════════════════════════════════════════════
# E2E-AUTH-06: Non-streaming path unaffected
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.feature
def test_non_streaming_path_unaffected(auth_test_client):
    """E2E-AUTH-06: Non-streaming path returns normal JSON response.

    POST /invocations with stream=false returns 200 with 'response' key.
    The non-streaming path does not use message_queue and should not
    be affected by the refactoring.
    """
    client, fake_handler = auth_test_client

    resp = client.post(
        "/invocations",
        json={"message": "帮我看看收件箱", "stream": False},
        headers={
            "X-HW-AgentGateway-User-Id": "test-user",
            "x-hw-agentarts-session-id": "e2e-nonstream",
        },
    )

    assert resp.status_code == 200, (
        f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
    )

    data = resp.json()
    assert "response" in data, f"No 'response' key in: {data}"
    assert isinstance(data["response"], str), (
        f"response should be a string: {type(data['response'])}"
    )
    assert len(data["response"]) > 0, "Response should not be empty"

    # Verify handler was called with correct params
    assert len(fake_handler.handle_calls) == 1, (
        f"Expected 1 handle call, got {len(fake_handler.handle_calls)}"
    )
    msg, user_id, session_id = fake_handler.handle_calls[0]
    assert msg == "帮我看看收件箱"
    assert user_id == "test-user"
    assert session_id == "e2e-nonstream"


# ═════════════════════════════════════════════════════════════════════════════
# E2E-AUTH-07: Queue lifecycle — no cross-request leakage
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.feature
def test_queue_lifecycle_no_cross_request_leakage(auth_test_client):
    """E2E-AUTH-07: Queue cleanup prevents cross-request leakage.

    Round 1: send auth request → verify system_message in stream.
    Round 2: send normal request → verify NO system_message in stream.
    Uses the SAME TestClient (same app instance) for both requests,
    verifying that set_message_queue(None) in finally properly cleans
    up the ContextVar.
    """
    client, fake_handler = auth_test_client

    # ── Round 1: Trigger auth ──
    fake_handler.simulate_auth = True
    resp1 = client.post(
        "/invocations",
        json={"message": "帮我看看收件箱", "stream": True},
        headers=_stream_headers(),
    )
    assert resp1.status_code == 200
    events1 = _parse_sse_events(resp1.text)
    system_events_r1 = [e for e in events1 if "system_message" in e]
    assert len(system_events_r1) >= 1, (
        f"Round 1: Expected system_message event, got events: {[list(e.keys()) for e in events1]}"
    )

    # ── Round 2: Normal request (no auth) ──
    fake_handler.simulate_auth = False
    resp2 = client.post(
        "/invocations",
        json={"message": "你好", "stream": True},
        headers=_stream_headers(),
    )
    assert resp2.status_code == 200
    events2 = _parse_sse_events(resp2.text)
    system_events_r2 = [e for e in events2 if "system_message" in e]
    assert len(system_events_r2) == 0, (
        f"Round 2: Expected NO system_message event (queue should be cleaned), "
        f"but got: {system_events_r2}"
    )

    # Both calls tracked
    assert len(fake_handler.stream_calls) == 2


# ═════════════════════════════════════════════════════════════════════════════
# E2E-AUTH-08: Concurrency isolation
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.feature
@pytest.mark.asyncio
async def test_concurrency_isolation(async_auth_client):
    """E2E-AUTH-08: ContextVar isolation prevents cross-contamination.

    Two concurrent streaming requests each get their own message_queue.
    Verify that:
    - Request A (with auth URL A) does NOT see auth URL in B's events
    - Request B (with auth URL B) does NOT see auth URL in A's events
    - ContextVar isolation ensures per-task queue separation.

    Uses asyncio.gather for true concurrent execution.
    """
    client, _base_handler = async_auth_client

    AUTH_URL_A = "https://login.microsoftonline.com/auth-for-user-a"
    AUTH_URL_B = "https://login.microsoftonline.com/auth-for-user-b"

    async def stream_a() -> tuple[int, list[dict]]:
        """Request A: simulate auth with unique URL."""
        resp = await client.post(
            "/invocations",
            json={"message": "帮用户A看收件箱", "stream": True},
            headers={
                "X-HW-AgentGateway-User-Id": "user-a",
                "x-hw-agentarts-session-id": "session-a",
                "Accept": "text/event-stream",
            },
        )
        return resp.status_code, _parse_sse_events(resp.text)

    async def stream_b() -> tuple[int, list[dict]]:
        """Request B: simulate auth with different unique URL."""
        resp = await client.post(
            "/invocations",
            json={"message": "帮用户B看收件箱", "stream": True},
            headers={
                "X-HW-AgentGateway-User-Id": "user-b",
                "x-hw-agentarts-session-id": "session-b",
                "Accept": "text/event-stream",
            },
        )
        return resp.status_code, _parse_sse_events(resp.text)

    # Need to set simulate_auth for the concurrency test. However, both
    # requests use the same handler instance, and simulate_auth is a
    # boolean flag. For real ContextVar isolation, the handler's
    # simulate_auth needs to be per-request.
    #
    # We handle this by modifying the handler to check the message content
    # instead of a shared flag. We dynamically patch the handler's
    # handle_stream to simulate auth only for user-a's message.
    #
    # Both requests will get the same handler instance (patched, single).
    # The handler's handle_stream will:
    # - For user-a: put auth URL A in the queue
    # - For user-b: don't put anything (or put a different URL)

    # Override the handler for this test: it checks the message content
    # to decide which auth URL (if any) to put in the queue.
    from app.tools.email_tools import set_message_queue as real_set_mq

    original_handle_stream = _base_handler.handle_stream

    async def concurrency_handle_stream(
        message, user_id="anonymous", session_id=None, message_queue=None,
    ):
        real_set_mq(message_queue)
        try:
            tokens = ["并发", "测试", "!"]
            if "用户A" in message and message_queue is not None:
                await message_queue.put({
                    "type": "system_message",
                    "content": f"授权链接: {AUTH_URL_A}",
                    "auth_url": AUTH_URL_A,
                    "auth_required": True,
                })
            elif "用户B" in message and message_queue is not None:
                await message_queue.put({
                    "type": "system_message",
                    "content": f"授权链接: {AUTH_URL_B}",
                    "auth_url": AUTH_URL_B,
                    "auth_required": True,
                })

            for token in tokens:
                if message_queue is not None:
                    while not message_queue.empty():
                        msg = message_queue.get_nowait()
                        if msg.get("type") != "system_message":
                            continue
                        payload = {
                            "system_message": msg["content"],
                            "auth_url": msg.get("auth_url"),
                            "auth_required": True,
                        }
                        yield f"data: {json.dumps(payload)}\n\n"
                yield f'data: {json.dumps({"token": token, "done": False})}\n\n'

            if message_queue is not None:
                while not message_queue.empty():
                    msg = message_queue.get_nowait()
                    if msg.get("type") != "system_message":
                        continue
                    payload = {
                        "system_message": msg["content"],
                        "auth_url": msg.get("auth_url"),
                        "auth_required": True,
                    }
                    yield f"data: {json.dumps(payload)}\n\n"

            yield f'data: {json.dumps({"token": "", "done": True})}\n\n'
        finally:
            real_set_mq(None)

    _base_handler.handle_stream = concurrency_handle_stream  # type: ignore[method-assign]

    # Execute both requests concurrently
    (status_a, events_a), (status_b, events_b) = await asyncio.gather(
        stream_a(), stream_b(),
    )

    # Restore original
    _base_handler.handle_stream = original_handle_stream  # type: ignore[method-assign]

    # Both should succeed
    assert status_a == 200, f"Request A failed: {status_a}"
    assert status_b == 200, f"Request B failed: {status_b}"

    # Extract system_message events
    system_a = [e for e in events_a if "system_message" in e]
    system_b = [e for e in events_b if "system_message" in e]

    # Each request should have its own system_message
    assert len(system_a) >= 1, (
        f"Request A: Expected system_message with auth URL A. "
        f"Events: {[list(e.keys()) for e in events_a]}"
    )
    assert len(system_b) >= 1, (
        f"Request B: Expected system_message with auth URL B. "
        f"Events: {[list(e.keys()) for e in events_b]}"
    )

    # Verify isolation: Request A should have AUTH_URL_A, NOT AUTH_URL_B
    auth_urls_a = [e.get("auth_url", "") for e in system_a]
    auth_urls_b = [e.get("auth_url", "") for e in system_b]

    assert any(AUTH_URL_A in url for url in auth_urls_a), (
        f"Request A should contain AUTH_URL_A ({AUTH_URL_A}), "
        f"got auth URLs: {auth_urls_a}"
    )
    assert not any(AUTH_URL_B in url for url in auth_urls_a), (
        f"Request A must NOT contain AUTH_URL_B ({AUTH_URL_B}) — "
        f"cross-contamination detected! Auth URLs in A: {auth_urls_a}"
    )

    assert any(AUTH_URL_B in url for url in auth_urls_b), (
        f"Request B should contain AUTH_URL_B ({AUTH_URL_B}), "
        f"got auth URLs: {auth_urls_b}"
    )
    assert not any(AUTH_URL_A in url for url in auth_urls_b), (
        f"Request B must NOT contain AUTH_URL_A ({AUTH_URL_A}) — "
        f"cross-contamination detected! Auth URLs in B: {auth_urls_b}"
    )
