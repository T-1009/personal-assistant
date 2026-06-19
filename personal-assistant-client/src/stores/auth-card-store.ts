import { create } from "zustand";

interface AuthCardState {
  /** The message ID associated with this auth request */
  messageId: string | null;
  /** OAuth provider associated with the pending authorization request. */
  provider: string | null;
  /** OAuth authorization URL to open in a popup / new tab. */
  authUrl: string | null;
  /** Human-readable message explaining why authorization is needed. */
  message: string;
  /** Whether the user has completed authorization (green card). */
  authComplete: boolean;
  setAuth: (
    messageId: string,
    provider: string,
    url: string,
    message: string,
  ) => void;
  setAuthComplete: (provider: string, message?: string) => void;
  clearAuth: () => void;
}

export const useAuthCardStore = create<AuthCardState>((set) => ({
  messageId: null,
  provider: null,
  authUrl: null,
  message: "",
  authComplete: false,
  setAuth: (messageId, provider, url, message) =>
    set({
      messageId,
      provider,
      authUrl: url,
      message,
      authComplete: false,
    }),
  setAuthComplete: (provider, message) =>
    set((state) => {
      if (!state.authUrl || state.provider !== provider) {
        return state;
      }
      return {
        authComplete: true,
        message: message ?? state.message,
      };
    }),
  clearAuth: () =>
    set({
      messageId: null,
      provider: null,
      authUrl: null,
      message: "",
      authComplete: false,
    }),
}));
