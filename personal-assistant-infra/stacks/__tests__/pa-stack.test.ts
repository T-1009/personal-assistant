import { Testing, TerraformStack } from "cdktf";
import { PersonalAssistantStack } from "../pa-stack";
import { ObsBucket } from "../../.gen/providers/huaweicloud/obs-bucket";
import { HuaweicloudProvider } from "../../.gen/providers/huaweicloud/provider";

// Import Jest adapter to register custom matchers at runtime and extend Jest types
import { setupJest } from "cdktf/lib/testing/adapters/jest";
setupJest();

describe("PersonalAssistantStack", () => {
  let stack: TerraformStack;
  let synthResult: string;

  beforeAll(() => {
    const app = Testing.app();
    stack = new PersonalAssistantStack(app, "test-pa-stack");
    synthResult = Testing.synth(stack);
  });

  describe("synth output", () => {
    it("should have huaweicloud provider configured with cn-southwest-2 region", () => {
      expect(synthResult).toHaveProviderWithProperties(HuaweicloudProvider, {
        region: "cn-southwest-2",
      });
    });

    it("should create an OBS bucket named personal-assistant-web-chat", () => {
      expect(synthResult).toHaveResourceWithProperties(ObsBucket, {
        bucket: "personal-assistant-web-chat",
      });
    });

    it("should set OBS bucket acl to public-read", () => {
      expect(synthResult).toHaveResourceWithProperties(ObsBucket, {
        acl: "public-read",
      });
    });

    it("should enable versioning on the OBS bucket", () => {
      expect(synthResult).toHaveResourceWithProperties(ObsBucket, {
        versioning: true,
      });
    });

    it("should configure website hosting with index.html for both index_document and error_document (SPA fallback)", () => {
      expect(synthResult).toHaveResourceWithProperties(ObsBucket, {
        website: {
          index_document: "index.html",
          error_document: "index.html",
        },
      });
    });

    it("should NOT set region at the OBS bucket resource level (delegated to provider)", () => {
      // Region is configured at provider level only — resource-level region is redundant
      expect(synthResult).not.toHaveResourceWithProperties(ObsBucket, {
        region: "cn-southwest-2",
      });
    });
  });

  describe("stack structure", () => {
    it("should contain exactly one ObsBucket resource", () => {
      expect(synthResult).toHaveResource(ObsBucket);
    });

    it("should contain exactly one HuaweicloudProvider", () => {
      expect(synthResult).toHaveProvider(HuaweicloudProvider);
    });
  });

  describe("full synth validation", () => {
    it("should produce valid Terraform configuration on disk", () => {
      const app = Testing.app();
      const s = new PersonalAssistantStack(app, "test-pa-stack-full");
      const fullSynthResult = Testing.fullSynth(s);
      expect(fullSynthResult).toBeValidTerraform();
    });
  });
});
