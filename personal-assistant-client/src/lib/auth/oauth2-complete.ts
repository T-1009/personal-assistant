import { buildHeaders, getRequestToken } from "@/lib/chat/chat-api-client";

export interface OAuth2CompletePayload {
  provider: string;
  session_uri: string;
  state: string;
  error?: string | null;
  error_description?: string | null;
}

export interface OAuth2CompleteResult {
  status: "complete" | "already_complete";
  provider: string;
  message: string;
}

export async function completeOAuth2Auth(
  payload: OAuth2CompletePayload,
): Promise<OAuth2CompleteResult> {
  const idToken = await getRequestToken();
  const headers = buildHeaders(idToken);
  headers.Accept = "application/json";

  const response = await fetch("/invocations/auth/oauth2/complete", {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let detail = `OAuth2 complete failed: ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // Keep the safe generic message.
    }
    throw new Error(detail);
  }

  return (await response.json()) as OAuth2CompleteResult;
}
