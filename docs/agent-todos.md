# Agent To-Dos

Current objective: stabilize OLX daily ingestion into BigQuery Bronze, then start Silver.

## Current Baseline

- Source scope: OLX only.
- Geography: Krakow + nearby municipalities (~30 km).
- Modes: `rent`, `sale`.
- Bronze policy: append-only, no dedup, no SCD.
- Warehouse: BigQuery Sandbox-compatible flow.
- Scheduler: GitHub Actions (`parse` job + `sink` job).

## Immediate Backlog (Next 2-3 Days)

1. Validate daily pipeline stability.
- [ ] Run workflow manually once with `pages=10` and verify both jobs succeed.
- [ ] Confirm Bronze table row growth after each run.
- [ ] Confirm retry behavior in sink job by reviewing workflow logs.

2. Data quality hardening.
- [ ] Expand extraction from `detail_params` into normalized typed fields.
- [ ] Add normalization for high-value OLX params per mode (rent vs sale).
- [ ] Add parser regression fixtures for known noisy `detail_params` keys.

3. Observability.
- [ ] Add run summary in GitHub Actions with counts by mode.
- [ ] Record parse count vs sink count to detect data loss.
- [ ] Add simple null-rate report notebook for key columns.

## Silver Preparation Backlog

- [ ] Define Silver table contracts for:
  - listing identity
  - listing versions (SCD2)
  - current listing view
- [ ] Define `change_hash` payload contract (which fields are versioned).
- [ ] Add first Silver transform prototype (SQL or dbt later).
- [ ] Add tests for `is_current` and version-window behavior.

## Source Expansion (Later)

- [ ] Re-introduce second source after OLX stability window is complete.
- [ ] Keep adapter interface source-isolated.
- [ ] Reuse Bronze contract and sink path for new sources.

## Definition Of Done For Current Sprint

- [ ] At least 3 consecutive daily OLX runs complete in GitHub Actions.
- [ ] `rent_bronze` and `sale_bronze` both receive rows every day.
- [ ] Core parser and sink tests are green.
- [ ] Documentation is consistent with OLX + BigQuery + Bronze-first flow.
