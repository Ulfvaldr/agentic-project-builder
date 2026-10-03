from __future__ import annotations

import unittest

from dataclasses import replace

from agentic_project_builder.comparison import (
    build_comparison,
    explain_differences,
    field_date_summary,
    fixture_as_of_range,
    format_currency_billions,
    format_integer,
    format_percent,
    format_performance,
    format_top_sectors,
    validate_selection,
)
from agentic_project_builder.fixtures import load_etf_fixtures
from agentic_project_builder.models import Performance, Sector


class FormattingTests(unittest.TestCase):
    def test_formatters_match_javascript_display_strings_and_rounding_edges(self) -> None:
        self.assertEqual(format_percent(-0.0), "0.00%")
        self.assertEqual(format_percent(0.03), "0.0300%")
        self.assertEqual(format_percent(0.1), "0.10%")
        self.assertEqual(format_percent(-0.001), "-0.0010%")
        self.assertEqual(format_percent(-0.00001), "-0.0000%")
        self.assertEqual(format_currency_billions(806.18442), "$806.18B")
        self.assertEqual(format_currency_billions(690.1), "$690.1B")
        self.assertEqual(format_integer(3507), "3,507")
        self.assertEqual(
            format_top_sectors((Sector("Technology", 40.9), Sector("Industrials", 11.8))),
            "Technology 40.90%; Industrials 11.80%",
        )
        self.assertEqual(
            format_performance(Performance(13.05, 20.17, "2026-08-31")),
            "YTD 13.05%; 1-year 20.17% (as of 2026-08-31)",
        )


class ComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.etfs = load_etf_fixtures()

    def test_selection_and_comparison_rows_match_javascript_contract(self) -> None:
        self.assertEqual(validate_selection("SPY", "QQQ", self.etfs).as_dict(), {"valid": True, "message": ""})
        self.assertEqual(
            validate_selection("SPY", "SPY", self.etfs).message,
            "Choose two distinct ETFs before comparing.",
        )
        self.assertEqual(
            validate_selection("SPY", "NOPE", self.etfs).message,
            "Choose two ETFs from the fixture list.",
        )

        comparison = build_comparison("SPY", "QQQ", self.etfs)
        self.assertTrue(comparison.validation.valid)
        self.assertEqual(len(comparison.rows), 8)
        self.assertEqual(
            [row.label for row in comparison.rows],
            [
                "Issuer", "Net expense ratio", "Assets under management", "Inception date",
                "Benchmark / category", "Holdings count", "Largest sector exposures",
                "Performance snapshot",
            ],
        )
        self.assertEqual(comparison.rows[2].left, "$806.18B (as of 2026-09-22)")
        invalid = build_comparison("VTI", "VTI", self.etfs)
        self.assertEqual(invalid.rows, ())
        self.assertEqual(invalid.explanation, ())
        self.assertIsNone(invalid.left)

    def test_explanations_and_known_threshold_edges_match_javascript(self) -> None:
        spy, qqq, _ = self.etfs
        self.assertEqual(
            explain_differences(spy, qqq),
            (
                "SPY has the lower net expense ratio (0.0945% vs. 0.18%).",
                "SPY has the larger asset base ($806.18B vs. $498.64B).",
                "SPY tracks S&P 500 Index / U.S. large blend equities; QQQ tracks Nasdaq-100 Index / U.S. large growth equities.",
                "SPY is broader by holdings count (504 vs. 102).",
                "SPY's largest sector exposure is Information Technology; QQQ's is Technology.",
                "SPY has the higher YTD return in the fixture snapshot (13.05% vs. 12.15%).",
            ),
        )
        near_equal = replace(
            qqq,
            expense_ratio=spy.expense_ratio + 0.00004,
            aum=spy.aum,
            benchmark=spy.benchmark,
            holdings_count=spy.holdings_count - 50,
            top_sectors=(),
            performance=replace(qqq.performance, ytd_return=spy.performance.ytd_return + 0.004),
        )
        self.assertEqual(
            explain_differences(spy, near_equal),
            (
                "SPY and QQQ have the same net expense ratio in this fixture.",
                "SPY has the larger asset base ($806.18B vs. $806.18B).",
            ),
        )

    def test_date_helpers_preserve_empty_and_fallback_edge_behavior(self) -> None:
        self.assertEqual(fixture_as_of_range(self.etfs), "2026-04-28 to 2026-09-23")
        self.assertEqual(fixture_as_of_range(()), "undefined to undefined")
        summary = field_date_summary(self.etfs)
        self.assertIn(
            "SPY: profile 2026-09-22; performance 2026-08-31; AUM 2026-09-22; holdings/sectors 2026-09-22/2026-09-22",
            summary,
        )
        no_dates = replace(self.etfs[0], field_as_of_dates={})
        self.assertEqual(
            field_date_summary((no_dates,)),
            "SPY: profile 2026-09-22; performance 2026-08-31; AUM 2026-09-22; holdings/sectors 2026-09-22/2026-09-22",
        )


if __name__ == "__main__":
    unittest.main()
