# Agent To-Dos

Current objective: finalize Silver SCD Type 2 logic and start Gold/Analytics.

## Current Baseline

- Source scope: OLX only.
- Geography: Krakow + nearby municipalities (~30 km).
- Modes: `rent`, `sale`.
- Bronze policy: append-only, no dedup, no SCD.
- Silver policy: SCD Type 2 with `change_hash` on core fields.
- Warehouse: MotherDuck (DuckDB).
- Scheduler: GitHub Actions (`parse` job + `sink` job + `silver-sync` job).

## Immediate Backlog (Next 2-3 Days)

1. Silver Sync Hardening.
- [x] Implement initial silver-sync using dbt-core and DuckDB.
- [x] Add functional tests for dbt SCD Type 2 version-window behavior.
- [x] Monitor Silver growth and versioning accuracy via dbt tests.
- [x] Add listing identity handling via dbt incremental window functions.

2. Data quality hardening.
- [x] Expand extraction from `detail_params` into normalized typed fields.
- [x] Add normalization for high-value OLX params per mode (rent vs sale).
- [ ] Add parser regression fixtures for known noisy `detail_params` keys.

3. Observability.
- [ ] Add run summary in GitHub Actions with counts by mode.
- [ ] Record parse count vs sink count to detect data loss.
- [ ] Add simple null-rate report notebook for key columns.

## Gold / Analytics Backlog

- [ ] Define Gold table contracts for:
  - Daily H3 aggregates
  - Area-level trends
- [ ] Implement initial Gold transformation scripts.
- [ ] Create basic Jupyter notebook for rent/sale trend analysis.

## Source Expansion (Later)

- [ ] Re-introduce second source after Silver flow is robust.
- [ ] Keep adapter interface source-isolated.
- [ ] Reuse Bronze contract and sink path for new sources.

## Definition Of Done For Current Phase

- [x] At least 3 consecutive daily OLX runs complete in GitHub Actions.
- [x] `rent_bronze` and `sale_bronze` both receive rows every day.
- [x] Core parser and sink tests are green.
- [x] Silver Sync merges Bronze observations into Identity and Version tables.
- [x] Documentation is consistent with OLX + MotherDuck Bronze/Silver flow.
