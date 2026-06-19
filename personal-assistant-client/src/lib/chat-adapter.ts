import type {
  ChatModelAdapter,
  ChatModelRunOptions,
  ChatModelRunResult,
} from "@assistant-ui/react";
import { handleChatEvent } from "@/lib/chat/chat-event-handler";
import { invokeChat } from "@/lib/chat/chat-api-client";
import { parseSSEStream } from "@/lib/chat/sse-parser";
import { useAuthCardStore } from "@/stores/auth-card-store";
export { getSessionId, resetSessionId } from "@/lib/chat/session";

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
    const lastUserMessage = [...messages]
      .reverse()
      .find((m) => m.role === "user");
    const query: string =
      lastUserMessage?.content.find((p) => p.type === "text")?.text ?? "";
    const assistantMessageId =
      options.unstable_assistantMessageId ?? "unknown";
    let fullText = "";

    useAuthCardStore.getState().clearAuth();
    const stream = await invokeChat(query, abortSignal);

    for await (const event of parseSSEStream(stream)) {
      const result = handleChatEvent(event, {
        assistantMessageId,
        fullText,
      });
      fullText = result.fullText;

      for (const text of result.contentUpdates) {
        yield {
          content: [{ type: "text", text }],
        };
      }

      if (result.done) break;
    }

    yield {
      content: [{ type: "text", text: fullText }],
      status: { type: "complete", reason: "stop" },
    };
  },
};
