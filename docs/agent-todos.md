# Agent To-Dos

This file turns the agent role definitions into an execution checklist.

Current priority:

1. Build the ingestion foundation
2. Land data in Neon every day
3. Make the data useful in notebooks
4. Build the web app later

## Recommended Execution Order

1. System Architect
2. Data Agent
3. Ingestion Agent
4. Ops Agent
5. Geo Analytics Agent
6. Web Agent

The first four roles are on the critical path for Phase 1.

## System Architect

### Now

- [ ] Freeze the first source order as `Otodom` then `OLX`
- [ ] Freeze the collection contract as public pages, public embedded data, and official APIs when legitimately available
- [ ] Freeze the v1 geography as Krakow plus 30 km radius
- [ ] Freeze the v1 property scope as `flat` and `house`
- [ ] Freeze the seller classification contract as `seller_segment` and `seller_type`
- [ ] Decide the exact center point used for the 30 km radius filter
- [ ] Define the first success milestone: one source manually ingested into Neon

### Next

- [ ] Decide whether to keep municipality allowlists for edge cases outside the pure radius check
- [ ] Decide when cross-source deduplication moves from backlog to active work
- [ ] Decide whether daily aggregation runs immediately after each source or once after all source jobs finish

### Done When

- [ ] The source order, scope, and ingest policy are stable enough that implementation can proceed without architecture churn

## Data Agent

### Now

- [ ] Create the initial SQL schema file for `sources`, `ingest_runs`, `listings`, `listing_observations`, `listing_current`, and `h3_daily_metrics`
- [ ] Add database-level smoke tests for schema bootstrap and core constraints
- [ ] Define enum-like constraints for `listing_type`, `property_type`, `seller_segment`, and `seller_type`
- [ ] Add indexes for source lookup, observation history, and H3 analytics
- [ ] Define the upsert strategy for `listings`
- [ ] Define insert-only behavior for `listing_observations`
- [ ] Define how inactive listings are marked when they disappear from source results
- [ ] Add a seed for the known sources: `otodom` and `olx`

### Next

- [ ] Create a `listing_current` view or refreshable table
- [ ] Create daily aggregation SQL for `h3_daily_metrics`
- [ ] Create notebook-friendly SQL views for rent vs sale and flat vs house comparisons
- [ ] Define a raw payload retention policy in SQL terms

### Later

- [ ] Add cross-source deduplication tables if needed
- [ ] Add reference tables for municipality normalization

### Done When

- [ ] Neon can be bootstrapped from SQL files alone
- [ ] The schema supports history, seller classification, and H3-based analytics without redesign

## Ingestion Agent

### Now

- [ ] Inspect `Otodom` public listing pages and identify the safest parse path
- [ ] Inspect `OLX` public listing pages and official developer options and identify the safest parse path
- [ ] Create the canonical Python models for raw source output and normalized listing data
- [ ] Create source adapter interfaces so each portal is isolated
- [ ] Build the first parser fixture set from saved source responses
- [ ] Write failing functional parser tests before implementing each adapter parser
- [ ] Write failing behavior-level normalization tests before implementing canonical mapping
- [ ] Extract and normalize seller signals into `private`, `professional`, or `unknown`
- [ ] Preserve finer seller type details such as `agency`, `developer`, or `private`
- [ ] Implement pagination handling for search result pages
- [ ] Implement retry and rate-limit handling
- [ ] Implement source run metrics and error capture

### Next

- [ ] Build a manual CLI command for a single-source ingest run
- [ ] Add inactive-listing detection
- [ ] Add source health checks that fail loudly when selectors break
- [ ] Add fixture-based parser tests for both sources
- [ ] Add functional ingest tests for a full run against a disposable test database
- [ ] Add compact raw payload storage for debugging

### Later

- [ ] Add a third public source if coverage is still weak
- [ ] Add browser automation only if a public page cannot be parsed via simple HTTP

### Done When

- [ ] A source can be ingested repeatably
- [ ] Seller classification is captured
- [ ] Broken selectors can be diagnosed from stored evidence

## Ops Agent

### Now

- [ ] Finalize the local env contract around `NEON_DATABASE_URL` and `NEON_BRANCH`
- [ ] Create a Python project bootstrap flow using `uv`
- [ ] Add `ruff` check and format commands to the standard workflow
- [ ] Add `pytest` to the standard local and CI workflow
- [ ] Define the command entrypoints that GitHub Actions will run later

### Next

- [ ] Add GitHub Actions workflow files for daily ingestion
- [ ] Add a matrix job for source and listing type where useful
- [ ] Add GitHub secret names and setup instructions
- [ ] Add a smoke-check step after ingestion
- [ ] Add failure visibility through workflow output and job summaries

### Later

- [ ] Add daily aggregation workflows
- [ ] Add backup and export routines if Neon free-tier limits become tight

### Done When

- [ ] A fresh clone can be set up with `uv`
- [ ] Daily ingestion can run unattended in GitHub Actions

## Geo Analytics Agent

### Now

- [ ] Choose the H3 resolutions for storage and aggregation, currently `res8` and `res9`
- [ ] Define the exact radius filter logic for Krakow plus 30 km
- [ ] Define the fallback logic when coordinates are missing but municipality text exists
- [ ] Decide how municipality and district labels are normalized

### Next

- [ ] Implement H3 assignment in the Python pipeline
- [ ] Implement daily H3 aggregation logic
- [ ] Build notebook queries for hex-level trend analysis
- [ ] Validate that the chosen H3 resolutions are useful for both city and suburb views

### Later

- [ ] Add area scoring logic using transparent metrics
- [ ] Add commute or amenity overlays if you later bring in more datasets

### Done When

- [ ] Every usable listing can be assigned to a meaningful location bucket
- [ ] Hex-level daily metrics are ready for notebook and future web map use

## Web Agent

### Now

- [ ] Stay out of the critical path until the ingestion and notebook phases are useful
- [ ] Review the future data contract so the web app reads precomputed data rather than raw history tables directly

### Next

- [ ] Design the first read-only pages: rent map, sale map, area comparison, listing history
- [ ] Define the API or query layer for pre-aggregated metrics
- [ ] Keep the UI lightweight enough for Vercel Hobby limits

### Later

- [ ] Build the Next.js app
- [ ] Build the hex map with filters
- [ ] Build listing history charts
- [ ] Add area comparison views

### Done When

- [ ] The app answers practical buy/rent questions using precomputed metrics, not expensive live analytics

## Cross-Agent Handoffs

- [ ] System Architect hands scope and source policy to Data and Ingestion before implementation starts
- [ ] Data Agent publishes schema contracts before Ingestion writes database code
- [ ] Ingestion Agent publishes normalized sample payloads before Geo Analytics builds aggregations
- [ ] Ops Agent wires scheduled jobs only after manual ingest commands are stable
- [ ] Web Agent starts only after notebook analytics already prove the data model is useful

## Immediate Sprint

If you want the fastest path to first data, the next work items should be:

- [ ] create `sql/001_init.sql`
- [ ] create Python config and Neon connection module
- [ ] create canonical listing and seller models
- [ ] create `Otodom` adapter skeleton
- [ ] save parser fixtures from real public pages
- [ ] write failing functional tests for schema, parser, normalization, and ingest flow
- [ ] run the first manual ingest against Neon
