import { create } from "zustand";

interface AuthCardState {
  /** The message ID associated with this auth request */
  messageId: string | null;
  /** OAuth authorization URL to open in a popup / new tab. */
  authUrl: string | null;
  /** Human-readable message explaining why authorization is needed. */
  message: string;
  /** Whether the user has completed authorization (green card). */
  authComplete: boolean;
  setAuth: (messageId: string, url: string, message: string) => void;
  setAuthComplete: (complete: boolean, message?: string) => void;
  clearAuth: () => void;
}

export const useAuthCardStore = create<AuthCardState>((set) => ({
  messageId: null,
  authUrl: null,
  message: "",
  authComplete: false,
  setAuth: (messageId, url, message) =>
    set({ messageId, authUrl: url, message, authComplete: false }),
  setAuthComplete: (complete, message) => 
    set((state) => ({ authComplete: complete, message: message ?? state.message })),
  clearAuth: () => set({ messageId: null, authUrl: null, message: "", authComplete: false }),
}));
