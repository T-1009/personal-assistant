import { afterEach, describe, expect, it, vi } from "vitest";
import {
  normalizeMarkdownFilename,
  saveMarkdownFile,
} from "./save-markdown";

type TestPickerWindow = Window & {
  showSaveFilePicker?: (options: unknown) => Promise<{
    createWritable(): Promise<{
      write(data: Blob): Promise<void>;
      close(): Promise<void>;
    }>;
  }>;
};

function setSaveFilePicker(value: TestPickerWindow["showSaveFilePicker"]): void {
  Object.defineProperty(window, "showSaveFilePicker", {
    configurable: true,
    value,
  });
}

afterEach(() => {
  setSaveFilePicker(undefined);
  vi.restoreAllMocks();
});

describe("saveMarkdownFile", () => {
  it("normalizes unsafe names and keeps the Markdown extension", () => {
    expect(normalizeMarkdownFilename(' 日报:2024/02/14.md ')).toBe(
      "日报-2024-02-14.md",
    );
    expect(normalizeMarkdownFilename("<>.md")).toBe("--.md");
    expect(normalizeMarkdownFilename("   ")).toBe("report.md");
  });

  it("opens the native save picker and writes UTF-8 Markdown", async () => {
    const write = vi.fn().mockResolvedValue(undefined);
    const close = vi.fn().mockResolvedValue(undefined);
    const createWritable = vi.fn().mockResolvedValue({ write, close });
    const showSaveFilePicker = vi
      .fn()
      .mockResolvedValue({ createWritable });
    setSaveFilePicker(showSaveFilePicker);

    const result = await saveMarkdownFile(
      "# 日报\n\nGitHub、Email、Calendar",
      "日报-2024-02-14.md",
    );

    expect(result).toBe("saved");
    expect(showSaveFilePicker).toHaveBeenCalledWith({
      suggestedName: "日报-2024-02-14.md",
      types: [
        {
          description: "Markdown",
          accept: { "text/markdown": [".md"] },
        },
      ],
    });
    expect(createWritable).toHaveBeenCalledOnce();
    expect(write).toHaveBeenCalledOnce();
    const blob = write.mock.calls[0]?.[0] as Blob;
    expect(blob.type).toBe("text/markdown;charset=utf-8");
    expect(await blob.text()).toBe("# 日报\n\nGitHub、Email、Calendar");
    expect(close).toHaveBeenCalledOnce();
  });

  it("does not start a fallback download when the user cancels", async () => {
    const showSaveFilePicker = vi
      .fn()
      .mockRejectedValue(new DOMException("cancelled", "AbortError"));
    setSaveFilePicker(showSaveFilePicker);
    const anchorClick = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);

    await expect(saveMarkdownFile("# 日报", "日报.md")).resolves.toBe(
      "cancelled",
    );
    expect(anchorClick).not.toHaveBeenCalled();
  });

  it.each(["picker", "createWritable", "write", "close"] as const)(
    "propagates an unexpected %s failure without starting a fallback download",
    async (failureStage) => {
      const failure = new Error(`${failureStage} failed`);
      const write = vi.fn(async () => {
        if (failureStage === "write") throw failure;
      });
      const close = vi.fn(async () => {
        if (failureStage === "close") throw failure;
      });
      const createWritable = vi.fn(async () => {
        if (failureStage === "createWritable") throw failure;
        return { write, close };
      });
      const showSaveFilePicker = vi.fn(async () => {
        if (failureStage === "picker") throw failure;
        return { createWritable };
      });
      setSaveFilePicker(showSaveFilePicker);
      const anchorClick = vi
        .spyOn(HTMLAnchorElement.prototype, "click")
        .mockImplementation(() => undefined);

      await expect(saveMarkdownFile("# 日报", "日报.md")).rejects.toBe(
        failure,
      );
      expect(anchorClick).not.toHaveBeenCalled();
    },
  );

  it("falls back to a standard Markdown download when no picker exists", async () => {
    setSaveFilePicker(undefined);
    const createObjectURL = vi.fn().mockReturnValue("blob:report");
    const revokeObjectURL = vi.fn();
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: createObjectURL,
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: revokeObjectURL,
    });
    const anchorClick = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);

    await expect(
      saveMarkdownFile("# 周报", "周报-2024-02-12_2024-02-18.md"),
    ).resolves.toBe("saved");

    expect(createObjectURL).toHaveBeenCalledOnce();
    const blob = createObjectURL.mock.calls[0]?.[0] as Blob;
    expect(await blob.text()).toBe("# 周报");
    expect(anchorClick).toHaveBeenCalledOnce();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:report");
  });
});
