# Schema V1

## Core Tables (Local Phase 1)

### Bronze Layer

#### `bronze_listing_observations` (append only)

- `ingest_run_id`
- `observed_at`
- `source`
- `source_listing_id`
- `source_url`
- `raw_payload`
- `normalized_json`
- `payload_hash`
- `seller_evidence`

Bronze rules:

- insert only, no updates or deletes in normal flow
- do not deduplicate in ingestion code
- every parsed row is a fact row for auditability
- keep source-mode tracks explicit (`mode = rent|sale`) in Bronze rows
- keep both:
  - `detail_params` as the full raw parameter map
  - `detail_params_common` plus mode-specific maps (`detail_params_rent` / `detail_params_sale`)

### Silver Layer

#### `silver_listing_identity`

- `source`
- `source_listing_id`
- `first_seen_at`
- `last_seen_at`
- `is_active`
- `inactive_at`

#### `silver_listing_versions` (dbt snapshot / SCD Type 2)

- `source`
- `source_listing_id`
- `dbt_valid_from`
- `dbt_valid_to`
- `dbt_scd_id`
- `dbt_updated_at`

#### `silver_listing_current` (dbt table model)

- one current row per `(source, source_listing_id, mode)`
- derived from `silver_listing_versions where dbt_valid_to is null`

Silver rules:

- generated and managed entirely by `dbt-core` (`dbt run` and `dbt snapshot`).
- primary key on `silver_listing_identity(source, source_listing_id, mode)`
- only one current row per listing id should exist in `silver_listing_versions` (`dbt_valid_to is null`)
- append a new `silver_listing_versions` row only when tracked columns change (handled natively by `dbt snapshot`)
- unchanged Bronze observations are ignored via dbt's built-in snapshot checks
- update `silver_listing_identity.last_seen_at` via incremental dbt models
- `silver_listing_identity.is_active` inferred via window functions inside the pipeline

### Gold Layer

#### `gold_h3_daily_metrics`

- date
- H3 resolution and cell id
- listing counts
- median/p25/p75 price metrics
- split dimensions (`rent/sale`, `flat/house`, `seller_segment`)

## Modeling Notes

- Bronze is the raw historical source of truth
- Silver is the curated listing-history source of truth
- Gold is read-optimized and should be rebuildable from Silver
- store compact normalized payload JSON, not full page dumps
- keep `listing_type` as `rent` or `sale`
- keep `property_type` as `flat` or `house` in v1
- `seller_segment` should be `private`, `professional`, or `unknown`
- `seller_type` should preserve finer detail such as `agency`, `developer`, `private`, or `unknown`
