import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

/**
 * Mock CPU-heavy modules to keep App smoke tests lightweight.
 * - RuntimeProvider → simple passthrough (tested separately)
 * - Thread → empty placeholder (huge dependency tree)
 */
vi.mock("@/components/RuntimeProvider", () => ({
  RuntimeProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
}));

vi.mock("@/components/assistant-ui/thread", () => ({
  Thread: () => <div data-testid="thread">Thread</div>,
}));

// TooltipProvider from radix-ui (via @/components/ui/tooltip) works fine in tests

import App from "./App";

describe("App", () => {
  it("renders without crashing", () => {
    expect(() => render(<App />)).not.toThrow();
  });

  it('shows LoginPlaceholder with "登录后可体验完整功能" text', () => {
    render(<App />);
    expect(
      screen.getByText("登录后可体验完整功能"),
    ).toBeInTheDocument();
  });

  it("renders the Thread component area", () => {
    render(<App />);
    expect(screen.getByTestId("thread")).toBeInTheDocument();
  });
});
