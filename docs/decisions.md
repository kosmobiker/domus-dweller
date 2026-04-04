# Decisions

These decisions are already made.

## Product Scope

- v1 includes flats and houses
- commercial real estate is excluded
- geography is Krakow plus roughly a 30 km radius
- Facebook Marketplace is out of scope for v1
- daily ingestion is enough for v1

## Delivery Sequence

1. Scrape and store data
2. Analyze data in Jupyter notebooks
3. Build the web application

## Technology Direction

- Neon Postgres remains the system of record
- GitHub Actions remains the scheduler
- Python is the preferred language for the data pipeline
- Python 3.13 is the baseline runtime
- `uv` is the preferred dependency manager
- `ruff` is the default lint and format tool
- H3 remains the spatial indexing strategy
- the web app is a later phase, not the first milestone
- seller classification must distinguish at least `private` from `professional`
