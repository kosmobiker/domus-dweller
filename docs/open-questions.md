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

7. Keep MotherDuck Bronze as the single append-only store, or add a secondary export (compressed artifacts or another warehouse) with tight cost controls later?
8. Do we add a weekly backfill job or stay daily-only?
9. How to handle Otodom and OLX detail page firewalls in GitHub Actions? (GHA IPs are often blocked).
10. Should we use a local-run + git-push approach for detail pages if GHA remains blocked?
11. Should we run dbt as a separate GHA job or combine it with the sink job?
