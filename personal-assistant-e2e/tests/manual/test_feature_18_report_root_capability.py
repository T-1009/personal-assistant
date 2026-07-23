"""Manual deployed E2E probe for the Feature 18 Report root capability."""

from __future__ import annotations

import json
import os
from uuid import uuid4

import httpx
import pytest

pytestmark = [pytest.mark.manual, pytest.mark.feature]


@pytest.fixture
def deployed_client():
    base_url = os.getenv("PA_E2E_DEPLOYED_BASE_URL", "").rstrip("/")
    token = os.getenv("PA_E2E_BEARER_TOKEN", "").strip()
    if not base_url or not token:
        pytest.skip("PA_E2E_DEPLOYED_BASE_URL and PA_E2E_BEARER_TOKEN are required")
    if httpx.URL(base_url).scheme != "https":
        pytest.fail("PA_E2E_DEPLOYED_BASE_URL must use HTTPS")
    authorization = token if token.lower().startswith("bearer ") else f"Bearer {token}"
    with httpx.Client(
        base_url=base_url,
        headers={"Authorization": authorization},
        timeout=180.0,
    ) as client:
        yield client


def _sse_events(response: httpx.Response) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for line in response.text.splitlines():
        if not line.startswith("data: "):
            continue
        event = json.loads(line.removeprefix("data: "))
        if isinstance(event, dict):
            events.append(event)
    return events


def _sse_text(response: httpx.Response) -> str:
    tokens: list[str] = []
    for event in _sse_events(response):
        token = event.get("token")
        if isinstance(token, str):
            tokens.append(token)
    return "".join(tokens)


def test_feature_18_deployed_explicit_date_report_uses_root_capability(
    deployed_client,
):
    client = deployed_client
    expected_github_login = os.getenv("PA_E2E_EXPECTED_GITHUB_LOGIN", "").strip()
    conversation_id: str | None = None
    try:
        created = client.post(
            "/api/conversations",
            json={"title": f"Feature 18 report probe {uuid4()}"},
        )
        assert created.status_code == 201
        conversation_id = created.json()["id"]

        response = client.post(
            "/invocations",
            json={
                "conversation_id": conversation_id,
                "client_message_id": str(uuid4()),
                "message": (
                    "请生成 2024 年 2 月 14 日的日报，使用默认数据源。"
                    "报告时间范围必须严格使用我给定的日期，不要使用今天。"
                    "请保留数据覆盖说明；"
                    "如果 GitHub 已授权，请明确写出当前 OAuth GitHub 账号，"
                    "并说明活动范围是该账号可访问的全部仓库；"
                    "只能统计该 OAuth 账号的活动，不要把平台身份当作报告主体。"
                    "任一来源不可用时输出 warning，不要编造缺失内容。"
                ),
                "stream": True,
            },
            headers={"Accept": "text/event-stream"},
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        events = _sse_events(response)
        report = _sse_text(response)
        assert report.strip()
        assert "日报" in report
        assert any(date in report for date in ("2024-02-14", "2024 年 2 月 14 日"))
        assert any(label in report for label in ("GitHub", "工程活动"))
        assert any(label in report for label in ("邮件", "Email"))
        assert any(label in report for label in ("日历", "Calendar"))
        assert any(label in report for label in ("数据覆盖", "warning", "提醒"))

        report_events = [event for event in events if event.get("report_ready") is True]
        assert len(report_events) == 1
        report_event = report_events[0]
        assert report_event.get("report_format") == "markdown"
        assert report_event.get("report_type") == "daily"
        filename = report_event.get("report_filename")
        assert isinstance(filename, str)
        assert filename.endswith(".md")
        assert "2024-02-14" in filename
        artifact = report_event.get("report_content")
        assert isinstance(artifact, str)
        assert artifact.startswith("# 日报")
        assert "2024-02-14" in artifact
        assert any(label in artifact for label in ("GitHub", "工程活动"))
        assert any(label in artifact for label in ("邮件", "Email"))
        assert any(label in artifact for label in ("日历", "Calendar"))

        lowered = report.lower()
        github_oauth_subject_visible = any(
            label in report
            for label in ("OAuth 账号", "OAuth GitHub", "GitHub 账号", "授权账号")
        )
        github_repository_scope_visible = any(
            label in report for label in ("仓库范围", "可访问仓库", "可访问的全部")
        )
        github_warning_visible = "github" in lowered and any(
            label in lowered for label in ("warning", "不可用", "失败", "未授权")
        )
        assert (
            github_oauth_subject_visible and github_repository_scope_visible
        ) or github_warning_visible

        if expected_github_login:
            assert expected_github_login.casefold() in report.casefold()
            assert github_oauth_subject_visible
            assert github_repository_scope_visible

        for sensitive in ("access_token", "api_key", "authorization: bearer", "ak/sk"):
            assert sensitive not in lowered
            assert sensitive not in artifact.lower()
    finally:
        if conversation_id is not None:
            client.delete(f"/api/conversations/{conversation_id}")
