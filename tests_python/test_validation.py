from __future__ import annotations

from copy import deepcopy
import unittest

from agentic_project_builder.fixtures import load_raw_fixtures
from agentic_project_builder.validation import validate_fixtures


class FixtureValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixtures = load_raw_fixtures()

    def test_malformed_roots_raise_exact_historical_errors(self) -> None:
        vectors = (
            (None, "Cannot read properties of null (reading 'entries')"),
            (42, "etfs.entries is not a function or its return value is not iterable"),
            ("boxed", "etfs.entries is not a function or its return value is not iterable"),
            (True, "etfs.entries is not a function or its return value is not iterable"),
            ({}, "etfs.entries is not a function or its return value is not iterable"),
        )

        for value, message in vectors:
            with self.subTest(value=value):
                with self.assertRaises(TypeError) as raised:
                    validate_fixtures(value)
                self.assertEqual(str(raised.exception), message)

    def test_null_record_raises_exact_historical_error(self) -> None:
        with self.assertRaises(TypeError) as raised:
            validate_fixtures([None, {}])
        self.assertEqual(str(raised.exception), "Cannot read properties of null (reading 'ticker')")

    def test_empty_fixture_reports_exact_historical_error_list(self) -> None:
        self.assertEqual(validate_fixtures([]), ["Fixture must contain at least two ETF records."])

    def test_primitive_records_report_exact_historical_errors_in_order(self) -> None:
        expected = [
            "ETF 0 missing ticker.",
            "ETF 0 missing name.",
            "ETF 0 missing issuer.",
            "ETF 0 missing inceptionDate.",
            "ETF 0 missing benchmark.",
            "ETF 0 missing asOfDate.",
            "undefined expenseRatio must be a number.",
            "undefined aum must be a number in billions.",
            "undefined holdingsCount must be an integer.",
            "undefined must list top sectors.",
            "undefined must list top holdings for traceability.",
            "undefined missing performance snapshot.",
            "undefined must include ISO fieldAsOfDates for expenseRatio, aum, inceptionDate, benchmark, holdingsCount, topSectors, topHoldings, performance.",
            "undefined must include source links.",
        ]

        for record in (42, "boxed", True, []):
            with self.subTest(record=record):
                self.assertEqual(validate_fixtures([record, self.fixtures[0]]), expected)

    def test_committed_fixtures_pass_schema_and_official_spot_checks(self) -> None:
        self.assertEqual(validate_fixtures(self.fixtures), [])

    def test_reports_all_schema_errors_in_stable_order(self) -> None:
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
        self.assertIn(
            "SPY missing required official source URL containing "
            "ssga.com/us/en/intermediary/etfs/state-street-spdr-sp-500-etf-trust-spy.",
            errors,
        )
        self.assertGreaterEqual(len(errors), 7)


if __name__ == "__main__":
    unittest.main()
