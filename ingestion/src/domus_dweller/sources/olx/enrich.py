from __future__ import annotations

import argparse
import contextlib
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from curl_cffi import requests as curl_requests
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from domus_dweller.jsonio import write_json_atomic
from domus_dweller.sources.olx.parser import _is_olx_url, parse_detail_page

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
)

# Detail pages that are blocked or gone will not become available by retrying.
PERMANENT_HTTP_STATUSES = frozenset({403, 404, 410})
SKIPPED_DETAIL_STATUSES = PERMANENT_HTTP_STATUSES

COMMON_DETAIL_PARAM_KEYS = {
    "powierzchnia",
    "powierzchnia działki",
    "rodzaj zabudowy",
    "liczba pokoi",
    "poziom",
    "liczba pięter",
    "umeblowane",
}
RENT_DETAIL_PARAM_KEYS = {
    "czynsz (dodatkowo)",
    "zwierzęta",
    "winda",
    "parking",
    "rodzaj pokoju",
    "preferowani",
}
SALE_DETAIL_PARAM_KEYS = {
    "cena za m²",
    "rynek",
}

DEFAULT_WORKERS = 8


class EnrichmentDatabaseError(RuntimeError):
    """Raised when the listing database cannot be reached for `--only-new`."""


class RateLimiter:
    """Global minimum interval between request starts, shared across threads.

    Concurrency is bounded by the worker count, but politeness is bounded here.
    This keeps the request rate independent of how many workers are in flight,
    which is the property we actually care about for staying unblocked.
    """

    def __init__(
        self,
        min_interval_sec: float,
        *,
        clock: Any = time.monotonic,
        sleep: Any = time.sleep,
    ) -> None:
        self._min_interval = max(0.0, min_interval_sec)
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._next_start = 0.0

    def acquire(self) -> None:
        if self._min_interval <= 0:
            return
        with self._lock:
            now = self._clock()
            start_at = max(now, self._next_start)
            self._next_start = start_at + self._min_interval
        delay = start_at - self._clock()
        if delay > 0:
            self._sleep(delay)


def _build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Enrich parsed OLX listing rows by opening each source URL and extracting "
            "detail-page attributes."
        )
    )
    parser.add_argument("--input", type=Path, required=True, help="Input merged OLX listings JSON.")
    parser.add_argument("--output", type=Path, required=True, help="Output enriched JSON path.")
    parser.add_argument(
        "--save-html-dir",
        type=Path,
        default=None,
        help="Optional directory to store fetched detail HTML.",
    )
    parser.add_argument(
        "--pause-ms",
        type=int,
        default=250,
        help=(
            "Minimum interval between detail requests in milliseconds, shared across "
            "workers. Defaults to 250 (4 requests/second)."
        ),
    )
    parser.add_argument(
        "--timeout-sec",
        type=float,
        default=20.0,
        help="Per-request timeout in seconds. Defaults to 20.",
    )
    parser.add_argument(
        "--mode",
        choices=("auto", "rent", "sale"),
        default="auto",
        help=(
            "Listing mode for track-specific fields. "
            "Use `rent`/`sale` when known, otherwise `auto`."
        ),
    )
    parser.add_argument(
        "--max-consecutive-403",
        type=int,
        default=8,
        help=(
            "Fail-fast guard for blocked detail fetches. "
            "When this many 403 responses occur in a row, stop detail fetching and "
            "keep remaining listings unchanged. Set 0 to disable."
        ),
    )
    parser.add_argument(
        "--only-new",
        action="store_true",
        default=False,
        help="Only fetch detail pages for listings not already present in MotherDuck/DuckDB.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=(
            "Concurrent detail-page workers. Request rate is still governed by "
            f"--pause-ms. Defaults to {DEFAULT_WORKERS}."
        ),
    )
    parser.add_argument(
        "--database",
        default="my_db",
        help="Database to check for existing listings when --only-new is enabled.",
    )
    return parser.parse_args()


def _status_code_from_exception(exc: BaseException) -> int | None:
    """Read the HTTP status from curl_cffi and httpx error objects."""
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    return status_code if isinstance(status_code, int) else None


def _is_retryable_fetch_error(exc: BaseException) -> bool:
    return _status_code_from_exception(exc) not in PERMANENT_HTTP_STATUSES


@retry(
    retry=retry_if_exception(_is_retryable_fetch_error),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
def _fetch_html(url: str, client: Any, *, timeout_sec: float) -> str:
    response = client.get(url, timeout=timeout_sec)
    response.raise_for_status()
    return response.text


def fetch_existing_listing_ids(*, database: str = "my_db", token: str | None = None) -> set[str]:
    """Retrieve existing source_listing_ids from MotherDuck or local DuckDB.

    A missing table is treated as "no known listings yet" (fresh database, before
    bootstrap). A connection failure raises instead of returning an empty set:
    silently falling back to an empty set would turn `--only-new` into a full
    re-crawl of every listing, which is both very slow and a fast route to being
    rate limited.
    """
    import os

    import duckdb
    from dotenv import load_dotenv

    load_dotenv()
    token = token or os.getenv("MOTHERDUCK_TOKEN")
    is_local_file = (
        not token
        or token.lower() == "local"
        or database.endswith((".duckdb", ".db"))
        or Path(database).exists()
    )

    try:
        if is_local_file:
            con = duckdb.connect(database)
        else:
            con = duckdb.connect(f"md:{database}?token={token}")
    except Exception as exc:
        raise EnrichmentDatabaseError(
            f"could not connect to database {database!r} for --only-new lookup: {exc}"
        ) from exc

    existing_ids: set[str] = set()
    query_errors: list[str] = []
    try:
        for sql in (
            "SELECT DISTINCT source_listing_id FROM silver.listing_identity WHERE source = 'olx'",
            "SELECT DISTINCT source_listing_id FROM bronze.rent_bronze WHERE source = 'olx'",
            "SELECT DISTINCT source_listing_id FROM bronze.sale_bronze WHERE source = 'olx'",
        ):
            try:
                rows = con.execute(sql).fetchall()
            except Exception as exc:  # table may not exist yet
                query_errors.append(f"{sql.split(' FROM ')[1].split()[0]}: {exc}")
                continue
            existing_ids.update(str(row[0]).strip() for row in rows if row[0])
    finally:
        con.close()

    if query_errors and not existing_ids:
        print(
            "[enrich] Warning: no existing listing IDs found and some lookups failed: "
            + "; ".join(query_errors)
        )
    return existing_ids


def _split_detail_params_by_track(
    detail_params: dict[str, Any], *, mode: str | None
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    common: dict[str, Any] = {}
    rent_only: dict[str, Any] = {}
    sale_only: dict[str, Any] = {}

    for key, value in detail_params.items():
        normalized_key = str(key).strip().casefold()
        if normalized_key in COMMON_DETAIL_PARAM_KEYS:
            common[normalized_key] = value
            continue
        if normalized_key in RENT_DETAIL_PARAM_KEYS:
            rent_only[normalized_key] = value
            continue
        if normalized_key in SALE_DETAIL_PARAM_KEYS:
            sale_only[normalized_key] = value
            continue

        # Unknown params are still preserved under active mode track.
        if mode == "rent":
            rent_only[normalized_key] = value
        elif mode == "sale":
            sale_only[normalized_key] = value

    return common, rent_only, sale_only


def _infer_mode(*, listing: dict[str, Any], default_mode: str | None) -> str | None:
    raw_mode = str(listing.get("mode", "")).strip().casefold()
    if raw_mode in {"rent", "sale"}:
        return raw_mode

    source_url = str(listing.get("source_url", "")).casefold()
    if "/wynajem/" in source_url:
        return "rent"
    if "/sprzedaz/" in source_url:
        return "sale"

    if default_mode in {"rent", "sale"}:
        return default_mode
    return None


def _merge_listing_with_details(
    listing: dict[str, Any], details: dict[str, Any], *, mode: str | None
) -> dict[str, Any]:
    merged = dict(listing)
    detail_params = details.get("detail_params")
    if isinstance(detail_params, dict):
        common, rent_only, sale_only = _split_detail_params_by_track(detail_params, mode=mode)
        merged["detail_params_common"] = common
        merged["detail_params_rent"] = rent_only if mode == "rent" else {}
        merged["detail_params_sale"] = sale_only if mode == "sale" else {}

    if mode in {"rent", "sale"}:
        merged["mode"] = mode

    for key, value in details.items():
        if key == "seller_segment":
            if value and value != "unknown":
                merged[key] = value
            continue

        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, (dict, list)) and not value:
            continue
        merged[key] = value
    return merged


def enrich_listings(
    listings: list[dict[str, Any]],
    *,
    save_html_dir: Path | None,
    pause_ms: int,
    timeout_sec: float,
    default_mode: str | None,
    max_consecutive_403: int = 8,
    existing_ids: set[str] | None = None,
    workers: int = 1,
) -> list[dict[str, Any]]:
    """Fetch detail pages for new listings and merge the extracted fields.

    `pause_ms` is the *global* minimum interval between request starts, shared by
    every worker. Raising `workers` overlaps in-flight requests so latency is
    hidden, but it does not raise the request rate: politeness is controlled by
    `pause_ms` alone. That is the whole point — wall-clock time drops without
    making the crawl more aggressive.
    """
    if save_html_dir is not None:
        save_html_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = [dict(listing) for listing in listings]
    pending: list[int] = []
    skipped_existing = 0
    skipped_offsite = 0

    for index, listing in enumerate(listings):
        source_listing_id = str(listing.get("source_listing_id", "")).strip()
        source_url = str(listing.get("source_url", "")).strip()

        if existing_ids is not None and source_listing_id in existing_ids:
            skipped_existing += 1
            continue
        if not source_url:
            continue
        if not _is_olx_url(source_url):
            # Cross-site promo cards (e.g. Otodom) can never be enriched here.
            skipped_offsite += 1
            continue
        pending.append(index)

    limiter = RateLimiter(pause_ms / 1000)
    stop_event = threading.Event()
    lock = threading.Lock()
    counters = {"consecutive_403": 0, "unavailable": 0, "fetched": 0}
    errors: list[BaseException] = []
    sessions: list[Any] = []
    thread_local = threading.local()

    def _client() -> Any:
        """One session per thread; a curl handle is not safe to share."""
        client = getattr(thread_local, "client", None)
        if client is None:
            client = curl_requests.Session(impersonate="chrome120")
            thread_local.client = client
            with lock:
                sessions.append(client)
        return client

    def _fetch(index: int) -> None:
        if stop_event.is_set():
            return

        listing = listings[index]
        source_listing_id = str(listing.get("source_listing_id", "")).strip()
        source_url = str(listing.get("source_url", "")).strip()

        limiter.acquire()
        if stop_event.is_set():
            return

        print(f"[enrich] Processing {index + 1}/{len(listings)}")
        try:
            raw_html = _fetch_html(source_url, _client(), timeout_sec=timeout_sec)
        except Exception as exc:
            status_code = _status_code_from_exception(exc)
            if status_code not in SKIPPED_DETAIL_STATUSES:
                stop_event.set()
                with lock:
                    if not errors:
                        errors.append(exc)
                return

            print(
                f"[enrich] Skipping detail page for listing due to HTTP {status_code}: {source_url}"
            )
            with lock:
                counters["unavailable"] += 1
                if status_code == 403:
                    counters["consecutive_403"] += 1
                    threshold_reached = (
                        max_consecutive_403 > 0
                        and counters["consecutive_403"] >= max_consecutive_403
                    )
                else:
                    counters["consecutive_403"] = 0
                    threshold_reached = False

            if threshold_reached:
                print(
                    "[enrich] Consecutive 403 threshold reached. "
                    "Stopping detail fetches and preserving remaining rows."
                )
                stop_event.set()
            return

        with lock:
            counters["consecutive_403"] = 0
            counters["fetched"] += 1

        if save_html_dir is not None:
            file_name = source_listing_id if source_listing_id else f"listing_{index + 1}"
            (save_html_dir / f"{file_name}.html").write_text(raw_html, encoding="utf-8")

        detail_fields = parse_detail_page(raw_html)
        listing_mode = _infer_mode(listing=listing, default_mode=default_mode)
        results[index] = _merge_listing_with_details(listing, detail_fields, mode=listing_mode)

    if pending:
        try:
            with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
                futures = [executor.submit(_fetch, index) for index in pending]
                for future in as_completed(futures):
                    exc = future.exception()
                    if exc is not None:
                        stop_event.set()
                        with lock:
                            if not errors:
                                errors.append(exc)
        finally:
            for client in sessions:
                with contextlib.suppress(Exception):
                    client.close()

    if skipped_existing > 0:
        print(f"[enrich] Skipped {skipped_existing} existing listings (only-new delta enrichment).")
    if skipped_offsite > 0:
        print(
            f"[enrich] Skipped {skipped_offsite} off-site URLs (not olx.pl); "
            "rows were kept unchanged."
        )
    if counters["unavailable"] > 0:
        print(
            f"[enrich] Skipped {counters['unavailable']} detail pages with HTTP "
            f"{sorted(SKIPPED_DETAIL_STATUSES)}; rows were kept unchanged."
        )
    print(
        f"[enrich] Fetched {counters['fetched']}/{len(pending)} pending detail pages "
        f"with {max(1, workers)} worker(s)."
    )

    if errors:
        raise errors[0]
    return results


def _read_listing_rows(input_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected list payload in {input_path}")
    return [row for row in payload if isinstance(row, dict)]


def main() -> None:
    args = _build_args()
    if not args.input.exists():
        print(f"[enrich] Input file {args.input} does not exist. Skipping enrichment.")
        return
    rows = _read_listing_rows(args.input)
    if not rows:
        print(f"[enrich] No listings found in {args.input}. Skipping enrichment.")
        return
    mode = None if args.mode == "auto" else args.mode

    existing_ids: set[str] | None = None
    if args.only_new:
        try:
            existing_ids = fetch_existing_listing_ids(database=args.database)
        except EnrichmentDatabaseError as exc:
            print(f"[enrich] ERROR: {exc}", file=sys.stderr)
            print(
                "[enrich] Refusing to fall back to a full re-crawl. "
                "Re-run once the database is reachable.",
                file=sys.stderr,
            )
            raise SystemExit(2) from exc
        print(
            f"[enrich] Found {len(existing_ids)} existing listing IDs in database {args.database}"
        )

    enriched_rows = enrich_listings(
        rows,
        save_html_dir=args.save_html_dir,
        pause_ms=args.pause_ms,
        timeout_sec=args.timeout_sec,
        default_mode=mode,
        max_consecutive_403=args.max_consecutive_403,
        existing_ids=existing_ids,
        workers=args.workers,
    )
    write_json_atomic(args.output, enriched_rows)
    print(
        f"Wrote {len(enriched_rows)} enriched OLX listings to {args.output} "
        f"(input rows: {len(rows)})."
    )


if __name__ == "__main__":
    main()
