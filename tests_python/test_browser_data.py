from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from agentic_project_builder.browser_data import build_browser_data, write_browser_data
from agentic_project_builder.fixtures import load_etf_fixtures


class BrowserDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.etfs = load_etf_fixtures()

    def test_payload_contains_python_generated_display_data_for_every_selection(self) -> None:
        payload = build_browser_data(self.etfs)

        self.assertEqual(
            payload["funds"][0],
            {"ticker": "SPY", "name": "State Street SPDR S&P 500 ETF Trust"},
        )
        self.assertEqual(len(payload["comparisons"]), 9)
        self.assertEqual(payload["comparisons"]["SPY:SPY"]["validation"]["valid"], False)
        comparison = payload["comparisons"]["SPY:QQQ"]
        self.assertEqual(comparison["leftTicker"], "SPY")
        self.assertEqual(comparison["rightTicker"], "QQQ")
        self.assertEqual(len(comparison["rows"]), 8)
        self.assertEqual(comparison["rows"][2]["left"], "$806.18B (as of 2026-09-22)")
        self.assertIn("Fixture field-date range: 2026-04-28 to 2026-09-23.", payload["fixtureMetadata"])
        self.assertGreaterEqual(len(payload["sources"]), 3)
        self.assertIn("not investment advice", payload["disclaimer"])

    def test_writer_produces_stable_pretty_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "browser-data.json"
            write_browser_data(output, self.etfs)
            text = output.read_text(encoding="utf-8")

        self.assertTrue(text.endswith("\n"))
        self.assertEqual(json.loads(text), build_browser_data(self.etfs))


if __name__ == "__main__":
    unittest.main()