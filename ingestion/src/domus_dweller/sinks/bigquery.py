from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime
from hashlib import sha256
from typing import Any, Protocol

from domus_dweller.sinks.bigquery_bootstrap import BRONZE_SCHEMA_FIELDS


class BigQueryClientProtocol(Protocol):
    def load_table_from_json(
        self,
        json_rows: list[dict[str, Any]],
        destination: str,
        *,
        job_config: Any | None = None,
    ) -> Any:
        ...


REQUIRED_FIELDS = ("source", "source_listing_id", "source_url", "mode", "snapshot_date", "layer")


@dataclass(frozen=True)
class BigQueryTarget:
    project: str
    dataset: str
    mode: str

    @property
    def table_id(self) -> str:
        return f"{self.project}.{self.dataset}.{self.mode}_bronze"


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))


def _payload_hash(row: dict[str, Any]) -> str:
    payload_for_hash = {
        key: row[key]
        for key in sorted(row)
        if key not in {"payload_hash", "raw_json", "ingested_at"}
    }
    return sha256(_canonical_json(payload_for_hash).encode("utf-8")).hexdigest()


def _normalize_for_bigquery(
    row: dict[str, Any], *, mode: str, snapshot_date: date, ingested_at: datetime
) -> dict[str, Any]:
    # Essential metadata
    base = dict(row)
    base["mode"] = mode
    base.setdefault("layer", "bronze")
    base.setdefault("snapshot_date", snapshot_date.isoformat())
    base["ingested_at"] = ingested_at.astimezone(UTC).isoformat()
    base["raw_json"] = dict(row)
    base["payload_hash"] = _payload_hash(base)

    # Filter only columns present in v2 schema
    allowed_cols = {f.name for f in BRONZE_SCHEMA_FIELDS}
    normalized = {k: v for k, v in base.items() if k in allowed_cols}

    missing = [field for field in REQUIRED_FIELDS if not normalized.get(field)]
    if missing:
        raise ValueError(
            f"Missing required fields for BigQuery row: {', '.join(sorted(missing))}. "
            f"Row keys: {sorted(normalized)}"
        )

    return normalized


def _build_client(project: str) -> BigQueryClientProtocol:
    try:
        from google.cloud import bigquery
        from google.oauth2 import service_account
    except ImportError as exc:
        raise RuntimeError(
            "BigQuery dependencies are missing. Install `google-cloud-bigquery` first."
        ) from exc

    service_account_json = os.getenv("BIGQUERY_SERVICE_ACCOUNT_JSON")
    if service_account_json:
        info = json.loads(service_account_json)
        credentials = service_account.Credentials.from_service_account_info(info)
        return bigquery.Client(project=project, credentials=credentials)

    return bigquery.Client(project=project)


def load_rows_to_bigquery(
    rows: list[dict[str, Any]],
    *,
    mode: str,
    project: str,
    dataset: str,
    client: BigQueryClientProtocol | None = None,
    snapshot_date: date | None = None,
    ingested_at: datetime | None = None,
) -> int:
    if mode not in {"rent", "sale"}:
        raise ValueError(f"`mode` must be `rent` or `sale`, got: {mode}")
    if not project.strip():
        raise ValueError("BigQuery project is required.")
    if not dataset.strip():
        raise ValueError("BigQuery dataset is required.")

    effective_snapshot_date = snapshot_date or date.today()
    effective_ingested_at = ingested_at or datetime.now(UTC)
    normalized_rows = [
        _normalize_for_bigquery(
            row,
            mode=mode,
            snapshot_date=effective_snapshot_date,
            ingested_at=effective_ingested_at,
        )
        for row in rows
    ]

    target = BigQueryTarget(project=project, dataset=dataset, mode=mode)
    effective_client = client or _build_client(project=project)

    try:
        from google.cloud import bigquery
    except ImportError as exc:
        raise RuntimeError(
            "BigQuery dependencies are missing. Install `google-cloud-bigquery` first."
        ) from exc

    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
    )
    load_job = effective_client.load_table_from_json(
        normalized_rows,
        target.table_id,
        job_config=job_config,
    )
    load_job.result()
    errors = getattr(load_job, "errors", None)
    if errors:
        raise RuntimeError(f"BigQuery load job returned errors for `{target.table_id}`: {errors}")

    output_rows = getattr(load_job, "output_rows", None)
    if isinstance(output_rows, int):
        return output_rows
    return len(normalized_rows)
