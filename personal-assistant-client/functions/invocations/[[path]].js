const FORWARDED_HEADERS = [
  "accept",
  "authorization",
  "content-type",
  "x-hw-agentarts-session-id",
  "x-hw-agentgateway-user-id",
];

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

function buildUpstreamUrl(env, requestUrl) {
  const invocationsUrl = getInvocationsUrl(env);
  const incomingUrl = new URL(requestUrl);
  const prefix = "/invocations";
  const incomingPath = incomingUrl.pathname;
  if (incomingPath !== prefix && !incomingPath.startsWith(`${prefix}/`)) {
    throw new Error("Unsupported invocations proxy path");
  }

  const basePath = invocationsUrl.pathname.replace(/\/$/, "");
  const suffix = incomingPath.slice(prefix.length);
  invocationsUrl.pathname = `${basePath}${suffix}`;
  invocationsUrl.search = incomingUrl.search;
  return invocationsUrl;
}

export async function onRequestPost({ request, env }) {
  try {
    const upstreamUrl = buildUpstreamUrl(env, request.url);
    const headers = new Headers();
    for (const name of FORWARDED_HEADERS) {
      const value = request.headers.get(name);
      if (value) headers.set(name, value);
    }

    const upstreamRequest = new Request(upstreamUrl, {
      method: request.method,
      headers,
      body: await request.arrayBuffer(),
      redirect: "manual",
    });
    const upstreamResponse = await fetch(upstreamRequest);
    const responseHeaders = new Headers(upstreamResponse.headers);

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
    return Response.json(
      { message: "AgentArts Gateway is unavailable" },
      { status: 502 },
    );
  }
}
