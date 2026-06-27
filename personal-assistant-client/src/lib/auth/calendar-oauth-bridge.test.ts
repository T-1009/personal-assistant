import { describe, expect, it } from "vitest";

import {
  CALENDAR_OAUTH_FAILED_MESSAGE,
  formatCalendarOAuthError,
} from "@/lib/auth/calendar-oauth-bridge";

describe("formatCalendarOAuthError", () => {
  it("returns a safe fallback for unknown errors", () => {
    expect(formatCalendarOAuthError(null)).toBe(CALENDAR_OAUTH_FAILED_MESSAGE);
  });

  it("maps missing auth context to a login-state message", () => {
    expect(
      formatCalendarOAuthError(
        new Error("Missing X-HW-AgentGateway-User-Id header"),
      ),
    ).toBe("请保持原聊天窗口处于登录状态后，再重新完成日历授权。");
  });

  it("maps AgentArts Identity permission failures to an admin action", () => {
    expect(
      formatCalendarOAuthError(
        new Error(
          "Calendar authorization service is not configured correctly. " +
            "Please contact the administrator to grant AgentArts Identity " +
            "completeResourceTokenAuth permission.",
        ),
      ),
    ).toBe("日历授权服务权限尚未配置完成，请联系管理员检查 AgentArts Identity 权限。");
  });

  it("maps generic 502 responses to a temporary service message", () => {
    expect(formatCalendarOAuthError(new Error("OAuth2 complete failed: 502"))).toBe(
      "日历授权服务暂时不可用，请稍后重试。",
    );
  });
});
