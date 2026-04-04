from __future__ import annotations

import argparse
from datetime import date

import httpx
from domus_dweller.sources.olx import ingest_bigquery
from domus_dweller.sources.olx.ingest_bigquery import (
    _build_search_url,
    _fetch_html,
    _prepare_rows_for_load,
)


def test_given_rooms_seed_when_building_search_url_then_rooms_category_slug_is_used() -> None:
    # Given / When
    url = _build_search_url(mode="rent", property_type="pokoje", city="krakow", page=3)

    # Then
    assert url == "https://www.olx.pl/nieruchomosci/stancje-pokoje/krakow/?page=3"


def test_given_sale_mode_when_building_search_url_then_sale_slug_is_used() -> None:
    # Given / When
    url = _build_search_url(mode="sale", property_type="mieszkania", city="krakow", page=2)

    # Then
    assert url == "https://www.olx.pl/nieruchomosci/mieszkania/sprzedaz/krakow/?page=2"


def test_given_enriched_rows_when_preparing_for_load_then_bronze_fields_are_injected() -> None:
    # Given
    rows = [
        {
            "source": "olx",
            "source_listing_id": "olx-1",
            "source_url": "https://www.olx.pl/d/oferta/example-CID3-ID1.html",
            "title": "Oferta",
        }
    ]

    # When
    prepared = _prepare_rows_for_load(rows, mode="rent", snapshot_date=date(2026, 4, 4))

    # Then
    assert len(prepared) == 1
    assert prepared[0]["mode"] == "rent"
    assert prepared[0]["snapshot_date"] == "2026-04-04"
    assert prepared[0]["layer"] == "bronze"


def test_given_http_client_when_fetching_html_then_response_text_is_returned() -> None:
    # Given
    class _FakeResponse:
        text = "<html></html>"

        def raise_for_status(self) -> None:
            return None

    class _FakeClient:
        def get(self, url: str, timeout: float):
            assert url == "https://example.com"
            assert timeout == 7.5
            return _FakeResponse()

    # When
    raw_html = _fetch_html("https://example.com", _FakeClient(), timeout_sec=7.5)

    # Then
    assert raw_html == "<html></html>"


def test_given_search_pages_when_collecting_rows_then_rows_are_deduplicated(monkeypatch) -> None:
    # Given
    calls: list[str] = []

    def _fake_fetch(url: str, client, *, timeout_sec: float) -> str:
        calls.append(url)
        if url.endswith("page=1"):
            return "page-1"
        if url.endswith("page=2"):
            return "page-2"
        raise httpx.HTTPError("boom")

    def _fake_parse(raw_html: str) -> list[dict[str, str]]:
        if raw_html == "page-1":
            return [
                {"source_listing_id": "1", "source_url": "u1", "source": "olx"},
                {"source_listing_id": "2", "source_url": "u2", "source": "olx"},
            ]
        if raw_html == "page-2":
            return [
                {"source_listing_id": "2", "source_url": "u2", "source": "olx"},
                {"source_listing_id": "3", "source_url": "u3", "source": "olx"},
            ]
        return []

    monkeypatch.setattr(ingest_bigquery, "_fetch_html", _fake_fetch)
    monkeypatch.setattr(ingest_bigquery, "parse_search_results", _fake_parse)

    # When
    rows = ingest_bigquery._collect_search_rows(
        mode="rent",
        cities=["krakow"],
        property_types=["mieszkania"],
        pages=3,
        search_timeout_sec=20.0,
    )

    # Then
    assert [row["source_listing_id"] for row in rows] == ["1", "2", "3"]
    assert len(calls) == 3


def test_given_seed_when_page_parse_is_empty_then_collection_stops_for_seed(monkeypatch) -> None:
    # Given
    calls: list[str] = []

    def _fake_fetch(url: str, client, *, timeout_sec: float) -> str:
        calls.append(url)
        return "empty"

    monkeypatch.setattr(ingest_bigquery, "_fetch_html", _fake_fetch)
    monkeypatch.setattr(ingest_bigquery, "parse_search_results", lambda _: [])

    # When
    rows = ingest_bigquery._collect_search_rows(
        mode="sale",
        cities=["krakow"],
        property_types=["domy"],
        pages=5,
        search_timeout_sec=20.0,
    )

    # Then
    assert rows == []
    assert len(calls) == 1


def test_given_mode_pipeline_when_running_then_collect_and_sink_are_wired(
    monkeypatch,
) -> None:
    # Given
    captured: dict = {}

    monkeypatch.setattr(
        ingest_bigquery,
        "_collect_search_rows",
        lambda **kwargs: [
            {
                "source": "olx",
                "source_listing_id": "olx-1",
                "source_url": "https://www.olx.pl/d/oferta/example-CID3-ID1.html",
                "title": "Oferta",
            }
        ],
    )
    def _fake_load(rows, *, mode, project, dataset, snapshot_date):
        captured["rows"] = rows
        captured["mode"] = mode
        captured["project"] = project
        captured["dataset"] = dataset
        captured["snapshot_date"] = snapshot_date
        return len(rows)

    monkeypatch.setattr(ingest_bigquery, "load_rows_to_bigquery", _fake_load)

    # When
    inserted = ingest_bigquery.run_olx_mode_to_bigquery(
        mode="rent",
        project="dw",
        dataset="bronze",
        cities=["krakow"],
        property_types=["mieszkania"],
        pages=1,
        search_timeout_sec=20.0,
        snapshot_date=date(2026, 4, 4),
    )

    # Then
    assert inserted == 1
    assert captured["mode"] == "rent"
    assert captured["project"] == "dw"
    assert captured["dataset"] == "bronze"
    assert captured["snapshot_date"] == date(2026, 4, 4)
    assert captured["rows"][0]["layer"] == "bronze"
    assert captured["rows"][0]["mode"] == "rent"
    assert captured["rows"][0]["snapshot_date"] == "2026-04-04"


def test_given_mode_both_when_running_main_then_both_tracks_are_executed(
    monkeypatch,
    capsys,
) -> None:
    # Given
    calls: list[tuple[str, list[str]]] = []

    monkeypatch.setattr(
        ingest_bigquery,
        "_build_args",
        lambda: argparse.Namespace(
            mode="both",
            project="dw",
            dataset="bronze",
            snapshot_date="2026-04-04",
            pages=2,
            search_timeout_sec=20.0,
            cities=["krakow"],
            property_types_rent=["mieszkania", "pokoje"],
            property_types_sale=["mieszkania"],
        ),
    )

    def _fake_run(**kwargs):
        calls.append((kwargs["mode"], kwargs["property_types"]))
        return 2 if kwargs["mode"] == "rent" else 3

    monkeypatch.setattr(ingest_bigquery, "run_olx_mode_to_bigquery", _fake_run)

    # When
    ingest_bigquery.main()
    out = capsys.readouterr().out

    # Then
    assert calls == [("rent", ["mieszkania", "pokoje"]), ("sale", ["mieszkania"])]
    assert "Total inserted rows: 5." in out
