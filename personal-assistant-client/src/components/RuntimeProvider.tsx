import { type ReactNode } from "react";
import {
  useLocalRuntime,
  AssistantRuntimeProvider,
} from "@assistant-ui/react";
import { chatAdapter } from "../lib/chat-adapter";

export function RuntimeProvider({ children }: { children: ReactNode }) {
  const runtime = useLocalRuntime(chatAdapter);
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {children}
    </AssistantRuntimeProvider>
  );
}
