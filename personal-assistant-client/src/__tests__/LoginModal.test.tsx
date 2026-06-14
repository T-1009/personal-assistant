import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LoginModal } from "@/components/landing/LoginModal";

describe("LoginModal", () => {
  const defaultProps = {
    open: true,
    onClose: vi.fn(),
    onMicrosoftLogin: vi.fn(),
  };

  it("when open=true, renders the modal with heading", () => {
    render(<LoginModal {...defaultProps} />);
    expect(screen.getByText("选择登录方式")).toBeInTheDocument();
  });

  it("when open=false, renders nothing", () => {
    const { container } = render(
      <LoginModal {...defaultProps} open={false} />
    );
    expect(screen.queryByText("选择登录方式")).not.toBeInTheDocument();
    expect(container.innerHTML).toBe("");
  });

  it("clicking the backdrop calls onClose", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    const { container } = render(
      <LoginModal {...defaultProps} onClose={onClose} />
    );
    const backdrop = container.querySelector(".fixed.inset-0") as HTMLElement;
    expect(backdrop).not.toBeNull();
    await user.click(backdrop);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("clicking the X close button calls onClose", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<LoginModal {...defaultProps} onClose={onClose} />);
    // The X button is a <button> containing an SVG icon
    const buttons = screen.getAllByRole("button");
    // First button is the X close button
    const xButton = buttons[0];
    await user.click(xButton);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('clicking "取消" button calls onClose', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<LoginModal {...defaultProps} onClose={onClose} />);
    await user.click(screen.getByRole("button", { name: "取消" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("clicking the Microsoft row calls onMicrosoftLogin", async () => {
    const onMicrosoftLogin = vi.fn();
    const user = userEvent.setup();
    render(
      <LoginModal {...defaultProps} onMicrosoftLogin={onMicrosoftLogin} />
    );
    await user.click(screen.getByText("Microsoft 账号"));
    expect(onMicrosoftLogin).toHaveBeenCalledTimes(1);
  });

  it("GitHub row has opacity-50 and cursor-not-allowed classes and 即将支持 badge", () => {
    render(<LoginModal {...defaultProps} />);
    const githubText = screen.getByText("GitHub 账号");
    // Find the parent row div (the container with the classes)
    const githubRow = githubText.closest(".opacity-50") as HTMLElement;
    expect(githubRow).not.toBeNull();
    expect(githubRow.className).toContain("cursor-not-allowed");
    // The "即将支持" badge should be present
    const badges = screen.getAllByText("即将支持");
    expect(badges.length).toBeGreaterThanOrEqual(1);
    // Verify the first badge is inside the GitHub row
    expect(githubRow).toContainElement(badges[0]);
  });

  it("WeChat row has opacity-50 and cursor-not-allowed classes and 即将支持 badge", () => {
    render(<LoginModal {...defaultProps} />);
    const wechatText = screen.getByText("微信账号");
    const wechatRow = wechatText.closest(".opacity-50") as HTMLElement;
    expect(wechatRow).not.toBeNull();
    expect(wechatRow.className).toContain("cursor-not-allowed");
    // There are two "即将支持" badges; the second one is in the WeChat row
    const badges = screen.getAllByText("即将支持");
    expect(badges.length).toBeGreaterThanOrEqual(2);
    expect(wechatRow).toContainElement(badges[1]);
  });

  it("GitHub and WeChat rows do NOT trigger onMicrosoftLogin when clicked", async () => {
    const onMicrosoftLogin = vi.fn();
    const user = userEvent.setup();
    render(
      <LoginModal {...defaultProps} onMicrosoftLogin={onMicrosoftLogin} />
    );
    await user.click(screen.getByText("GitHub 账号"));
    await user.click(screen.getByText("微信账号"));
    expect(onMicrosoftLogin).not.toHaveBeenCalled();
  });
});
