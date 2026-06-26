import {
  CALENDAR_OAUTH_FAILED_MESSAGE,
  CALENDAR_OAUTH_MISSING_PARAMS_MESSAGE,
  CALENDAR_OAUTH_PENDING_MESSAGE,
  CALENDAR_OAUTH_PROVIDER,
  CALENDAR_OAUTH_TIMEOUT_MS,
  CALENDAR_OAUTH_UNAVAILABLE_MESSAGE,
  createCalendarOAuthRequest,
  isCalendarOAuthResponse,
  openCalendarOAuthChannel,
} from "@/lib/auth/calendar-oauth-bridge";
import { useEffect, useMemo, useState } from "react";

type CallbackStatus = "loading" | "complete" | "failed";

export default function M365CalendarCallbackPage() {
  const params = useMemo(
    () => new URLSearchParams(window.location.search),
    [],
  );
  const [status, setStatus] = useState<CallbackStatus>("loading");
  const [message, setMessage] = useState(CALENDAR_OAUTH_PENDING_MESSAGE);

  useEffect(() => {
    let cancelled = false;
    let timeoutId: number | undefined;
    let channel: BroadcastChannel | null = null;

    function fail(message: string) {
      if (!cancelled) {
        setStatus("failed");
        setMessage(message);
      }
      channel?.close();
    }

    async function complete() {
      const error = params.get("error");
      const errorDescription = params.get("error_description");
      const sessionUri = params.get("session_uri");
      const state = params.get("state") ?? params.get("custom_state");

      if (error) {
        const failedMessage = errorDescription || "日历授权失败，请重新发起授权。";
        fail(failedMessage);
        return;
      }

      if (!sessionUri || !state) {
        fail(CALENDAR_OAUTH_MISSING_PARAMS_MESSAGE);
        return;
      }

      channel = openCalendarOAuthChannel();
      if (!channel) {
        fail(CALENDAR_OAUTH_UNAVAILABLE_MESSAGE);
        return;
      }

      const request = createCalendarOAuthRequest({
        provider: CALENDAR_OAUTH_PROVIDER,
        sessionUri,
        state,
      });

      channel.onmessage = (event) => {
        if (!isCalendarOAuthResponse(event.data)) return;
        if (
          event.data.provider !== CALENDAR_OAUTH_PROVIDER ||
          event.data.requestId !== request.requestId
        ) {
          return;
        }

        if (timeoutId !== undefined) {
          window.clearTimeout(timeoutId);
        }
        if (!cancelled) {
          setStatus(event.data.status);
          setMessage(event.data.message);
        }
        channel?.close();
      };

      timeoutId = window.setTimeout(() => {
        fail(CALENDAR_OAUTH_FAILED_MESSAGE);
      }, CALENDAR_OAUTH_TIMEOUT_MS);

      channel.postMessage(request);
    }

    void complete();
    return () => {
      cancelled = true;
      if (timeoutId !== undefined) {
        window.clearTimeout(timeoutId);
      }
      channel?.close();
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
