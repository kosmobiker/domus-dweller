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

#### `silver_listing_versions` (SCD Type 2)

- `source`
- `source_listing_id`
- `valid_from`
- `valid_to`
- `is_current`
- `change_hash`
- `normalized_json`

#### `silver_listing_current` (view/table)

- one current row per `(source, source_listing_id)`
- derived from `silver_listing_versions is_current = true`

Silver rules:

- primary key on `silver_listing_identity(source, source_listing_id)`
- only one current row per listing id should exist in `silver_listing_versions`
- append a new `silver_listing_versions` row only when `change_hash` changes
- unchanged Bronze observations must not create new Silver SCD rows
- update `silver_listing_identity.last_seen_at` on every successful full snapshot
- mark `silver_listing_identity.is_active = false` when listing disappears from a full snapshot

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
