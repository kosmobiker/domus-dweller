import json
from pathlib import Path

from domus_dweller import merge_pages


def test_given_paginated_json_files_when_merging_then_unique_listing_ids_are_kept(
    monkeypatch,
    tmp_path: Path,
) -> None:
    # Given
    page_1 = tmp_path / "olx_page_1.json"
    page_2 = tmp_path / "olx_page_2.json"
    output = tmp_path / "olx_all.json"
    page_1.write_text(
        json.dumps(
            [
                {"source_listing_id": "olx-1", "title": "A"},
                {"source_listing_id": "olx-2", "title": "B"},
            ]
        ),
        encoding="utf-8",
    )
    page_2.write_text(
        json.dumps(
            [
                {"source_listing_id": "olx-2", "title": "B duplicate"},
                {"source_listing_id": "olx-3", "title": "C"},
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "merge_pages",
            "--pattern",
            str(tmp_path / "olx_page_*.json"),
            "--output",
            str(output),
        ],
    )

    # When
    merge_pages.main()

    # Then
    merged = json.loads(output.read_text(encoding="utf-8"))
    assert [row["source_listing_id"] for row in merged] == ["olx-1", "olx-2", "olx-3"]
