import type {
  ChatModelAdapter,
  ChatModelRunOptions,
  ChatModelRunResult,
} from "@assistant-ui/react";
import { handleChatEvent } from "@/lib/chat/chat-event-handler";
import {
  cancelChat,
  ChatApiError,
  invokeChat,
} from "@/lib/chat/chat-api-client";
import { parseSSEStream } from "@/lib/chat/sse-parser";

/**
 * ChatModelAdapter that connects to the backend SSE API.
 *
 * Requests use `/invocations` in every environment. The Vite dev proxy
 * forwards them to the local service, while the production Cloudflare Pages
 * Function forwards them to AgentArts Runtime.
 */
type ConversationIdResolver = (
  options: ChatModelRunOptions,
) => string | undefined | Promise<string | undefined>;
type DuplicateMessageHandler = (conversationId: string) => void;
type CancellationResult =
  | { ok: true }
  | { ok: false; error: unknown };
type PendingCancellation = {
  clientMessageId: string;
  result: Promise<CancellationResult>;
};

const defaultConversationIdResolver: ConversationIdResolver = (options) =>
  options.unstable_threadId;
const pendingCancellations = new Map<string, PendingCancellation>();

function startCancellation(
  conversationId: string,
  clientMessageId: string,
): PendingCancellation {
  return {
    clientMessageId,
    result: cancelChat(conversationId, clientMessageId).then(
      () => ({ ok: true }),
      (error: unknown) => {
        console.error("Failed to cancel Invocation", error);
        return { ok: false, error };
      },
    ),
  };
}

function trackCancellation(
  conversationId: string,
  clientMessageId: string,
): void {
  const pending = startCancellation(conversationId, clientMessageId);
  pendingCancellations.set(conversationId, pending);
  void pending.result.then((result) => {
    if (result.ok && pendingCancellations.get(conversationId) === pending) {
      pendingCancellations.delete(conversationId);
    }
  });
}

async function waitForPendingCancellation(conversationId: string): Promise<void> {
  let pending = pendingCancellations.get(conversationId);
  if (!pending) return;

  let result = await pending.result;
  if (!result.ok) {
    const current = pendingCancellations.get(conversationId);
    if (current === pending) {
      const retry = startCancellation(conversationId, pending.clientMessageId);
      pendingCancellations.set(conversationId, retry);
      pending = retry;
    } else if (current) {
      pending = current;
    }
    result = await pending.result;
  }

  if (result.ok) {
    if (pendingCancellations.get(conversationId) === pending) {
      pendingCancellations.delete(conversationId);
    }
  } else {
    throw result.error;
  }
}

async function* runChat(
  options: ChatModelRunOptions,
  resolveConversationId: ConversationIdResolver,
  onDuplicateMessage?: DuplicateMessageHandler,
): AsyncGenerator<ChatModelRunResult, void> {
    const { messages, abortSignal } = options;
    const lastUserMessage = [...messages]
      .reverse()
      .find((m) => m.role === "user");
    const query: string =
      lastUserMessage?.content.find((p) => p.type === "text")?.text ?? "";
    const assistantMessageId =
      options.unstable_assistantMessageId ?? "unknown";
    const conversationId = await resolveConversationId(options);
    if (!conversationId) {
      throw new Error("Conversation initialization did not return an ID.");
    }
    await waitForPendingCancellation(conversationId);
    const clientMessageId = crypto.randomUUID();
    let fullText = "";
    let completed = false;
    let invocationStarted = false;
    let cancellationStarted = false;

    const handleAbort = () => {
      if (!invocationStarted || cancellationStarted) return;
      cancellationStarted = true;
      trackCancellation(conversationId, clientMessageId);
    };
    abortSignal.addEventListener("abort", handleAbort, { once: true });

    try {
      invocationStarted = true;
      if (abortSignal.aborted) handleAbort();

      let stream: ReadableStream<Uint8Array>;
      try {
        stream = await invokeChat(
          query,
          conversationId,
          clientMessageId,
          abortSignal,
        );
      } catch (error) {
        if (
          error instanceof ChatApiError &&
          error.code === "duplicate_message"
        ) {
          onDuplicateMessage?.(conversationId);
        }
        throw error;
      }

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

        if (result.done) {
          completed = true;
          break;
        }
      }
    } finally {
      abortSignal.removeEventListener("abort", handleAbort);
    }

    if (!completed) {
      throw new Error("The chat stream ended before a completion event.");
    }

    yield {
      content: [{ type: "text", text: fullText }],
      status: { type: "complete", reason: "stop" },
    };
}

export function createChatAdapter(
  resolveConversationId: ConversationIdResolver = defaultConversationIdResolver,
  onDuplicateMessage?: DuplicateMessageHandler,
): ChatModelAdapter {
  return {
    run(options) {
      return runChat(options, resolveConversationId, onDuplicateMessage);
    },
  };
}

export const chatAdapter = createChatAdapter();
