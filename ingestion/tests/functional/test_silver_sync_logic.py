from __future__ import annotations

import duckdb
import pytest
from domus_dweller.sinks.motherduck_silver_bootstrap import bootstrap_silver
from domus_dweller.sinks.motherduck_silver_sync import sync_silver


class _KeepAliveConnection:
    def __init__(self, inner: duckdb.DuckDBPyConnection) -> None:
        self._inner = inner

    def execute(self, sql: str, **kwargs: object) -> duckdb.DuckDBPyConnection:
        return self._inner.execute(sql, **kwargs)

    def close(self) -> None:
        # Ignore close to keep in-memory DB alive between bootstrap and sync
        return None

    def __getattr__(self, name: str) -> object:
        return getattr(self._inner, name)


@pytest.fixture
def mock_db(monkeypatch):
    """
    Creates an in-memory DuckDB with the necessary Bronze and Silver schemas.
    """
    real_conn = duckdb.connect(":memory:")
    conn = _KeepAliveConnection(real_conn)

    # Mock the connection in both bootstrap and sync modules
    monkeypatch.setattr(
        "domus_dweller.sinks.motherduck_silver_bootstrap.duckdb.connect",
        lambda *args, **kwargs: conn,
    )
    monkeypatch.setattr(
        "domus_dweller.sinks.motherduck_silver_sync.duckdb.connect",
        lambda *args, **kwargs: conn,
    )

    # Setup Bronze
    conn.execute("CREATE SCHEMA bronze;")
    conn.execute("""
        CREATE TABLE bronze.rent_bronze (
            source VARCHAR, source_listing_id VARCHAR, mode VARCHAR, 
            snapshot_date DATE, ingested_at TIMESTAMP, raw_json JSON
        );
    """)
    conn.execute("""
        CREATE TABLE bronze.sale_bronze (
            source VARCHAR, source_listing_id VARCHAR, mode VARCHAR, 
            snapshot_date DATE, ingested_at TIMESTAMP, raw_json JSON
        );
    """)

    # Bootstrap Silver
    bootstrap_silver(database="memory", token="fake")

    yield conn
    real_conn.close()


def test_silver_sync_collapses_duplicates_and_versions_changes(mock_db):
    # 1. Given: Noisy Bronze data for one listing
    # Day 1: First sighting
    # Day 2: Identical snapshot (Noise)
    # Day 3: Price change (Functional Change)
    mock_db.execute("""
        INSERT INTO bronze.sale_bronze VALUES 
        ('olx', '123', 'sale', '2026-01-01', '2026-01-01 10:00:00', 
         '{"title": "Flat", "price_total": 100, "area_sqm": 50, "rooms": 2}'),
        ('olx', '123', 'sale', '2026-01-02', '2026-01-02 10:00:00', 
         '{"title": "Flat", "price_total": 100, "area_sqm": 50, "rooms": 2}'),
        ('olx', '123', 'sale', '2026-01-03', '2026-01-03 10:00:00', 
         '{"title": "Flat", "price_total": 120, "area_sqm": 50, "rooms": 2}')
    """)

    # 2. When: Syncing to Silver
    sync_silver(database="memory", token="fake")

    # 3. Then: We should have 1 Identity and EXACTLY 2 Versions (Noise collapsed)
    identity_count = mock_db.execute("SELECT count(*) FROM silver.listing_identity").fetchone()[0]
    version_count = mock_db.execute("SELECT count(*) FROM silver.listing_versions").fetchone()[0]

    assert identity_count == 1
    assert version_count == 2, "Daily noise not collapsed; expected 2 versions."

    # Verify Timeline
    query = "SELECT valid_from, valid_to, is_current, price_total FROM silver.listing_versions"
    versions = mock_db.execute(f"{query} ORDER BY valid_from").fetchall()

    # Version 1 (Jan 1 to Jan 3)
    assert versions[0][3] == 100
    assert versions[0][2] is False
    assert versions[0][1] == versions[1][0]  # v1 valid_to == v2 valid_from

    # Version 2 (Jan 3 to now)
    assert versions[1][3] == 120
    assert versions[1][2] is True
    assert versions[1][1] is None
