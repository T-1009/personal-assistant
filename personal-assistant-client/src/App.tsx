import { useIsAuthenticated } from "@azure/msal-react";
import React, { Suspense, useCallback, useEffect, useRef } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useAuthCardStore } from "@/stores/auth-card-store";
import { completeOAuth2Auth } from "@/lib/auth/oauth2-complete";
import {
  CALENDAR_OAUTH_SUCCESS_MESSAGE,
  type CalendarOAuthRequest,
  createCalendarOAuthResponse,
  formatCalendarOAuthError,
  isCalendarOAuthRequest,
  openCalendarOAuthChannel,
} from "@/lib/auth/calendar-oauth-bridge";
import { AuthGuard } from "@/components/landing/AuthGuard";
import { LoadingState } from "@/components/landing/LoadingState";
import { ChunkErrorBoundary } from "@/components/landing/ChunkErrorBoundary";

const ChatPage = React.lazy(() => import("./components/chat/ChatPage"));
const LandingPage = React.lazy(() => import("./components/landing/LandingPage"));
const M365CalendarCallbackPage = React.lazy(
  () => import("./components/auth/M365CalendarCallbackPage"),
);

function App() {
  const isAuthenticated = useIsAuthenticated();
  const hydrated = useAuthStore((s) => s.hydrated);
  const idToken = useAuthStore((s) => s.idToken);
  const pendingCalendarOAuthRequests = useRef(
    new Map<string, CalendarOAuthRequest>(),
  );
  const calendarOAuthChannel = useRef<BroadcastChannel | null>(null);
  const canShowChat = isAuthenticated && Boolean(idToken);
  const isCalendarCallback =
    window.location.pathname === "/auth/callback/m365-calendar";

  const completeCalendarOAuthRequest = useCallback(
    async (request: CalendarOAuthRequest, channel: BroadcastChannel) => {
      const authState = useAuthStore.getState();
      if (!authState.hydrated || !authState.idToken) {
        pendingCalendarOAuthRequests.current.set(request.requestId, request);
        return;
      }

      try {
        await completeOAuth2Auth({
          provider: request.provider,
          session_uri: request.session_uri,
          state: request.state,
        });
        const message = CALENDAR_OAUTH_SUCCESS_MESSAGE;
        useAuthCardStore.getState().setAuthComplete(request.provider, message);
        channel.postMessage(
          createCalendarOAuthResponse({
            provider: request.provider,
            requestId: request.requestId,
            status: "complete",
            message,
          }),
        );
      } catch (error) {
        const message = formatCalendarOAuthError(error);
        useAuthCardStore.getState().setAuthFailed(request.provider, message);
        channel.postMessage(
          createCalendarOAuthResponse({
            provider: request.provider,
            requestId: request.requestId,
            status: "failed",
            message,
          }),
        );
      }
    },
    [],
  );

  useEffect(() => {
    if (isCalendarCallback) return;

    const channel = openCalendarOAuthChannel();
    calendarOAuthChannel.current = channel;
    if (!channel) return;

    channel.onmessage = (event) => {
      if (!isCalendarOAuthRequest(event.data)) return;
      void completeCalendarOAuthRequest(event.data, channel);
    };

    return () => {
      channel.close();
      if (calendarOAuthChannel.current === channel) {
        calendarOAuthChannel.current = null;
      }
    };
  }, [completeCalendarOAuthRequest, isCalendarCallback]);

  useEffect(() => {
    if (isCalendarCallback || !hydrated || !idToken) return;

    const channel = calendarOAuthChannel.current;
    if (!channel) return;

    const requests = Array.from(pendingCalendarOAuthRequests.current.values());
    pendingCalendarOAuthRequests.current.clear();
    for (const request of requests) {
      void completeCalendarOAuthRequest(request, channel);
    }
  }, [completeCalendarOAuthRequest, hydrated, idToken, isCalendarCallback]);

  if (isCalendarCallback) {
    return (
      <ChunkErrorBoundary>
        <Suspense fallback={<LoadingState />}>
          <M365CalendarCallbackPage />
        </Suspense>
      </ChunkErrorBoundary>
    );
  }

  return (
    <AuthGuard>
      <ChunkErrorBoundary>
        <Suspense fallback={<LoadingState />}>
          {!hydrated ? <LoadingState /> :
           canShowChat ? <ChatPage /> : <LandingPage />}
        </Suspense>
      </ChunkErrorBoundary>
    </AuthGuard>
  );
}

export default App;
