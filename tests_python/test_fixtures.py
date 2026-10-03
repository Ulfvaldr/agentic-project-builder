from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import unittest

from agentic_project_builder.fixtures import default_fixture_path, default_static_root, load_etf_fixtures


ROOT = Path(__file__).resolve().parents[1]


class FixtureLoaderTests(unittest.TestCase):
    def test_loads_typed_frozen_models_from_repository_independent_path(self) -> None:
        etfs = load_etf_fixtures()

        self.assertEqual([etf.ticker for etf in etfs], ["SPY", "QQQ", "VTI"])
        self.assertEqual(etfs[0].top_sectors[0].name, "Information Technology")
        self.assertEqual(etfs[0].field_as_of_dates["aum"], "2026-09-22")
        self.assertEqual(default_fixture_path(), default_static_root() / "fixtures" / "etfs.json")
        with self.assertRaises(FrozenInstanceError):
            etfs[0].ticker = "NOPE"  # type: ignore[misc]
        with self.assertRaises(TypeError):
            etfs[0].field_as_of_dates["aum"] = "x"  # type: ignore[index]

    def test_packaged_site_is_an_exact_copy_of_repository_assets(self) -> None:
        relative_paths = (
            Path("index.html"),
            Path("fixtures/etfs.json"),
            Path("src/comparison.js"),
            Path("src/dataProvider.js"),
            Path("src/main.js"),
            Path("src/styles.css"),
        )
        packaged_root = default_static_root()

        for relative_path in relative_paths:
            with self.subTest(path=str(relative_path)):
                self.assertEqual(
                    (packaged_root / relative_path).read_bytes(),
                    (ROOT / relative_path).read_bytes(),
                )

    def test_loader_accepts_injected_reader_and_path(self) -> None:
        calls: list[tuple[Path, str]] = []
        payload = json.dumps([
            {
                "ticker": "ONE", "name": "One", "issuer": "Issuer",
                "expenseRatio": 0.1, "aum": 1.0, "inceptionDate": "2020-01-01",
                "benchmark": "Index", "holdingsCount": 1,
                "topSectors": [{"name": "Tech", "weight": 100.0}],
                "topHoldings": ["A"],
                "performance": {"ytdReturn": 1.0, "oneYearReturn": 2.0, "asOfDate": "2024-01-01"},
                "asOfDate": "2024-01-01", "fieldAsOfDates": {"aum": "2024-01-01"},
                "sources": [{"label": "Source", "publisher": "Publisher", "url": "https://example.test"}]
            }
        ])

        def reader(path: Path, encoding: str) -> str:
            calls.append((path, encoding))
            return payload

        custom = Path("anywhere/data.json")
        loaded = load_etf_fixtures(custom, reader=reader)

        self.assertEqual(calls, [(custom, "utf-8")])
        self.assertEqual(loaded[0].performance.one_year_return, 2.0)
        self.assertIsInstance(loaded, tuple)


if __name__ == "__main__":
    unittest.main()
