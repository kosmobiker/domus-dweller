from __future__ import annotations

import argparse
import glob
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from curl_cffi import requests as curl_requests

from domus_dweller.merge_pages import _merge_unique
from domus_dweller.sources.olx.parser import parse_search_results

DEFAULT_CITIES = [
    "krakow",
    "wieliczka",
    "skawina",
    "niepolomice",
    "zabierzow",
    "zielonki",
    "swiatniki-gorne",
]

DEFAULT_RENT_PROPERTIES = ["mieszkania", "domy", "pokoje"]
DEFAULT_SALE_PROPERTIES = ["mieszkania", "domy"]
OLX_BASE_URL = "https://www.olx.pl/nieruchomosci"


@dataclass(frozen=True)
class Seed:
    mode: str
    city: str
    property_type: str
    seed_name: str
    base_url: str


@dataclass
class CrawlSummary:
    mode: str
    seeds_processed: int
    pages_fetched: int
    total_unique_listings: int
    duration_seconds: float


def build_seeds(
    *,
    mode: str,
    cities: list[str],
    property_types: list[str] | None = None,
) -> list[Seed]:
    if property_types is None:
        property_types = DEFAULT_RENT_PROPERTIES if mode == "rent" else DEFAULT_SALE_PROPERTIES

    seeds: list[Seed] = []
    mode_slug = "wynajem" if mode == "rent" else "sprzedaz"

    for city in cities:
        for prop in property_types:
            seed_name = f"{prop}_{city}"
            if prop == "pokoje":
                category_slug = "stancje-pokoje"
                base_url = f"{OLX_BASE_URL}/{category_slug}/{city}/"
            else:
                base_url = f"{OLX_BASE_URL}/{prop}/{mode_slug}/{city}/"

            seeds.append(
                Seed(
                    mode=mode,
                    city=city,
                    property_type=prop,
                    seed_name=seed_name,
                    base_url=base_url,
                )
            )
    return seeds


def fetch_page(
    url: str,
    session: curl_requests.Session | None = None,
    *,
    timeout: int = 45,
    max_retries: int = 3,
    retry_delay: float = 2.0,
    impersonate: str = "chrome120",
) -> str:
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            if session is not None:
                response = session.get(url, timeout=timeout)
            else:
                response = curl_requests.get(
                    url,
                    impersonate=impersonate,
                    timeout=timeout,
                )

            if response.status_code == 200:
                return response.text

            msg = (
                f"Failed to fetch {url}: HTTP {response.status_code} "
                f"on attempt {attempt}/{max_retries}"
            )
            last_error = RuntimeError(msg)
        except Exception as exc:  # noqa: BLE001
            last_error = RuntimeError(
                f"Network error fetching {url} on attempt {attempt}/{max_retries}: {exc}"
            )

        if attempt < max_retries:
            time.sleep(retry_delay * attempt)

    if last_error:
        raise last_error
    raise RuntimeError(f"Failed to fetch {url} after {max_retries} attempts")


def _crawl_seed(
    seed: Seed,
    *,
    max_pages: int,
    raw_dir: Path,
    parsed_dir: Path,
    session: curl_requests.Session | None = None,
) -> tuple[int, int]:
    """Crawl a single seed sequentially up to max_pages.

    Returns (pages_fetched, total_items_extracted).
    """
    seen_ids: set[str] = set()
    pages_fetched = 0
    total_items = 0

    print(f"[OLX {seed.mode}] Seed {seed.seed_name}")

    for page in range(1, max_pages + 1):
        url = f"{seed.base_url}?page={page}"
        raw_path = raw_dir / f"olx_{seed.mode}_{seed.seed_name}_page_{page}.html"
        parsed_path = parsed_dir / f"olx_{seed.mode}_{seed.seed_name}_page_{page}.json"

        print(f"[OLX {seed.mode}] Fetch {seed.seed_name} page {page}/{max_pages}")
        try:
            html = fetch_page(url, session=session)
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(html, encoding="utf-8")
        except Exception as exc:
            print(
                f"[OLX {seed.mode}] Fetch failed for {seed.seed_name} page {page}: {exc}, "
                "stopping seed"
            )
            if raw_path.exists():
                raw_path.unlink()
            break

        pages_fetched += 1
        print(f"[OLX {seed.mode}] Parse {seed.seed_name} page {page}/{max_pages}")
        listings = parse_search_results(html)

        if not listings:
            print(
                f"[OLX {seed.mode}] Empty parsed page at {seed.seed_name} page {page}, "
                "stopping this seed"
            )
            if raw_path.exists():
                raw_path.unlink()
            break

        # Check for pagination loop / wrapping (e.g. OLX repeating earlier pages)
        page_ids = [str(item.get("source_listing_id", "")).strip() for item in listings]
        page_ids = [pid for pid in page_ids if pid]

        if page > 1 and page_ids:
            overlap = sum(1 for pid in page_ids if pid in seen_ids)
            overlap_ratio = overlap / len(page_ids)
            if overlap_ratio >= 0.6:
                print(
                    f"[OLX {seed.mode}] Pagination loop detected at {seed.seed_name} "
                    f"page {page} ({overlap}/{len(page_ids)} duplicates, {overlap_ratio:.0%}), "
                    "stopping this seed"
                )
                if raw_path.exists():
                    raw_path.unlink()
                break

        seen_ids.update(page_ids)
        parsed_path.parent.mkdir(parents=True, exist_ok=True)
        parsed_path.write_text(
            json.dumps(listings, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        total_items += len(listings)
        print(f"Wrote {len(listings)} parsed listings to {parsed_path}")

    return pages_fetched, total_items


def run_crawl(
    *,
    mode: str,
    cities: list[str],
    property_types: list[str] | None = None,
    max_pages: int = 30,
    workers: int = 4,
    raw_dir: Path,
    parsed_dir: Path,
    snapshot_date: str,
) -> CrawlSummary:
    start_time = time.monotonic()
    raw_dir.mkdir(parents=True, exist_ok=True)
    parsed_dir.mkdir(parents=True, exist_ok=True)

    seeds = build_seeds(mode=mode, cities=cities, property_types=property_types)
    print(
        f"Starting OLX {mode} run for {snapshot_date} "
        f"(pages={max_pages}, cities={len(cities)}, seeds={len(seeds)}, workers={workers})"
    )

    total_pages_fetched = 0

    if workers <= 1:
        with curl_requests.Session(impersonate="chrome120") as session:
            for seed in seeds:
                pages, _ = _crawl_seed(
                    seed,
                    max_pages=max_pages,
                    raw_dir=raw_dir,
                    parsed_dir=parsed_dir,
                    session=session,
                )
                total_pages_fetched += pages
    else:

        def _worker_task(seed: Seed) -> int:
            with curl_requests.Session(impersonate="chrome120") as session:
                pages, _ = _crawl_seed(
                    seed,
                    max_pages=max_pages,
                    raw_dir=raw_dir,
                    parsed_dir=parsed_dir,
                    session=session,
                )
                return pages

        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_seed = {executor.submit(_worker_task, seed): seed for seed in seeds}
            for future in as_completed(future_to_seed):
                try:
                    pages = future.result()
                    total_pages_fetched += pages
                except Exception as exc:
                    seed = future_to_seed[future]
                    print(f"[OLX {mode}] Worker failed for seed {seed.seed_name}: {exc}")

    print(f"[OLX {mode}] Merge search pages")
    pattern = str(parsed_dir / f"olx_{mode}_*_page_*.json")
    all_rows: list[dict] = []
    for file_path in sorted(glob.glob(pattern)):
        try:
            payload = json.loads(Path(file_path).read_text(encoding="utf-8"))
            if isinstance(payload, list):
                all_rows.extend(payload)
        except Exception as exc:
            print(f"Warning: could not read {file_path}: {exc}")

    merged = _merge_unique(all_rows)
    merged_output = parsed_dir / f"olx_{mode}_all.json"
    merged_output.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(merged)} unique listings to {merged_output}")
    print(f"Finished OLX {mode} run for {snapshot_date}")

    duration = time.monotonic() - start_time
    return CrawlSummary(
        mode=mode,
        seeds_processed=len(seeds),
        pages_fetched=total_pages_fetched,
        total_unique_listings=len(merged),
        duration_seconds=duration,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="High-speed concurrent search orchestrator for OLX housing listings."
    )
    parser.add_argument(
        "--mode",
        choices=("rent", "sale", "both"),
        default="both",
        help="Crawl mode: rent, sale, or both (default: both).",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Snapshot date (YYYY-MM-DD). Defaults to UTC today.",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=30,
        help="Max pages per seed (default: 30).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Concurrent seed workers (default: 4).",
    )
    parser.add_argument(
        "--cities",
        default=None,
        help=(
            "Space- or comma-separated list of cities to crawl. "
            "Defaults to Kraków + 6 municipalities."
        ),
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=None,
        help="Directory to save raw HTML files. Defaults to data/raw/<date>.",
    )
    parser.add_argument(
        "--parsed-dir",
        type=Path,
        default=None,
        help="Directory to save parsed JSON files. Defaults to data/parsed/<date>.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    snapshot_date = args.date or date.today().isoformat()

    if args.cities:
        # Support space or comma separation
        raw_cities = args.cities.replace(",", " ").split()
        cities = [c.strip().lower() for c in raw_cities if c.strip()]
    else:
        cities = DEFAULT_CITIES

    raw_dir = args.raw_dir or Path(f"data/raw/{snapshot_date}")
    parsed_dir = args.parsed_dir or Path(f"data/parsed/{snapshot_date}")

    modes = ["rent", "sale"] if args.mode == "both" else [args.mode]
    summaries: list[CrawlSummary] = []

    for mode in modes:
        summary = run_crawl(
            mode=mode,
            cities=cities,
            max_pages=args.pages,
            workers=args.workers,
            raw_dir=raw_dir,
            parsed_dir=parsed_dir,
            snapshot_date=snapshot_date,
        )
        summaries.append(summary)

    print("\n================== CRAWL SUMMARY ==================")
    for s in summaries:
        print(
            f"Mode: {s.mode:<5} | Seeds: {s.seeds_processed} | Pages: {s.pages_fetched} | "
            f"Listings: {s.total_unique_listings} | Time: {s.duration_seconds:.1f}s"
        )
    print("===================================================\n")


if __name__ == "__main__":
    main()
