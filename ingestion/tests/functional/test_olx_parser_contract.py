from collections.abc import Callable
from importlib import import_module
from pathlib import Path

import pytest


def _fixture_path(source: str, fixture_name: str) -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures" / source / fixture_name


def _load_search_results_parser(source: str) -> Callable[[str], list[dict]]:
    module_name = f"domus_dweller.sources.{source}.parser"
    function_name = "parse_search_results"

    try:
        module = import_module(module_name)
    except ModuleNotFoundError as exc:
        pytest.fail(
            "Given source fixtures for OLX, when importing parser modules, "
            f"then `{module_name}` must exist. Missing module: {exc.name}"
        )

    parser = getattr(module, function_name, None)
    if parser is None:
        pytest.fail(
            "Given source fixtures for OLX, when loading parser entrypoints, "
            f"then `{module_name}.{function_name}` must exist."
        )

    return parser


@pytest.mark.parametrize(
    ("source", "fixture_name"),
    [
        ("olx", "search_results.html"),
    ],
)
def test_given_public_search_fixtures_when_parsing_then_common_contract_is_present(
    source: str,
    fixture_name: str,
) -> None:
    # Given
    raw_payload = _fixture_path(source, fixture_name).read_text(encoding="utf-8")
    parse_search_results = _load_search_results_parser(source)

    # When
    listings = parse_search_results(raw_payload)

    # Then
    assert listings, f"{source} parser returned no listings for fixture {fixture_name}."
    for listing in listings:
        assert listing["source"] == source
        assert listing["source_listing_id"]
        assert listing["source_url"]
        assert listing["seller_segment"] in {"private", "professional", "unknown"}
