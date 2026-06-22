import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { useAuthCardStore } from "@/stores/auth-card-store";
import { AuthCard } from "./AuthCard";

describe("AuthCard", () => {
  afterEach(() => {
    useAuthCardStore.getState().clearAuth();
  });

  it("keeps rendering a historical message card after a newer Auth Card arrives", () => {
    const authStore = useAuthCardStore.getState();
    authStore.setAuth(
      "auth-message-1",
      "m365-provider-common",
      "https://auth-1.example.com",
      "请先完成日历授权",
    );
    authStore.setAuth(
      "auth-message-2",
      "m365-provider-common",
      "https://auth-2.example.com",
      "请再完成邮件授权",
    );

    render(<AuthCard messageId="auth-message-1" />);

    expect(screen.getByText("请先完成日历授权")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "点击授权" })).toHaveAttribute(
      "href",
      "https://auth-1.example.com",
    );
  });
});
