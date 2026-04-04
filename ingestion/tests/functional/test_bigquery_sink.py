from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from domus_dweller.sinks.bigquery import load_rows_to_bigquery


class _FakeBigQueryClient:
    def __init__(self, errors: list[dict] | None = None) -> None:
        self.errors = errors or []
        self.table_id: str | None = None
        self.rows: list[dict] = []
        self.job_config = None

    class _FakeLoadJob:
        def __init__(self, errors: list[dict], output_rows: int) -> None:
            self.errors = errors
            self.output_rows = output_rows

        def result(self) -> None:
            return None

    def load_table_from_json(
        self,
        json_rows: list[dict],
        destination: str,
        *,
        job_config=None,
    ):
        self.table_id = destination
        self.rows = json_rows
        self.job_config = job_config
        return _FakeBigQueryClient._FakeLoadJob(self.errors, len(json_rows))


def test_given_rows_when_loading_then_rows_are_appended_to_mode_table() -> None:
    # Given
    client = _FakeBigQueryClient()
    rows = [
        {
            "source": "olx",
            "source_listing_id": "olx-1",
            "source_url": "https://www.olx.pl/d/oferta/example-CID3-ID1.html",
            "title": "Oferta",
        }
    ]

    # When
    inserted = load_rows_to_bigquery(
        rows,
        mode="rent",
        project="dw-project",
        dataset="bronze",
        client=client,
        snapshot_date=date(2026, 4, 4),
        ingested_at=datetime(2026, 4, 4, 8, 30, tzinfo=UTC),
    )

    # Then
    assert inserted == 1
    assert client.table_id == "dw-project.bronze.rent_bronze"
    assert client.rows[0]["mode"] == "rent"
    assert client.rows[0]["layer"] == "bronze"
    assert client.rows[0]["snapshot_date"] == "2026-04-04"
    assert client.rows[0]["ingested_at"] == "2026-04-04T08:30:00+00:00"
    assert client.rows[0]["payload_hash"]
    assert client.rows[0]["raw_json"]["source_listing_id"] == "olx-1"


def test_given_missing_required_fields_when_loading_then_error_is_raised() -> None:
    # Given
    client = _FakeBigQueryClient()
    rows = [{"source": "olx"}]

    # When / Then
    with pytest.raises(ValueError, match="Missing required fields"):
        load_rows_to_bigquery(
            rows,
            mode="sale",
            project="dw-project",
            dataset="bronze",
            client=client,
        )


def test_given_bigquery_insert_errors_when_loading_then_error_is_raised() -> None:
    # Given
    client = _FakeBigQueryClient(errors=[{"index": 0, "errors": ["invalid"]}])
    rows = [
        {
            "source": "olx",
            "source_listing_id": "olx-2",
            "source_url": "https://www.olx.pl/d/oferta/example-CID3-ID2.html",
            "title": "Oferta 2",
        }
    ]

    # When / Then
    with pytest.raises(RuntimeError, match="BigQuery load job returned errors"):
        load_rows_to_bigquery(
            rows,
            mode="sale",
            project="dw-project",
            dataset="bronze",
            client=client,
        )
