from __future__ import annotations

import argparse
import sys
from types import ModuleType, SimpleNamespace

from domus_dweller.sinks import bigquery_bootstrap


def _install_fake_bigquery_modules(monkeypatch) -> SimpleNamespace:
    state = SimpleNamespace(
        created_datasets=[],
        created_tables=[],
    )

    class _SchemaField:
        def __init__(self, name: str, field_type: str, mode: str = "NULLABLE") -> None:
            self.name = name
            self.field_type = field_type
            self.mode = mode

    class _Dataset:
        def __init__(self, dataset_id: str) -> None:
            self.dataset_id = dataset_id
            self.location = None

    class _Table:
        def __init__(self, table_id: str, schema: list[_SchemaField]) -> None:
            self.table_id = table_id
            self.schema = schema
            self.time_partitioning = None
            self.clustering_fields = None

    class _TimePartitioning:
        def __init__(self, *, type_: str, field: str) -> None:
            self.type_ = type_
            self.field = field

    class _Client:
        def __init__(self, *, project: str) -> None:
            self.project = project

        def create_dataset(self, dataset_ref: _Dataset, *, exists_ok: bool) -> None:
            state.created_datasets.append((dataset_ref, exists_ok))

        def create_table(self, table: _Table, *, exists_ok: bool) -> None:
            state.created_tables.append((table, exists_ok))

    bigquery_module = ModuleType("google.cloud.bigquery")
    bigquery_module.Client = _Client
    bigquery_module.Dataset = _Dataset
    bigquery_module.Table = _Table
    bigquery_module.SchemaField = _SchemaField
    bigquery_module.TimePartitioning = _TimePartitioning
    bigquery_module.TimePartitioningType = SimpleNamespace(DAY="DAY")

    cloud_module = ModuleType("google.cloud")
    cloud_module.bigquery = bigquery_module
    google_module = ModuleType("google")
    google_module.cloud = cloud_module

    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.cloud", cloud_module)
    monkeypatch.setitem(sys.modules, "google.cloud.bigquery", bigquery_module)

    return state


def test_given_bronze_fields_when_building_schema_then_schema_matches_contract() -> None:
    # Given
    fake_bigquery = SimpleNamespace(
        SchemaField=lambda name, field_type, mode="NULLABLE": (name, field_type, mode)
    )

    # When
    schema = bigquery_bootstrap._build_schema(fake_bigquery)

    # Then
    assert len(schema) == len(bigquery_bootstrap.BRONZE_SCHEMA_FIELDS)
    assert schema[0] == ("ingested_at", "TIMESTAMP", "REQUIRED")
    assert schema[-1] == ("raw_json", "JSON", "NULLABLE")


def test_given_project_dataset_when_bootstrapping_then_dataset_and_mode_tables_are_created(
    monkeypatch,
) -> None:
    # Given
    state = _install_fake_bigquery_modules(monkeypatch)

    # When
    bigquery_bootstrap.bootstrap_bigquery_bronze(
        project="dw-proj",
        dataset="bronze",
        location="EU",
    )

    # Then
    assert len(state.created_datasets) == 1
    dataset_ref, dataset_exists_ok = state.created_datasets[0]
    assert dataset_exists_ok is True
    assert dataset_ref.dataset_id == "dw-proj.bronze"
    assert dataset_ref.location == "EU"

    assert len(state.created_tables) == 2
    table_ids = [table.table_id for table, _ in state.created_tables]
    assert table_ids == ["dw-proj.bronze.rent_bronze", "dw-proj.bronze.sale_bronze"]
    for table, exists_ok in state.created_tables:
        assert exists_ok is True
        assert table.time_partitioning.field == "snapshot_date"
        assert table.time_partitioning.type_ == "DAY"
        assert table.clustering_fields == ["source", "source_listing_id"]


def test_given_cli_args_when_running_main_then_bootstrap_is_called(monkeypatch) -> None:
    # Given
    called: dict[str, str] = {}

    monkeypatch.setattr(
        bigquery_bootstrap,
        "_build_args",
        lambda: argparse.Namespace(project="p1", dataset="d1", location="EU"),
    )

    def _fake_bootstrap(*, project: str, dataset: str, location: str) -> None:
        called["project"] = project
        called["dataset"] = dataset
        called["location"] = location

    monkeypatch.setattr(bigquery_bootstrap, "bootstrap_bigquery_bronze", _fake_bootstrap)

    # When
    bigquery_bootstrap.main()

    # Then
    assert called == {"project": "p1", "dataset": "d1", "location": "EU"}
