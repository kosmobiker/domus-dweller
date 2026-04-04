# domus-dweller

Zero-cost housing analytics for Krakow and nearby suburbs.

The goal is to collect flat and house listings over time, normalize them into a single dataset, and expose price history, map-based exploration, and area-level analytics for Krakow plus roughly a 30 km radius.

## Principles

- Stay on `master`.
- Optimize for zero recurring cost.
- Treat each source as an isolated adapter.
- Store both raw observations and normalized facts.
- Prefer simple analytics before adding AI.

## Current Direction

- Phase 1: Python scraping + Neon Postgres storage
- Phase 2: Jupyter notebook analysis on top of Neon
- Phase 3: lightweight web app, likely Next.js on Vercel

## Proposed Stack

- Data pipeline: Python
- Python version: 3.13
- Environment and dependency manager: `uv`
- Linting and formatting: `ruff`
- Database: Neon Postgres
- Jobs: GitHub Actions scheduled workflows
- Notebook analysis: Jupyter + SQL/Pandas
- Geospatial indexing: H3 via Python `h3`
- Maps later: MapLibre + OpenStreetMap tiles
- Web later: Next.js on Vercel

## Repo Docs

- [AGENTS.md](/home/user/domus-dweller/AGENTS.md)
- [SKILLS.md](/home/user/domus-dweller/SKILLS.md)
- [docs/agent-todos.md](/home/user/domus-dweller/docs/agent-todos.md)
- [docs/architecture.md](/home/user/domus-dweller/docs/architecture.md)
- [docs/collection-policy.md](/home/user/domus-dweller/docs/collection-policy.md)
- [docs/decisions.md](/home/user/domus-dweller/docs/decisions.md)
- [docs/data-sources.md](/home/user/domus-dweller/docs/data-sources.md)
- [docs/phase-1-ingestion.md](/home/user/domus-dweller/docs/phase-1-ingestion.md)
- [docs/roadmap.md](/home/user/domus-dweller/docs/roadmap.md)
- [docs/schema-v1.md](/home/user/domus-dweller/docs/schema-v1.md)
- [docs/testing.md](/home/user/domus-dweller/docs/testing.md)
- [docs/open-questions.md](/home/user/domus-dweller/docs/open-questions.md)

## Proposed Repo Shape

```text
ingestion/      Python scraping and normalization pipeline
notebooks/      Jupyter analysis
sql/            schema, migrations, and analysis queries
apps/
  web/          Next.js app on Vercel
packages/
  analytics/    optional shared analytics code for later app work
  db/           optional app-side database access helpers
  scrapers/     optional JS/TS scraping experiments if ever needed
  shared/       shared code for later frontend work
docs/           architecture and planning
.github/        scheduled workflows
```

## Local Tooling

```bash
uv sync --group dev
uv run ruff check .
uv run ruff format .
uv run pytest
```

## Environment

Before any database work or ingestion runs, you need to provide Neon connection variables.

Start with:

- `NEON_DATABASE_URL`

See [.env.example](/home/user/domus-dweller/.env.example) for the current contract.
