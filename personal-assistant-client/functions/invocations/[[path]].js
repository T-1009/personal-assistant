const FORWARDED_HEADERS = [
  "accept",
  "authorization",
  "content-type",
  "x-hw-agentarts-session-id",
  "x-hw-agentgateway-user-id",
];
const CALLBACK_AUTH_COOKIE = "pa_oauth2_callback_auth";
const CALLBACK_SESSION_COOKIE = "pa_oauth2_callback_session";
const CALLBACK_USER_COOKIE = "pa_oauth2_callback_user";
const CALLBACK_AUTH_COOKIE_MAX_AGE_SECONDS = 600;
const CALLBACK_AUTH_COOKIE_PATH = "/auth/callback/m365-calendar";

function buildCallbackContextCookie(name, value) {
  const trimmed = value?.trim();
  if (!trimmed) return null;

  return [
    `${name}=${encodeURIComponent(trimmed)}`,
    `Max-Age=${CALLBACK_AUTH_COOKIE_MAX_AGE_SECONDS}`,
    `Path=${CALLBACK_AUTH_COOKIE_PATH}`,
    "HttpOnly",
    "Secure",
    "SameSite=Lax",
  ].join("; ");
}

function buildCallbackContextCookies(request) {
  const cookies = [
    buildCallbackContextCookie(
      CALLBACK_AUTH_COOKIE,
      request.headers.get("Authorization"),
    ),
    buildCallbackContextCookie(
      CALLBACK_SESSION_COOKIE,
      request.headers.get("x-hw-agentarts-session-id"),
    ),
    buildCallbackContextCookie(
      CALLBACK_USER_COOKIE,
      request.headers.get("X-HW-AgentGateway-User-Id"),
    ),
  ];
  return cookies.filter(Boolean);
}

function buildExpiredCallbackContextCookie(name) {
  return [
    `${name}=`,
    "Max-Age=0",
    `Path=${CALLBACK_AUTH_COOKIE_PATH}`,
    "HttpOnly",
    "Secure",
    "SameSite=Lax",
  ].join("; ");
}

export function buildExpiredCallbackContextCookies() {
  return [
    buildExpiredCallbackContextCookie(CALLBACK_AUTH_COOKIE),
    buildExpiredCallbackContextCookie(CALLBACK_SESSION_COOKIE),
    buildExpiredCallbackContextCookie(CALLBACK_USER_COOKIE),
  ];
}

export function applyCallbackContextCookies(headers, request) {
  const cookies = buildCallbackContextCookies(request);
  if (!cookies.length) return;

  for (const cookie of cookies) {
    headers.append("Set-Cookie", cookie);
  }
}

export function applyExpiredCallbackContextCookies(headers) {
  for (const cookie of buildExpiredCallbackContextCookies()) {
    headers.append("Set-Cookie", cookie);
  }
}

export function getCallbackContextFromCookies(request) {
  const cookieHeader = request.headers.get("Cookie");
  if (!cookieHeader) {
    return {};
  }

  const cookies = {};
  for (const part of cookieHeader.split(";")) {
    const [rawKey, ...rawValue] = part.trim().split("=");
    if (!rawKey) continue;
    cookies[rawKey] = decodeURIComponent(rawValue.join("="));
  }

  return {
    authorization: cookies[CALLBACK_AUTH_COOKIE],
    sessionId: cookies[CALLBACK_SESSION_COOKIE],
    userId: cookies[CALLBACK_USER_COOKIE],
  };
}

export function applyCallbackContextHeaders(headers, request) {
  const context = getCallbackContextFromCookies(request);
  if (context.authorization) {
    headers.set("Authorization", context.authorization);
  }
  if (context.sessionId) {
    headers.set("x-hw-agentarts-session-id", context.sessionId);
  }
  if (context.userId) {
    headers.set("X-HW-AgentGateway-User-Id", context.userId);
  }
}

function getInvocationsUrl(env) {
  const value = env?.AGENTARTS_INVOCATIONS_URL?.trim();
  if (!value) {
    throw new Error("AGENTARTS_INVOCATIONS_URL is not configured");
  }

  const url = new URL(value);
  if (url.protocol !== "https:" && url.protocol !== "http:") {
    throw new Error("AGENTARTS_INVOCATIONS_URL must use http or https");
  }
  return url;
}

export function buildUpstreamUrl(
  env,
  requestUrl,
  { publicPrefix = "/invocations", upstreamPrefix = "" } = {},
) {
  const invocationsUrl = getInvocationsUrl(env);
  const incomingUrl = new URL(requestUrl);
  const incomingPath = incomingUrl.pathname;
  if (
    incomingPath !== publicPrefix &&
    !incomingPath.startsWith(`${publicPrefix}/`)
  ) {
    throw new Error("Unsupported invocations proxy path");
  }

  const basePath = invocationsUrl.pathname.replace(/\/$/, "");
  const normalizedUpstreamPrefix = upstreamPrefix
    ? `/${upstreamPrefix.replace(/^\/|\/$/g, "")}`
    : "";
  const suffix = incomingPath.slice(publicPrefix.length);
  invocationsUrl.pathname = `${basePath}${normalizedUpstreamPrefix}${suffix}`;
  invocationsUrl.search = incomingUrl.search;
  return invocationsUrl;
}

export async function proxyInvocationsRequest({
  request,
  env,
  publicPrefix,
  upstreamPrefix,
}) {
  try {
    const upstreamUrl = buildUpstreamUrl(env, request.url, {
      publicPrefix,
      upstreamPrefix,
    });
    const headers = new Headers();
    for (const name of FORWARDED_HEADERS) {
      const value = request.headers.get(name);
      if (value) headers.set(name, value);
    }

    const init = {
      method: request.method,
      headers,
      redirect: "manual",
    };
    if (request.method !== "GET" && request.method !== "HEAD") {
      init.body = await request.arrayBuffer();
    }

    const upstreamRequest = new Request(upstreamUrl, init);
    const upstreamResponse = await fetch(upstreamRequest);
    const responseHeaders = new Headers(upstreamResponse.headers);
    applyCallbackContextCookies(responseHeaders, request);

    responseHeaders.set("Cache-Control", "no-store");

    return new Response(upstreamResponse.body, {
      status: upstreamResponse.status,
      statusText: upstreamResponse.statusText,
      headers: responseHeaders,
    });
  } catch (error) {
    console.error("AgentArts proxy request failed", error);
    if (
      error instanceof Error &&
      error.message.startsWith("AGENTARTS_INVOCATIONS_URL")
    ) {
      return Response.json(
        { message: "Frontend proxy is not configured" },
        { status: 500 },
      );
    }
    if (
      error instanceof Error &&
      error.message.startsWith("Unsupported invocations proxy path")
    ) {
      return Response.json(
        { message: "Unsupported proxy path" },
        { status: 404 },
      );
    }
    return Response.json(
      { message: "AgentArts Gateway is unavailable" },
      { status: 502 },
    );
  }
}

export async function onRequestPost({ request, env }) {
  return proxyInvocationsRequest({ request, env });
}

export async function onRequestGet({ request, env }) {
  return proxyInvocationsRequest({ request, env });
}
