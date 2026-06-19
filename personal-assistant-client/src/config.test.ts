import { describe, expect, it } from "vitest";

import { getPublicConfig } from "./config";

describe("getPublicConfig", () => {
  it("normalizes configured Entra values", () => {
    expect(
      getPublicConfig({
        VITE_ENTRA_CLIENT_ID: " client-id ",
        VITE_ENTRA_TENANT_ID: " tenant-id ",
      }),
    ).toEqual({
      entraClientId: "client-id",
      entraTenantId: "tenant-id",
      isEntraEnabled: true,
    });
  });

  it("uses dev mode and the common tenant when Entra is not configured", () => {
    expect(getPublicConfig({})).toEqual({
      entraClientId: "",
      entraTenantId: "common",
      isEntraEnabled: false,
    });
  });
});
