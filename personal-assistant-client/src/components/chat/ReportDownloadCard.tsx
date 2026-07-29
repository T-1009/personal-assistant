import { saveMarkdownFile } from "@/lib/save-markdown";
import { useReportDownloadStore } from "@/stores/report-download-store";
import {
  AlertCircleIcon,
  CheckCircleIcon,
  DownloadIcon,
  FileTextIcon,
  LoaderCircleIcon,
} from "lucide-react";
import { useState, type FC } from "react";

export interface ReportDownloadCardProps {
  messageId: string;
  isMessageRunning?: boolean;
}

type SaveStatus = "idle" | "saving" | "saved" | "failed";

export const ReportDownloadCard: FC<ReportDownloadCardProps> = ({
  messageId,
  isMessageRunning = false,
}) => {
  const report = useReportDownloadStore(
    (state) => state.reportsByMessageId[messageId],
  );
  const [status, setStatus] = useState<SaveStatus>("idle");

  if (!report) return null;

  const isSaved = status === "saved";
  const isFailed = status === "failed";
  const isSaving = status === "saving";
  const isPending = isSaving || isMessageRunning;
  const statusText = isMessageRunning
    ? "Markdown 报告正在整理"
    : isSaved
      ? "Markdown 报告已保存"
      : isFailed
        ? "报告保存失败"
        : "Markdown 报告已生成";
  const buttonText = isMessageRunning
    ? "整理中"
    : isSaving
      ? "保存中"
      : isSaved
        ? "再次保存"
        : isFailed
          ? "重试"
          : "下载报告";
  const cardClass = isSaved
    ? "flex items-start gap-3 rounded-xl border border-green-200 bg-green-50 p-4 dark:border-green-800 dark:bg-green-950"
    : isFailed
      ? "flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-950"
      : "flex items-start gap-3 rounded-xl border border-blue-200 bg-blue-50 p-4 dark:border-blue-800 dark:bg-blue-950";
  const textClass = isSaved
    ? "text-sm font-medium text-green-800 dark:text-green-200"
    : isFailed
      ? "text-sm font-medium text-red-800 dark:text-red-200"
      : "text-sm font-medium text-blue-800 dark:text-blue-200";
  const buttonClass = isSaved
    ? "inline-flex h-8 items-center gap-2 rounded-md bg-green-600 px-3 text-sm font-medium text-white transition-colors hover:bg-green-700 disabled:cursor-wait disabled:opacity-70"
    : isFailed
      ? "inline-flex h-8 items-center gap-2 rounded-md bg-red-600 px-3 text-sm font-medium text-white transition-colors hover:bg-red-700 disabled:cursor-wait disabled:opacity-70"
      : "inline-flex h-8 items-center gap-2 rounded-md bg-blue-600 px-3 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-wait disabled:opacity-70";

  const handleSave = async () => {
    if (isMessageRunning) return;
    setStatus("saving");
    try {
      const result = await saveMarkdownFile(report.content, report.filename);
      setStatus(result === "saved" ? "saved" : "idle");
    } catch {
      setStatus("failed");
    }
  };

  return (
    <div className="mb-4 mt-4 w-full" data-slot="report-download-card">
      <div className={cardClass}>
        {isSaved ? (
          <CheckCircleIcon className="mt-0.5 size-5 shrink-0 text-green-600 dark:text-green-400" />
        ) : isFailed ? (
          <AlertCircleIcon className="mt-0.5 size-5 shrink-0 text-red-600 dark:text-red-400" />
        ) : (
          <FileTextIcon className="mt-0.5 size-5 shrink-0 text-blue-600 dark:text-blue-400" />
        )}
        <div className="min-w-0 flex-1">
          <p className={textClass}>{statusText}</p>
          <p className="mt-1 truncate text-xs text-current opacity-70">
            {report.filename}
          </p>
        </div>
        <button
          type="button"
          onClick={handleSave}
          disabled={isPending}
          className={buttonClass}
          aria-label="下载 Markdown 报告"
        >
          {isPending ? (
            <LoaderCircleIcon className="size-4 animate-spin" />
          ) : (
            <DownloadIcon className="size-4" />
          )}
          {buttonText}
        </button>
      </div>
    </div>
  );
};
