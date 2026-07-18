# AGENTS

This repository is for building a personal housing analytics system focused on Krakow and surrounding municipalities.

Execution checklist: [docs/agent-todos.md](/home/user/domus-dweller/docs/agent-todos.md)

## Standing Rules

- The default branch is `master`. Do not rename it to `main`.
- Zero recurring spend is a hard constraint unless explicitly changed.
- Favor public, stable, low-friction data sources before brittle or login-gated sources.
- Scope for v1 is flats and houses; exclude commercial real estate.
- Geography for v1 is Krakow plus an approximate 30 km radius.
- Daily ingestion is the default cadence for v1.
- Seller classification is mandatory: every listing should be labeled at least as `private`, `professional`, or `unknown`.
- Current active source is OLX only; Otodom remains deferred until OLX flow is fully stable and Silver sync is robust.
- Bronze storage target is MotherDuck (DuckDB) Bronze tables (`bronze.rent_bronze`, `bronze.sale_bronze`).
- Silver storage target is MotherDuck (DuckDB) Silver tables (`silver.listing_identity`, `silver.listing_versions`).
- Do not require Neon environment variables for current bootstrap/ingest flows.
- Keep ingestion parse-only from search pages for now; detail-page enrichment is disabled in runtime flow.
- Prefer TDD: write or update failing tests before implementing parser, normalization, or schema behavior.
- Prefer functional and integration tests over fine-grained unit tests.
- Keep source-specific scraping logic isolated from normalization and analytics logic.
- Never rely on a single site-specific parser shape across all adapters.
- Record historical observations; do not overwrite previous prices.
- Make architectural decisions that still work if one source breaks.

## Agent Roles

### 1. System Architect

Owns cross-cutting design decisions:

- system boundaries
- cost control
- source prioritization
- schema strategy
- workflow sequencing

### 2. Ingestion Agent

Owns source adapters:

- fetching listings
- parsing listing payloads
- handling throttling and retries
- storing parse artifacts for sink job handoff
- source health checks

### 3. Data Agent

Owns the database model and dbt project:

- normalized listing schema
- historical observation model (dbt snapshots)
- aggregations and incremental models
- dbt tests for data integrity (unique, not_null, etc.)
- deduplication rules
- migrations

### 4. Geo Analytics Agent

Owns spatial logic:

- H3 resolution choice
- assigning listings to cells
- hex-level aggregates
- city vs suburb rollups
- map payload generation

### 5. Web Agent

Owns the user-facing app:

- filters and search UX
- map and charts
- listing detail views
- historical trend pages
- area comparison pages

### 6. Ops Agent

Owns automation:

- GitHub Actions schedules
- secret management
- failure reporting
- data freshness checks
- deployment workflow

## Definition Of Done For Any Source

A source is not considered integrated until all of the following exist:

- fetcher with retry and rate limiting
- parser covered by fixture-based functional tests
- normalization covered by behavior-focused tests at the pipeline boundary
- normalized output mapped to the common schema
- source id and source listing id captured
- seller classification extracted and normalized
- at least one ingest functional test against a test database path or mocked persistence layer
- raw payload or extracted source JSON stored for debugging
- ingest run metrics recorded
- failure mode documented

## Decision Biases

- Prefer Python for ingestion, normalization, and notebook-driven analysis.
- Prefer `uv` for dependency and environment management.
- Prefer `ruff` for linting and formatting.
- Target Python `3.13` unless a dependency forces a lower version.
- Prefer TypeScript only when the web application work begins.
- Prefer simple HTTP fetching plus HTML parsing before browser automation.
- Prefer application-side H3 computation before database GIS extensions.
- Prefer daily batch analytics before near-real-time updates.
- Prefer explicit SQL and `dbt-core` for transformations and analytics over heavy ORMs.

## Implementation Guidelines

### Source Adapter Design

When adding a source:

- define the search URLs or discovery entrypoints
- identify stable listing identifiers
- capture the minimum raw payload needed for debugging
- extract seller classification and preserve source evidence for it
- map to the canonical schema
- tag unsupported fields instead of guessing
- write a parser fixture before broad crawling
- for current OLX flow, prioritize robust search-page extraction over fragile detail-page scraping

### Historical Modeling

When persisting observations:

- keep immutable observations separate from current listing state
- store `observed_at`, `first_seen_at`, and `last_seen_at`
- keep both total price and normalized price per square meter
- use dbt snapshot for SCD Type 2 logic instead of custom Python scripts
- treat disappearance as a state change, not a delete

### Geo Skill

When working with maps:

- store latitude and longitude in the canonical listing record
- compute H3 cell ids in the Python pipeline first
- aggregate daily metrics by cell and listing type
- use different H3 resolutions for zoomed-out and zoomed-in views

### Analytics Skill

Use the `dbt-transformation-patterns` skill when building analytics pipelines.

Start with robust metrics:

- median price
- median price per square meter
- listing count
- new listings
- removed listings
- days on market
- price change frequency

Avoid starting with fragile composite scores before the base metrics are trustworthy.

### AI Skill

Use "AI" only where it adds leverage:

- amenity extraction from Polish listing descriptions
- duplicate detection across portals
- outlier explanation
- natural-language search over saved analytics summaries

Default to rule-based or statistical methods first. Only add models after the baseline pipeline is reliable.

### Zero-Cost Skill

Before adding any dependency or service:

- check whether MotherDuck (DuckDB) and Vercel free tier are enough
- prefer GitHub Actions scheduled jobs over always-on workers
- avoid storage-heavy raw HTML retention if compact JSON is enough
- avoid paid geocoding and paid map tiles
- favor notebook-first analysis before building product UI
