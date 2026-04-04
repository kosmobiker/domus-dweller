from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from domus_dweller.sinks import olx_files_to_bigquery


def test_given_rent_and_sale_files_when_running_sink_cli_then_both_modes_are_loaded(
    monkeypatch,
    tmp_path: Path,
) -> None:
    # Given
    rent_path = tmp_path / "olx_rent_all.json"
    sale_path = tmp_path / "olx_sale_all.json"
    rent_path.write_text(
        json.dumps(
            [
                {
                    "source": "olx",
                    "source_listing_id": "olx-r1",
                    "source_url": "https://www.olx.pl/d/oferta/r1.html",
                    "title": "Rent 1",
                }
            ]
        ),
        encoding="utf-8",
    )
    sale_path.write_text(
        json.dumps(
            [
                {
                    "source": "olx",
                    "source_listing_id": "olx-s1",
                    "source_url": "https://www.olx.pl/d/oferta/s1.html",
                    "title": "Sale 1",
                }
            ]
        ),
        encoding="utf-8",
    )

    calls: list[tuple[str, int, date]] = []

    def _fake_load_rows_to_bigquery(
        rows,
        *,
        mode,
        project,
        dataset,
        client=None,
        snapshot_date=None,
        ingested_at=None,
    ) -> int:
        assert project == "dw-project"
        assert dataset == "bronze"
        calls.append((mode, len(rows), snapshot_date))
        return len(rows)

    monkeypatch.setattr(olx_files_to_bigquery, "load_rows_to_bigquery", _fake_load_rows_to_bigquery)
    monkeypatch.setattr(
        "sys.argv",
        [
            "olx_files_to_bigquery",
            "--mode",
            "both",
            "--project",
            "dw-project",
            "--dataset",
            "bronze",
            "--date",
            "2026-04-04",
            "--input-rent",
            str(rent_path),
            "--input-sale",
            str(sale_path),
        ],
    )

    # When
    olx_files_to_bigquery.main()

    # Then
    assert calls == [
        ("rent", 1, date(2026, 4, 4)),
        ("sale", 1, date(2026, 4, 4)),
    ]


def test_given_missing_mode_file_when_running_sink_cli_then_file_not_found_is_raised(
    monkeypatch,
    tmp_path: Path,
) -> None:
    # Given
    missing_path = tmp_path / "missing.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "olx_files_to_bigquery",
            "--mode",
            "rent",
            "--project",
            "dw-project",
            "--input-rent",
            str(missing_path),
        ],
    )

    # When / Then
    with pytest.raises(FileNotFoundError, match="Input file does not exist"):
        olx_files_to_bigquery.main()


def test_given_non_list_payload_when_running_sink_cli_then_value_error_is_raised(
    monkeypatch,
    tmp_path: Path,
) -> None:
    # Given
    rent_path = tmp_path / "olx_rent_all.json"
    rent_path.write_text(json.dumps({"not": "a-list"}), encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "olx_files_to_bigquery",
            "--mode",
            "rent",
            "--project",
            "dw-project",
            "--input-rent",
            str(rent_path),
        ],
    )

    # When / Then
    with pytest.raises(ValueError, match="Expected list JSON payload"):
        olx_files_to_bigquery.main()


def test_given_sale_mode_when_running_sink_cli_then_only_sale_track_is_loaded(
    monkeypatch,
    tmp_path: Path,
) -> None:
    # Given
    sale_path = tmp_path / "olx_sale_all.json"
    sale_path.write_text(
        json.dumps(
            [
                {
                    "source": "olx",
                    "source_listing_id": "olx-s1",
                    "source_url": "https://www.olx.pl/d/oferta/s1.html",
                }
            ]
        ),
        encoding="utf-8",
    )
    calls: list[str] = []

    def _fake_load_rows_to_bigquery(rows, *, mode, **_kwargs) -> int:
        calls.append(mode)
        return len(rows)

    monkeypatch.setattr(olx_files_to_bigquery, "load_rows_to_bigquery", _fake_load_rows_to_bigquery)
    monkeypatch.setattr(
        "sys.argv",
        [
            "olx_files_to_bigquery",
            "--mode",
            "sale",
            "--project",
            "dw-project",
            "--input-sale",
            str(sale_path),
        ],
    )

    # When
    olx_files_to_bigquery.main()

    # Then
    assert calls == ["sale"]
