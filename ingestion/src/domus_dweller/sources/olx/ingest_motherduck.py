from __future__ import annotations

import argparse
from datetime import date
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from domus_dweller.sinks.motherduck import load_rows_to_motherduck
from domus_dweller.sources.olx.parser import parse_search_results

OLX_BASE_URL = "https://www.olx.pl/nieruchomosci"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
)
DEFAULT_CITIES = (
    "krakow",
    "wieliczka",
    "skawina",
    "niepolomice",
    "zabierzow",
    "zielonki",
    "swiatniki-gorne",
)
DEFAULT_RENT_PROPERTY_TYPES = ("mieszkania", "domy", "pokoje")
DEFAULT_SALE_PROPERTY_TYPES = ("mieszkania", "domy")


def _build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch and parse OLX listings, then load rows directly to MotherDuck."
    )
    parser.add_argument("--mode", choices=("rent", "sale", "both"), default="both")
    parser.add_argument(
        "--database",
        default="my_db",
        help="MotherDuck database name. Defaults to `my_db`.",
    )
    parser.add_argument(
        "--snapshot-date",
        default=None,
        help="Snapshot date in YYYY-MM-DD. Defaults to current date.",
    )
    parser.add_argument("--pages", type=int, default=30)
    parser.add_argument("--search-timeout-sec", type=float, default=20.0)
    parser.add_argument("--cities", nargs="+", default=list(DEFAULT_CITIES))
    parser.add_argument(
        "--property-types-rent",
        nargs="+",
        default=list(DEFAULT_RENT_PROPERTY_TYPES),
    )
    parser.add_argument(
        "--property-types-sale",
        nargs="+",
        default=list(DEFAULT_SALE_PROPERTY_TYPES),
    )
    return parser.parse_args()


def _build_search_url(*, mode: str, property_type: str, city: str, page: int) -> str:
    if property_type == "pokoje":
        return f"{OLX_BASE_URL}/stancje-pokoje/{city}/?page={page}"

    mode_slug = "wynajem" if mode == "rent" else "sprzedaz"
    return f"{OLX_BASE_URL}/{property_type}/{mode_slug}/{city}/?page={page}"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
def _fetch_html(url: str, client: httpx.Client, *, timeout_sec: float) -> str:
    response = client.get(url, timeout=timeout_sec)
    response.raise_for_status()
    return response.text


def _collect_search_rows(
    *,
    mode: str,
    cities: list[str],
    property_types: list[str],
    pages: int,
    search_timeout_sec: float,
) -> list[dict[str, Any]]:
    seen_ids: set[str] = set()
    rows: list[dict[str, Any]] = []

    with httpx.Client(
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        for city in cities:
            for property_type in property_types:
                seed = f"{property_type}_{city}"
                print(f"[olx:{mode}] Seed {seed}")
                for page in range(1, pages + 1):
                    url = _build_search_url(
                        mode=mode,
                        property_type=property_type,
                        city=city,
                        page=page,
                    )
                    print(f"[olx:{mode}] Fetch {seed} page {page}/{pages}")
                    try:
                        raw_html = _fetch_html(url, client, timeout_sec=search_timeout_sec)
                    except httpx.HTTPError as exc:
                        print(f"[olx:{mode}] Fetch failed for {seed} page {page}: {exc}")
                        break

                    parsed = parse_search_results(raw_html)
                    if not parsed:
                        print(
                            f"[olx:{mode}] Empty parsed page at {seed} page {page}, stopping seed"
                        )
                        break

                    added = 0
                    for row in parsed:
                        listing_id = str(row.get("source_listing_id", "")).strip()
                        if not listing_id or listing_id in seen_ids:
                            continue
                        seen_ids.add(listing_id)
                        rows.append(row)
                        added += 1
                    print(f"[olx:{mode}] Parsed {len(parsed)} rows ({added} new)")

    return rows


def run_olx_mode_to_motherduck(
    *,
    mode: str,
    database: str,
    cities: list[str],
    property_types: list[str],
    pages: int,
    search_timeout_sec: float,
    snapshot_date: date,
) -> int:
    search_rows = _collect_search_rows(
        mode=mode,
        cities=cities,
        property_types=property_types,
        pages=pages,
        search_timeout_sec=search_timeout_sec,
    )
    print(f"[olx:{mode}] Search rows collected: {len(search_rows)}")

    inserted = load_rows_to_motherduck(
        search_rows,
        mode=mode,
        database=database,
        snapshot_date=snapshot_date,
    )
    print(f"[olx:{mode}] Inserted {inserted} rows into {database}.bronze.{mode}_bronze")
    return inserted


def main() -> None:
    args = _build_args()
    snapshot_date = date.fromisoformat(args.snapshot_date) if args.snapshot_date else date.today()

    modes = ["rent", "sale"] if args.mode == "both" else [args.mode]
    total_inserted = 0
    for mode in modes:
        property_types = args.property_types_rent if mode == "rent" else args.property_types_sale
        inserted = run_olx_mode_to_motherduck(
            mode=mode,
            database=args.database,
            cities=args.cities,
            property_types=property_types,
            pages=args.pages,
            search_timeout_sec=args.search_timeout_sec,
            snapshot_date=snapshot_date,
        )
        total_inserted += inserted

    print(f"Finished OLX MotherDuck ingestion. Total inserted rows: {total_inserted}.")


if __name__ == "__main__":
    main()
