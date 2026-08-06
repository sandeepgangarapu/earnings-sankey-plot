from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .models import Statement
from .normalize import available_periods, normalize_companyfacts
from .render import render_html, render_svg
from .sec import SECClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_PATH = PROJECT_ROOT / "examples" / "alphabet_q1_fy26.json"


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}.")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a standardized income-statement Sankey diagram."
    )
    parser.add_argument("ticker", nargs="?", help="SEC ticker, for example AAPL")
    parser.add_argument("--fiscal-year", "--fy", type=int)
    parser.add_argument("--period", choices=("Q1", "Q2", "Q3", "FY"))
    parser.add_argument(
        "--user-agent",
        default=os.environ.get("SEC_USER_AGENT"),
        help="Declared SEC user agent (or set SEC_USER_AGENT).",
    )
    parser.add_argument("--sample", action="store_true", help="Render the bundled example.")
    parser.add_argument("--input", type=Path, help="Render a normalized Statement JSON file.")
    parser.add_argument(
        "--override",
        type=Path,
        help="JSON fields to layer over SEC-normalized data (useful for segment detail).",
    )
    parser.add_argument("--output", type=Path, help="Destination HTML path.")
    parser.add_argument("--json-output", type=Path, help="Also save normalized JSON.")
    parser.add_argument("--svg-output", type=Path, help="Also save the chart as SVG.")
    return parser


def _statement_from_args(args: argparse.Namespace) -> Statement:
    if args.input:
        return Statement.from_dict(_load_json(args.input))
    if args.sample:
        return Statement.from_dict(_load_json(SAMPLE_PATH))
    if not args.ticker:
        raise ValueError("Provide a ticker, --sample, or --input.")
    if not args.user_agent:
        raise ValueError(
            "Set SEC_USER_AGENT to your name/company and contact email before using SEC data."
        )

    client = SECClient(args.user_agent)
    identity, companyfacts = client.companyfacts(args.ticker)
    periods = available_periods(companyfacts)
    matching = [
        item
        for item in periods
        if (args.fiscal_year is None or item["fiscal_year"] == args.fiscal_year)
        and (args.period is None or item["period"] == args.period)
    ]
    if not matching:
        raise ValueError(
            f"No SEC period matched fiscal_year={args.fiscal_year!r}, period={args.period!r}."
        )
    selected = matching[0]
    return normalize_companyfacts(
        companyfacts,
        identity,
        selected["fiscal_year"],
        selected["period"],
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        statement = _statement_from_args(args)
        if args.override:
            statement = statement.with_override(_load_json(args.override))
        output = args.output or Path("output") / (
            f"{statement.ticker.lower()}-{statement.fiscal_year}-{statement.period.lower()}.html"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render_html(statement), encoding="utf-8")
        if args.json_output:
            args.json_output.parent.mkdir(parents=True, exist_ok=True)
            args.json_output.write_text(
                json.dumps(statement.to_dict(), indent=2) + "\n", encoding="utf-8"
            )
        if args.svg_output:
            args.svg_output.parent.mkdir(parents=True, exist_ok=True)
            args.svg_output.write_text(render_svg(statement) + "\n", encoding="utf-8")
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    print(f"Created {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
