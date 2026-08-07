# Phase 1 Ingestion

## Goal

Run a reliable daily OLX pipeline that:

1. parses listings from search pages,
2. stores Bronze rows in append mode,
3. keeps rent and sale separated.

No dedup and no SCD in ingestion. Those belong to Silver.

## Stack

- Python 3.13
- `uv` for env/deps
- `ruff` for linting
- `curl` (Makefile fetch) + `selectolax` for HTML parsing
- `httpx` available for direct ingestion mode
- MotherDuck (DuckDB) for Bronze storage (`bronze.rent_bronze`, `bronze.sale_bronze`)
- GitHub Actions for daily scheduling

## Daily Job Shape

Three jobs in GitHub Actions (`daily-olx-motherduck.yml`):

1. `parse` job:
   - run `make daily-olx-parse`
   - upload parsed artifacts for the same snapshot date

2. `sink` job (depends on `parse`):
   - download artifacts
   - run `make motherduck-bootstrap`
   - run `make daily-olx-sink-motherduck` (with retries)

3. `silver` job (depends on `parse` + `sink`):
   - run `make silver-sync` (dbt deps + dbt build)
   - run `dbt test` to verify Silver integrity

## Local Commands

```bash
make daily-olx-parse DATE=2026-04-04 PAGES=30
make motherduck-bootstrap MD_DATABASE=my_db
make daily-olx-sink-motherduck DATE=2026-04-04 MD_DATABASE=my_db
```

Direct one-step ingestion is also available via the Python module (no Make target):

```bash
uv run python -m domus_dweller.sources.olx.ingest_motherduck --database my_db
```

## Testing Policy

- Prefer functional tests over helper-level unit tests.
- Parser coverage should rely on frozen fixtures.
- Sink tests should verify required fields, mode routing, and load behavior.
- Keep Bronze behavior append-only.

## Success Criteria

Phase 1 is considered stable when:

- at least 3 consecutive daily runs succeed in GitHub Actions,
- both MotherDuck Bronze tables receive rows daily,
- parser + sink tests remain green in CI,
- docs and runbook stay consistent with the actual workflow.
