# Architecture

## Goal

Build a personal housing analytics platform for Krakow and nearby suburbs with:

- historical rent and sale prices
- support for flats and houses
- exclusion of commercial listings in v1
- map exploration by H3 hexagon
- area-level analytics
- low operational overhead
- zero recurring infrastructure spend

## Recommended Stack By Phase

### Phase 1: Ingestion And Storage

- Language: Python
- Phase-1 storage: local JSON and CSV snapshots under `data/`
- Optional local analysis engine: DuckDB over those files
- Scheduled jobs: GitHub Actions cron
- Scraping libs: `httpx` or `requests`, `selectolax` or `beautifulsoup4`
- Data access: SQL-first, `psycopg`, optional SQLAlchemy Core
- Geospatial index: Python `h3`
- Analysis: Jupyter + SQL + Pandas

### Phase 2: Lightweight Product UI

- App framework: Next.js with TypeScript
- Deployment: Vercel free tier
- Map rendering: MapLibre with OpenStreetMap-compatible tiles

## System Shape

There should be five layers.

### 1. Source Adapters

Each source adapter is isolated and returns a common intermediate object.

**Note on Anti-Bot Hurdles:**
- **Search Pages:** Currently fetchable from GitHub Actions (low friction).
- **Detail Pages:** Frequently blocked by CloudFlare/Firewalls on GHA IPs.
- **Otodom:** Highly protected; search-page scraping from GHA is currently unstable or blocked.

### 2. Bronze Layer (Append-Only Facts)

This layer persists parsed facts exactly as observed. Orchestrated via GitHub Actions and the `sink` job.

### 3. Silver Layer (Clean + Dedup + SCD)

This layer converts Bronze facts into curated listing history.
- **Engine:** dbt (data build tool).
- **Orchestration:** GitHub Actions `dbt-run` job following the `sink` job.
- **Identity:** Listings are tracked by `source` + `source_listing_id`.

Responsibilities:

- trim and standardize strings
- derive price per square meter
- classify Krakow vs suburb
- normalize room and area values
- reject obviously broken records
- deduplicate repeated observations
- compute stable `change_hash`
- maintain SCD Type 2 history (`valid_from`, `valid_to`, `is_current`)
- maintain listing identity state (`first_seen`, `last_seen`, `is_active`)

### 4. Gold Layer (Read-Optimized Analytics)

This layer stores aggregated and query-ready outputs for notebooks and UI.

Responsibilities:

- daily H3 metrics and rollups
- area-level trends and comparison metrics
- notebook/app-facing read models with stable contracts

### 5. Serving Layer

This layer exposes Gold outputs to notebooks and the web app.

## Historical Price Model

Bronze stores every observation; Silver stores only changed states.

For each changed listing state, keep:

- `listing_id`
- `observed_at`
- `price_total`
- `price_per_sqm`
- `area_sqm`
- `rooms`
- `is_active`
- `status`
- `h3_cell_res8`
- `h3_cell_res9`

Silver gives you:

- price history by listing without duplicate snapshots
- days-on-market estimates
- price drop detection
- supply changes over time

## H3 Strategy

Do H3 indexing in application code instead of relying on database GIS extensions.

Recommended starting resolutions:

- `res8` for metro-level and suburb views
- `res9` for Krakow neighborhood views

Store both cell ids on each observation. Aggregate daily metrics into separate rows per:

- date
- resolution
- cell id
- listing type
- property type

Metrics to precompute:

- listing count
- median total price
- median price per sqm
- p25 and p75 price per sqm
- new listings
- removed listings
- median days on market

## Geographic Scope

Use Krakow as the center and treat the first version as "Krakow plus approximately 30 km radius".

Practical rule for v1:

- keep a reference point for central Krakow
- compute distance from listing coordinates when coordinates exist
- keep municipality and district labels when coordinates do not exist
- allow manual municipality inclusion rules for bordering areas

This avoids paying for geocoding while still making suburb filtering useful.

## Daily Workflow

GitHub Actions should run on a UTC schedule.

Recommended flow:

1. `scrape-source-to-bronze` matrix job per source
2. `build-silver-history`
3. `aggregate-gold-metrics`
4. `smoke-check`

Recommended rules:

- source jobs must be independent
- failures in one source should not block other sources
- every run writes a row into `ingest_runs`
- failed parsers should keep enough raw context to debug
- Bronze remains append-only
- Silver and Gold should be rebuildable from Bronze

## Analysis Shape Before The Website

Before the web app exists, the system should already support:

- notebook queries by rent vs sale
- notebook queries by flat vs house
- daily and weekly price trend analysis
- H3 cell analytics
- municipality and district comparisons
- listing-level price history inspection

## Website Shape

The site should stay lightweight and mostly read precomputed data.

Recommended pages:

- home dashboard
- rent map
- sale map
- area comparison
- listing history drill-down
- methodology page

Recommended UX:

- map with hex overlay and color scale by median price per sqm
- filters for rent/sale, flat/house, budget, rooms, area
- sparkline or mini chart for cell history
- compare two areas or two hexes over time

## Zero-Cost Constraints

These constraints affect the design directly:

- no always-on workers
- no paid geocoding
- no paid map tiles
- no big object storage for full raw HTML
- no heavy real-time analytics layer

Because of that:

- schedule batch jobs once or twice daily
- store compact raw JSON instead of full page bodies where possible
- prefer listing-provided coordinates or textual area references
- precompute metrics nightly instead of querying everything live

## Source Risk Policy

Treat sources in tiers.

### Tier 1

Public pages with stable HTML or embedded JSON and no login barrier.

Start here first.

### Tier 2

Pages needing more browser automation or stronger anti-bot handling.

Add only after Tier 1 works reliably.

### Tier 3

Login-gated, auth-heavy, or highly brittle sources.

Do not put these in v1. Facebook Marketplace most likely belongs here.

## Suggested v1 Scope

The smallest serious version is:

- Krakow plus approximately 30 km radius
- rent and sale
- flats and houses
- one or two sources first
- daily updates
- notebook-first analytics
- listing and area history

Commercial real estate stays out of scope for v1.
