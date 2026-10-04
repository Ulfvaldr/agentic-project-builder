from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import math
from typing import Any, Callable, Mapping, Sequence

from .models import Etf, Performance, Sector


def _special_number_text(value: float) -> str | None:
    numeric = float(value)
    if math.isnan(numeric):
        return "NaN"
    if math.isinf(numeric):
        return "∞" if numeric > 0 else "-∞"
    return None


def _fixed_decimal(value: float, digits: int) -> str:
    numeric = float(value)
    special = _special_number_text(numeric)
    if special is not None:
        return "Infinity" if special == "∞" else "-Infinity" if special == "-∞" else special
    if abs(numeric) >= 1e21:
        mantissa, exponent = repr(numeric).lower().split("e")
        return f"{mantissa}e{'+' if int(exponent) >= 0 else '-'}{abs(int(exponent))}"
    if numeric == 0:
        numeric = 0.0
    quantum = Decimal(1).scaleb(-digits)
    rounded = Decimal.from_float(numeric).quantize(quantum, rounding=ROUND_HALF_UP)
    return f"{rounded:.{digits}f}"


def format_percent(value: float) -> str:
    numeric = float(value)
    digits = 4 if 0 < abs(numeric) < 0.1 else 2
    return f"{_fixed_decimal(numeric, digits)}%"


def format_currency_billions(value: float) -> str:
    numeric = float(value)
    special = _special_number_text(numeric)
    if special is not None:
        return f"${special}B"
    rounded = Decimal(str(numeric)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    text = f"{rounded:,.2f}".rstrip("0").rstrip(".")
    return f"${text}B"


def format_integer(value: int | float) -> str:
    numeric = float(value)
    special = _special_number_text(numeric)
    if special is not None:
        return special
    rounded = Decimal(str(numeric)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    return f"{rounded:,.3f}".rstrip("0").rstrip(".")


def format_top_sectors(sectors: tuple[Sector, ...]) -> str:
    return "; ".join(f"{sector.name} {format_percent(sector.weight)}" for sector in sectors)


def format_performance(performance: Performance) -> str:
    return (
        f"YTD {format_percent(performance.ytd_return)}; "
        f"1-year {format_percent(performance.one_year_return)} "
        f"(as of {performance.as_of_date})"
    )


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: bool
    message: str

    def as_dict(self) -> dict[str, bool | str]:
        return {"valid": self.valid, "message": self.message}


@dataclass(frozen=True, slots=True)
class ComparisonRow:
    label: str
    left: str
    right: str

    def as_dict(self) -> dict[str, str]:
        return {"label": self.label, "left": self.left, "right": self.right}


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    validation: ValidationResult
    left: Etf | None
    right: Etf | None
    rows: tuple[ComparisonRow, ...]
    explanation: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "validation": self.validation.as_dict(),
            "leftTicker": self.left.ticker if self.left else None,
            "rightTicker": self.right.ticker if self.right else None,
            "rows": [row.as_dict() for row in self.rows],
            "explanation": list(self.explanation),
        }


Formatter = Callable[[Any], str]


@dataclass(frozen=True, slots=True)
class ComparisonField:
    attribute: str
    label: str
    formatter: Formatter | None = None
    as_of_key: str | None = None


COMPARISON_FIELDS = (
    ComparisonField("issuer", "Issuer"),
    ComparisonField("expense_ratio", "Net expense ratio", format_percent, "expenseRatio"),
    ComparisonField("aum", "Assets under management", format_currency_billions, "aum"),
    ComparisonField("inception_date", "Inception date", None, "inceptionDate"),
    ComparisonField("benchmark", "Benchmark / category", None, "benchmark"),
    ComparisonField("holdings_count", "Holdings count", format_integer, "holdingsCount"),
    ComparisonField("top_sectors", "Largest sector exposures", format_top_sectors, "topSectors"),
    ComparisonField("performance", "Performance snapshot", format_performance),
)


def validate_selection(left_ticker: str, right_ticker: str, etfs: Sequence[Etf]) -> ValidationResult:
    tickers = {etf.ticker for etf in etfs}
    if left_ticker not in tickers or right_ticker not in tickers:
        return ValidationResult(False, "Choose two ETFs from the fixture list.")
    if left_ticker == right_ticker:
        return ValidationResult(False, "Choose two distinct ETFs before comparing.")
    return ValidationResult(True, "")


def _format_field_value(etf: Etf, field: ComparisonField) -> str:
    raw = getattr(etf, field.attribute)
    formatted = field.formatter(raw) if field.formatter else str(raw)
    as_of_date = etf.field_as_of_dates.get(field.as_of_key) if field.as_of_key else None
    return f"{formatted} (as of {as_of_date})" if as_of_date else formatted


def build_comparison(left_ticker: str, right_ticker: str, etfs: Sequence[Etf]) -> ComparisonResult:
    validation = validate_selection(left_ticker, right_ticker, etfs)
    if not validation.valid:
        return ComparisonResult(validation, None, None, (), ())
    left = next(etf for etf in etfs if etf.ticker == left_ticker)
    right = next(etf for etf in etfs if etf.ticker == right_ticker)
    rows = tuple(
        ComparisonRow(field.label, _format_field_value(left, field), _format_field_value(right, field))
        for field in COMPARISON_FIELDS
    )
    return ComparisonResult(validation, left, right, rows, explain_differences(left, right))


def _number_after_fixed_decimal(value: float, digits: int) -> float:
    return float(_fixed_decimal(value, digits))


def explain_differences(left: Etf, right: Etf) -> tuple[str, ...]:
    messages: list[str] = []
    er_diff = _number_after_fixed_decimal(left.expense_ratio - right.expense_ratio, 4)
    if er_diff == 0:
        messages.append(f"{left.ticker} and {right.ticker} have the same net expense ratio in this fixture.")
    else:
        cheaper = left if er_diff < 0 else right
        costlier = right if cheaper is left else left
        messages.append(
            f"{cheaper.ticker} has the lower net expense ratio "
            f"({format_percent(cheaper.expense_ratio)} vs. {format_percent(costlier.expense_ratio)})."
        )

    larger = left if left.aum >= right.aum else right
    smaller = right if larger is left else left
    messages.append(
        f"{larger.ticker} has the larger asset base "
        f"({format_currency_billions(larger.aum)} vs. {format_currency_billions(smaller.aum)})."
    )

    if left.benchmark != right.benchmark:
        messages.append(f"{left.ticker} tracks {left.benchmark}; {right.ticker} tracks {right.benchmark}.")

    if abs(left.holdings_count - right.holdings_count) > 50:
        broader = left if left.holdings_count > right.holdings_count else right
        narrower = right if broader is left else left
        messages.append(
            f"{broader.ticker} is broader by holdings count "
            f"({format_integer(broader.holdings_count)} vs. {format_integer(narrower.holdings_count)})."
        )

    if left.top_sectors and right.top_sectors and left.top_sectors[0].name and right.top_sectors[0].name:
        messages.append(
            f"{left.ticker}'s largest sector exposure is {left.top_sectors[0].name}; "
            f"{right.ticker}'s is {right.top_sectors[0].name}."
        )

    ytd_diff = _number_after_fixed_decimal(left.performance.ytd_return - right.performance.ytd_return, 2)
    if ytd_diff != 0:
        leader = left if ytd_diff > 0 else right
        lagger = right if leader is left else left
        messages.append(
            f"{leader.ticker} has the higher YTD return in the fixture snapshot "
            f"({format_percent(leader.performance.ytd_return)} vs. {format_percent(lagger.performance.ytd_return)})."
        )
    return tuple(messages)


def fixture_as_of_range(etfs: Sequence[Etf]) -> str:
    dates = sorted({date for etf in etfs for date in (etf.as_of_date, *etf.field_as_of_dates.values())})
    if len(dates) == 1:
        return dates[0]
    if not dates:
        return "undefined to undefined"
    return f"{dates[0]} to {dates[-1]}"


def field_date_summary(etfs: Sequence[Etf]) -> str:
    summaries = []
    for etf in etfs:
        dates: Mapping[str, str] = etf.field_as_of_dates
        summaries.append(
            f"{etf.ticker}: profile {etf.as_of_date}; performance {etf.performance.as_of_date}; "
            f"AUM {dates.get('aum', etf.as_of_date)}; holdings/sectors "
            f"{dates.get('holdingsCount', etf.as_of_date)}/{dates.get('topSectors', etf.as_of_date)}"
        )
    return " | ".join(summaries)
