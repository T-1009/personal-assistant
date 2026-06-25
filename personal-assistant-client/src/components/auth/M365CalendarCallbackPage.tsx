import { completeOAuth2Auth } from "@/lib/auth/oauth2-complete";
import { useEffect, useMemo, useState } from "react";

const PROVIDER = "m365-calendar-provider";

type CallbackStatus = "loading" | "complete" | "failed";

interface CallbackMessage {
  type: "m365-calendar-auth";
  status: "complete" | "failed";
  provider: string;
  message: string;
}

function notifyOpener(status: "complete" | "failed", message: string) {
  const payload: CallbackMessage = {
    type: "m365-calendar-auth",
    status,
    provider: PROVIDER,
    message,
  };
  window.opener?.postMessage(payload, window.location.origin);
}

export default function M365CalendarCallbackPage() {
  const params = useMemo(
    () => new URLSearchParams(window.location.search),
    [],
  );
  const [status, setStatus] = useState<CallbackStatus>("loading");
  const [message, setMessage] = useState("正在完成日历授权，请稍候…");

  useEffect(() => {
    let cancelled = false;

    async function complete() {
      const error = params.get("error");
      const errorDescription = params.get("error_description");
      const sessionUri = params.get("session_uri");
      const state = params.get("state") ?? params.get("custom_state");

      if (error) {
        const failedMessage = errorDescription || "日历授权失败，请重新发起授权。";
        if (!cancelled) {
          setStatus("failed");
          setMessage(failedMessage);
        }
        notifyOpener("failed", failedMessage);
        return;
      }

      if (!sessionUri) {
        const failedMessage = "授权回调缺少必要参数，请重新发起日历授权。";
        if (!cancelled) {
          setStatus("failed");
          setMessage(failedMessage);
        }
        notifyOpener("failed", failedMessage);
        return;
      }

      try {
        await completeOAuth2Auth({
          provider: PROVIDER,
          session_uri: sessionUri,
          state,
        });
        const successMessage = "日历授权已完成，可以关闭此窗口并重试刚才的问题。";
        if (!cancelled) {
          setStatus("complete");
          setMessage(successMessage);
        }
        notifyOpener("complete", successMessage);
      } catch (e) {
        const failedMessage =
          e instanceof Error ? e.message : "日历授权完成失败，请重新发起授权。";
        if (!cancelled) {
          setStatus("failed");
          setMessage(failedMessage);
        }
        notifyOpener("failed", failedMessage);
      }
    }

    void complete();
    return () => {
      cancelled = true;
    };
  }, [params]);

  const isComplete = status === "complete";
  const isFailed = status === "failed";

  return (
    <main className="flex min-h-dvh items-center justify-center bg-background px-6">
      <section className="w-full max-w-md rounded-2xl border bg-card p-6 text-center shadow-sm">
        <div
          className={
            isComplete
              ? "mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-green-100 text-green-700"
              : isFailed
                ? "mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-red-100 text-red-700"
                : "mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-blue-100 text-blue-700"
          }
        >
          {isComplete ? "✓" : isFailed ? "!" : "…"}
        </div>
        <h1 className="text-lg font-semibold">
          {isComplete ? "授权完成" : isFailed ? "授权失败" : "正在授权"}
        </h1>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">{message}</p>
        <button
          type="button"
          onClick={() => window.close()}
          className="mt-6 inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          关闭窗口
        </button>
      </section>
    </main>
  );
}
