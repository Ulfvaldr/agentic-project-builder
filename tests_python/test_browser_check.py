from __future__ import annotations

import os
from pathlib import Path
import unittest
from contextlib import redirect_stderr
from io import StringIO
from unittest.mock import patch

from agentic_project_builder.browser_check import (
    BrowserConfig,
    _valid_websocket_handshake,
    browser_check_from_environment,
    failure_for_event,
    page_state_failures,
)


class BrowserCheckTests(unittest.TestCase):
    def test_default_environment_configuration(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = BrowserConfig.from_environment()
        self.assertEqual(config.url, "http://127.0.0.1:4173/")
        self.assertEqual(config.chrome_path, Path("C:/Program Files/Google/Chrome/Application/chrome.exe"))
        self.assertEqual(config.cdp_port, 9333)

    def test_environment_compatibility_and_explicit_overrides(self) -> None:
        with patch.dict(
            os.environ,
            {"URL": "http://example.test/", "CHROME_PATH": "X:/Chrome/chrome.exe", "CDP_PORT": "9444"},
            clear=False,
        ):
            config = BrowserConfig.from_environment()
            override = BrowserConfig.from_environment(url="http://override.test/", cdp_port=9555)

        self.assertEqual(config.url, "http://example.test/")
        self.assertEqual(config.chrome_path, Path("X:/Chrome/chrome.exe"))
        self.assertEqual(config.cdp_port, 9444)
        self.assertEqual(override.url, "http://override.test/")
        self.assertEqual(override.cdp_port, 9555)

    def test_checker_returns_nonzero_when_chrome_cannot_start(self) -> None:
        stderr = StringIO()
        with redirect_stderr(stderr):
            result = browser_check_from_environment(chrome_path="Z:/missing/chrome.exe", cdp_port=19444)
        self.assertEqual(result, 1)
        self.assertTrue(stderr.getvalue().strip())

    def test_accepts_case_insensitive_websocket_accept_header(self) -> None:
        key = "dGhlIHNhbXBsZSBub25jZQ=="
        header = (
            "HTTP/1.1 101 WebSocket Protocol Handshake\r\n"
            "Upgrade: WebSocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo="
        )
        self.assertTrue(_valid_websocket_handshake(header, key))

    def test_detects_console_runtime_http_and_network_failures(self) -> None:
        events = [
            {"method": "Log.entryAdded", "params": {"entry": {"level": "error", "text": "bad"}}},
            {"method": "Log.entryAdded", "params": {"entry": {"level": "warning", "text": "warn"}}},
            {"method": "Runtime.exceptionThrown", "params": {"exceptionDetails": {"text": "boom"}}},
            {"method": "Network.responseReceived", "params": {"response": {"status": 404, "url": "http://x/missing"}}},
            {"method": "Network.loadingFailed", "params": {"errorText": "net::ERR_FAILED", "requestId": "1"}},
        ]
        self.assertEqual(
            [failure_for_event(event) for event in events],
            [
                "Log.error: bad",
                "Log.warning: warn",
                "Runtime.exceptionThrown: boom",
                "HTTP 404: http://x/missing",
                "Network.loadingFailed: net::ERR_FAILED 1",
            ],
        )
        self.assertIsNone(failure_for_event({"method": "Log.entryAdded", "params": {"entry": {"level": "info"}}}))
        self.assertIsNone(failure_for_event({"method": "Network.responseReceived", "params": {"response": {"status": 399}}}))

    def test_page_state_failures_require_rendered_interactive_comparison(self) -> None:
        healthy = {
            "fundCount": 3,
            "rowCount": 9,
            "explanationCount": 6,
            "sourceCount": 6,
            "validation": "",
            "heading": "FieldSPYQQQ",
        }
        self.assertEqual(page_state_failures(healthy), [])
        self.assertEqual(
            page_state_failures({**healthy, "rowCount": 0, "validation": "broken"}),
            ["Expected 9 rendered comparison rows, got 0", "Unexpected validation message: broken"],
        )


if __name__ == "__main__":
    unittest.main()
