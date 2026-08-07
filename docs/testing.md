# Testing

## Default Approach

Use TDD for ingestion and data contracts.

Preferred order:

1. write a failing functional test,
2. implement smallest change,
3. refactor safely.

## High-Value Test Layers

1. Parser functional tests
- validate extraction from frozen OLX fixtures
- protect against selector drift
- verify seller classification behavior

2. Ingestion orchestration functional tests
- validate search collection, dedup-in-memory, and sink wiring
- validate mode routing (`rent` vs `sale`)

3. MotherDuck sink functional tests
- validate required field enforcement
- validate payload hashing and append behavior
- validate load-job error handling

4. Bootstrap functional tests
- validate dataset/table creation contract
- validate partitioning/clustering setup

5. Silver / dbt Layer Tests
- functional testing via `test_dbt_silver_layer.py`
- standard `dbt test` assertions (unique, not_null, accepted_values)

## Current Focus

- Prefer tests around behavior and contracts, not tiny helpers.
- Keep CI free from live network dependencies.
- Use fixtures and monkeypatched clients for deterministic runs.

## Test Files

All functional tests live in `ingestion/tests/functional/`:

- `test_olx_parser_contract.py` – parser extraction contract
- `test_olx_parser_quality.py` – parser field quality and coverage
- `test_olx_detail_enrichment.py` – detail page enrichment logic
- `test_olx_end_to_end_pipeline.py` – full pipeline integration
- `test_olx_ingest_motherduck.py` – direct ingestion mode
- `test_motherduck_sink_integration.py` – sink append and upsert behavior
- `test_motherduck_bootstrap.py` – schema/table creation
- `test_olx_files_to_motherduck_cli.py` – file-based sink CLI
- `test_merge_pages_cli.py` – page merge CLI
- `test_parse_cli.py` – parse CLI entry point
- `test_dbt_silver_layer.py` – Silver SCD and identity models

Fixtures: `ingestion/tests/fixtures/olx/search_results.html`

## Commands

```bash
make lint                   # ruff check
make test                   # pytest with 70% coverage minimum
make verify                 # lint + test (mirrors CI)
uv run pytest -q            # quick test run
uv run pytest --cov=domus_dweller --cov-report=term-missing -q
```
