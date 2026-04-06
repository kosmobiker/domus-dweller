from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime
from hashlib import sha256
from typing import Any

import duckdb

REQUIRED_FIELDS = ("source", "source_listing_id", "source_url", "mode", "snapshot_date", "layer")


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))


def _payload_hash(row: dict[str, Any]) -> str:
    payload_for_hash = {
        key: row[key]
        for key in sorted(row)
        if key not in {"payload_hash", "raw_json", "ingested_at"}
    }
    return sha256(_canonical_json(payload_for_hash).encode("utf-8")).hexdigest()


def _normalize_row(
    row: dict[str, Any], *, mode: str, snapshot_date: date, ingested_at: datetime
) -> dict[str, Any]:
    base = dict(row)
    base["mode"] = mode
    base.setdefault("layer", "bronze")
    base.setdefault("snapshot_date", snapshot_date.isoformat())
    base["ingested_at"] = ingested_at.astimezone(UTC).isoformat()

    # We store the full row in raw_json
    base["raw_json"] = json.dumps(row)
    base["payload_hash"] = _payload_hash(base)

    # Ensure required fields are present
    missing = [field for field in REQUIRED_FIELDS if not base.get(field)]
    if missing:
        raise ValueError(
            f"Missing required fields for row: {', '.join(sorted(missing))}. "
            f"Row keys: {sorted(base.keys())}"
        )

    return base


def load_rows_to_motherduck(
    rows: list[dict[str, Any]],
    *,
    mode: str,
    database: str = "my_db",
    snapshot_date: date | None = None,
    ingested_at: datetime | None = None,
    token: str | None = None,
) -> int:
    if not rows:
        return 0

    if mode not in {"rent", "sale"}:
        raise ValueError(f"`mode` must be `rent` or `sale`, got: {mode}")

    token = token or os.getenv("MOTHERDUCK_TOKEN")
    if not token:
        raise ValueError("MOTHERDUCK_TOKEN environment variable is not set.")

    effective_snapshot_date = snapshot_date or date.today()
    effective_ingested_at = ingested_at or datetime.now(UTC)

    normalized_rows = [
        _normalize_row(
            row,
            mode=mode,
            snapshot_date=effective_snapshot_date,
            ingested_at=effective_ingested_at,
        )
        for row in rows
    ]

    # Connect to MotherDuck
    con = duckdb.connect(f"md:{database}?token={token}")

    table_name = f"bronze.{mode}_bronze"

    # Use DuckDB's ability to insert from a list of dicts (via a replacement scan or json)
    # Since we have a list of dicts, we can use a temporary view or just JSON string
    json_rows = json.dumps(normalized_rows)

    con.execute(f"INSERT INTO {table_name} SELECT * FROM read_json_auto(?)", [json_rows])

    count = len(normalized_rows)
    con.close()
    return count
