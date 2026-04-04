# Schema V1

## Core Tables (Local Phase 1)

### `listing_identity`

- `source`
- `source_listing_id`
- `first_seen_at`
- `last_seen_at`
- `is_active`
- `inactive_at`

### `listing_versions` (SCD Type 2)

- `source`
- `source_listing_id`
- `valid_from`
- `valid_to`
- `is_current`
- `change_hash`
- `source_url`
- `title`
- `seller_segment`
- `price_total`
- `currency`
- `normalized_json`

## Constraints

- primary key on `listing_identity(source, source_listing_id)`
- only one current row per listing id should exist in `listing_versions`
- append a new `listing_versions` row only when `change_hash` changes
- update `listing_identity.last_seen_at` on every successful observation
- mark `listing_identity.is_active = false` when listing disappears from a full snapshot

## Modeling Notes

- `listing_versions` is the historical source of truth
- unchanged listings should not create new SCD rows
- `listing_current` is derived by filtering `is_current = true`
- store compact normalized payload JSON, not full page dumps
- keep `listing_type` as `rent` or `sale`
- keep `property_type` as `flat` or `house` in v1
- `seller_segment` should be `private`, `professional`, or `unknown`
- `seller_type` should preserve finer detail such as `agency`, `developer`, `private`, or `unknown`
