# Roadmap

## Phase 0: Foundation

- confirm scope and source priorities
- choose the primary implementation language for data work
- define the canonical schema
- create local development workflow

## Phase 1: Ingestion MVP

- build one source adapter
- persist raw snapshots
- normalize into canonical listings
- store listing observations
- run the pipeline manually

Success means one source can be ingested repeatably and inspected in Neon.

## Phase 2: Scheduled Pipeline

- add GitHub Actions cron
- add source run logging
- add failure alerts through workflow output
- add daily aggregation jobs

Success means data refreshes automatically every day.

## Phase 3: Notebook Analytics

- create H3 daily metrics
- create reusable SQL queries
- create Jupyter notebooks for area comparisons
- create Jupyter notebooks for listing history
- validate rent vs sale and flat vs house analytics

Success means the project is already useful without any web interface.

## Phase 4: Analytics Web App

- render the rent map
- render the sale map
- add area history charts
- expose listing detail history

Success means the app answers practical questions about where to rent or buy.

## Phase 5: Expansion

- add second and third sources
- add suburb comparisons
- add duplicate detection across sources
- add amenity extraction

## Phase 6: Decision Support

- build neighborhood scores from transparent metrics
- add alerting for price drops or new supply
- add personal shortlists and watch areas
- add recommendation logic based on user preferences
