from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src")}


class CliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "agentic_project_builder", *args],
            cwd=ROOT,
            env=ENV,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_help_lists_parallel_python_commands(self) -> None:
        result = self.run_cli("--help")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("validate-fixtures", result.stdout)
        self.assertIn("serve", result.stdout)
        self.assertIn("check-browser", result.stdout)
        self.assertIn("compare", result.stdout)


if __name__ == "__main__":
    unittest.main()
