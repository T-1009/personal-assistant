const AGENTARTS_INVOCATIONS_URL =
  "https://defaultgw-ha3wenzqga.cn-southwest-2.huaweicloud-agentarts.com/runtimes/personal-assistant/invocations";
const FORWARDED_HEADERS = [
  "accept",
  "authorization",
  "content-type",
  "x-hw-agentarts-session-id",
  "x-hw-agentgateway-user-id",
];

export async function onRequestPost({ request }) {
  try {
    const headers = new Headers();
    for (const name of FORWARDED_HEADERS) {
      const value = request.headers.get(name);
      if (value) headers.set(name, value);
    }

    const upstreamRequest = new Request(AGENTARTS_INVOCATIONS_URL, {
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
    return Response.json(
      { message: "AgentArts Gateway is unavailable" },
      { status: 502 },
    );
  }
}
