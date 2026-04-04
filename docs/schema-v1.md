# Schema V1

## Core Tables

### `sources`

- `id`
- `code`
- `name`
- `is_active`

### `ingest_runs`

- `id`
- `source_id`
- `job_name`
- `started_at`
- `finished_at`
- `status`
- `records_seen`
- `records_inserted`
- `records_updated`
- `records_failed`
- `error_summary`

### `listings`

- `id`
- `source_id`
- `source_listing_id`
- `source_url`
- `listing_type`
- `property_type`
- `seller_segment`
- `seller_type`
- `seller_name`
- `seller_profile_url`
- `title`
- `first_seen_at`
- `last_seen_at`

### `listing_observations`

- `id`
- `listing_id`
- `observed_at`
- `is_active`
- `status`
- `seller_segment`
- `seller_type`
- `seller_name`
- `price_total`
- `currency`
- `price_per_sqm`
- `area_sqm`
- `rooms`
- `floor`
- `address_text`
- `district`
- `municipality`
- `lat`
- `lng`
- `h3_cell_res8`
- `h3_cell_res9`
- `description`
- `raw_payload`
- `seller_evidence`

### `listing_current`

- `listing_id`
- `observed_at`
- `is_active`
- `seller_segment`
- `seller_type`
- `price_total`
- `price_per_sqm`
- `area_sqm`
- `rooms`
- `district`
- `municipality`
- `lat`
- `lng`
- `h3_cell_res8`
- `h3_cell_res9`

### `h3_daily_metrics`

- `metric_date`
- `resolution`
- `cell_id`
- `listing_type`
- `property_type`
- `listing_count`
- `new_listings`
- `removed_listings`
- `median_price_total`
- `median_price_per_sqm`
- `p25_price_per_sqm`
- `p75_price_per_sqm`

## Constraints

- unique on `listings(source_id, source_listing_id)`
- index on `listing_observations(listing_id, observed_at desc)`
- index on `listing_observations(h3_cell_res8, observed_at desc)`
- index on `listing_observations(h3_cell_res9, observed_at desc)`
- index on `h3_daily_metrics(metric_date, resolution, cell_id, listing_type, property_type)`

## Modeling Notes

- `listing_observations` is the historical source of truth
- `listing_current` is a convenience table or materialized view
- `raw_payload` should be compact JSON, not a full raw page dump
- keep `listing_type` as `rent` or `sale`
- keep `property_type` as `flat` or `house` in v1
- `seller_segment` should be `private`, `professional`, or `unknown`
- `seller_type` should preserve finer detail such as `agency`, `developer`, `private`, or `unknown`
