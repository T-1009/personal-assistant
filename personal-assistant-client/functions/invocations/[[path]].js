const FORWARDED_HEADERS = [
  "accept",
  "authorization",
  "content-type",
  "x-hw-agentarts-session-id",
  "x-hw-agentgateway-user-id",
];
const CALLBACK_AUTH_COOKIE = "pa_oauth2_callback_auth";
const CALLBACK_AUTH_COOKIE_MAX_AGE_SECONDS = 600;
const CALLBACK_AUTH_COOKIE_PATH = "/auth/callback/m365-calendar";

function buildCallbackAuthCookie(authorization) {
  const value = authorization?.trim();
  if (!value) return null;

  return [
    `${CALLBACK_AUTH_COOKIE}=${encodeURIComponent(value)}`,
    `Max-Age=${CALLBACK_AUTH_COOKIE_MAX_AGE_SECONDS}`,
    `Path=${CALLBACK_AUTH_COOKIE_PATH}`,
    "HttpOnly",
    "Secure",
    "SameSite=Lax",
  ].join("; ");
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
    const callbackAuthCookie = buildCallbackAuthCookie(
      request.headers.get("Authorization"),
    );
    if (callbackAuthCookie) {
      responseHeaders.append("Set-Cookie", callbackAuthCookie);
    }

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
