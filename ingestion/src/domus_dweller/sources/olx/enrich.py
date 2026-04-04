from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import httpx
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
    return parser.parse_args()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
def _fetch_html(url: str, client: httpx.Client, *, timeout_sec: float) -> str:
    response = client.get(url, timeout=timeout_sec)
    response.raise_for_status()
    return response.text


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
) -> list[dict[str, Any]]:
    if save_html_dir is not None:
        save_html_dir.mkdir(parents=True, exist_ok=True)

    enriched_rows: list[dict[str, Any]] = []
    with httpx.Client(
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        consecutive_403 = 0
        for index, listing in enumerate(listings):
            print(f"[enrich] Processing {index + 1}/{len(listings)}")
            source_url = str(listing.get("source_url", "")).strip()
            if not source_url:
                consecutive_403 = 0
                enriched_rows.append(dict(listing))
                continue

            try:
                raw_html = _fetch_html(source_url, client, timeout_sec=timeout_sec)
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code if exc.response is not None else None
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
                source_listing_id = str(listing.get("source_listing_id", "")).strip()
                file_name = source_listing_id if source_listing_id else f"listing_{index + 1}"
                (save_html_dir / f"{file_name}.html").write_text(raw_html, encoding="utf-8")

            detail_fields = parse_detail_page(raw_html)
            listing_mode = _infer_mode(listing=listing, default_mode=default_mode)
            enriched_rows.append(
                _merge_listing_with_details(listing, detail_fields, mode=listing_mode)
            )

            if pause_ms > 0 and index < len(listings) - 1:
                time.sleep(pause_ms / 1000)

    return enriched_rows


def _read_listing_rows(input_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected list payload in {input_path}")
    return [row for row in payload if isinstance(row, dict)]


def main() -> None:
    args = _build_args()
    rows = _read_listing_rows(args.input)
    mode = None if args.mode == "auto" else args.mode
    enriched_rows = enrich_listings(
        rows,
        save_html_dir=args.save_html_dir,
        pause_ms=args.pause_ms,
        timeout_sec=args.timeout_sec,
        default_mode=mode,
        max_consecutive_403=args.max_consecutive_403,
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
