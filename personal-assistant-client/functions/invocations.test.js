import { afterEach, describe, expect, it, vi } from "vitest";

import { onRequestPost as onRequestPostRoot } from "./invocations.js";
import { onRequestPost as onRequestPostNested } from "./invocations/[[path]].js";

describe("Cloudflare Pages invocations proxy", () => {
  const originalFetch = globalThis.fetch;
  const env = {
    AGENTARTS_INVOCATIONS_URL:
      "https://runtime.example.com/runtimes/personal-assistant/invocations",
  };

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("forwards the request to the full AgentArts Runtime path", async () => {
    const upstreamBody = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode("data: token\n\n"));
        controller.close();
      },
    });
    const mockFetch = vi.fn().mockResolvedValue(
      new Response(upstreamBody, {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      }),
    );
    globalThis.fetch = mockFetch;

    const request = new Request(
      "https://agentarts-personal-assistant.pages.dev/invocations",
      {
        method: "POST",
        headers: {
          Authorization: "Bearer test-jwt",
          Cookie: "should-not-be-forwarded=true",
          "Content-Type": "application/json",
          "x-hw-agentarts-session-id": "test-session",
        },
        body: JSON.stringify({ message: "hello", stream: true }),
      },
    );

    const response = await onRequestPostRoot({ request, env });
    const forwardedRequest = mockFetch.mock.calls[0][0];

    expect(forwardedRequest.url).toBe(
      env.AGENTARTS_INVOCATIONS_URL,
    );
    expect(forwardedRequest.headers.get("Authorization")).toBe(
      "Bearer test-jwt",
    );
    expect(forwardedRequest.headers.get("x-hw-agentarts-session-id")).toBe(
      "test-session",
    );
    expect(forwardedRequest.headers.get("Cookie")).toBeNull();
    expect(await forwardedRequest.json()).toEqual({
      message: "hello",
      stream: true,
    });
    expect(response.headers.get("Content-Type")).toContain("text/event-stream");
    expect(response.headers.get("Cache-Control")).toBe("no-store");
    expect(await response.text()).toBe("data: token\n\n");
  });

  it("returns 502 when the Gateway request fails", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error("network error"));

    const request = new Request(
      "https://agentarts-personal-assistant.pages.dev/invocations",
      {
        method: "POST",
        body: "{}",
      },
    );

    const response = await onRequestPostRoot({ request, env });

    expect(response.status).toBe(502);
    expect(await response.json()).toEqual({
      message: "AgentArts Gateway is unavailable",
    });
  });

  it("fails clearly when the upstream URL is not configured", async () => {
    const request = new Request(
      "https://agentarts-personal-assistant.pages.dev/invocations",
      {
        method: "POST",
        body: "{}",
      },
    );

    const response = await onRequestPostRoot({ request, env: {} });

    expect(response.status).toBe(500);
    expect(await response.json()).toEqual({
      message: "Frontend proxy is not configured",
    });
  });

  it("forwards nested invocations paths to matching runtime subpaths", async () => {
    const upstreamBody = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode("ok"));
        controller.close();
      },
    });
    const mockFetch = vi.fn().mockResolvedValue(
      new Response(upstreamBody, {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    globalThis.fetch = mockFetch;

    const request = new Request(
      "https://agentarts-personal-assistant.pages.dev/invocations/auth/oauth2/complete",
      {
        method: "POST",
        headers: {
          Authorization: "Bearer test-jwt",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          provider: "m365-calendar-provider",
          session_uri: "urn:uuid:test",
        }),
      },
    );

    const response = await onRequestPostNested({ request, env });
    const forwardedRequest = mockFetch.mock.calls[0][0];

    expect(forwardedRequest.url).toBe(
      "https://runtime.example.com/runtimes/personal-assistant/invocations/auth/oauth2/complete",
    );
    expect(forwardedRequest.headers.get("Authorization")).toBe(
      "Bearer test-jwt",
    );
    expect(await forwardedRequest.json()).toEqual({
      provider: "m365-calendar-provider",
      session_uri: "urn:uuid:test",
    });
    expect(response.status).toBe(200);
    expect(await response.text()).toBe("ok");
  });
});
