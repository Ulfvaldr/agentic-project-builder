from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from agentic_project_builder.comparison import (
    build_comparison,
    field_date_summary,
    fixture_as_of_range,
    format_currency_billions,
    format_integer,
    format_percent,
)
from agentic_project_builder.fixtures import load_etf_fixtures


ROOT = Path(__file__).resolve().parents[1]
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src")}


class CrossRuntimeParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        result = subprocess.run(
            ["node", "tests_python/js_parity_runner.mjs"], cwd=ROOT,
            capture_output=True, text=True, timeout=10, check=True,
        )
        cls.javascript = json.loads(result.stdout)
        cls.etfs = load_etf_fixtures()

    def test_all_ordered_fixture_pairs_match_javascript_outputs(self) -> None:
        python_results = {
            f"{left.ticker}:{right.ticker}": build_comparison(left.ticker, right.ticker, self.etfs).as_dict()
            for left in self.etfs for right in self.etfs
        }
        self.assertEqual(python_results, self.javascript["comparisons"])

    def test_unknown_and_empty_selections_match_javascript_outputs(self) -> None:
        vectors = (("", "QQQ"), ("SPY", ""), ("NOPE", "QQQ"), ("SPY", "NOPE"))
        python_results = {
            f"{left}:{right}": build_comparison(left, right, self.etfs).as_dict()
            for left, right in vectors
        }
        self.assertEqual(python_results, self.javascript["selectionComparisons"])

    def test_all_formatting_vectors_and_date_helpers_match_javascript(self) -> None:
        for expected in self.javascript["formatting"]:
            value = expected["value"]
            self.assertEqual(format_percent(value), expected["percent"], value)
            self.assertEqual(format_currency_billions(value), expected["currency"], value)
            self.assertEqual(format_integer(value), expected["integer"], value)
        self.assertEqual(fixture_as_of_range(self.etfs), self.javascript["fixtureAsOfRange"])
        self.assertEqual(field_date_summary(self.etfs), self.javascript["fieldDateSummary"])


class CliBehaviorTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "agentic_project_builder", *args], cwd=ROOT,
            env=ENV, capture_output=True, text=True, timeout=10,
        )

    def test_validate_and_compare_commands_have_stable_output_and_exit_codes(self) -> None:
        valid = self.run_cli("validate-fixtures")
        self.assertEqual(valid.returncode, 0, valid.stderr)
        self.assertEqual(valid.stdout.strip(), "Validated 3 ETF fixture records with field-level provenance spot-checks.")

        comparison = self.run_cli("compare", "SPY", "QQQ")
        self.assertEqual(comparison.returncode, 0, comparison.stderr)
        payload = json.loads(comparison.stdout)
        self.assertTrue(payload["validation"]["valid"])
        self.assertEqual(len(payload["rows"]), 8)

        invalid = self.run_cli("compare", "SPY", "SPY")
        self.assertEqual(invalid.returncode, 1)
        self.assertEqual(json.loads(invalid.stdout)["rows"], [])

    def test_validator_aggregates_to_stderr_and_returns_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "bad.json"
            fixture.write_text("[]", encoding="utf-8")
            result = self.run_cli("validate-fixtures", "--fixture", str(fixture))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr.strip(), "Fixture must contain at least two ETF records.")


if __name__ == "__main__":
    unittest.main()
