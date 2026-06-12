import { useMsal, useIsAuthenticated } from "@azure/msal-react";
import { loginRequest } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { LogIn, LogOut } from "lucide-react";
import { useMemo } from "react";

/** Extract initials from a display name (e.g. "John Doe" → "JD", "Alice" → "A") */
function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }
  return (parts[0]?.[0] ?? "?").toUpperCase();
}

/** Deterministic color from a string (for avatar background) */
function avatarColor(name: string): string {
  const colors = [
    "bg-blue-500", "bg-green-500", "bg-purple-500", "bg-amber-500",
    "bg-rose-500", "bg-cyan-500", "bg-indigo-500", "bg-teal-500",
  ];
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return colors[Math.abs(hash) % colors.length];
}

export function LoginButton() {
  const { instance, accounts } = useMsal();
  const isAuthenticated = useIsAuthenticated();

  const account = accounts[0];
  const displayName = account?.name ?? account?.username ?? "";
  const initials = useMemo(() => getInitials(displayName), [displayName]);

  // Dev mode: MSAL not configured → skip OAuth
  if (!import.meta.env.VITE_ENTRA_CLIENT_ID) {
    return (
      <span className="text-xs text-muted-foreground">
        Dev Mode — Proxy auth enabled
      </span>
    );
  }

  const handleLogin = async () => {
    try {
      await instance.loginRedirect(loginRequest);
      // Redirect back → handleRedirectPromise() in main.tsx processes the token
      // → LOGIN_SUCCESS event fires → zustand auto-synced
    } catch (e) {
      console.error("Login failed:", e);
    }
  };

  const handleLogout = async () => {
      await instance.logoutRedirect();
      // Redirect back → LOGOUT_SUCCESS event → zustand cleared (see main.tsx)
  };

  if (isAuthenticated) {
    return (
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div
            className={`${avatarColor(displayName)} flex h-7 w-7 items-center justify-center rounded-full text-xs font-medium text-white`}
            title={displayName}
          >
            {initials}
          </div>
          <span className="text-sm font-medium text-foreground max-w-[120px] truncate">
            {displayName}
          </span>
        </div>
        <Button variant="outline" size="sm" onClick={handleLogout}>
          <LogOut className="mr-2 h-4 w-4" />
          Logout
        </Button>
      </div>
    );
  }

  return (
    <Button variant="default" size="sm" onClick={handleLogin}>
      <LogIn className="mr-2 h-4 w-4" />
      Sign in with Microsoft
    </Button>
  );
}
