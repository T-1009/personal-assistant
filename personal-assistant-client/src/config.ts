interface PublicEnv {
  readonly VITE_ENTRA_CLIENT_ID?: string;
  readonly VITE_ENTRA_TENANT_ID?: string;
}

export interface PublicConfig {
  readonly entraClientId: string;
  readonly entraTenantId: string;
  readonly isEntraEnabled: boolean;
}

function normalized(value: string | undefined): string {
  return value?.trim() ?? "";
}

/**
 * Browser-visible, build-time configuration.
 *
 * VITE_* values are embedded in the JavaScript bundle and must never contain
 * secrets. Server-side Pages Function settings belong in `context.env`.
 */
export function getPublicConfig(env: PublicEnv = import.meta.env): PublicConfig {
  const entraClientId = normalized(env.VITE_ENTRA_CLIENT_ID);
  const entraTenantId = normalized(env.VITE_ENTRA_TENANT_ID) || "common";

  return {
    entraClientId,
    entraTenantId,
    isEntraEnabled: entraClientId.length > 0,
  };
}
