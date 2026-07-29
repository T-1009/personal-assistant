import { beforeEach, describe, expect, it } from "vitest";
import { useAuthCardStore } from "@/stores/auth-card-store";
import { useReportDownloadStore } from "@/stores/report-download-store";
import { handleChatEvent } from "./chat-event-handler";

describe("handleChatEvent report_ready", () => {
  beforeEach(() => {
    useAuthCardStore.getState().clearAuth();
    useReportDownloadStore.getState().clearReport();
  });

  it("stores the original Markdown for the matching assistant message", () => {
    const result = handleChatEvent(
      {
        type: "report_ready",
        report_ready: true,
        report_format: "markdown",
        report_filename: "日报-2024-02-14.md",
        report_content: "# 日报\n\n- 时间范围：2024-02-14",
        report_type: "daily",
      },
      { assistantMessageId: "assistant-report-1", fullText: "生成中" },
    );

    expect(result).toEqual({
      fullText: "生成中",
      contentUpdates: [],
      done: false,
    });
    expect(
      useReportDownloadStore.getState().reportsByMessageId[
        "assistant-report-1"
      ],
    ).toEqual({
      content: "# 日报\n\n- 时间范围：2024-02-14",
      filename: "日报-2024-02-14.md",
      format: "markdown",
    });
  });

  it("ignores incomplete report events without changing OAuth state", () => {
    useAuthCardStore.getState().setAuth(
      "auth-message",
      "github-provider",
      "https://github.example/authorize",
      "请完成 GitHub 授权",
    );

    handleChatEvent(
      {
        report_ready: true,
        report_format: "markdown",
        report_filename: "empty.md",
        report_content: "",
      },
      { assistantMessageId: "assistant-report-2", fullText: "" },
    );

    expect(useReportDownloadStore.getState().reportsByMessageId).toEqual({});
    expect(
      useAuthCardStore.getState().cardsByMessageId["auth-message"]?.message,
    ).toBe("请完成 GitHub 授权");
  });
});
