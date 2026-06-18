import { afterEach, describe, expect, it, vi } from "vitest";

import { onRequestPost } from "./invocations.js";

describe("Cloudflare Pages invocations proxy", () => {
  const originalFetch = globalThis.fetch;

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
      "https://agentarts-personal-assistant.pages.dev/api/invocations",
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

    const response = await onRequestPost({ request });
    const forwardedRequest = mockFetch.mock.calls[0][0];

    expect(forwardedRequest.url).toBe(
      "https://defaultgw-ha3wenzqga.cn-southwest-2.huaweicloud-agentarts.com/runtimes/personal-assistant/invocations",
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
      "https://agentarts-personal-assistant.pages.dev/api/invocations",
      {
        method: "POST",
        body: "{}",
      },
    );

    const response = await onRequestPost({ request });

    expect(response.status).toBe(502);
    expect(await response.json()).toEqual({
      message: "AgentArts Gateway is unavailable",
    });
  });
});
