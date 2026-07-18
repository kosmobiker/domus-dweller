# Schema V1

## Core Tables

### Bronze Layer

#### `bronze.rent_bronze` & `bronze.sale_bronze` (append only)
These tables store the parsed listing data as extracted from the source platforms.

- `source` (e.g., 'olx')
- `source_listing_id`
- `source_url`
- `mode` ('rent' or 'sale')
- `snapshot_date`
- `layer`
- `ingested_at`
- `payload_hash`
- `raw_json` (contains the full JSON structure including `detail_params`)

Bronze rules:
- insert only, no updates or deletes in normal flow
- do not deduplicate in ingestion code
- every parsed row is a fact row for auditability
- rent and sale are split into separate tables natively
- keep the full raw parameter map in `raw_json`

### Silver Layer

Generated and managed entirely by `dbt-core` (`dbt run` and `dbt snapshot`). Primary keys generally involve `(source, source_listing_id, mode)`.

#### `silver.listing_identity`
Tracks the active lifecycle of unique listings.

- `source`
- `source_listing_id`
- `mode`
- `first_seen_at`
- `last_seen_at`

#### `silver.listing_versions` (dbt snapshot / SCD Type 2)
Tracks historical changes to core attributes over time.

- `dbt_scd_id`
- `source`
- `source_listing_id`
- `mode`
- `title`
- `price_total`
- `price_per_sqm`
- `area_sqm`
- `rooms`
- `floor`
- `city`
- `district`
- `seller_segment`
- `dbt_valid_from`
- `dbt_valid_to`
- `dbt_updated_at`

#### `silver.listing_current`
The latest state of all tracked listings.

- one current row per `(source, source_listing_id, mode)`
- derived from `silver.listing_versions` where `dbt_valid_to is null`
- contains all current structural, location, and pricing fields (e.g., `price_total`, `price_per_sqm`, `area_sqm`, `rooms`, `city`, `district`)

Silver rules:
- only one current row per listing id should exist in `silver.listing_versions` (`dbt_valid_to is null`)
- append a new `silver.listing_versions` row only when tracked columns change (handled natively by `dbt snapshot`)
- unchanged Bronze observations are ignored via dbt's built-in snapshot checks
- update `listing_identity.last_seen_at` via incremental dbt models

### Gold Layer

#### `gold_h3_daily_metrics` (Planned)
- date
- H3 resolution and cell id
- listing counts
- median/p25/p75 price metrics
- split dimensions (`rent/sale`, `flat/house`, `seller_segment`)

## Modeling Notes
- Bronze is the raw historical source of truth
- Silver is the curated listing-history source of truth
- Gold is read-optimized and should be rebuildable from Silver
- store compact normalized payload JSON in Bronze, not full HTML page dumps
- `seller_segment` should be `private`, `professional`, or `unknown`
- unnormalized raw keys (like Polish `powierzchnia` or `liczba pokoi`) remain in `raw_json` until they are formally extracted into Silver
