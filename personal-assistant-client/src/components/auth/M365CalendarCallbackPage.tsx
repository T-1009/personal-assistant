import { completeOAuth2Auth } from "@/lib/auth/oauth2-complete";
import { useEffect, useMemo, useState } from "react";

const CALENDAR_OAUTH_PROVIDER = "m365-calendar-provider";

const CALENDAR_OAUTH_PENDING_MESSAGE = "正在完成日历授权，请稍候…";

const CALENDAR_OAUTH_SUCCESS_MESSAGE =
  "日历授权已完成，可以关闭此窗口并重试刚才的问题。";

const CALENDAR_OAUTH_FAILED_MESSAGE =
  "日历授权完成失败，请重新发起授权。";

const CALENDAR_OAUTH_MISSING_PARAMS_MESSAGE =
  "授权回调缺少必要参数，请重新发起日历授权。";

type CallbackStatus = "loading" | "complete" | "failed";

function formatCalendarOAuthError(error: unknown): string {
  const message = error instanceof Error ? error.message.trim() : "";
  if (!message) {
    return CALENDAR_OAUTH_FAILED_MESSAGE;
  }

  if (
    message.includes("Missing X-HW-AgentGateway-User-Id header") ||
    message.includes("Authentication required")
  ) {
    return "请保持原聊天窗口处于登录状态后，再重新完成日历授权。";
  }

  return message;
}

export default function M365CalendarCallbackPage() {
  const params = useMemo(
    () => new URLSearchParams(window.location.search),
    [],
  );
  const [status, setStatus] = useState<CallbackStatus>("loading");
  const [message, setMessage] = useState(CALENDAR_OAUTH_PENDING_MESSAGE);

  useEffect(() => {
    let cancelled = false;

    function notifyParent(
      nextStatus: Exclude<CallbackStatus, "loading">,
      nextMessage: string,
    ) {
      window.opener?.postMessage(
        {
          type: "m365-calendar-auth",
          status: nextStatus,
          provider: CALENDAR_OAUTH_PROVIDER,
          message: nextMessage,
        },
        window.location.origin,
      );
    }

    function finish(nextStatus: Exclude<CallbackStatus, "loading">, nextMessage: string) {
      if (cancelled) return;
      setStatus(nextStatus);
      setMessage(nextMessage);
      notifyParent(nextStatus, nextMessage);
      window.setTimeout(() => window.close(), 1000);
    }

    async function complete() {
      const error = params.get("error");
      const errorDescription = params.get("error_description");
      const sessionUri = params.get("session_uri");
      const state = params.get("state") ?? params.get("custom_state");

      if (error) {
        finish("failed", errorDescription || "日历授权失败，请重新发起授权。");
        return;
      }

      if (!sessionUri || !state) {
        finish("failed", CALENDAR_OAUTH_MISSING_PARAMS_MESSAGE);
        return;
      }

      try {
        const body = await completeOAuth2Auth({
          provider: CALENDAR_OAUTH_PROVIDER,
          session_uri: sessionUri,
          state,
        });
        finish("complete", body.message || CALENDAR_OAUTH_SUCCESS_MESSAGE);
      } catch (error) {
        finish("failed", formatCalendarOAuthError(error));
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
