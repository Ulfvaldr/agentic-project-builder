from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class Sector:
    name: str
    weight: float


@dataclass(frozen=True, slots=True)
class Performance:
    ytd_return: float
    one_year_return: float
    as_of_date: str


@dataclass(frozen=True, slots=True)
class Source:
    label: str
    publisher: str
    url: str


@dataclass(frozen=True, slots=True)
class Etf:
    ticker: str
    name: str
    issuer: str
    expense_ratio: float
    aum: float
    inception_date: str
    benchmark: str
    holdings_count: int
    top_sectors: tuple[Sector, ...]
    top_holdings: tuple[str, ...]
    performance: Performance
    as_of_date: str
    field_as_of_dates: Mapping[str, str]
    sources: tuple[Source, ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> Etf:
        performance = value["performance"]
        return cls(
            ticker=value["ticker"],
            name=value["name"],
            issuer=value["issuer"],
            expense_ratio=value["expenseRatio"],
            aum=value["aum"],
            inception_date=value["inceptionDate"],
            benchmark=value["benchmark"],
            holdings_count=value["holdingsCount"],
            top_sectors=tuple(Sector(item["name"], item["weight"]) for item in value["topSectors"]),
            top_holdings=tuple(value["topHoldings"]),
            performance=Performance(
                performance["ytdReturn"], performance["oneYearReturn"], performance["asOfDate"]
            ),
            as_of_date=value["asOfDate"],
            field_as_of_dates=MappingProxyType(dict(value.get("fieldAsOfDates", {}))),
            sources=tuple(Source(item["label"], item["publisher"], item["url"]) for item in value["sources"]),
        )
