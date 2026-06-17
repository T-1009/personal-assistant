import { create } from "zustand";

interface AuthCardState {
  /** OAuth authorization URL to open in a popup / new tab. */
  authUrl: string | null;
  /** Human-readable message explaining why authorization is needed. */
  message: string;
  /** Whether the user has completed authorization (green card). */
  authComplete: boolean;
  setAuth: (url: string, message: string) => void;
  setAuthComplete: (complete: boolean) => void;
  clearAuth: () => void;
}

export const useAuthCardStore = create<AuthCardState>((set) => ({
  authUrl: null,
  message: "",
  authComplete: false,
  setAuth: (url, message) =>
    set({ authUrl: url, message, authComplete: false }),
  setAuthComplete: (complete) => set({ authComplete: complete }),
  clearAuth: () => set({ authUrl: null, message: "", authComplete: false }),
}));
