from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from curl_cffi import requests as curl_requests
from tenacity import retry, stop_after_attempt, wait_exponential

from domus_dweller.sources.olx.parser import parse_detail_page

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
)

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
        help="Pause between detail requests in milliseconds. Defaults to 250.",
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
        "--database",
        default="my_db",
        help="Database to check for existing listings when --only-new is enabled.",
    )
    return parser.parse_args()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
def _fetch_html(url: str, client: Any, *, timeout_sec: float) -> str:
    response = client.get(url, timeout=timeout_sec)
    response.raise_for_status()
    return response.text


def fetch_existing_listing_ids(*, database: str = "my_db", token: str | None = None) -> set[str]:
    """Retrieve existing source_listing_ids from MotherDuck or local DuckDB."""
    import os

    import duckdb
    from dotenv import load_dotenv

    load_dotenv()
    token = token or os.getenv("MOTHERDUCK_TOKEN")
    try:
        is_local_file = (
            not token
            or token.lower() == "local"
            or database.endswith((".duckdb", ".db"))
            or Path(database).exists()
        )
        if is_local_file:
            con = duckdb.connect(database)
        else:
            con = duckdb.connect(f"md:{database}?token={token}")

        existing_ids: set[str] = set()
        # Query silver.listing_identity
        try:
            sql = (
                "SELECT DISTINCT source_listing_id FROM silver.listing_identity "
                "WHERE source = 'olx'"
            )
            rows = con.execute(sql).fetchall()
            existing_ids.update(str(r[0]).strip() for r in rows if r[0])
        except Exception:
            pass

        # Also query bronze tables if present
        for tbl in ["bronze.rent_bronze", "bronze.sale_bronze"]:
            try:
                rows = con.execute(
                    f"SELECT DISTINCT source_listing_id FROM {tbl} WHERE source = 'olx'"
                ).fetchall()
                existing_ids.update(str(r[0]).strip() for r in rows if r[0])
            except Exception:
                pass

        con.close()
        return existing_ids
    except Exception as exc:
        print(f"[enrich] Warning: could not connect to database {database} for existing IDs: {exc}")
        return set()


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
) -> list[dict[str, Any]]:
    if save_html_dir is not None:
        save_html_dir.mkdir(parents=True, exist_ok=True)

    enriched_rows: list[dict[str, Any]] = []
    skipped_existing = 0

    with curl_requests.Session(impersonate="chrome120") as client:
        consecutive_403 = 0
        for index, listing in enumerate(listings):
            source_listing_id = str(listing.get("source_listing_id", "")).strip()
            source_url = str(listing.get("source_url", "")).strip()

            if existing_ids and source_listing_id in existing_ids:
                skipped_existing += 1
                enriched_rows.append(dict(listing))
                continue

            print(f"[enrich] Processing {index + 1}/{len(listings)}")
            if not source_url:
                consecutive_403 = 0
                enriched_rows.append(dict(listing))
                continue

            try:
                raw_html = _fetch_html(source_url, client, timeout_sec=timeout_sec)
            except Exception as exc:
                # Check for HTTP 403 or 404 on either curl_cffi or httpx error
                response = getattr(exc, "response", None)
                status_code = getattr(response, "status_code", None)

                if status_code in {403, 404}:
                    print(
                        f"[enrich] Skipping detail page for listing due to HTTP {status_code}: "
                        f"{source_url}"
                    )
                    enriched_rows.append(dict(listing))
                    if status_code == 403:
                        consecutive_403 += 1
                        if max_consecutive_403 > 0 and consecutive_403 >= max_consecutive_403:
                            print(
                                "[enrich] Consecutive 403 threshold reached. "
                                "Stopping detail fetches and preserving remaining rows."
                            )
                            for tail_listing in listings[index + 1 :]:
                                enriched_rows.append(dict(tail_listing))
                            break
                    else:
                        consecutive_403 = 0
                    if pause_ms > 0 and index < len(listings) - 1:
                        time.sleep(pause_ms / 1000)
                    continue
                raise

            consecutive_403 = 0
            if save_html_dir is not None:
                file_name = source_listing_id if source_listing_id else f"listing_{index + 1}"
                (save_html_dir / f"{file_name}.html").write_text(raw_html, encoding="utf-8")

            detail_fields = parse_detail_page(raw_html)
            listing_mode = _infer_mode(listing=listing, default_mode=default_mode)
            enriched_rows.append(
                _merge_listing_with_details(listing, detail_fields, mode=listing_mode)
            )

            if pause_ms > 0 and index < len(listings) - 1:
                time.sleep(pause_ms / 1000)

    if skipped_existing > 0:
        print(f"[enrich] Skipped {skipped_existing} existing listings (only-new delta enrichment).")
    return enriched_rows


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
        existing_ids = fetch_existing_listing_ids(database=args.database)
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
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(enriched_rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {len(enriched_rows)} enriched OLX listings to {args.output} "
        f"(input rows: {len(rows)})."
    )


if __name__ == "__main__":
    main()
