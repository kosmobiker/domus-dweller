from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from domus_dweller.sources.olx.parser import parse_search_results as parse_olx_search_results

PARSERS: dict[str, Callable[[str], list[dict[str, Any]]]] = {
    "olx": parse_olx_search_results,
}


def _build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse saved search-results HTML for a source.")
    parser.add_argument("--source", choices=sorted(PARSERS), required=True)
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to source HTML fixture/file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output JSON file path. Prints to stdout when omitted.",
    )
    return parser.parse_args()


def main() -> None:
    args = _build_args()
    raw_html = args.input.read_text(encoding="utf-8")
    listings = PARSERS[args.source](raw_html)

    payload = json.dumps(listings, ensure_ascii=False, indent=2)
    if args.output is None:
        print(payload)
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload + "\n", encoding="utf-8")
    print(f"Wrote {len(listings)} parsed listings to {args.output}")


if __name__ == "__main__":
    main()
