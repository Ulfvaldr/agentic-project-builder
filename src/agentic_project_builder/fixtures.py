from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path
from typing import Any

from .models import Etf


TextReader = Callable[..., str]


_PACKAGE_ROOT = Path(__file__).resolve().parent


def default_static_root() -> Path:
    return _PACKAGE_ROOT / "site"


def default_fixture_path() -> Path:
    return default_static_root() / "fixtures" / "etfs.json"


def load_raw_fixtures(
    path: Path | str | None = None,
    *,
    reader: TextReader = Path.read_text,
) -> Any:
    fixture_path = Path(path) if path is not None else default_fixture_path()
    return json.loads(reader(fixture_path, encoding="utf-8"))


def load_etf_fixtures(
    path: Path | str | None = None,
    *,
    reader: TextReader = Path.read_text,
) -> tuple[Etf, ...]:
    values = load_raw_fixtures(path, reader=reader)
    return tuple(Etf.from_mapping(value) for value in values)
