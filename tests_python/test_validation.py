from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import unittest

from agentic_project_builder.fixtures import load_raw_fixtures
from agentic_project_builder.validation import validate_fixtures


class FixtureValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixtures = load_raw_fixtures()

    def javascript_schema_errors(self, value: object) -> list[str] | dict[str, str]:
        javascript = """
const etfs = JSON.parse(process.argv[1]);
const requiredStringFields = ['ticker', 'name', 'issuer', 'inceptionDate', 'benchmark', 'asOfDate'];
const requiredFieldDates = ['expenseRatio', 'aum', 'inceptionDate', 'benchmark', 'holdingsCount', 'topSectors', 'topHoldings', 'performance'];
try {
  const errors = [];
  if (!Array.isArray(etfs) || etfs.length < 2) errors.push('Fixture must contain at least two ETF records.');
  const tickers = new Set();
  for (const [index, etf] of etfs.entries()) {
    for (const field of requiredStringFields) {
      if (typeof etf[field] !== 'string' || etf[field].length === 0) errors.push(`ETF ${index} missing ${field}.`);
    }
    if (tickers.has(etf.ticker)) errors.push(`Duplicate ticker ${etf.ticker}.`);
    tickers.add(etf.ticker);
    if (typeof etf.expenseRatio !== 'number') errors.push(`${etf.ticker} expenseRatio must be a number.`);
    if (typeof etf.aum !== 'number') errors.push(`${etf.ticker} aum must be a number in billions.`);
    if (!Number.isInteger(etf.holdingsCount)) errors.push(`${etf.ticker} holdingsCount must be an integer.`);
    if (!Array.isArray(etf.topSectors) || etf.topSectors.length < 1) errors.push(`${etf.ticker} must list top sectors.`);
    if (!Array.isArray(etf.topHoldings) || etf.topHoldings.length < 1) errors.push(`${etf.ticker} must list top holdings for traceability.`);
    if (!etf.performance || typeof etf.performance.ytdReturn !== 'number' || typeof etf.performance.oneYearReturn !== 'number' || !etf.performance.asOfDate) errors.push(`${etf.ticker} missing performance snapshot.`);
    if (!etf.fieldAsOfDates || requiredFieldDates.some((field) => typeof etf.fieldAsOfDates[field] !== 'string' || !/^\\d{4}-\\d{2}-\\d{2}$/.test(etf.fieldAsOfDates[field]))) errors.push(`${etf.ticker} must include ISO fieldAsOfDates for ${requiredFieldDates.join(', ')}.`);
    if (!Array.isArray(etf.sources) || etf.sources.length < 1 || etf.sources.some((source) => !source.url || !source.publisher || !source.label)) errors.push(`${etf.ticker} must include source links.`);
  }
  process.stdout.write(JSON.stringify(errors));
} catch (error) {
  process.stdout.write(JSON.stringify({ name: error.constructor.name, message: error.message }));
}
"""
        result = subprocess.run(
            ["node", "-e", javascript, json.dumps(value)],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)

    def assert_javascript_and_python_raise_type_error(self, value: object) -> None:
        javascript_error = self.javascript_schema_errors(value)
        self.assertEqual(javascript_error["name"], "TypeError")
        with self.assertRaises(TypeError) as raised:
            validate_fixtures(value)
        self.assertEqual(str(raised.exception), javascript_error["message"])

    def test_malformed_roots_match_javascript(self) -> None:
        for value in (None, 42, "boxed", True, {}):
            with self.subTest(value=value):
                self.assert_javascript_and_python_raise_type_error(value)
        self.assertEqual(validate_fixtures([]), self.javascript_schema_errors([]))

    def test_null_record_throws_like_javascript(self) -> None:
        self.assert_javascript_and_python_raise_type_error([None, {}])

    def test_json_primitive_and_array_records_box_like_javascript(self) -> None:
        for record in (42, "boxed", True, []):
            with self.subTest(record=record):
                value = [record, self.fixtures[0]]
                self.assertEqual(validate_fixtures(value), self.javascript_schema_errors(value))

    def test_committed_fixtures_pass_schema_and_official_spot_checks(self) -> None:
        self.assertEqual(validate_fixtures(self.fixtures), [])

    def test_reports_all_schema_errors_in_javascript_order(self) -> None:
        broken = [{
            "ticker": "BAD", "name": "", "issuer": "Issuer", "inceptionDate": "2020-01-01",
            "benchmark": "Index", "asOfDate": "2024-01-01", "expenseRatio": "0.1", "aum": None,
            "holdingsCount": 1.5, "topSectors": [], "topHoldings": [], "performance": {},
            "fieldAsOfDates": {}, "sources": [],
        }]

        self.assertEqual(
            validate_fixtures(broken),
            [
                "Fixture must contain at least two ETF records.",
                "ETF 0 missing name.",
                "BAD expenseRatio must be a number.",
                "BAD aum must be a number in billions.",
                "BAD holdingsCount must be an integer.",
                "BAD must list top sectors.",
                "BAD must list top holdings for traceability.",
                "BAD missing performance snapshot.",
                "BAD must include ISO fieldAsOfDates for expenseRatio, aum, inceptionDate, benchmark, holdingsCount, topSectors, topHoldings, performance.",
                "BAD must include source links.",
            ],
        )

    def test_aggregates_duplicate_and_official_spot_check_regressions(self) -> None:
        broken = deepcopy(self.fixtures)
        broken[1]["ticker"] = "SPY"
        broken[0]["aum"] = 1
        broken[0]["fieldAsOfDates"]["aum"] = "2000-01-01"
        broken[0]["topSectors"][0] = {"name": "Wrong", "weight": 1}
        broken[0]["performance"]["ytdReturn"] = 1
        broken[0]["sources"] = []

        errors = validate_fixtures(broken)

        self.assertIn("Duplicate ticker SPY.", errors)
        self.assertIn("SPY aum expected 806.18442 from cited official source, got 1.", errors)
        self.assertIn("SPY aum as-of date expected 2026-09-22, got 2000-01-01.", errors)
        self.assertIn("SPY top sector 1 expected Information Technology 39.28%, got Wrong 1%.", errors)
        self.assertIn("SPY performance ytdReturn expected 13.05, got 1.", errors)
        self.assertIn("SPY missing required official source URL containing ssga.com/us/en/intermediary/etfs/state-street-spdr-sp-500-etf-trust-spy.", errors)
        self.assertGreaterEqual(len(errors), 7)


if __name__ == "__main__":
    unittest.main()
