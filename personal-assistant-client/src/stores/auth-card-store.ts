import { create } from "zustand";

interface AuthCardState {
  /** OAuth authorization URL to open in a popup / new tab. */
  authUrl: string | null;
  /** Human-readable message explaining why authorization is needed. */
  message: string;
  setAuth: (url: string, message: string) => void;
  clearAuth: () => void;
}

export const useAuthCardStore = create<AuthCardState>((set) => ({
  authUrl: null,
  message: "",
  setAuth: (url, message) => set({ authUrl: url, message }),
  clearAuth: () => set({ authUrl: null, message: "" }),
}));
