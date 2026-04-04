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
- Database: Neon Postgres free tier
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

There should be four layers.

### 1. Source Adapters

Each source adapter is isolated and returns a common intermediate object:

- source name
- source listing id
- source URL
- listing type: `rent` or `sale`
- property type: `flat`, `house`, later `room`
- title
- description
- address text
- district or municipality
- price
- currency
- area sqm
- rooms
- floor
- latitude and longitude when available
- image URLs
- seller type
- raw payload fragment

This layer should know source-specific selectors and source-specific quirks.

### 2. Normalization Layer

This layer converts adapter output into canonical records and validates them.

Responsibilities:

- trim and standardize strings
- derive price per square meter
- classify Krakow vs suburb
- normalize room and area values
- reject obviously broken records
- compute a listing fingerprint

### 3. Persistence Layer

Use Postgres as the system of record.

Suggested tables:

- `sources`
- `ingest_runs`
- `raw_listing_snapshots`
- `listings`
- `listing_observations`
- `listing_current`
- `h3_daily_metrics`
- `municipality_reference`
- `district_reference`

Suggested behavior:

- `raw_listing_snapshots`: immutable source payloads or compact extracted source JSON
- `listings`: canonical identity per source listing
- `listing_observations`: one row per observation time, preserving price history
- `listing_current`: current denormalized state for fast reads
- `h3_daily_metrics`: pre-aggregated daily metrics for the map

## Historical Price Model

Do not store only the latest value.

For each observed listing state, keep:

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

This gives you:

- price history by listing
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

1. `scrape-source` matrix job per source
2. `normalize-and-upsert`
3. `aggregate-daily-metrics`
4. `smoke-check`

Recommended rules:

- source jobs must be independent
- failures in one source should not block other sources
- every run writes a row into `ingest_runs`
- failed parsers should keep enough raw context to debug

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
- H3 price map later
- listing and area history

Commercial real estate stays out of scope for v1.
