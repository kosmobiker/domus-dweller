# Testing

## Default Approach

This project should use TDD for the ingestion and analytics foundation.

Testing bias:

- prefer functional tests
- prefer integration tests
- use narrow unit tests only when they buy real speed or clarity

The default rule is:

1. write a failing test
2. implement the smallest change that makes it pass
3. refactor without changing behavior

## Test Layers

### 1. Parser Functional Tests

Purpose:

- verify extraction from saved source fixtures
- protect against selector drift
- lock down seller signals

Examples:

- listing card extraction from search results
- detail page field extraction
- seller badge or agency/private signal extraction

These tests should use frozen fixtures, not live network calls.

These are functional tests because they validate behavior across realistic fixture inputs rather than tiny isolated helpers.

### 2. Normalization Behavior Tests

Purpose:

- verify canonical mapping
- verify numeric parsing
- verify seller classification normalization
- verify H3 assignment behavior when coordinates exist

Examples:

- `12 500 zł` becomes a numeric total price
- `agency` source label becomes `professional`
- `private owner` source label becomes `private`
- area and rooms parsing are normalized consistently

These should usually be table-driven behavior tests around meaningful input and output records, not micro-tests for tiny helper functions.

### 3. Persistence Integration Tests

Purpose:

- verify schema bootstrap
- verify upserts and insert-only history behavior
- verify inactive listing handling

Examples:

- repeated observations create history rows, not overwrites
- `listings` upsert on `(source_id, source_listing_id)` works
- missing listings are marked inactive correctly

These tests should run against an isolated test database, not production Neon.

### 4. Aggregation Functional Tests

Purpose:

- verify H3 daily metrics and notebook-facing queries

Examples:

- median price per sqm is computed correctly
- counts split correctly by `rent` vs `sale`
- counts split correctly by `flat` vs `house`
- counts split correctly by `private` vs `professional`

## Fixture Strategy

- keep raw source fixtures under version control when legally and practically reasonable
- prefer compact HTML or JSON excerpts over full pages
- keep fixtures named by source, page type, and scenario
- add fixtures for edge cases, not only happy paths

Important edge cases:

- missing coordinates
- missing rooms
- missing area
- price changes
- agency listings
- private listings
- removed listings

## Minimal Initial Test Plan

Before the first real ingest, add tests for:

- schema bootstrap
- Otodom search-result parsing
- Otodom detail parsing
- seller classification normalization
- canonical listing normalization
- one end-to-end ingest flow using fixtures and a test database

## Commands

```bash
uv run pytest
uv run pytest ingestion/tests -q
uv run ruff check .
uv run ruff format .
```

## Non-Goals

Do not start with:

- live-network tests in CI
- brittle screenshot-based parser tests
- broad unit-test suites for tiny helpers with little business value
- end-to-end browser automation unless a source truly requires it
