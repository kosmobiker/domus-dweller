# SKILLS

Project-specific working skills for this repository.

## 1. Source Adapter Design

When adding a source:

- define the search URLs or discovery entrypoints
- identify stable listing identifiers
- capture the minimum raw payload needed for debugging
- extract seller classification and preserve source evidence for it
- map to the canonical schema
- tag unsupported fields instead of guessing
- write a parser fixture before broad crawling

## 2. Historical Modeling

When persisting observations:

- keep immutable observations separate from current listing state
- store `observed_at`, `first_seen_at`, and `last_seen_at`
- keep both total price and normalized price per square meter
- treat disappearance as a state change, not a delete

## 3. Geo Skill

When working with maps:

- store latitude and longitude in the canonical listing record
- compute H3 cell ids in the Python pipeline first
- aggregate daily metrics by cell and listing type
- use different H3 resolutions for zoomed-out and zoomed-in views

## 4. Analytics Skill

Start with robust metrics:

- median price
- median price per square meter
- listing count
- new listings
- removed listings
- days on market
- price change frequency

Avoid starting with fragile composite scores before the base metrics are trustworthy.

## 5. AI Skill

Use "AI" only where it adds leverage:

- amenity extraction from Polish listing descriptions
- duplicate detection across portals
- outlier explanation
- natural-language search over saved analytics summaries

Default to rule-based or statistical methods first. Only add models after the baseline pipeline is reliable.

## 6. Zero-Cost Skill

Before adding any dependency or service:

- check whether Neon free tier and Vercel free tier are enough
- prefer GitHub Actions scheduled jobs over always-on workers
- avoid storage-heavy raw HTML retention if compact JSON is enough
- avoid paid geocoding and paid map tiles
- favor notebook-first analysis before building product UI
