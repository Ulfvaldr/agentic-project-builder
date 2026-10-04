from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src")}


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

    def test_build_browser_data_supports_explicit_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "browser-data.json"
            result = self.run_cli("build-browser-data", "--output", str(output))
            payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(payload["comparisons"]), 9)


if __name__ == "__main__":
    unittest.main()