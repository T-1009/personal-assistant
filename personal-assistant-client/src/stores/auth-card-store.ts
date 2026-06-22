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
  /** Whether the latest authorization attempt failed (red card). */
  authFailed: boolean;
  setAuth: (
    messageId: string,
    provider: string,
    url: string,
    message: string,
  ) => void;
  setAuthComplete: (provider: string, message?: string) => void;
  setAuthFailed: (provider: string, message?: string) => void;
  clearAuth: () => void;
}

export const useAuthCardStore = create<AuthCardState>((set) => ({
  messageId: null,
  provider: null,
  authUrl: null,
  message: "",
  authComplete: false,
  authFailed: false,
  setAuth: (messageId, provider, url, message) =>
    set({
      messageId,
      provider,
      authUrl: url,
      message,
      authComplete: false,
      authFailed: false,
    }),
  setAuthComplete: (provider, message) =>
    set((state) => {
      if (!state.authUrl || state.provider !== provider) {
        return state;
      }
      return {
        authComplete: true,
        authFailed: false,
        message: message ?? state.message,
      };
    }),
  setAuthFailed: (provider, message) =>
    set((state) => {
      if (!state.authUrl || state.provider !== provider) {
        return state;
      }
      return {
        authComplete: false,
        authFailed: true,
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
      authFailed: false,
    }),
}));
