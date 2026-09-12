from __future__ import annotations

import argparse
import sys
from pathlib import Path

from domus_dweller.sources.olx import fetch


def _build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch OLX search page with TLS impersonation.")
    parser.add_argument("--url", required=True, help="OLX search page URL to fetch.")
    parser.add_argument("--output", type=Path, required=True, help="Target HTML file path.")
    return parser.parse_args()


def main() -> None:
    args = _build_args()
    try:
        html = fetch.fetch_search_page(args.url)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(html, encoding="utf-8")
        print(f"Successfully fetched {args.url} -> {args.output} ({len(html)} bytes)")
    except Exception as exc:
        print(f"Error fetching {args.url}: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
