# Roadmap

## Phase 1: OLX Bronze Stability (Done)

- finalize OLX parsing quality and daily stability
- run daily GitHub Actions parse/sink jobs
- monitor null rates and parser drift
- keep Bronze append-only in MotherDuck (DuckDB)

Success: Daily ingestion is stable and monitored.

## Phase 2: Silver Foundations (Done)

- define Silver contracts (identity + versions + current)
- implement dedup and SCD from Bronze
- add data-quality tests for versioning behavior

Success: Stable `is_current` and version history for OLX listings in MotherDuck.

## Phase 3: Gold + Notebook Analytics (Active)

- add rent/sale aggregates
- add city/district/municipality views
- add initial H3 aggregates where coordinates allow
- EDA notebook exists: `notebooks/eda_motherduck_raw.ipynb`

Success: useful weekly notebook analysis without manual data wrangling.

## Phase 4: Source Expansion (Deferred)

- add second source after OLX is stable
- reuse Bronze contract and sink path
- keep source-specific parsing isolated

Success: second source lands in Bronze without breaking OLX pipeline.

## Phase 5: Web Frontend (Planned)

- Next.js app on Vercel free tier
- map visualization with MapLibre + OpenStreetMap tiles
- listing search, filters, price trend charts
- area comparison views

Success: public-facing analytics dashboard with zero recurring cost.

## Phase 6: Operations & Monitoring (Planned)

- freshness monitoring and failure alerting
- data quality dashboard
- null-rate and parser-drift tracking

Success: self-healing pipeline with proactive issue detection.
