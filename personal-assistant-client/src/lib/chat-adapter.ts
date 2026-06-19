import type {
  ChatModelAdapter,
  ChatModelRunOptions,
  ChatModelRunResult,
} from "@assistant-ui/react";
import type { SSEEvent } from "../types/chat";
import { useAuthCardStore } from "@/stores/auth-card-store";
import { useAuthStore } from "@/stores/auth-store";
import { acquireIdTokenSilently } from "@/lib/auth";

const baseUrl: string = (
  import.meta.env.VITE_API_BASE_URL ?? ""
).replace(/\/$/, "");

/**
 * Decode a base64url-encoded string to a native JavaScript string.
 *
 * Unlike atob(), this handles:
 * - base64url alphabet (- → +, _ → /)
 * - missing padding
 * - UTF-8 byte sequences in the decoded payload (e.g. Chinese names in claims)
 */
function base64UrlDecode(str: string): string {
  // Restore base64url → standard base64
  let base64 = str.replace(/-/g, "+").replace(/_/g, "/");
  // Restore padding
  while (base64.length % 4 !== 0) {
    base64 += "=";
  }
  // Decode binary string to UTF-8
  const binary = atob(base64);
  return new TextDecoder().decode(
    Uint8Array.from(binary, (c) => c.charCodeAt(0)),
  );
}

function extractUserIdFromToken(idToken: string): string | undefined {
  try {
    const payload = JSON.parse(base64UrlDecode(idToken.split(".")[1]));
    return (payload as Record<string, unknown>).sub as string | undefined
        ?? (payload as Record<string, unknown>).oid as string | undefined;
  } catch {
    return undefined;
  }
}

/** Check if token expires within the next 60 seconds */
function isTokenExpiringSoon(idToken: string): boolean {
  try {
    const payload = JSON.parse(base64UrlDecode(idToken.split(".")[1]));
    const exp = (payload as Record<string, unknown>).exp as number;
    return Date.now() >= (exp - 60) * 1000;
  } catch {
    return true; // can't parse — assume expired
  }
}

export function getSessionId(): string {
  try {
    const existing = localStorage.getItem("agentarts-session-id");
    if (existing) return existing;
    const id = crypto.randomUUID();
    localStorage.setItem("agentarts-session-id", id);
    return id;
  } catch {
    return crypto.randomUUID();
  }
}

/**
 * Remove the persisted session ID from localStorage to trigger a new
 * conversation on the next chat-adapter run.
 *
 * Safe to call when localStorage is unavailable (privacy mode, storage
 * quota exceeded, etc.) — errors are silently swallowed.
 */
export function resetSessionId(): void {
  try {
    localStorage.removeItem("agentarts-session-id");
  } catch {
    // privacy mode / localStorage unavailable — silent no-op
  }
}

/**
 * ChatModelAdapter that connects to the backend SSE API.
 *
 * - In dev mode (VITE_API_BASE_URL not set), requests go through the
 *   Vite dev proxy at `/invocations` -> `localhost:8080`.
 * - In production, VITE_API_BASE_URL is `/api`; the same-origin Cloudflare
 *   Pages Function proxies requests to the full AgentArts Runtime URL.
 */
export const chatAdapter: ChatModelAdapter = {
  async *run(options: ChatModelRunOptions): AsyncGenerator<ChatModelRunResult, void> {
    const { messages, abortSignal } = options;
    // Extract the last user message text as the query
    const lastUserMessage = [...messages]
      .reverse()
      .find((m) => m.role === "user");
    const query: string =
      lastUserMessage?.content.find((p) => p.type === "text")?.text ?? "";
    // Note: options.unstable_getMessage() cannot be safely called synchronously here
    // for just its id, so we extract assistantMessageId if passed or default
    const assistantMessageId = options.unstable_assistantMessageId;

    let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
    let fullText = "";
    useAuthCardStore.getState().clearAuth();

    try {
      // Get current idToken and refresh if close to expiry
      let idToken = useAuthStore.getState().idToken;
      if (idToken && isTokenExpiringSoon(idToken)) {
        const fresh = await acquireIdTokenSilently();
        if (fresh) {
          useAuthStore.getState().setIdToken(fresh);
          idToken = fresh;
        }
      }

      const headers: Record<string, string> = {
        Accept: "text/event-stream",
        "Content-Type": "application/json",
        "x-hw-agentarts-session-id": getSessionId(),
      };
      if (idToken) {
        headers["Authorization"] = `Bearer ${idToken}`;
        const userId = extractUserIdFromToken(idToken);
        if (userId) {
          headers["X-HW-AgentGateway-User-Id"] = userId;
        }
      }

      let response = await fetch(`${baseUrl}/invocations`, {
        method: "POST",
        headers,
        body: JSON.stringify({ message: query, stream: true }),
        signal: abortSignal,
      });

      // Token may have expired — try silent refresh once
      if ((response.status === 401 || response.status === 403) && idToken) {
        const freshToken = await acquireIdTokenSilently();
        if (freshToken) {
          useAuthStore.getState().setIdToken(freshToken);
          headers["Authorization"] = `Bearer ${freshToken}`;
          const userId = extractUserIdFromToken(freshToken);
          if (userId) {
            headers["X-HW-AgentGateway-User-Id"] = userId;
          }
          response = await fetch(`${baseUrl}/invocations`, {
            method: "POST",
            headers,
            body: JSON.stringify({ message: query, stream: true }),
            signal: abortSignal,
          });
        } else {
          useAuthStore.getState().clearToken();
          throw new Error("Authentication required. Please sign in.");
        }
      }

      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          useAuthStore.getState().clearToken();
          throw new Error("Authentication required. Please sign in.");
        }
        throw new Error(`Chat API error: ${response.status} ${response.statusText}`);
      }

      reader = response.body?.getReader();
      if (!reader) {
        throw new Error("No response body");
      }

      const decoder = new TextDecoder();
      let buffer = "";
      let isDone = false;

      while (!isDone) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        // Normalize CRLF / CR → LF per SSE spec
        buffer = buffer.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
        const lines = buffer.split("\n");
        // Keep the last partial line in the buffer
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          const raw = line.slice(5).trim();
          if (!raw) continue;

          try {
            const parsed: SSEEvent = JSON.parse(raw);

            if (parsed.error) {
              throw new Error(parsed.error);
            }

            if (typeof parsed.token === "string") {
              fullText += parsed.token;
              yield {
                content: [{ type: "text", text: fullText }],
              };
            }

            const systemMessage =
              typeof parsed.system_message === "string"
                ? parsed.system_message
                : "";
            const isAuthEvent =
              parsed.auth_required === true || parsed.auth_complete === true;

            // Auth events have a dedicated card and must not be duplicated in
            // the assistant message text.
            if (
              parsed.auth_required &&
              parsed.auth_url &&
              parsed.provider &&
              systemMessage.trim()
            ) {
              useAuthCardStore.getState().setAuth(
                assistantMessageId || "unknown",
                parsed.provider,
                parsed.auth_url,
                systemMessage,
              );
            }

            // Completion events are harmless when no matching pending card
            // exists, which lets the service emit them whenever a token is
            // available.
            if (parsed.auth_complete && parsed.provider) {
              useAuthCardStore
                .getState()
                .setAuthComplete(parsed.provider, systemMessage || undefined);
            }

            if (!isAuthEvent && systemMessage.trim()) {
              fullText += systemMessage;
              yield {
                content: [{ type: "text", text: fullText }],
              };
            }

            if (parsed.done) {
              isDone = true;
              break;
            }
          } catch (e) {
            // If JSON parsing threw, bubble it up (real errors).
            // If it was our own `throw` from parsed.error, bubble it too.
            if (e instanceof SyntaxError) continue;
            throw e;
          }
        }
      }
    } finally {
      reader?.releaseLock();
    }

    yield {
      content: [{ type: "text", text: fullText }],
      status: { type: "complete", reason: "stop" },
    };
  },
};
