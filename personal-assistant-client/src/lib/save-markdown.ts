export type SaveMarkdownResult = "saved" | "cancelled";

interface SaveFilePickerWritable {
  write(data: Blob): Promise<void>;
  close(): Promise<void>;
}

interface SaveFilePickerHandle {
  createWritable(): Promise<SaveFilePickerWritable>;
}

interface SaveFilePickerOptions {
  suggestedName: string;
  types: Array<{
    description: string;
    accept: Record<string, string[]>;
  }>;
}

type ShowSaveFilePicker = (
  options: SaveFilePickerOptions,
) => Promise<SaveFilePickerHandle>;

type WindowWithSaveFilePicker = Window & {
  showSaveFilePicker?: ShowSaveFilePicker;
};

const MARKDOWN_MIME_TYPE = "text/markdown;charset=utf-8";

export function normalizeMarkdownFilename(filename: string): string {
  const normalized = filename
    .replace(/[<>:"/\\|?*\u0000-\u001f]/g, "-")
    .replace(/\s+/g, " ")
    .trim();
  const basename = normalized.replace(/\.md$/i, "").slice(0, 120).trim();
  return `${basename || "report"}.md`;
}

function isAbortError(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "name" in error &&
    error.name === "AbortError"
  );
}

function downloadWithAnchor(content: string, filename: string): void {
  const blob = new Blob([content], { type: MARKDOWN_MIME_TYPE });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.hidden = true;
  document.body.append(anchor);
  try {
    anchor.click();
  } finally {
    anchor.remove();
    URL.revokeObjectURL(url);
  }
}

export async function saveMarkdownFile(
  content: string,
  requestedFilename: string,
): Promise<SaveMarkdownResult> {
  const filename = normalizeMarkdownFilename(requestedFilename);
  const pickerWindow = window as WindowWithSaveFilePicker;

  if (pickerWindow.showSaveFilePicker) {
    try {
      const handle = await pickerWindow.showSaveFilePicker({
        suggestedName: filename,
        types: [
          {
            description: "Markdown",
            accept: { "text/markdown": [".md"] },
          },
        ],
      });
      const writable = await handle.createWritable();
      await writable.write(new Blob([content], { type: MARKDOWN_MIME_TYPE }));
      await writable.close();
      return "saved";
    } catch (error) {
      if (isAbortError(error)) return "cancelled";
      throw error;
    }
  }

  downloadWithAnchor(content, filename);
  return "saved";
}
