import json
from pathlib import Path

from domus_dweller import parse


def test_given_olx_fixture_when_running_cli_then_json_is_printed(
    monkeypatch,
    capsys,
) -> None:
    # Given
    fixture = Path("ingestion/tests/fixtures/olx/search_results.html")
    monkeypatch.setattr(
        "sys.argv",
        [
            "parse",
            "--source",
            "olx",
            "--input",
            str(fixture),
        ],
    )

    # When
    parse.main()

    # Then
    stdout = capsys.readouterr().out
    parsed = json.loads(stdout)
    assert parsed[0]["source"] == "olx"
    assert parsed[0]["source_listing_id"] == "olx-98765"


def test_given_output_path_when_running_cli_then_file_is_written(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    # Given
    fixture = Path("ingestion/tests/fixtures/olx/search_results.html")
    output_path = tmp_path / "parsed" / "olx.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "parse",
            "--source",
            "olx",
            "--input",
            str(fixture),
            "--output",
            str(output_path),
        ],
    )

    # When
    parse.main()

    # Then
    stdout = capsys.readouterr().out
    assert "Wrote 1 parsed listings" in stdout
    parsed = json.loads(output_path.read_text(encoding="utf-8"))
    assert parsed[0]["source"] == "olx"
    assert parsed[0]["seller_segment"] == "private"
