from __future__ import annotations

import argparse
from dataclasses import dataclass


@dataclass(frozen=True)
class BronzeField:
    name: str
    field_type: str
    mode: str = "NULLABLE"


# Schema v2: Essential columns only to avoid sparse tables.
# All original data is preserved in 'raw_json'.
BRONZE_SCHEMA_FIELDS: tuple[BronzeField, ...] = (
    BronzeField("ingested_at", "TIMESTAMP", "REQUIRED"),
    BronzeField("snapshot_date", "DATE", "REQUIRED"),
    BronzeField("layer", "STRING", "REQUIRED"),
    BronzeField("mode", "STRING", "REQUIRED"),
    BronzeField("source", "STRING", "REQUIRED"),
    BronzeField("source_listing_id", "STRING", "REQUIRED"),
    BronzeField("source_url", "STRING", "REQUIRED"),
    BronzeField("title", "STRING"),
    BronzeField("price_total", "FLOAT"),
    BronzeField("currency", "STRING"),
    BronzeField("district", "STRING"),
    BronzeField("city", "STRING"),
    BronzeField("municipality", "STRING"),
    BronzeField("location_approx", "STRING"),
    BronzeField("images", "JSON"),
    BronzeField("seller_segment", "STRING"),
    BronzeField("payload_hash", "STRING", "REQUIRED"),
    BronzeField("raw_json", "JSON"),
)


def _build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create BigQuery Bronze dataset and rent/sale tables (v2 essential schema)."
    )
    parser.add_argument("--project", required=True, help="BigQuery project id.")
    parser.add_argument("--dataset", default="bronze", help="BigQuery dataset.")
    parser.add_argument("--location", default="EU", help="BigQuery location.")
    return parser.parse_args()


def _build_schema(bigquery) -> list:
    return [
        bigquery.SchemaField(field.name, field.field_type, mode=field.mode)
        for field in BRONZE_SCHEMA_FIELDS
    ]


def bootstrap_bigquery_bronze(*, project: str, dataset: str, location: str) -> None:
    try:
        from google.cloud import bigquery
    except ImportError as exc:
        raise RuntimeError(
            "BigQuery dependencies are missing. Install `google-cloud-bigquery` first."
        ) from exc

    client = bigquery.Client(project=project)
    dataset_ref = bigquery.Dataset(f"{project}.{dataset}")
    dataset_ref.location = location
    client.create_dataset(dataset_ref, exists_ok=True)
    print(f"Dataset ensured: {project}.{dataset} ({location})")

    schema = _build_schema(bigquery)
    for table_name in ("rent_bronze", "sale_bronze"):
        table = bigquery.Table(f"{project}.{dataset}.{table_name}", schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="snapshot_date",
        )
        table.clustering_fields = ["source", "source_listing_id"]
        client.create_table(table, exists_ok=True)
        print(f"Table ensured (v2): {project}.{dataset}.{table_name}")


def main() -> None:
    args = _build_args()
    bootstrap_bigquery_bronze(
        project=args.project,
        dataset=args.dataset,
        location=args.location,
    )


if __name__ == "__main__":
    main()
