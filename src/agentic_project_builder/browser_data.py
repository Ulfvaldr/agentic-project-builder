from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from .comparison import build_comparison, field_date_summary, fixture_as_of_range
from .fixtures import default_static_root
from .models import Etf


DISCLAIMER = (
    "For informational/educational purposes only. This is not investment advice and not a "
    "recommendation or offer to buy or sell any security. Data may be delayed or inaccurate; "
    "verify figures with the fund issuer. Fixture fields use the per-field as-of dates shown "
    "in the comparison rows and metadata, not one common date."
)


def build_browser_data(etfs: Sequence[Etf]) -> dict[str, Any]:
    comparisons = {
        f"{left.ticker}:{right.ticker}": build_comparison(left.ticker, right.ticker, etfs).as_dict()
        for left in etfs
        for right in etfs
    }
    unique_sources = {
        source.url: {"label": source.label, "publisher": source.publisher, "url": source.url}
        for etf in etfs
        for source in etf.sources
    }
    return {
        "funds": [{"ticker": etf.ticker, "name": etf.name} for etf in etfs],
        "comparisons": comparisons,
        "sources": list(unique_sources.values()),
        "fixtureMetadata": (
            f"Fixture field-date range: {fixture_as_of_range(etfs)}. "
            f"Field-level dates: {field_date_summary(etfs)}."
        ),
        "disclaimer": DISCLAIMER,
    }


def write_browser_data(path: Path | str, etfs: Sequence[Etf]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(build_browser_data(etfs), indent=2) + "\n", encoding="utf-8")


def default_browser_data_paths() -> tuple[Path, ...]:
    packaged = default_static_root() / "browser-data.json"
    repository = Path(__file__).resolve().parents[2] / "browser-data.json"
    return (packaged, repository) if (repository.parent / "pyproject.toml").is_file() else (packaged,)
