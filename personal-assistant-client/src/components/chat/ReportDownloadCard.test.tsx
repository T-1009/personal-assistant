import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { saveMarkdownFile } from "@/lib/save-markdown";
import { useReportDownloadStore } from "@/stores/report-download-store";
import { ReportDownloadCard } from "./ReportDownloadCard";

vi.mock("@/lib/save-markdown", () => ({
  saveMarkdownFile: vi.fn(),
}));

const saveMarkdownFileMock = vi.mocked(saveMarkdownFile);

describe("ReportDownloadCard", () => {
  beforeEach(() => {
    useReportDownloadStore.getState().clearReport();
    saveMarkdownFileMock.mockReset();
  });

  afterEach(() => {
    useReportDownloadStore.getState().clearReport();
  });

  it("renders only for the assistant message that owns the report", () => {
    useReportDownloadStore.getState().setReport("report-message", {
      content: "# 日报",
      filename: "日报-2024-02-14.md",
      format: "markdown",
    });

    const { rerender } = render(
      <ReportDownloadCard messageId="other-message" />,
    );
    expect(screen.queryByText("Markdown 报告已生成")).not.toBeInTheDocument();

    rerender(<ReportDownloadCard messageId="report-message" />);
    expect(screen.getByText("Markdown 报告已生成")).toBeInTheDocument();
    expect(screen.getByText("日报-2024-02-14.md")).toBeInTheDocument();
  });

  it("saves the exact Markdown and transitions to the completed state", async () => {
    saveMarkdownFileMock.mockResolvedValue("saved");
    useReportDownloadStore.getState().setReport("report-message", {
      content: "# 日报\n\n- 时间范围：2024-02-14",
      filename: "日报-2024-02-14.md",
      format: "markdown",
    });
    render(<ReportDownloadCard messageId="report-message" />);

    fireEvent.click(
      screen.getByRole("button", { name: "下载 Markdown 报告" }),
    );

    await waitFor(() => {
      expect(saveMarkdownFileMock).toHaveBeenCalledWith(
        "# 日报\n\n- 时间范围：2024-02-14",
        "日报-2024-02-14.md",
      );
    });
    expect(screen.getByText("Markdown 报告已保存")).toBeInTheDocument();
    expect(screen.getByText("再次保存")).toBeInTheDocument();
  });

  it("prefers the visible assistant Markdown over the report event fallback", async () => {
    saveMarkdownFileMock.mockResolvedValue("saved");
    useReportDownloadStore.getState().setReport("report-message", {
      content: "# 后端报告\n\n- 简略版本",
      filename: "日报-2024-02-14.md",
      format: "markdown",
    });
    render(
      <ReportDownloadCard
        messageId="report-message"
        displayedMarkdown={"# 前端报告\n\n- 更完整的展示版本"}
      />,
    );

    fireEvent.click(
      screen.getByRole("button", { name: "下载 Markdown 报告" }),
    );

    await waitFor(() => {
      expect(saveMarkdownFileMock).toHaveBeenCalledWith(
        "# 前端报告\n\n- 更完整的展示版本",
        "日报-2024-02-14.md",
      );
    });
  });

  it("waits for the assistant message to finish before saving visible Markdown", () => {
    useReportDownloadStore.getState().setReport("report-message", {
      content: "# 后端报告",
      filename: "日报-2024-02-14.md",
      format: "markdown",
    });
    render(
      <ReportDownloadCard
        messageId="report-message"
        displayedMarkdown={"# 前端报告\n\n- 仍在生成中"}
        isMessageRunning
      />,
    );

    const button = screen.getByRole("button", {
      name: "下载 Markdown 报告",
    });
    expect(screen.getByText("Markdown 报告正在整理")).toBeInTheDocument();
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(saveMarkdownFileMock).not.toHaveBeenCalled();
  });

  it("shows a retry action after a save error", async () => {
    saveMarkdownFileMock.mockRejectedValue(new Error("disk unavailable"));
    useReportDownloadStore.getState().setReport("report-message", {
      content: "# 月报",
      filename: "月报-2024-02-01_2024-02-29.md",
      format: "markdown",
    });
    render(<ReportDownloadCard messageId="report-message" />);

    fireEvent.click(
      screen.getByRole("button", { name: "下载 Markdown 报告" }),
    );

    expect(await screen.findByText("报告保存失败")).toBeInTheDocument();
    expect(screen.getByText("重试")).toBeInTheDocument();
  });
});
