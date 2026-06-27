import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { mockComplete } = vi.hoisted(() => ({
  mockComplete: vi.fn(),
}));

vi.mock("@/lib/auth/oauth2-complete", () => ({
  completeOAuth2Auth: mockComplete,
}));

import M365CalendarCallbackPage from "./M365CalendarCallbackPage";

describe("M365CalendarCallbackPage", () => {
  const originalOpener = window.opener;
  const originalClose = window.close;

  beforeEach(() => {
    mockComplete.mockReset();
    window.opener = {
      postMessage: vi.fn(),
    } as unknown as Window;
    window.close = vi.fn();
  });

  afterEach(() => {
    window.opener = originalOpener;
    window.close = originalClose;
    vi.restoreAllMocks();
  });

  it("shows a success state after completing OAuth", async () => {
    mockComplete.mockResolvedValue({
      status: "complete",
      provider: "m365-calendar-provider",
      message: "日历授权已完成，可以关闭此窗口并重试刚才的问题。",
    });
    window.history.pushState(
      {},
      "",
      "/auth/callback/m365-calendar?session_uri=urn:session:test&state=signed-state",
    );

    render(<M365CalendarCallbackPage />);

    await waitFor(() => {
      expect(screen.getByText("授权完成")).toBeInTheDocument();
    });
    expect(screen.getByText("日历授权已完成，可以关闭此窗口并重试刚才的问题。")).toBeInTheDocument();
    expect(mockComplete).toHaveBeenCalledWith({
      provider: "m365-calendar-provider",
      session_uri: "urn:session:test",
      state: "signed-state",
    });
    expect(window.opener.postMessage).toHaveBeenCalledWith(
      {
        type: "m365-calendar-auth",
        status: "complete",
        provider: "m365-calendar-provider",
        message: "日历授权已完成，可以关闭此窗口并重试刚才的问题。",
      },
      window.location.origin,
    );
  });

  it("shows a failed state when the callback is missing params", async () => {
    window.history.pushState({}, "", "/auth/callback/m365-calendar");

    render(<M365CalendarCallbackPage />);

    await waitFor(() => {
      expect(screen.getByText("授权失败")).toBeInTheDocument();
    });
    expect(mockComplete).not.toHaveBeenCalled();
  });
});
