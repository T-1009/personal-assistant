import { Construct } from "constructs";
import { TerraformStack, TerraformOutput } from "cdktf";
import { HuaweicloudProvider } from "../.gen/providers/huaweicloud/provider";
import { ObsBucket } from "../.gen/providers/huaweicloud/obs-bucket";

// TODO: Configure OBS backend (pa-terraform-state bucket) for remote state storage
// per AGENTS.md. Requires pre-existing state bucket (chicken-and-egg for first deploy).
// Tracked as post-deployment cleanup task in plan §19.

export class PersonalAssistantStack extends TerraformStack {
  constructor(scope: Construct, id: string) {
    super(scope, id);

    new HuaweicloudProvider(this, "huaweicloud", {
      region: "cn-southwest-2",
      accessKey: process.env.HUAWEICLOUD_SDK_AK,
      secretKey: process.env.HUAWEICLOUD_SDK_SK,
    });

    const webChatBucket = new ObsBucket(this, "web-chat", {
      bucket: "personal-assistant-web-chat",
      acl: "public-read",
      versioning: true,
      website: {
        indexDocument: "index.html",
        errorDocument: "index.html",
      },
    });

    new TerraformOutput(this, "website-endpoint", {
      value: `https://${webChatBucket.bucket}.obs-website.cn-southwest-2.myhuaweicloud.com`,
      description: "OBS static website hosting endpoint URL",
    });
  }
}
