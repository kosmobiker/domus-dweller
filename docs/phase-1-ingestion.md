# Phase 1 Ingestion

## Goal

Build a reliable daily pipeline that fetches housing listings, normalizes them, and stores historical observations in Neon.

At the end of Phase 1, the system should work without any web UI.

## Recommended Python Stack

- Python `3.13`
- `uv` for dependency management and virtual environments
- `ruff` for linting and formatting
- `httpx` for HTTP fetching
- `selectolax` for HTML parsing
- `pydantic` for validation
- `psycopg` for Postgres writes
- `h3` for spatial cell assignment
- `tenacity` for retries
- `python-dotenv` for local development
- `pandas` for notebook-facing reads

Avoid browser automation until a source proves it is necessary.

Preferred local commands:

- `uv sync --group dev`
- `uv run ruff check .`
- `uv run ruff format .`
- `uv run pytest`

## Testing Approach

Use TDD for the ingestion layer.

The preferred cycle is:

1. capture a real source fixture
2. write a failing parser test
3. implement the parser
4. write a failing normalization test
5. implement normalization and seller classification
6. add an integration test for database writes

Prefer functional tests over fine-grained unit tests.

Parser work should not start from live pages only. Freeze representative fixtures first so source drift does not make tests flaky.

## Environment Variables

Before implementing schema creation or ingestion commands, ask the user to configure Neon connection variables.

Current minimum contract:

- `NEON_DATABASE_URL`

Optional later:

- `NEON_DATABASE_URL_READONLY`
- `NEON_BRANCH`

## Collection Rule

Use the safest available ingestion path in this order:

1. officially documented APIs or exports that you are authorized to use
2. public listing pages and public embedded data
3. browser automation only when public pages require it and only without bypassing authentication or anti-bot protections

Do not plan on:

- login-gated collection
- bypassing CAPTCHA or anti-bot controls
- using undocumented private endpoints as the primary strategy

## Source Order

Recommended initial order:

1. Otodom
2. OLX
3. One additional public portal if needed

This order balances coverage and maintenance cost.

Seller classification is mandatory from the first source:

- `private`
- `professional`
- `unknown`

When possible, keep the more specific subtype too:

- `agency`
- `developer`
- `private`
- `unknown`

## Phase 1 Pipeline Steps

1. Discover listing result pages for a source and query type
2. Extract listing cards or embedded JSON
3. Visit listing detail pages only when needed
4. Normalize source fields into the canonical schema
5. Classify seller as private or professional and preserve source evidence
6. Assign H3 cells when coordinates exist
7. Upsert listing identity and insert a new observation row
8. Mark previously seen but now missing listings as inactive
9. Aggregate daily metrics after all source jobs finish

Each of these steps should have at least one test at the appropriate level:

- parser functional tests using frozen fixtures
- normalization behavior tests at the canonical-output boundary
- persistence integration tests

## Job Model

Use GitHub Actions on a daily schedule.

Suggested jobs:

- `ingest_otodom_rent`
- `ingest_otodom_sale`
- `ingest_olx_rent`
- `ingest_olx_sale`
- `aggregate_daily_metrics`

Keep each job independently rerunnable.

## Storage Policy

Store:

- normalized listing data
- immutable observations
- compact raw payload fragments for debugging
- ingest run metadata
- seller classification evidence such as source labels, profile type, or agency name

Do not store:

- full raw HTML for every page unless debugging requires it
- large image binaries
- expensive geocoding results from paid services

## Success Criteria

Phase 1 is successful when:

- at least one source runs daily without manual intervention
- price history is queryable for listings
- rent and sale can be analyzed separately
- flat and house can be analyzed separately
- private and professional listings can be analyzed separately
- H3 and municipality aggregates are available in notebooks
- the core ingestion path is covered by automated tests
