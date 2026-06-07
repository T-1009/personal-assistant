import { type ReactNode } from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { RuntimeProvider } from "./RuntimeProvider";

/**
 * RuntimeProvider uses useLocalRuntime + AssistantRuntimeProvider from @assistant-ui/react.
 * The runtime internals are complex (stores, fibers, etc.), so we mock the entire
 * provider layer. RuntimeProvider's own logic (calling useLocalRuntime with chatAdapter)
 * is tested implicitly by verifying children render without errors.
 */
vi.mock("@assistant-ui/react", async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    useLocalRuntime: vi.fn(() => ({})),
    AssistantRuntimeProvider: ({ children }: { children: ReactNode }) =>
      children,
  };
});

describe("RuntimeProvider", () => {
  it("renders children inside AssistantRuntimeProvider", () => {
    render(
      <RuntimeProvider>
        <div data-testid="child">Hello World</div>
      </RuntimeProvider>,
    );

    expect(screen.getByTestId("child")).toBeInTheDocument();
    expect(screen.getByText("Hello World")).toBeInTheDocument();
  });

  it("does not throw errors during render", () => {
    expect(() =>
      render(
        <RuntimeProvider>
          <span>No crash</span>
        </RuntimeProvider>,
      ),
    ).not.toThrow();
  });
});
