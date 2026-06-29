import {
  CALENDAR_OAUTH_PENDING_MESSAGE,
  CALENDAR_OAUTH_PROVIDER,
  formatCalendarOAuthError,
  isCalendarOAuthResponse,
  openCalendarOAuthChannel,
  type CalendarOAuthResponse,
} from "@/lib/auth/calendar-oauth-bridge";
import { acquireIdTokenSilently } from "@/lib/auth";
import { buildHeaders } from "@/lib/chat/chat-api-client";
import { useAuthStore } from "@/stores/auth-store";
import { useEffect, useRef, useState } from "react";

export function buildBackendCalendarCallbackUrl(
  origin = window.location.origin,
  search = window.location.search,
): URL {
  const target = new URL(
    "/invocations/auth/oauth2/callback/m365-calendar",
    origin,
  );
  target.search = search;
  return target;
}

export function getCalendarCallbackState(
  search = window.location.search,
): string | null {
  const params = new URLSearchParams(search);
  return params.get("state") || params.get("custom_state") || null;
}

async function getCalendarCallbackToken(): Promise<string | null> {
  return useAuthStore.getState().idToken ?? (await acquireIdTokenSilently());
}

async function completeCalendarOAuthCallback(
  search = window.location.search,
): Promise<CalendarOAuthResponse> {
  // Microsoft lands on this React route, but AgentArts Gateway still expects
  // the same Web Chat ID token used by normal /invocations calls. The shell
  // only transports the signed callback params; backend state decides ownership.
  const idToken = await getCalendarCallbackToken();
  if (!idToken) {
    throw new Error("Authentication required");
  }

  const headers = buildHeaders(idToken);
  headers.Accept = "application/json";
  delete headers["Content-Type"];

  const response = await fetch(
    buildBackendCalendarCallbackUrl(window.location.origin, search),
    {
      method: "GET",
      headers,
    },
  );
  if (!response.ok) {
    throw new Error(`OAuth2 callback failed: ${response.status}`);
  }

  const data = (await response.json()) as unknown;
  if (!isCalendarOAuthResponse(data)) {
    throw new Error("Invalid OAuth2 callback response");
  }
  return data;
}

function broadcastCalendarOAuthStatus(response: CalendarOAuthResponse) {
  // Broadcast only backend-returned UI status. Completion already happened on
  // the service, so other tabs cannot race to finish the same OAuth2 session.
  try {
    const channel = openCalendarOAuthChannel();
    channel?.postMessage(response);
    window.setTimeout(() => channel?.close(), 1000);
  } catch {}
  try {
    window.opener?.postMessage(response, window.location.origin);
  } catch {}
}

export default function M365CalendarCallbackPage() {
  const startedRef = useRef(false);
  const [status, setStatus] = useState<"pending" | "complete" | "failed">(
    "pending",
  );
  const [message, setMessage] = useState(CALENDAR_OAUTH_PENDING_MESSAGE);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;

    let cancelled = false;
    async function complete() {
      try {
        const response = await completeCalendarOAuthCallback();
        if (cancelled) return;
        if (response.status === "complete" || response.status === "failed") {
          setStatus(response.status);
          setMessage(response.message);
          broadcastCalendarOAuthStatus(response);
          if (response.status === "complete") {
            window.setTimeout(() => window.close(), 1200);
          }
        } else {
          setStatus("pending");
          setMessage(response.message);
        }
      } catch (error) {
        if (cancelled) return;
        const message = formatCalendarOAuthError(error);
        const callbackState = getCalendarCallbackState();
        setStatus("failed");
        setMessage(message);
        broadcastCalendarOAuthStatus({
          type: "m365-calendar-auth",
          requestId: callbackState ?? "",
          provider: CALENDAR_OAUTH_PROVIDER,
          status: "failed",
          message,
          state: callbackState,
        });
      }
    }

    void complete();
    return () => {
      cancelled = true;
    };
  }, []);

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
          {isComplete ? "✓" : isFailed ? "!" : "..."}
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
