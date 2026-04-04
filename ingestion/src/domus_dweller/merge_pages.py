from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path


def _build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge paginated parsed JSON files into one deduplicated file."
    )
    parser.add_argument("--pattern", required=True, help="Glob pattern for input JSON files.")
    parser.add_argument("--output", type=Path, required=True, help="Output merged JSON path.")
    return parser.parse_args()


def _merge_unique(records: list[dict]) -> list[dict]:
    seen: set[str] = set()
    merged: list[dict] = []
    for row in records:
        listing_id = str(row.get("source_listing_id", "")).strip()
        if not listing_id or listing_id in seen:
            continue
        seen.add(listing_id)
        merged.append(row)
    return merged


def main() -> None:
    args = _build_args()
    rows: list[dict] = []
    for file_path in sorted(glob.glob(args.pattern)):
        payload = json.loads(Path(file_path).read_text(encoding="utf-8"))
        if isinstance(payload, list):
            rows.extend(payload)
    merged = _merge_unique(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(merged)} unique listings to {args.output}")


if __name__ == "__main__":
    main()
