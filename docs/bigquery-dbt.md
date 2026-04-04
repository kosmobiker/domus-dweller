# BigQuery + dbt Plan

## Why this setup

- Bronze facts stay append-only.
- Silver/Gold transformations stay declarative and versioned in dbt.
- Cost can be controlled with partitioning, clustering, and incremental models.

## Daily Flow

1. Parse OLX (`make daily-olx-parse`) to produce `olx_rent_all.json` and `olx_sale_all.json`.
2. Load rows into BigQuery Bronze tables:
   - `bronze.rent_bronze`
   - `bronze.sale_bronze`
3. Run dbt:
   - `make dbt-build`
4. Consume:
   - `silver.silver_olx_rent_current`
   - `silver.silver_olx_sale_current`
   - `gold.gold_olx_daily_metrics`

## Cost Controls

- Partition Bronze by `snapshot_date`.
- Cluster by `source_listing_id`, `mode`, `seller_segment`.
- Use incremental materialization in Silver/Gold when volume grows.
- Keep large nested `detail_params` in Bronze; expose only needed columns in Silver.

## Credentials

- Keep BigQuery service account JSON only in GitHub Secrets.
- Generate `profiles.yml` in CI from secret value.
- Never commit `profiles.yml` with real keys.
