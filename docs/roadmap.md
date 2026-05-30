# Roadmap

## Phase 1: OLX Bronze Stability (Done)

- finalize OLX parsing quality and daily stability
- run daily GitHub Actions parse/sink jobs
- monitor null rates and parser drift
- keep Bronze append-only in MotherDuck (DuckDB)

Success: Daily ingestion is stable and monitored.

## Phase 2: Silver Foundations (Active)

- define Silver contracts (identity + versions + current)
- implement dedup and SCD from Bronze
- add data-quality tests for versioning behavior

Success: Stable `is_current` and version history for OLX listings in MotherDuck.

## Phase 3: Gold + Notebook Analytics (Active)

- add rent/sale aggregates
- add city/district/municipality views
- add initial H3 aggregates where coordinates allow

Success: useful weekly notebook analysis without manual data wrangling.

## Phase 4: Source Expansion (Deferred)

- add second source after OLX is stable
- reuse Bronze contract and sink path
- keep source-specific parsing isolated

Success: second source lands in Bronze without breaking OLX pipeline.
