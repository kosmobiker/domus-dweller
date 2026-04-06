# MotherDuck Ingestion (DuckDB Bronze)

This project now writes parsed OLX rows directly into MotherDuck (DuckDB) Bronze tables rather than a cloud warehouse. The sink is append-only and stores unchanged facts plus metadata that make downstream Silver work deterministic.

## Bronze Tables

`motherduck-bootstrap` creates two tables under the `bronze` schema:

- `bronze.rent_bronze`
- `bronze.sale_bronze`

Both share the same minimal contract:

- source identity (`source`, `source_listing_id`, `source_url`)
- required metadata (`mode`, `snapshot_date`, `layer`, `ingested_at`)
- debugging aids (`payload_hash`, `raw_json`)

The schema enforces a composite primary key on `(source, source_listing_id, snapshot_date)` so each observation is uniquely recorded per run.

## Connection & Secrets

Every sink run expects `MOTHERDUCK_TOKEN` to be set and optionally accepts `MOTHERDUCK_DATABASE`/`MD_DATABASE` via Make vars. The sink code uses the Python `duckdb` client (`md:<database>?token=<token>`) plus PyArrow to stream rows. It validates that required sink columns exist before loading and throws early if any are missing.

## Commands

1. **Parse job** (produce merged JSON per mode):
   ```bash
   make daily-olx-parse DATE=2026-04-04 PAGES=30
   ```
   This step fetches OLX search pages, parses each seed page, and merges them into `data/parsed/<date>/olx_<mode>_all.json`.

2. **Bootstrap MotherDuck tables** (one-time or when schema changes):
   ```bash
   make motherduck-bootstrap MD_DATABASE=my_db
   ```

3. **Sink job** (load parsed JSON into MotherDuck):
   ```bash
   make daily-olx-sink-motherduck DATE=2026-04-04 MD_DATABASE=my_db
   ```
   The target mode(s) default to both `rent` and `sale`. The command retries up to three times with exponential backoff if the sink fails.

4. **Direct ingestion mode** (scrape + sink without persisted artifacts):
   ```bash
   make daily-olx-motherduck MD_DATABASE=my_db PAGES=30 CITIES="krakow wieliczka" ENRICH_PAUSE_MS=250
   ```
   This command runs the ingestion pipeline end-to-end per mode, skipping the parse/sink split.

## Notes

- The sink keeps the original parsed row under `raw_json` and adds `payload_hash`, `ingested_at`, and `layer` so Silver can detect drift without re-parsing.
- The loader uses PyArrow to convert normalized dicts into a single table before issuing `INSERT INTO bronze.<mode>_bronze SELECT ... FROM arrow_table`. This keeps round-trips low and matches DuckDB's in-memory strengths.
- Keep the Bronze layer appendix-only; dedup/SCD should happen later when building Silver outputs in MotherDuck SQL scripts or notebooks.
