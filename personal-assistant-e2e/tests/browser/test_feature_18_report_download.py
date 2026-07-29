"""Browser E2E for the Feature 18 Markdown report download card."""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import time
from pathlib import Path

import httpx
import pytest
from test_feature_14_multi_conversation import ConversationHttpDouble

from conftest import PROJECT_ROOT, terminate_process_tree

CLIENT_DIR = PROJECT_ROOT / "personal-assistant-client"
pytestmark = [pytest.mark.browser, pytest.mark.feature, pytest.mark.slow]

REPORT_CONTENT = """# 日报

- 时间范围：2024-02-14T00:00:00+08:00 至 2024-02-14T23:59:59+08:00

## GitHub 工程活动

- 2024-02-14 | commit：Feature 18 download

## 邮件

- 本时间范围内没有可用证据。

## 日历

- 本时间范围内没有可用证据。

## 数据覆盖与提醒

所有已选择数据源均完成本次采集。
"""

ASSISTANT_DISPLAYED_MARKDOWN = """# 报告已生成

完整报告请使用下方下载按钮保存。
"""


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class ClientDevProcess:
    def __init__(self, port: int):
        self.port = port
        self.url = f"http://127.0.0.1:{port}"
        self.process: subprocess.Popen | None = None

    def start(self, timeout: float = 60.0) -> None:
        npm = "npm.cmd" if os.name == "nt" else "npm"
        self.process = subprocess.Popen(
            [
                npm,
                "run",
                "dev",
                "--",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.port),
                "--strictPort",
            ],
            cwd=str(CLIENT_DIR),
            env={**os.environ, "BROWSER": "none"},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.process.poll() is not None:
                _, stderr = self.process.communicate(timeout=5)
                raise RuntimeError(
                    "Vite exited before Feature 18 browser E2E startup: "
                    f"{stderr.decode(errors='replace')[-500:]}"
                )
            try:
                if httpx.get(self.url, timeout=2.0).status_code == 200:
                    return
            except (httpx.ConnectError, httpx.TimeoutException):
                pass
            time.sleep(0.5)
        self.stop()
        raise TimeoutError("Vite did not become ready for Feature 18 browser E2E")

    def stop(self) -> None:
        if self.process is not None:
            terminate_process_tree(self.process)
        self.process = None


@pytest.fixture
def vite_url():
    configured_url = os.getenv("PA_E2E_CLIENT_BASE_URL", "").rstrip("/")
    if configured_url:
        yield configured_url
        return
    if not (CLIENT_DIR / "node_modules").is_dir():
        pytest.skip("Client node_modules is required for browser E2E")
    process = ClientDevProcess(_find_free_port())
    process.start()
    try:
        yield process.url
    finally:
        process.stop()


class ReportHttpDouble(ConversationHttpDouble):
    def handle_invocation(self, route) -> None:
        request = route.request
        payload = json.loads(request.post_data or "{}")
        self.invocation_payloads.append(payload)
        if payload.get("conversation_id") not in self.conversations:
            self._json(route, 404, {"detail": "conversation not found"})
            return

        body = "".join(
            f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            for event in (
                {
                    "type": "report_ready",
                    "report_ready": True,
                    "report_format": "markdown",
                    "report_filename": "日报-2024-02-14.md",
                    "report_content": REPORT_CONTENT,
                    "report_type": "daily",
                },
                {"token": ASSISTANT_DISPLAYED_MARKDOWN, "done": False},
                {"token": "", "done": True},
            )
        )
        route.fulfill(status=200, content_type="text/event-stream", body=body)


def _handle_auth_route(route) -> None:
    response = route.fetch()
    body = response.text()
    body = re.sub(
        r"export async function acquireIdTokenSilently\(\): "
        r"Promise<string \| null> \{.*?\n\}\n\n"
        r"export async function clearInboundAuthSession",
        "export async function acquireIdTokenSilently(): Promise<string | null> {\n"
        '  return "feature18-browser-token";\n'
        "}\n\nexport async function clearInboundAuthSession",
        body,
        flags=re.S,
    )
    route.fulfill(status=response.status, headers=dict(response.headers), body=body)


def _handle_app_route(route) -> None:
    response = route.fetch()
    body = re.sub(
        r"const isAuthenticated = useIsAuthenticated\(\);",
        "const isAuthenticated = true; // Feature 18 browser auth double",
        response.text(),
        count=1,
    )
    body = re.sub(
        r"const canShowChat = [^;]+;",
        "const canShowChat = true; // Feature 18 browser auth double",
        body,
        count=1,
    )
    route.fulfill(status=response.status, headers=dict(response.headers), body=body)


def test_feature_18_report_download_card_and_markdown_file(vite_url):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("playwright is not installed")

    backend = ReportHttpDouble()
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
        except Exception as chrome_error:
            try:
                browser = playwright.chromium.launch(headless=True)
            except Exception as bundled_error:
                pytest.skip(
                    "Google Chrome and bundled Chromium are unavailable: "
                    f"chrome={chrome_error}; bundled={bundled_error}"
                )

        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.add_init_script(
            "Object.defineProperty(window, 'showSaveFilePicker', "
            "{ configurable: true, value: undefined });"
        )
        page.route(lambda url: "/src/lib/auth.ts" in url, _handle_auth_route)
        page.route(lambda url: "/src/App.tsx" in url, _handle_app_route)
        page.route("**/api/conversations**", backend.handle_conversations)
        page.route("**/invocations", backend.handle_invocation)
        try:
            page.goto(vite_url, wait_until="networkidle", timeout=30_000)
            try:
                page.get_by_label("Message input").wait_for(timeout=15_000)
            except Exception as error:
                raise AssertionError(
                    f"Chat UI did not load at {page.url}: "
                    f"{page.locator('body').inner_text()[-1000:]!r}"
                ) from error
            page.get_by_label("Message input").fill("请生成 2024-02-14 的日报")
            page.get_by_label("Send message").click()

            heading = page.get_by_role("heading", name="报告已生成", exact=True)
            heading.wait_for(timeout=15_000)
            card = page.locator('[data-slot="report-download-card"]')
            card.wait_for(timeout=15_000)
            assert card.get_by_text("Markdown 报告已生成", exact=True).is_visible()
            button = card.get_by_role("button", name="下载 Markdown 报告")
            assert button.count() == 1

            heading_box = heading.bounding_box()
            card_box = card.bounding_box()
            assert heading_box is not None and card_box is not None
            assert card_box["y"] > heading_box["y"]

            with page.expect_download(timeout=15_000) as download_info:
                button.click()
            download = download_info.value
            assert download.suggested_filename == "日报-2024-02-14.md"
            download_path = download.path()
            assert download_path is not None
            downloaded_content = Path(download_path).read_text(encoding="utf-8")
            assert REPORT_CONTENT != ASSISTANT_DISPLAYED_MARKDOWN
            assert downloaded_content == REPORT_CONTENT
        finally:
            page.close()
            browser.close()
