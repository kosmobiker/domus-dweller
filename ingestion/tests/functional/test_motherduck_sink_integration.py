from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import duckdb
import pyarrow as pa
from domus_dweller.sinks import olx_files_to_motherduck


def test_given_rent_json_when_running_sink_cli_then_brief_bronze_row_is_appended(
    monkeypatch,
    tmp_path: Path,
) -> None:
    # Given
    snapshot = date(2026, 4, 4)
    rents = [
        {
            "source": "olx",
            "source_listing_id": "olx-rent-1",
            "source_url": "https://www.olx.pl/d/oferta/rent-1.html",
            "title": "Studio in Krakow",
            "price_total": 1470,
            "currency": "PLN",
        }
    ]
    rent_file = tmp_path / "olx_rent_all.json"
    rent_file.write_text(json.dumps(rents), encoding="utf-8")

    real_connection = duckdb.connect(":memory:")
    class _KeepAliveConnection:
        def __init__(self, inner: duckdb.DuckDBPyConnection) -> None:
            self._inner = inner

        def execute(self, sql: str, **kwargs: object) -> duckdb.DuckDBPyConnection:
            return self._inner.execute(sql, **kwargs)

        def close(self) -> None:
            return None

        def __getattr__(self, name: str) -> object:
            return getattr(self._inner, name)

    connection = _KeepAliveConnection(real_connection)
    monkeypatch.setattr(
        "domus_dweller.sinks.motherduck.duckdb.connect",
        lambda *args, **kwargs: connection,
    )
    connection.execute("CREATE SCHEMA IF NOT EXISTS bronze;")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS bronze.rent_bronze (
            source VARCHAR,
            source_listing_id VARCHAR,
            source_url VARCHAR,
            mode VARCHAR,
            snapshot_date DATE,
            layer VARCHAR,
            ingested_at TIMESTAMP,
            payload_hash VARCHAR,
            raw_json JSON
        );
        """
    )

    original_table_cls = pa.Table

    class TableRecorder:
        @staticmethod
        def from_pylist(rows: list[dict[str, object]]) -> pa.Table:
            table = original_table_cls.from_pylist(rows)
            duckdb.register("arrow_table", table, connection=connection._inner)
            return table

    monkeypatch.setattr(pa, "Table", TableRecorder)

    monkeypatch.setenv("MOTHERDUCK_TOKEN", "fake-token")
    monkeypatch.setattr(
        "sys.argv",
        [
            "olx_files_to_motherduck",
            "--mode",
            "rent",
            "--database",
            "test-db",
            "--date",
            snapshot.isoformat(),
            "--input-rent",
            str(rent_file),
        ],
    )

    # When
    olx_files_to_motherduck.main()

    # Then
    rows = connection.execute(
        "SELECT source, source_listing_id, mode, snapshot_date, layer, payload_hash, raw_json "
        "FROM bronze.rent_bronze;"
    ).fetchall()
    assert len(rows) == 1
    source, listing_id, mode, snapshot_date, layer, payload_hash, raw_json = rows[0]
    assert source == "olx"
    assert listing_id == "olx-rent-1"
    assert mode == "rent"
    assert snapshot_date == snapshot
    assert layer == "bronze"
    assert payload_hash is not None and len(payload_hash) > 0
    assert json.loads(raw_json) == rents[0]

    connection._inner.close()
