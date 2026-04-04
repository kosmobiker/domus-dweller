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

3. BigQuery sink functional tests
- validate required field enforcement
- validate payload hashing and append behavior
- validate load-job error handling

4. Bootstrap functional tests
- validate dataset/table creation contract
- validate partitioning/clustering setup

## Current Focus

- Prefer tests around behavior and contracts, not tiny helpers.
- Keep CI free from live network dependencies.
- Use fixtures and monkeypatched clients for deterministic runs.

## Commands

```bash
uv run ruff check .
uv run pytest -q
uv run pytest --cov=domus_dweller --cov-report=term-missing -q
```
