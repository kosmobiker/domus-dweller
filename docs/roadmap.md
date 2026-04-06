# Roadmap

## Phase 1: OLX Bronze Stability (Now)

- finalize OLX parsing quality and daily stability
- run daily GitHub Actions parse/sink jobs
- monitor null rates and parser drift
- keep Bronze append-only in MotherDuck (DuckDB)

Success: 3-7 consecutive successful daily runs with expected row growth.

## Phase 2: Silver Foundations

- define Silver contracts (identity + versions + current)
- implement dedup and SCD from Bronze
- add data-quality tests for versioning behavior

Success: stable `is_current` and version history for OLX listings.

## Phase 3: Gold + Notebook Analytics

- add rent/sale aggregates
- add city/district/municipality views
- add initial H3 aggregates where coordinates allow

Success: useful weekly notebook analysis without manual data wrangling.

## Phase 4: Source Expansion

- add second source after OLX is stable
- reuse Bronze contract and sink path
- keep source-specific parsing isolated

Success: second source lands in Bronze without breaking OLX pipeline.
