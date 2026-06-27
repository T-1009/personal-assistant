import { describe, it, expect, vi, afterEach } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { InteractionStatus } from "@azure/msal-browser";
import { useAuthStore } from "@/stores/auth-store";

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

import App from "./App";

function setupAuth(isAuthenticated: boolean, hydrated: boolean) {
  mockUseIsAuthenticated.mockReturnValue(isAuthenticated);
  mockUseMsal.mockReturnValue({ inProgress: InteractionStatus.None });
  const store = useAuthStore.getState();
  store.setHydrated(hydrated);
  store.setIdToken(isAuthenticated ? "id-token" : null);
}

describe("App", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    useAuthStore.getState().setHydrated(false);
    useAuthStore.getState().clearToken();
    window.history.pushState({}, "", "/");
  });

  it("renders without crashing", () => {
    mockUseIsAuthenticated.mockReturnValue(false);
    mockUseMsal.mockReturnValue({ inProgress: InteractionStatus.None });
    expect(() => render(<App />)).not.toThrow();
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

  it("shows LoadingState when auth store is not hydrated", () => {
    mockUseIsAuthenticated.mockReturnValue(false);
    mockUseMsal.mockReturnValue({ inProgress: InteractionStatus.None });
    useAuthStore.getState().setHydrated(false);
    render(<App />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("routes calendar callback pathname to the callback page", async () => {
    setupAuth(false, true);
    window.history.pushState({}, "", "/auth/callback/m365-calendar");
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText("正在授权")).toBeInTheDocument();
    });
  });
});
