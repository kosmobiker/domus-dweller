from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from domus_dweller.sinks.motherduck import load_rows_to_motherduck


def _build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Load already parsed+enriched OLX JSON files into MotherDuck Bronze tables "
            "(`rent_bronze` and `sale_bronze`)."
        )
    )
    parser.add_argument("--mode", choices=("rent", "sale", "both"), default="both")
    parser.add_argument(
        "--database",
        default="my_db",
        help="MotherDuck database name. Defaults to `my_db`.",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Snapshot date in YYYY-MM-DD. Defaults to today.",
    )
    parser.add_argument(
        "--input-rent",
        type=Path,
        default=None,
        help="Path to enriched rent file. Defaults to data/parsed/<date>/olx_rent_all.json.",
    )
    parser.add_argument(
        "--input-sale",
        type=Path,
        default=None,
        help="Path to enriched sale file. Defaults to data/parsed/<date>/olx_sale_all.json.",
    )
    return parser.parse_args()


def _default_input_path(*, snapshot_date: date, mode: str) -> Path:
    return Path(f"data/parsed/{snapshot_date.isoformat()}/olx_{mode}_all.json")


def _read_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected list JSON payload in {path}")
    return [row for row in payload if isinstance(row, dict)]


def _sink_mode(
    *,
    mode: str,
    input_path: Path,
    database: str,
    snapshot_date: date,
) -> int:
    rows = _read_rows(input_path)
    inserted = load_rows_to_motherduck(
        rows,
        mode=mode,
        database=database,
        snapshot_date=snapshot_date,
    )
    print(f"[sink:{mode}] Loaded {inserted} rows from {input_path}")
    return inserted


def main() -> None:
    args = _build_args()
    snapshot_date = date.fromisoformat(args.date) if args.date else date.today()
    modes = ["rent", "sale"] if args.mode == "both" else [args.mode]
    input_paths = {
        "rent": args.input_rent or _default_input_path(snapshot_date=snapshot_date, mode="rent"),
        "sale": args.input_sale or _default_input_path(snapshot_date=snapshot_date, mode="sale"),
    }

    total_inserted = 0
    for mode in modes:
        path = input_paths[mode]
        if not path.exists():
            raise FileNotFoundError(f"Input file does not exist for mode `{mode}`: {path}")
        total_inserted += _sink_mode(
            mode=mode,
            input_path=path,
            database=args.database,
            snapshot_date=snapshot_date,
        )

    print(f"Finished loading OLX rows to MotherDuck. Total inserted rows: {total_inserted}.")


if __name__ == "__main__":
    main()
