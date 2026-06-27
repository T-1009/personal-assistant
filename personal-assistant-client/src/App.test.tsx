import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { InteractionStatus } from "@azure/msal-browser";
import { useAuthStore } from "@/stores/auth-store";
import { useAuthCardStore } from "@/stores/auth-card-store";

const { mockCompleteOAuth2Auth } = vi.hoisted(() => ({
  mockCompleteOAuth2Auth: vi.fn(),
}));

// Mock lazy-loaded chunks with simple test markers
vi.mock("./components/chat/ChatPage", () => ({
  default: () => <div data-testid="chat-page">ChatPage</div>,
}));

vi.mock("./components/landing/LandingPage", () => ({
  default: () => <div data-testid="landing-page">LandingPage</div>,
}));

// Mock @azure/msal-react hooks
const mockUseIsAuthenticated = vi.fn();
const mockUseMsal = vi.fn();

vi.mock("@azure/msal-react", () => ({
  useIsAuthenticated: () => mockUseIsAuthenticated(),
  useMsal: () => mockUseMsal(),
}));

vi.mock("@/lib/auth/oauth2-complete", () => ({
  completeOAuth2Auth: mockCompleteOAuth2Auth,
}));

import App from "./App";

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

function setupAuth(isAuthenticated: boolean, hydrated: boolean) {
  mockUseIsAuthenticated.mockReturnValue(isAuthenticated);
  mockUseMsal.mockReturnValue({ inProgress: InteractionStatus.None });
  const store = useAuthStore.getState();
  store.setHydrated(hydrated);
  store.setIdToken(isAuthenticated ? "id-token" : null);
}

describe("App", () => {
  const originalBroadcastChannel = globalThis.BroadcastChannel;

  beforeEach(() => {
    globalThis.BroadcastChannel =
      MockBroadcastChannel as unknown as typeof BroadcastChannel;
    mockCompleteOAuth2Auth.mockReset();
    window.history.pushState({}, "", "/");
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    MockBroadcastChannel.reset();
    globalThis.BroadcastChannel = originalBroadcastChannel;
    useAuthStore.getState().setHydrated(false);
    useAuthStore.getState().clearToken();
    useAuthCardStore.getState().clearAuth();
    window.history.pushState({}, "", "/");
  });

  it("renders without crashing", () => {
    mockUseIsAuthenticated.mockReturnValue(false);
    mockUseMsal.mockReturnValue({ inProgress: InteractionStatus.None });
    expect(() => render(<App />)).not.toThrow();
  });

  it("shows LoadingState when auth store is not hydrated", () => {
    mockUseIsAuthenticated.mockReturnValue(false);
    mockUseMsal.mockReturnValue({ inProgress: InteractionStatus.None });
    useAuthStore.getState().setHydrated(false);
    render(<App />);
    expect(screen.queryByTestId("landing-page")).not.toBeInTheDocument();
    expect(screen.queryByTestId("chat-page")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("routes calendar callback pathname to the callback page", async () => {
    setupAuth(false, true);
    window.history.pushState({}, "", "/auth/callback/m365-calendar");
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText("授权失败")).toBeInTheDocument();
    });
  });

  it("shows LandingPage when hydrated and not authenticated", async () => {
    setupAuth(false, true);
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId("landing-page")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("chat-page")).not.toBeInTheDocument();
  });

  it("shows ChatPage when hydrated and authenticated", async () => {
    setupAuth(true, true);
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId("chat-page")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("landing-page")).not.toBeInTheDocument();
  });

  it("completes calendar OAuth requests from the authenticated main window", async () => {
    setupAuth(true, true);
    useAuthCardStore.getState().setAuth(
      "auth-message-1",
      "m365-calendar-provider",
      "https://login.example.com",
      "请完成日历授权",
    );
    mockCompleteOAuth2Auth.mockResolvedValue({
      status: "complete",
      provider: "m365-calendar-provider",
      message: "日历授权已完成，可以关闭此窗口并重试刚才的问题。",
    });

    render(<App />);

    const popupChannel = new BroadcastChannel("m365-calendar-auth");
    const responses: unknown[] = [];
    popupChannel.onmessage = (event) => {
      responses.push(event.data);
    };

    popupChannel.postMessage({
      type: "m365-calendar-auth-request",
      requestId: "request-1",
      provider: "m365-calendar-provider",
      session_uri: "urn:ietf:params:oauth:request_uri:test",
      state: "signed-state",
    });

    await waitFor(() => {
      expect(mockCompleteOAuth2Auth).toHaveBeenCalledWith({
        provider: "m365-calendar-provider",
        session_uri: "urn:ietf:params:oauth:request_uri:test",
        state: "signed-state",
      });
    });

    await waitFor(() => {
      expect(responses).toContainEqual({
        type: "m365-calendar-auth",
        requestId: "request-1",
        provider: "m365-calendar-provider",
        status: "complete",
        message: "日历授权已完成，可以关闭此窗口并重试刚才的问题。",
      });
    });

    expect(
      useAuthCardStore.getState().cardsByMessageId["auth-message-1"],
    ).toMatchObject({
      authComplete: true,
      authFailed: false,
    });
  });

  it("shows LandingPage when MSAL is authenticated but idToken is missing", async () => {
    setupAuth(true, true);
    useAuthStore.getState().clearToken();

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId("landing-page")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("chat-page")).not.toBeInTheDocument();
  });

  it("shows LoadingState during MSAL transition", () => {
    mockUseIsAuthenticated.mockReturnValue(false);
    mockUseMsal.mockReturnValue({ inProgress: InteractionStatus.Startup });
    useAuthStore.getState().setHydrated(true);
    render(<App />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });
});
