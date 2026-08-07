# domus-dweller

Zero-cost housing analytics for Krakow and nearby suburbs.

The goal is to collect flat and house listings over time, normalize them into a single dataset, and expose price history, map-based exploration, and area-level analytics for Krakow plus roughly a 30 km radius.

## Principles

- Stay on `master`.
- Optimize for zero recurring cost.
- Treat each source as an isolated adapter.
- Store both raw observations and normalized facts.
- Prefer simple analytics and rule-based extraction.

## Current Direction

- ~~Phase 1~~: OLX-only ingestion (rent + sale) from search pages. **Done.** Bronze append-only tables in MotherDuck.
- ~~Phase 2~~: Silver transformations (cleaning, dedup, SCD). **Done.** Identity, versions, and current-state models via dbt.
- **Phase 3 (Active)**: Gold aggregates + notebook analytics.
- Phase 4+: source expansion, web app.

## Data Layers

- Bronze: parse everything in append mode (raw + normalized facts, no dedup, no SCD).
- Silver: cleaning, canonicalization, deduplication, and SCD via **dbt** (`is_current`, `valid_from`, `valid_to`).
- Gold: aggregated, analytics-ready datasets for notebooks and the future app.

## Stack

- Data pipeline: Python
- Transformation: dbt-core + DuckDB/MotherDuck SQL + notebooks
- Python version: 3.13
- Environment and dependency manager: `uv`
- Linting and formatting: `ruff`
- Local parse artifacts: JSON under `data/parsed/` (used by parse job and sink job)
- Jobs: GitHub Actions scheduled workflows (Ingestion + Sink + Silver Sync)
- Notebook analysis: Jupyter + SQL/Pandas
- Geospatial indexing: H3 via Python `h3`
- Maps later: MapLibre + OpenStreetMap tiles
- Web later: Next.js on Vercel

## Repo Docs

- [AGENTS.md](/home/user/domus-dweller/AGENTS.md)

- [docs/agent-todos.md](/home/user/domus-dweller/docs/agent-todos.md)
- [docs/architecture.md](/home/user/domus-dweller/docs/architecture.md)
- [docs/collection-policy.md](/home/user/domus-dweller/docs/collection-policy.md)
- [docs/decisions.md](/home/user/domus-dweller/docs/decisions.md)
- [docs/data-sources.md](/home/user/domus-dweller/docs/data-sources.md)
- [docs/motherduck-ingestion.md](/home/user/domus-dweller/docs/motherduck-ingestion.md)
- [docs/phase-1-ingestion.md](/home/user/domus-dweller/docs/phase-1-ingestion.md)
- [docs/roadmap.md](/home/user/domus-dweller/docs/roadmap.md)
- [docs/schema-v1.md](/home/user/domus-dweller/docs/schema-v1.md)
- [docs/testing.md](/home/user/domus-dweller/docs/testing.md)
- [docs/open-questions.md](/home/user/domus-dweller/docs/open-questions.md)

## Repo Shape

```text
ingestion/                    Python scraping and normalization pipeline
  src/domus_dweller/          main package
    sources/olx/              OLX parser, enrichment, direct ingest
    sources/otodom/           Otodom adapter (placeholder)
    sinks/                    MotherDuck sink, bootstrap, file loader
    parse.py                  CLI entry point for parsing
    merge_pages.py            merges per-page JSONs into combined file
  tests/
    functional/               11 functional test modules
    fixtures/olx/             frozen HTML fixtures
transform/                    dbt-core project
  models/staging/             stg_bronze_listings (JSON unpacking)
  models/silver/              listing_identity, listing_versions, listing_current
  snapshots/                  dbt snapshot for SCD Type 2
notebooks/                    Jupyter analysis (eda_motherduck_raw.ipynb)
data/
  raw/                        fetched HTML pages (per date)
  parsed/                     parsed JSON artifacts (per date)
sql/                          standalone SQL scripts
apps/web/                     Next.js app on Vercel (placeholder)
packages/                     stub dirs: analytics, db, scrapers, shared
docs/                         architecture and planning
.github/workflows/            ci.yml + daily-olx-motherduck.yml
```

## Local Tooling

```bash
make lint           # ruff check
make test           # pytest with 70% coverage minimum
make data           # run dbt test against prod
make verify         # lint + test (mirrors CI)
make silver-sync    # dbt deps + dbt build against prod
```

Always run `make verify` before pushing.

## Runbook

Local parse:

```bash
make daily-olx-parse DATE=$(date +%F) PAGES=30
```

MotherDuck bootstrap:

```bash
make motherduck-bootstrap MD_DATABASE=my_db
```

Local sink:

```bash
make daily-olx-sink-motherduck DATE=$(date +%F) MD_DATABASE=my_db
```

Silver sync (after sink):

```bash
make silver-sync
```

Direct ingestion mode (scrape + sink without parse artifacts, no Make target):

```bash
uv run python -m domus_dweller.sources.olx.ingest_motherduck --database my_db
```
