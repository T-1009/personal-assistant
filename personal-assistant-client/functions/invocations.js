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

export async function onRequestPost({ request, env }) {
  try {
    const invocationsUrl = getInvocationsUrl(env);
    const headers = new Headers();
    for (const name of FORWARDED_HEADERS) {
      const value = request.headers.get(name);
      if (value) headers.set(name, value);
    }

    const upstreamRequest = new Request(invocationsUrl, {
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
