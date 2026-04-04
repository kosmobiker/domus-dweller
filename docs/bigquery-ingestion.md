# BigQuery Ingestion (Sandbox-Friendly)

This project now supports direct OLX ingestion into BigQuery Bronze tables without storing local HTML/JSON artifacts.
The loader uses BigQuery **load jobs** (not streaming `insertAll`) to stay compatible with Sandbox.

## Bronze Tables

Created via BigQuery bootstrap:

- `rent_bronze`
- `sale_bronze`

Both live under a single dataset (default: `bronze`) and include:

- source identity (`source`, `source_listing_id`, `source_url`)
- temporal metadata (`snapshot_date`, `ingested_at`, `layer`, `mode`)
- parsed/enriched listing fields
- raw debug payload (`raw_json`)
- stable payload fingerprint (`payload_hash`)

## Connection Options

### Ingestion Loader (Python client)

No SQLAlchemy connection string is required for loading rows.

Authentication options:

1. Application Default Credentials (recommended for local + GitHub Actions)
2. `BIGQUERY_SERVICE_ACCOUNT_JSON` env var with full service-account JSON

Required runtime args:

- `--project` (GCP project id)
- `--dataset` (dataset name)

## Commands

Two-job GitHub Actions shape:

1. Parse+enrich job
2. Sink-to-BigQuery job

The repository now provides exactly two operational Make commands for that flow:

```bash
make daily-olx-parse DATE=2026-04-04
make daily-olx-sink-bigquery DATE=2026-04-04 BQ_PROJECT=<your-project-id> BQ_DATASET=bronze
```

`daily-olx-sink-bigquery` includes retry logic (3 attempts with backoff).

Create BigQuery schema in Sandbox (recommended):

```bash
make bigquery-bootstrap BQ_PROJECT=<your-project-id> BQ_DATASET=bronze BQ_LOCATION=EU
```

Run daily direct ingestion:

```bash
make daily-olx-bigquery BQ_PROJECT=<your-project-id> BQ_DATASET=bronze
```

Run only one mode:

```bash
make daily-olx-bigquery-rent BQ_PROJECT=<your-project-id> BQ_DATASET=bronze
make daily-olx-bigquery-sale BQ_PROJECT=<your-project-id> BQ_DATASET=bronze
```

## Notes For BigQuery Sandbox

- Sandbox is enough for this flow.
- Keep Bronze append-only.
- Keep Silver/Gold transforms as a separate step (later).
