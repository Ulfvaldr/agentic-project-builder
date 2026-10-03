from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
import os
from pathlib import Path
import sys

from .comparison import build_comparison
from .fixtures import default_fixture_path, default_static_root, load_etf_fixtures, load_raw_fixtures
from .server import serve
from .validation import validate_fixtures


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agentic-project-builder")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-fixtures", help="validate committed ETF fixtures")
    validate.add_argument("--fixture", type=Path, default=default_fixture_path())

    server = subparsers.add_parser("serve", help="serve the static demo")
    server.add_argument("--root", type=Path, default=default_static_root())
    server.add_argument("--host", default="")
    server.add_argument("--port", type=int, default=None)

    browser = subparsers.add_parser("check-browser", help="check initial load and reload in Chrome")
    browser.add_argument("--url")
    browser.add_argument("--chrome-path")
    browser.add_argument("--cdp-port", type=int)

    compare = subparsers.add_parser("compare", help="compare two fixture-backed ETFs")
    compare.add_argument("left_ticker")
    compare.add_argument("right_ticker")
    compare.add_argument("--fixture", type=Path, default=default_fixture_path())
    return parser


def _validate_command(path: Path) -> int:
    fixtures = load_raw_fixtures(path)
    errors = validate_fixtures(fixtures)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Validated {len(fixtures)} ETF fixture records with field-level provenance spot-checks.")
    return 0


def _compare_command(left: str, right: str, path: Path) -> int:
    result = build_comparison(left, right, load_etf_fixtures(path))
    print(json.dumps(result.as_dict(), indent=2))
    return 0 if result.validation.valid else 1


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate-fixtures":
        return _validate_command(args.fixture)
    if args.command == "compare":
        return _compare_command(args.left_ticker, args.right_ticker, args.fixture)
    if args.command == "serve":
        port = args.port if args.port is not None else int(os.environ.get("PORT", "4173"))
        serve(args.root, host=args.host, port=port)
        return 0
    if args.command == "check-browser":
        from .browser_check import browser_check_from_environment

        return browser_check_from_environment(
            url=args.url, chrome_path=args.chrome_path, cdp_port=args.cdp_port
        )
    return 2
