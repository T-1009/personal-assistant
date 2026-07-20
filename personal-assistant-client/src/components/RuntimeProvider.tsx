import { type ReactNode, useMemo } from "react";
import {
  AssistantRuntimeProvider,
  useAui,
  useLocalRuntime,
  useRemoteThreadListRuntime,
} from "@assistant-ui/react";
import { createChatAdapter } from "../lib/chat-adapter";
import { conversationThreadListAdapter } from "@/lib/conversations/runtime";
import { loadConversationHistory } from "@/lib/conversations/api";

function useConversationThreadRuntime() {
  const aui = useAui();
  const adapter = useMemo(
    () =>
      createChatAdapter(
        async () => {
          const item = aui.threadListItem();
          const current = item.getState().remoteId;
          if (current) return current;
          return (await item.initialize()).remoteId;
        },
        (conversationId) => {
          void loadConversationHistory(conversationId)
            .then((history) => {
              aui.thread().import(history);
            })
            .catch((error) => {
              console.error("Failed to refresh Conversation history", error);
            });
        },
      ),
    [aui],
  );
  return useLocalRuntime(adapter);
}

export function RuntimeProvider({ children }: { children: ReactNode }) {
  const runtime = useRemoteThreadListRuntime({
    runtimeHook: useConversationThreadRuntime,
    adapter: conversationThreadListAdapter,
  });
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {children}
    </AssistantRuntimeProvider>
  );
}
