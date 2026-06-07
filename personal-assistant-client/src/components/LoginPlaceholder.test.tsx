import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { LoginPlaceholder } from "./LoginPlaceholder";

describe("LoginPlaceholder", () => {
  it("renders the placeholder text", () => {
    render(<LoginPlaceholder />);
    expect(
      screen.getByText("登录后可体验完整功能"),
    ).toBeInTheDocument();
  });

  it('has aria-disabled="true" attribute', () => {
    render(<LoginPlaceholder />);
    const element = screen.getByText("登录后可体验完整功能");
    expect(element).toHaveAttribute("aria-disabled", "true");
  });

  it("applies cursor-not-allowed styling", () => {
    render(<LoginPlaceholder />);
    const element = screen.getByText("登录后可体验完整功能");
    expect(element.className).toContain("cursor-not-allowed");
  });
});
