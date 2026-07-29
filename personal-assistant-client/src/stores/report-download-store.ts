import { create } from "zustand";

export interface ReportDownloadEntry {
  content: string;
  filename: string;
  format: "markdown";
}

interface ReportDownloadState {
  reportsByMessageId: Record<string, ReportDownloadEntry>;
  setReport: (messageId: string, report: ReportDownloadEntry) => void;
  clearReport: (messageId?: string) => void;
}

export const useReportDownloadStore = create<ReportDownloadState>((set) => ({
  reportsByMessageId: {},
  setReport: (messageId, report) =>
    set((state) => ({
      reportsByMessageId: {
        ...state.reportsByMessageId,
        [messageId]: report,
      },
    })),
  clearReport: (messageId) =>
    set((state) => {
      if (!messageId) return { reportsByMessageId: {} };
      const reportsByMessageId = { ...state.reportsByMessageId };
      delete reportsByMessageId[messageId];
      return { reportsByMessageId };
    }),
}));
