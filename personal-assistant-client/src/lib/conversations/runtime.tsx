import {
  RuntimeAdapterProvider,
  useAuiState,
  type RemoteThreadListAdapter,
  type ThreadHistoryAdapter,
  type ThreadMessage,
} from "@assistant-ui/react";
import { type PropsWithChildren, useMemo } from "react";
import { useConversationListStore } from "@/stores/conversation-list-store";
import {
  createConversation,
  deleteConversation,
  getConversation,
  listConversations,
  loadConversationHistory,
  patchConversation,
} from "./api";

interface PageCursor {
  active?: string;
  archived?: string;
  activeDone?: boolean;
  archivedDone?: boolean;
}

function encodePageCursor(cursor: PageCursor): string {
  return encodeURIComponent(JSON.stringify(cursor));
}

function decodePageCursor(value: string | undefined): PageCursor {
  if (!value) return {};
  try {
    const parsed = JSON.parse(decodeURIComponent(value)) as PageCursor;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function firstUserTitle(messages: readonly ThreadMessage[]): string {
  const text = messages
    .find((message) => message.role === "user")
    ?.content.find((part) => part.type === "text")?.text;
  return text?.trim().replace(/\s+/g, " ").slice(0, 60) || "新对话";
}

function createHistoryAdapter(
  conversationId: string | undefined,
): ThreadHistoryAdapter {
  return {
    async load() {
      if (!conversationId) return { headId: null, messages: [] };
      return loadConversationHistory(conversationId);
    },
    async append() {
      // InvocationService is the only writer for durable messages.
    },
  };
}

function ConversationThreadProvider({ children }: PropsWithChildren) {
  const conversationId = useAuiState(
    (state) => state.threadListItem.remoteId,
  );
  const history = useMemo(
    () => createHistoryAdapter(conversationId),
    [conversationId],
  );
  const adapters = useMemo(() => ({ history }), [history]);
  return (
    <RuntimeAdapterProvider adapters={adapters}>
      {children}
    </RuntimeAdapterProvider>
  );
}

const conversationThreadListAdapter: RemoteThreadListAdapter = {
  async list(options) {
    useConversationListStore.getState().setError(null);
    try {
      const cursor = decodePageCursor(options?.after);
      const [active, archived] = await Promise.all([
        cursor.activeDone
          ? Promise.resolve({ items: [], nextCursor: undefined })
          : listConversations("active", cursor.active),
        cursor.archivedDone
          ? Promise.resolve({ items: [], nextCursor: undefined })
          : listConversations("archived", cursor.archived),
      ]);
      const next: PageCursor = {
        active: active.nextCursor,
        archived: archived.nextCursor,
        activeDone: !active.nextCursor,
        archivedDone: !archived.nextCursor,
      };
      const hasMore = !next.activeDone || !next.archivedDone;

      return {
        threads: [...active.items, ...archived.items].map((item) => ({
          status: item.status === "archived" ? "archived" : "regular",
          remoteId: item.id,
          externalId: item.id,
          title: item.title,
          lastMessageAt: item.updatedAt,
        })),
        nextCursor: hasMore ? encodePageCursor(next) : undefined,
      };
    } catch (error) {
      useConversationListStore
        .getState()
        .setError(
          error instanceof Error
            ? error.message
            : "Conversations could not be loaded.",
        );
      throw error;
    }
  },
  async initialize() {
    const conversation = await createConversation();
    return { remoteId: conversation.id, externalId: conversation.id };
  },
  async rename(remoteId, newTitle) {
    await patchConversation(remoteId, { title: newTitle });
  },
  async archive(remoteId) {
    await patchConversation(remoteId, { status: "archived" });
  },
  async unarchive(remoteId) {
    await patchConversation(remoteId, { status: "active" });
  },
  delete: deleteConversation,
  async fetch(remoteId) {
    const item = await getConversation(remoteId);
    return {
      status: item.status === "archived" ? "archived" : "regular",
      remoteId: item.id,
      externalId: item.id,
      title: item.title,
      lastMessageAt: item.updatedAt,
    };
  },
  async generateTitle(remoteId, messages) {
    const title = firstUserTitle(messages);
    await patchConversation(remoteId, { title });
    return new ReadableStream({
      start(controller) {
        controller.enqueue({
          type: "part-start",
          path: [0],
          part: { type: "text" },
        });
        controller.enqueue({ type: "text-delta", path: [0], textDelta: title });
        controller.enqueue({ type: "part-finish", path: [0] });
        controller.close();
      },
    });
  },
  unstable_Provider: ConversationThreadProvider,
};

export function createConversationThreadListAdapter(): RemoteThreadListAdapter {
  let initialListSettled: Promise<void> | undefined;

  return {
    ...conversationThreadListAdapter,
    list(options) {
      const request = conversationThreadListAdapter.list(options);
      if (!options?.after && !initialListSettled) {
        initialListSettled = request.then(
          () => undefined,
          () => undefined,
        );
      }
      return request;
    },
    async initialize(threadId) {
      await initialListSettled;
      return conversationThreadListAdapter.initialize(threadId);
    },
  };
}
