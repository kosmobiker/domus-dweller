# OLX Ingestion Optimization & Detail-Page Enrichment Plan

This document outlines the diagnostic findings, architectural recommendations, and an actionable, step-by-step task checklist to resolve two core issues in the OLX ingestion pipeline:
1. **Parse job taking too long** (~27–30+ minutes in GitHub Actions).
2. **Missing listing detail data** (losing critical ad attributes such as administrative rent, building type, floor, furnishing, elevator, pets, parking, and full descriptions).

---

## 1. Problem Diagnosis & Analysis

### 1.1 Why the Parsing Job Takes ~30 Minutes
From the execution logs of `daily-olx-parse DATE=2026-11-10 PAGES=30`:
- **Scope**: 7 cities (`krakow`, `wieliczka`, `skawina`, `niepolomice`, `zabierzow`, `zielonki`, `swiatniki-gorne`) across 3 rental categories (`mieszkania`, `domy`, `pokoje` = 21 seeds) and 2 sale categories (`mieszkania`, `domy` = 14 seeds) = **35 total seeds**.
- **Process Spawning Overhead**:
  The Makefile runs a nested bash loop. For **every single page** of every seed:
  ```bash
  uv run python -m domus_dweller.sources.olx.fetch_search --url "..." --output "..."
  uv run python -m domus_dweller.parse --source olx --input "..." --output "..."
  ```
  Spawning two fresh Python runtimes per page via `uv run` causes significant startup, dependency resolution, TLS handshake, and teardown overhead across hundreds of requests.
- **Connection Overhead**:
  Every request opens a brand-new TCP + TLS connection without HTTP keep-alive or connection pooling.
- **Pagination Overscanning & "Infinite" Wrapping**:
  In OLX, requesting `?page=N` beyond the available results does not always return HTTP 404 or an empty page. For smaller municipalities (e.g., Wieliczka, Skawina, Niepołomice), OLX wraps around or displays promoted/fallback ads (e.g., pages 27–30 in Wieliczka each returned 87 identical ads). The shell script only checks `[ $(wc -c < "$parsed") -le 3 ]`, so it blindly crawls up to page 30 even when no new ads exist.
- **Strictly Sequential Execution**:
  All 35 seeds run one after another, taking ~12 minutes for rent and ~15 minutes for sale.

---

### 1.2 Why Ads Are Not Digested (Missing Detail Data)
Currently, `AGENTS.md` notes:
> *"Keep ingestion parse-only from search pages for now; detail-page enrichment is disabled in runtime flow."*

While the search page (and its embedded `__PRERENDERED_STATE__`) contains price, approximate location, area, rooms, and coordinates, **high-value analytical attributes are only present on the ad detail page**:
- **Rental utility / admin charges (`czynsz administracyjny` / `czynsz dodatkowo`)**: Crucial in Polish real estate where base rent is often 2,500 PLN but admin rent adds another 800–1,200 PLN.
- **Building metadata**: `rodzaj zabudowy` (blok, kamienica, apartamentowiec, dom), `liczba pięter` (building total floors).
- **Floor info**: `poziom / piętro` (reliable structured extraction).
- **Living conditions**: `umeblowane` (furnished), `winda` (elevator), `zwierzęta` (pets allowed), `parking` (parking spot).
- **Market type**: `rynek` (pierwotny vs wtórny).
- **Full description**: Complete text needed for NLP / feature extraction.
- **Seller details**: Verified profile name and link.

### 1.3 Constraints & Guardrails
- **Zero Recurring Spend**: Paid residential proxies or scraping APIs are out of scope.
- **Anti-Bot & Rate Limiting**: Fetching all ~4,600 detail pages daily would take 2.5+ hours and trigger Cloudflare/OLX HTTP 403 blocks.
- **GitHub Actions Limits**: Standard GHA runners provide 2,000 minutes/month. Daily jobs must stay under 10–12 minutes total.

---

## 2. Strategic Solution

### Strategy A: High-Speed Search Ingestion (Python Orchestrator)
Replace the bash shell loop with a dedicated Python runner (`domus_dweller.sources.olx.orchestrator`):
1. **Concurrent Seed Processing**: Run 3–4 seeds in parallel using `asyncio` or a thread pool.
2. **Persistent Session & Keep-Alive**: Reuse `curl_cffi` sessions with HTTP/2 and TLS impersonation (`chrome120`).
3. **Smart Pagination Termination**:
   - Stop when page has 0 parsed items.
   - Stop when **pagination loop/wrap** is detected (e.g., if ≥60% of listing IDs on page $N$ were already observed in page 1 or previous pages of the same seed).
   - Stop when the search page indicates no further pages (e.g. `next` link absent).
4. **Expected Impact**: Reduces search ingestion time from **27 minutes down to 4–6 minutes**.

---

### Strategy B: Incremental Detail Enrichment (Delta Ingestion)
Instead of crawling 4,600 detail pages every day, implement **incremental delta enrichment**:
1. **Only Fetch New Listings**:
   - Compare scraped `source_listing_id`s against existing listings in MotherDuck Silver (`silver.listing_identity`) or Bronze history.
   - For a daily run in Krakow + 30km, typically only **80–250 listings are new** on any given day.
2. **Upgrade `enrich.py` to `curl_cffi`**:
   - Existing `enrich.py` uses standard `httpx`, which gets blocked with HTTP 403.
   - Switch to `curl_cffi` with browser impersonation.
3. **Polite Throttling & Fail-Safe**:
   - 250ms–350ms jittered delay per detail request.
   - Concurrency of 2–3 requests.
   - Retain the `max_consecutive_403=8` fail-fast circuit breaker.
   - Fetching ~150 new ads will take only **1 to 2 minutes**.
4. **Merge & Preserve**:
   - Merge enriched fields (`rent_additional`, `building_type`, `floor`, `furnished`, `elevator`, `parking`, `market_type`) into the listing payload before sinking to Bronze.

---

## 3. Actionable Implementation Checklist (Tasks for Next Model)

Follow Test-Driven Development (TDD) as mandated by repository rules: write/update functional tests in `ingestion/tests/` before implementation.

### Milestone 1: High-Speed Python Ingestion Orchestrator

- [ ] **Task 1.1: Create Functional Tests for Seed Orchestration**
  - Path: `ingestion/tests/functional/test_olx_orchestrator.py`
  - Test cases:
    - Empty page halts pagination for that seed.
    - Duplicate detection halts pagination when OLX wraps back to previous pages.
    - Concurrent seed workers write expected parsed files into `data/parsed/<date>/`.
    - Merged output contains all unique listings across seeds.

- [ ] **Task 1.2: Implement Python Search Orchestrator**
  - Path: `ingestion/src/domus_dweller/sources/olx/orchestrator.py`
  - Implementation details:
    - CLI options: `--mode (rent|sale|both)`, `--date YYYY-MM-DD`, `--pages INT (default 30)`, `--workers INT (default 4)`, `--cities LIST`.
    - Use `curl_cffi` session pool with persistent keep-alive.
    - Track `seen_seed_ids: set[str]` per seed to detect circular pagination / duplicate pages.
    - Parse HTML directly in memory using `domus_dweller.sources.olx.parser.parse_search_results` and write page JSON + raw HTML.
    - Automatically call `merge_pages` logic at the end of each mode.

- [ ] **Task 1.3: Update Makefile Target `daily-olx-parse`**
  - Path: `Makefile`
  - Replace the bash `run_olx_job` loop with:
    ```makefile
    daily-olx-parse:
    	uv run python -m domus_dweller.sources.olx.orchestrator \
    		--mode both \
    		--date $(DATE) \
    		--pages $(PAGES) \
    		--cities "$(CITIES)" \
    		--workers 4
    ```

---

### Milestone 2: Upgrade Detail-Page Enrichment (`enrich.py`)

- [ ] **Task 2.1: Upgrade HTTP Client in `enrich.py` from `httpx` to `curl_cffi`**
  - Path: `ingestion/src/domus_dweller/sources/olx/enrich.py`
  - Details:
    - Replace `httpx.Client` with `curl_cffi.requests.Session(impersonate="chrome120")`.
    - Ensure TLS fingerprints match modern desktop browser.
    - Update retry decorator to catch `curl_cffi.requests.errors.RequestsError`.

- [ ] **Task 2.2: Add Incremental Filtering (`--only-new`)**
  - Path: `ingestion/src/domus_dweller/sources/olx/enrich.py`
  - Details:
    - Add `--only-new` flag and `--database` flag.
    - When `--only-new` is enabled, connect to MotherDuck / DuckDB and query:
      ```sql
      SELECT DISTINCT source_listing_id FROM silver.listing_identity WHERE source = 'olx'
      ```
    - Filter parsed search listings: only fetch detail pages for `source_listing_id`s not present in the database.
    - For listings that already exist in the database, keep existing search-page data untouched.
    - Gracefully fallback to enriching all input listings if database is unreachable or table does not exist.

- [ ] **Task 2.3: Expand Enriched Fields to Bronze Raw JSON**
  - Ensure all extracted detail fields (`rent_additional`, `rent_additional_currency`, `building_type`, `floor`, `furnished`, `elevator`, `pets_allowed`, `parking`, `market_type`, `seller_name`, `seller_profile_url`, `description`) are preserved in the JSON saved to `data/parsed/<date>/olx_<mode>_all.json`.

- [ ] **Task 2.4: Update Functional Tests for `enrich.py`**
  - Path: `ingestion/tests/functional/test_olx_detail_enrichment.py`
  - Add test verifying `--only-new` flag skips known IDs and only fetches new listings.
  - Verify TLS impersonated mock fetch.

---

### Milestone 3: Integrate Enrichment into Daily Workflow

- [ ] **Task 3.1: Add `daily-olx-enrich` Target in `Makefile`**
  - Path: `Makefile`
  - Add:
    ```makefile
    daily-olx-enrich:
    	uv run python -m domus_dweller.sources.olx.enrich \
    		--input data/parsed/$(DATE)/olx_rent_all.json \
    		--output data/parsed/$(DATE)/olx_rent_all.json \
    		--mode rent \
    		--only-new \
    		--database "$(MD_DATABASE)"
    	uv run python -m domus_dweller.sources.olx.enrich \
    		--input data/parsed/$(DATE)/olx_sale_all.json \
    		--output data/parsed/$(DATE)/olx_sale_all.json \
    		--mode sale \
    		--only-new \
    		--database "$(MD_DATABASE)"
    ```

- [ ] **Task 3.2: Update GitHub Actions Workflow**
  - Path: `.github/workflows/daily-olx-motherduck.yml`
  - Insert enrichment step in `parse` job:
    ```yaml
    - name: Parse OLX Search Pages
      run: make daily-olx-parse DATE=${{ steps.prep.outputs.run_date }} PAGES=${{ steps.prep.outputs.pages }}

    - name: Enrich New Listings from Detail Pages
      run: make daily-olx-enrich DATE=${{ steps.prep.outputs.run_date }} MD_DATABASE=${{ env.MD_DATABASE }}
    ```

---

### Milestone 4: Silver Model & dbt Updates

- [ ] **Task 4.1: Update Staging SQL Model to Expose Detail Fields**
  - Path: `transform/models/staging/stg_bronze_listings.sql`
  - Extract the new JSON keys from `raw_json`:
    - `CAST(j->>'rent_additional' AS DOUBLE) as rent_additional`
    - `j->>'rent_additional_currency' as rent_additional_currency`
    - `j->>'building_type' as building_type`
    - `j->>'market_type' as market_type`
    - `CAST(j->>'furnished' AS BOOLEAN) as is_furnished`
    - `CAST(j->>'elevator' AS BOOLEAN) as has_elevator`
    - `CAST(j->>'parking' AS BOOLEAN) as has_parking`
    - `j->>'seller_name' as seller_name`
    - `j->>'description' as description`

- [ ] **Task 4.2: Update Silver Snapshot `listing_versions`**
  - Path: `transform/snapshots/listing_versions.sql`
  - Add `rent_additional` to `check_cols` to track utility/admin price increases across time:
    ```sql
    check_cols=['price_total', 'rent_additional', 'area_sqm', 'rooms', 'floor', 'district', 'city']
    ```

- [ ] **Task 4.3: Update Schema Documentation & dbt Tests**
  - Path: `transform/models/silver/schema.yml`
  - Add column descriptions and accepted values (e.g. for `market_type` if present).

---

## 4. Verification and Rollout Plan

1. **Local Test Suite**:
   ```bash
   uv run pytest ingestion/tests/functional/test_olx_orchestrator.py
   uv run pytest ingestion/tests/functional/test_olx_detail_enrichment.py
   uv run pytest --cov=domus_dweller
   ```
2. **Local Dry Run (1 page, 1 city)**:
   ```bash
   uv run python -m domus_dweller.sources.olx.orchestrator --mode rent --pages 1 --cities "krakow" --workers 1
   ```
3. **MotherDuck Staging Sync**:
   Run `make silver-sync` locally against a test database to verify dbt model compilation and snapshot schema compatibility.
4. **Deploy & Monitor**:
   Push to `master` and trigger the GitHub Actions workflow manually (`workflow_dispatch` with `pages=5` as a canary test).
