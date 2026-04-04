# Open Questions

## Ingestion Scope

1. Keep `pokoje` in rent track or restrict to flats/houses only?
2. What is the final page cap per seed for daily runs (`30`, `50`, or dynamic stop)?

## Data Quality

3. Which `detail_params` keys should be promoted to first-class columns next?
4. Should we enforce minimum required fields in Bronze beyond current mandatory keys?

## Silver Design

5. Which fields define `change_hash` for SCD versioning?
6. How should listing inactivity be detected (missing for 1 full run or more)?

## Cost and Operations

7. Keep BigQuery Sandbox only, or enable billing with strict budget alert for Silver/Gold later?
8. Do we add a weekly backfill job or stay daily-only?
