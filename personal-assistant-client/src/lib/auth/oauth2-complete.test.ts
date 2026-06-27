import { afterEach, describe, expect, it, vi } from "vitest";

const { mockGetRequestToken, mockBuildHeaders } = vi.hoisted(() => ({
  mockGetRequestToken: vi.fn(),
  mockBuildHeaders: vi.fn(),
}));

vi.mock("@/lib/chat/chat-api-client", () => ({
  getRequestToken: mockGetRequestToken,
  buildHeaders: mockBuildHeaders,
}));

import { completeOAuth2Auth } from "@/lib/auth/oauth2-complete";

describe("completeOAuth2Auth", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.clearAllMocks();
  });

  it("uses response detail when complete fails", async () => {
    mockGetRequestToken.mockResolvedValue("id-token");
    mockBuildHeaders.mockReturnValue({ Authorization: "Bearer id-token" });
    globalThis.fetch = vi.fn().mockResolvedValue(
      Response.json({ detail: "Calendar authorization failed." }, { status: 502 }),
    );

    await expect(
      completeOAuth2Auth({
        provider: "m365-calendar-provider",
        session_uri: "urn:uuid:test",
        state: "state",
      }),
    ).rejects.toThrow("Calendar authorization failed.");
  });

  it("uses response message when detail is unavailable", async () => {
    mockGetRequestToken.mockResolvedValue("id-token");
    mockBuildHeaders.mockReturnValue({ Authorization: "Bearer id-token" });
    globalThis.fetch = vi.fn().mockResolvedValue(
      Response.json({ message: "AgentArts Gateway is unavailable" }, { status: 502 }),
    );

    await expect(
      completeOAuth2Auth({
        provider: "m365-calendar-provider",
        session_uri: "urn:uuid:test",
        state: "state",
      }),
    ).rejects.toThrow("AgentArts Gateway is unavailable");
  });
});
