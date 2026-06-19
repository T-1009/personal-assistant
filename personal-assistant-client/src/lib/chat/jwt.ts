function decodeBase64Url(value: string): string {
  let base64 = value.replace(/-/g, "+").replace(/_/g, "/");
  while (base64.length % 4 !== 0) {
    base64 += "=";
  }

  const binary = atob(base64);
  return new TextDecoder().decode(
    Uint8Array.from(binary, (character) => character.charCodeAt(0)),
  );
}

function decodeJwtPayload(idToken: string): Record<string, unknown> {
  const encodedPayload = idToken.split(".")[1];
  if (!encodedPayload) {
    throw new Error("Invalid JWT");
  }
  return JSON.parse(decodeBase64Url(encodedPayload)) as Record<string, unknown>;
}

export function extractUserIdFromToken(
  idToken: string,
): string | undefined {
  try {
    const payload = decodeJwtPayload(idToken);
    const userId = payload.sub ?? payload.oid;
    return typeof userId === "string" ? userId : undefined;
  } catch {
    return undefined;
  }
}

/** Return true when the token expires within the next 60 seconds. */
export function isTokenExpiringSoon(idToken: string): boolean {
  try {
    const expiration = decodeJwtPayload(idToken).exp;
    return (
      typeof expiration !== "number" ||
      Date.now() >= (expiration - 60) * 1000
    );
  } catch {
    return true;
  }
}

