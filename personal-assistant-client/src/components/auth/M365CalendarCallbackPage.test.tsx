import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import M365CalendarCallbackPage from "./M365CalendarCallbackPage";

class MockBroadcastChannel {
  static channels = new Map<string, Set<MockBroadcastChannel>>();

  name: string;
  onmessage: ((event: MessageEvent) => void) | null = null;
  private closed = false;

  constructor(name: string) {
    this.name = name;
    const channels = MockBroadcastChannel.channels.get(name) ?? new Set();
    channels.add(this);
    MockBroadcastChannel.channels.set(name, channels);
  }

  postMessage(data: unknown) {
    const channels = MockBroadcastChannel.channels.get(this.name);
    if (!channels) return;

    for (const channel of channels) {
      if (channel === this || channel.closed) continue;
      channel.onmessage?.({ data } as MessageEvent);
    }
  }

  close() {
    this.closed = true;
    MockBroadcastChannel.channels.get(this.name)?.delete(this);
  }

  static reset() {
    MockBroadcastChannel.channels.clear();
  }
}

describe("M365CalendarCallbackPage", () => {
  const originalClose = window.close;
  const originalBroadcastChannel = globalThis.BroadcastChannel;

  beforeEach(() => {
    globalThis.BroadcastChannel =
      MockBroadcastChannel as unknown as typeof BroadcastChannel;
    window.close = vi.fn();
    window.history.pushState({}, "", "/");
  });

  afterEach(() => {
    window.close = originalClose;
    MockBroadcastChannel.reset();
    globalThis.BroadcastChannel = originalBroadcastChannel;
    window.history.pushState({}, "", "/");
    vi.restoreAllMocks();
  });

  it("shows a success state after the main window completes OAuth", async () => {
    const requests: unknown[] = [];
    const mainWindowChannel = new BroadcastChannel("m365-calendar-auth");
    mainWindowChannel.onmessage = (event) => {
      requests.push(event.data);
      if (
        event.data &&
        typeof event.data === "object" &&
        "requestId" in event.data
      ) {
        mainWindowChannel.postMessage({
          type: "m365-calendar-auth",
          requestId: (event.data as { requestId: string }).requestId,
          provider: "m365-calendar-provider",
          status: "complete",
          message: "日历授权已完成，可以关闭此窗口并重试刚才的问题。",
        });
      }
    };

    window.history.pushState(
      {},
      "",
      "/auth/callback/m365-calendar?session_uri=urn:session:test&state=signed-state",
    );

    render(<M365CalendarCallbackPage />);

    await waitFor(() => {
      expect(screen.getByText("授权完成")).toBeInTheDocument();
    });
    expect(
      screen.getByText("日历授权已完成，可以关闭此窗口并重试刚才的问题。"),
    ).toBeInTheDocument();
    expect(requests).toContainEqual({
      type: "m365-calendar-auth-request",
      requestId: "signed-state",
      provider: "m365-calendar-provider",
      session_uri: "urn:session:test",
      state: "signed-state",
    });
  });

  it("shows a failed state when the callback is missing params", async () => {
    window.history.pushState({}, "", "/auth/callback/m365-calendar");

    render(<M365CalendarCallbackPage />);

    await waitFor(() => {
      expect(screen.getByText("授权失败")).toBeInTheDocument();
    });
    expect(
      screen.getByText("授权回调缺少必要参数，请重新发起日历授权。"),
    ).toBeInTheDocument();
  });

  it("shows a failed state when the OAuth provider returns an error", async () => {
    window.history.pushState(
      {},
      "",
      "/auth/callback/m365-calendar?error=access_denied&error_description=用户取消授权",
    );

    render(<M365CalendarCallbackPage />);

    await waitFor(() => {
      expect(screen.getByText("授权失败")).toBeInTheDocument();
    });
    expect(screen.getByText("用户取消授权")).toBeInTheDocument();
  });
});
