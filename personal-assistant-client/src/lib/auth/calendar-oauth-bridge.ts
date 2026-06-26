export const CALENDAR_OAUTH_PROVIDER = "m365-calendar-provider";

export const CALENDAR_OAUTH_CHANNEL_NAME = "m365-calendar-auth";

export const CALENDAR_OAUTH_PENDING_MESSAGE =
  "正在完成日历授权，请稍候…";

export const CALENDAR_OAUTH_SUCCESS_MESSAGE =
  "日历授权已完成，可以关闭此窗口并重试刚才的问题。";

export const CALENDAR_OAUTH_FAILED_MESSAGE =
  "日历授权完成失败，请重新发起授权。";

export const CALENDAR_OAUTH_UNAVAILABLE_MESSAGE =
  "当前浏览器不支持日历授权回传，请返回原聊天窗口后重新发起授权。";

export const CALENDAR_OAUTH_MISSING_PARAMS_MESSAGE =
  "授权回调缺少必要参数，请重新发起日历授权。";

export const CALENDAR_OAUTH_TIMEOUT_MS = 15_000;

export interface CalendarOAuthRequest {
  type: "m365-calendar-auth-request";
  requestId: string;
  provider: string;
  session_uri: string;
  state: string;
}

export interface CalendarOAuthResponse {
  type: "m365-calendar-auth-response";
  requestId: string;
  provider: string;
  status: "complete" | "failed";
  message: string;
}

export type CalendarOAuthMessage =
  | CalendarOAuthRequest
  | CalendarOAuthResponse;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

export function openCalendarOAuthChannel(): BroadcastChannel | null {
  if (typeof window === "undefined" || typeof BroadcastChannel === "undefined") {
    return null;
  }

  try {
    return new BroadcastChannel(CALENDAR_OAUTH_CHANNEL_NAME);
  } catch {
    return null;
  }
}

export function createCalendarOAuthRequest(input: {
  provider?: string;
  requestId?: string;
  sessionUri: string;
  state: string;
}): CalendarOAuthRequest {
  return {
    type: "m365-calendar-auth-request",
    requestId: input.requestId ?? input.state,
    provider: input.provider ?? CALENDAR_OAUTH_PROVIDER,
    session_uri: input.sessionUri,
    state: input.state,
  };
}

export function createCalendarOAuthResponse(input: {
  provider: string;
  requestId: string;
  status: "complete" | "failed";
  message: string;
}): CalendarOAuthResponse {
  return {
    type: "m365-calendar-auth-response",
    requestId: input.requestId,
    provider: input.provider,
    status: input.status,
    message: input.message,
  };
}

export function isCalendarOAuthRequest(
  value: unknown,
): value is CalendarOAuthRequest {
  if (!isRecord(value) || value.type !== "m365-calendar-auth-request") {
    return false;
  }

  return (
    isString(value.requestId) &&
    isString(value.provider) &&
    isString(value.session_uri) &&
    isString(value.state)
  );
}

export function isCalendarOAuthResponse(
  value: unknown,
): value is CalendarOAuthResponse {
  if (!isRecord(value) || value.type !== "m365-calendar-auth-response") {
    return false;
  }

  return (
    isString(value.requestId) &&
    isString(value.provider) &&
    (value.status === "complete" || value.status === "failed") &&
    isString(value.message)
  );
}

export function formatCalendarOAuthError(error: unknown): string {
  const message = error instanceof Error ? error.message.trim() : "";
  if (!message) {
    return CALENDAR_OAUTH_FAILED_MESSAGE;
  }

  if (
    message.includes("Missing X-HW-AgentGateway-User-Id header") ||
    message.includes("Authentication required")
  ) {
    return "请保持原聊天窗口处于登录状态后，再重新完成日历授权。";
  }

  return message;
}
