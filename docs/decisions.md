# Decisions

## Scope

- v1 geography: Krakow + ~30 km.
- v1 property scope: residential only.
- commercial real estate: excluded.
- cadence: daily ingestion.

## Source Strategy

- current source: OLX only.
- rent and sale are separate ingestion tracks.
- additional sources return later after OLX stability.

## Data Layer Policy

- Bronze: append-only facts, no dedup, no SCD.
- Silver: cleaning, deduplication, SCD (`is_current`, validity windows).
- Gold: aggregated analytics-ready outputs.

## Platform Direction

- scheduler: GitHub Actions.
- Bronze warehouse: MotherDuck (DuckDB).
- parser/sink code: Python (`uv`, `ruff`, `pytest`).
- Alembic: not used, prefer direct SQL/DuckDB migrations.

## Cost Constraint

- keep zero recurring spend by default.
- avoid paid services unless explicitly approved.
