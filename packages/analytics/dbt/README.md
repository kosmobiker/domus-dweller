# dbt + BigQuery (Bronze/Silver/Gold)

This dbt project is the transformation layer for OLX data in BigQuery:

- Bronze: raw append tables loaded by ingestion
- Silver: cleaned current-state listing tables split by `rent` and `sale`
- Gold: daily aggregated metrics

## Expected Bronze Tables

In dataset `bronze` (configurable via `--vars`):

- `olx_rent_all`
- `olx_sale_all`

Each table is expected to contain enriched ingestion columns (including `detail_params*` fields).

## Local Setup

1. Copy profile template:

```bash
cp packages/analytics/dbt/profiles.yml.template packages/analytics/dbt/profiles.yml
```

2. Fill real GCP service account credentials in `profiles.yml`.

3. Run dbt with BigQuery adapter:

```bash
uvx --from dbt-bigquery dbt --project-dir packages/analytics/dbt --profiles-dir packages/analytics/dbt debug
uvx --from dbt-bigquery dbt --project-dir packages/analytics/dbt --profiles-dir packages/analytics/dbt build --vars '{"bronze_dataset":"bronze","silver_dataset":"silver","gold_dataset":"gold"}'
```

## Suggested GitHub Actions Flow

1. Run ingestion (`make daily-olx`) and upload/load Bronze rows to BigQuery tables.
2. Run dbt build against BigQuery.
3. Publish `gold_olx_daily_metrics` to downstream consumers (notebooks/app).
