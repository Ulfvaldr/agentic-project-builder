from __future__ import annotations

import re
from typing import Any


REQUIRED_STRING_FIELDS = ("ticker", "name", "issuer", "inceptionDate", "benchmark", "asOfDate")
REQUIRED_FIELD_DATES = (
    "expenseRatio", "aum", "inceptionDate", "benchmark", "holdingsCount",
    "topSectors", "topHoldings", "performance",
)
OFFICIAL_SPOT_CHECKS: dict[str, dict[str, Any]] = {
    "SPY": {
        "aum": 806.18442,
        "asOfDate": "2026-09-22",
        "fieldAsOfDates": {"aum": "2026-09-22", "holdingsCount": "2026-09-22", "topSectors": "2026-09-22", "performance": "2026-08-31"},
        "holdingsCount": 504,
        "topSectors": (("Information Technology", 39.28), ("Financials", 11.53), ("Communication Services", 10.00)),
        "performance": {"ytdReturn": 13.05, "oneYearReturn": 20.17, "asOfDate": "2026-08-31"},
        "sourceUrlIncludes": "ssga.com/us/en/intermediary/etfs/state-street-spdr-sp-500-etf-trust-spy",
    },
    "QQQ": {
        "aum": 498.64,
        "asOfDate": "2026-09-21",
        "fieldAsOfDates": {"aum": "2026-09-21", "holdingsCount": "2026-09-21", "topSectors": "2026-08-30", "performance": "2026-08-30"},
        "holdingsCount": 102,
        "topSectors": (("Technology", 66.36), ("Consumer Discretionary", 16.65), ("Telecommunications", 4.72)),
        "performance": {"oneYearReturn": 26.27, "asOfDate": "2026-08-30"},
        "sourceUrlIncludes": "invesco.com/qqq-etf/en/about.html",
    },
    "VTI": {
        "aum": 690.1,
        "asOfDate": "2026-08-31",
        "fieldAsOfDates": {"expenseRatio": "2026-04-28", "aum": "2026-08-31", "holdingsCount": "2026-08-31", "topSectors": "2026-08-31", "performance": "2026-08-31"},
        "holdingsCount": 3507,
        "topSectors": (("Technology", 40.90), ("Consumer Discretionary", 12.00), ("Industrials", 11.80)),
        "performance": {"ytdReturn": 13.45, "oneYearReturn": 20.24, "asOfDate": "2026-08-31"},
        "sourceUrlIncludes": "investor.vanguard.com/investment-products/etfs/profile/vti",
    },
}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_integer(value: Any) -> bool:
    return _is_number(value) and float(value).is_integer()


def _is_iso_date(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is not None


def _display_text(value: Any) -> str:
    if value is None:
        return "undefined"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def validate_fixtures(etfs: Any) -> list[str]:
    if etfs is None:
        raise TypeError("Cannot read properties of null (reading 'entries')")
    if not isinstance(etfs, list):
        raise TypeError("etfs.entries is not a function or its return value is not iterable")
    errors: list[str] = []
    if len(etfs) < 2:
        errors.append("Fixture must contain at least two ETF records.")

    tickers: set[Any] = set()
    for index, record in enumerate(etfs):
        if record is None:
            raise TypeError(f"Cannot read properties of null (reading '{REQUIRED_STRING_FIELDS[0]}')")
        etf = record if isinstance(record, dict) else {}
        for field in REQUIRED_STRING_FIELDS:
            value = etf.get(field)
            if not isinstance(value, str) or len(value) == 0:
                errors.append(f"ETF {index} missing {field}.")
        ticker = etf.get("ticker")
        if ticker in tickers:
            errors.append(f"Duplicate ticker {_display_text(ticker)}.")
        tickers.add(ticker)
        if not _is_number(etf.get("expenseRatio")):
            errors.append(f"{_display_text(ticker)} expenseRatio must be a number.")
        if not _is_number(etf.get("aum")):
            errors.append(f"{_display_text(ticker)} aum must be a number in billions.")
        if not _is_integer(etf.get("holdingsCount")):
            errors.append(f"{_display_text(ticker)} holdingsCount must be an integer.")
        sectors = etf.get("topSectors")
        if not isinstance(sectors, list) or len(sectors) < 1:
            errors.append(f"{_display_text(ticker)} must list top sectors.")
        holdings = etf.get("topHoldings")
        if not isinstance(holdings, list) or len(holdings) < 1:
            errors.append(f"{_display_text(ticker)} must list top holdings for traceability.")
        performance = etf.get("performance")
        if (
            not isinstance(performance, dict)
            or not _is_number(performance.get("ytdReturn"))
            or not _is_number(performance.get("oneYearReturn"))
            or not performance.get("asOfDate")
        ):
            errors.append(f"{_display_text(ticker)} missing performance snapshot.")
        dates = etf.get("fieldAsOfDates")
        if not isinstance(dates, dict) or any(not _is_iso_date(dates.get(field)) for field in REQUIRED_FIELD_DATES):
            errors.append(
                f"{_display_text(ticker)} must include ISO fieldAsOfDates for {', '.join(REQUIRED_FIELD_DATES)}."
            )
        sources = etf.get("sources")
        if (
            not isinstance(sources, list)
            or len(sources) < 1
            or any(not isinstance(source, dict) or not source.get("url") or not source.get("publisher") or not source.get("label") for source in sources)
        ):
            errors.append(f"{_display_text(ticker)} must include source links.")
        _check_official_spot_check(etf, errors)
    return errors


def _check_official_spot_check(etf: dict[str, Any], errors: list[str]) -> None:
    ticker = etf.get("ticker")
    expected = OFFICIAL_SPOT_CHECKS.get(ticker)
    if expected is None:
        return
    for field, value in expected.items():
        if field in {"fieldAsOfDates", "topSectors", "performance", "sourceUrlIncludes"}:
            continue
        if etf.get(field) != value:
            errors.append(
                f"{ticker} {field} expected {_display_text(value)} from cited official source, got {_display_text(etf.get(field))}."
            )
    dates = etf.get("fieldAsOfDates") if isinstance(etf.get("fieldAsOfDates"), dict) else {}
    for field, value in expected.get("fieldAsOfDates", {}).items():
        if dates.get(field) != value:
            errors.append(f"{ticker} {field} as-of date expected {value}, got {_display_text(dates.get(field))}.")
    sectors = etf.get("topSectors") if isinstance(etf.get("topSectors"), list) else []
    for index, (name, weight) in enumerate(expected.get("topSectors", ())):
        actual = sectors[index] if index < len(sectors) and isinstance(sectors[index], dict) else {}
        if actual.get("name") != name or actual.get("weight") != weight:
            errors.append(
                f"{ticker} top sector {index + 1} expected {name} {_display_text(weight)}%, "
                f"got {_display_text(actual.get('name'))} {_display_text(actual.get('weight'))}%."
            )
    performance = etf.get("performance") if isinstance(etf.get("performance"), dict) else {}
    for field, value in expected.get("performance", {}).items():
        if performance.get(field) != value:
            errors.append(
                f"{ticker} performance {field} expected {_display_text(value)}, got {_display_text(performance.get(field))}."
            )
    sources = etf.get("sources") if isinstance(etf.get("sources"), list) else []
    required_url = expected["sourceUrlIncludes"]
    if not any(isinstance(source, dict) and required_url in str(source.get("url", "")) for source in sources):
        errors.append(f"{ticker} missing required official source URL containing {required_url}.")
