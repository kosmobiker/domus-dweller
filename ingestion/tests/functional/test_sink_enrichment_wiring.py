"""Test that the file-based sink pipeline calls AI enrichment before MotherDuck insert.

This is the integration test that was missing: it verifies the actual wiring
between read → enrich → sink in olx_files_to_motherduck._sink_mode().
"""
from __future__ import annotations

import json
from pathlib import Path

from domus_dweller.sinks import olx_files_to_motherduck


def test_sink_mode_calls_enrich_with_ai_before_motherduck_insert(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """The file-based sink MUST call enrich_with_ai on parsed rows
    before inserting them into MotherDuck. This test would have caught
    the missing enrichment wiring."""
    # Given: A parsed JSON file with listings
    rent_path = tmp_path / "olx_rent_all.json"
    rent_path.write_text(
        json.dumps(
            [
                {
                    "source": "olx",
                    "source_listing_id": "olx-r1",
                    "source_url": "https://www.olx.pl/d/oferta/r1.html",
                    "title": "Mieszkanie 2 pokoje",
                    "description": "Piękne mieszkanie 45m2, 2 pokoje, umeblowane.",
                    "area_sqm": None,
                    "rooms": None,
                },
                {
                    "source": "olx",
                    "source_listing_id": "olx-r2",
                    "source_url": "https://www.olx.pl/d/oferta/r2.html",
                    "title": "Kawalerka centrum",
                    "description": "Kawalerka 30m2 w centrum.",
                    "area_sqm": None,
                    "rooms": None,
                },
            ]
        ),
        encoding="utf-8",
    )

    # Track call order to verify enrich happens BEFORE sink
    call_order: list[str] = []

    def _fake_enrich(rows, *, mode):
        call_order.append("enrich")
        # Simulate AI filling in data (proves rows are mutated in-place)
        for row in rows:
            if not row.get("area_sqm"):
                row["area_sqm"] = 45.0

    def _fake_load(rows, *, mode, database, snapshot_date=None, ingested_at=None):
        call_order.append("sink")
        # Verify that enrichment already happened on these rows
        for row in rows:
            assert row.get("area_sqm") == 45.0, (
                "enrich_with_ai must be called before load_rows_to_motherduck"
            )
        return len(rows)

    monkeypatch.setattr(olx_files_to_motherduck, "enrich_with_ai", _fake_enrich)
    monkeypatch.setattr(olx_files_to_motherduck, "load_rows_to_motherduck", _fake_load)

    # When: Running the sink pipeline
    monkeypatch.setattr(
        "sys.argv",
        [
            "olx_files_to_motherduck",
            "--mode", "rent",
            "--database", "my_db",
            "--date", "2026-07-26",
            "--input-rent", str(rent_path),
        ],
    )
    olx_files_to_motherduck.main()

    # Then: enrich was called BEFORE sink
    assert call_order == ["enrich", "sink"], (
        f"Expected enrich→sink order, got: {call_order}"
    )


def test_sink_mode_calls_enrich_for_both_rent_and_sale(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """When running in 'both' mode, enrichment must run for each mode separately."""
    rent_path = tmp_path / "olx_rent_all.json"
    sale_path = tmp_path / "olx_sale_all.json"
    for p in (rent_path, sale_path):
        p.write_text(
            json.dumps(
                [
                    {
                        "source": "olx",
                        "source_listing_id": "olx-1",
                        "source_url": "https://www.olx.pl/d/oferta/1.html",
                        "description": "Test listing",
                    }
                ]
            ),
            encoding="utf-8",
        )

    enrich_calls: list[str] = []

    def _fake_enrich(rows, *, mode):
        enrich_calls.append(mode)

    def _fake_load(rows, *, mode, **kwargs):
        return len(rows)

    monkeypatch.setattr(olx_files_to_motherduck, "enrich_with_ai", _fake_enrich)
    monkeypatch.setattr(olx_files_to_motherduck, "load_rows_to_motherduck", _fake_load)
    monkeypatch.setattr(
        "sys.argv",
        [
            "olx_files_to_motherduck",
            "--mode", "both",
            "--database", "my_db",
            "--date", "2026-07-26",
            "--input-rent", str(rent_path),
            "--input-sale", str(sale_path),
        ],
    )

    olx_files_to_motherduck.main()

    assert enrich_calls == ["rent", "sale"]
