import json
from pathlib import Path

import httpx
from domus_dweller.sources.olx import enrich
from domus_dweller.sources.olx.parser import parse_detail_page


def test_given_olx_detail_html_when_parsing_then_extra_listing_fields_are_extracted() -> None:
    # Given
    raw_html = """
    <html><body>
      <script type="application/ld+json">
        {
          "@type": "Product",
          "description": "Szczegółowy opis mieszkania."
        }
      </script>
      <p data-nx-name="P3">Prywatne</p>
      <p data-nx-name="P3">Powierzchnia: 25,32 m²</p>
      <p data-nx-name="P3">Powierzchnia działki: 410 m²</p>
      <p data-nx-name="P3">Liczba pokoi: Kawalerka</p>
      <p data-nx-name="P3">Poziom: 2</p>
      <p data-nx-name="P3">Liczba pięter: Jednopiętrowy</p>
      <p data-nx-name="P3">Czynsz (dodatkowo): 600 zł</p>
      <p data-nx-name="P3">Rodzaj zabudowy: Blok</p>
      <p data-nx-name="P3">Rynek: Wtórny</p>
      <p data-nx-name="P3">Umeblowane: Nie</p>
      <a data-testid="user-profile-link" href="/oferty/uzytkownik/abc123/"></a>
      <h4 data-testid="user-profile-user-name">Jan Kowalski</h4>
    </body></html>
    """

    # When
    details = parse_detail_page(raw_html)

    # Then
    assert details["description"] == "Szczegółowy opis mieszkania."
    assert details["area_sqm"] == 25.32
    assert details["rooms"] == 1.0
    assert details["floor"] == "2"
    assert details["rent_additional"] == 600.0
    assert details["rent_additional_currency"] == "PLN"
    assert details["building_type"] == "Blok"
    assert details["market_type"] == "Wtórny"
    assert details["furnished"] is False
    assert details["building_floors"] == 1
    assert details["land_area_sqm"] == 410.0
    assert details["seller_segment"] == "private"
    assert details["seller_type"] == "private"
    assert details["seller_name"] == "Jan Kowalski"
    assert details["seller_profile_url"] == "https://www.olx.pl/oferty/uzytkownik/abc123/"


def test_given_snapshot_and_detail_pages_when_running_enrich_cli_then_listings_are_enriched(
    monkeypatch,
    tmp_path: Path,
) -> None:
    # Given
    input_path = tmp_path / "olx_all.json"
    output_path = tmp_path / "olx_all_enriched.json"
    input_path.write_text(
        json.dumps(
            [
                {
                    "source": "olx",
                    "source_listing_id": "olx-1",
                    "source_url": "https://www.olx.pl/d/oferta/example-CID3-ID1.html",
                    "title": "Oferta",
                    "seller_segment": "unknown",
                }
            ]
        ),
        encoding="utf-8",
    )

    raw_detail_html = """
    <html><body>
      <p data-nx-name="P3">Firma</p>
      <p data-nx-name="P3">Powierzchnia: 52 m²</p>
      <p data-nx-name="P3">Liczba pokoi: 2</p>
      <p data-nx-name="P3">Rodzaj zabudowy: Blok</p>
      <p data-nx-name="P3">Umeblowane: Tak</p>
    </body></html>
    """

    def _fake_fetch_html(url: str, *_args, **_kwargs) -> str:
        assert url == "https://www.olx.pl/d/oferta/example-CID3-ID1.html"
        return raw_detail_html

    monkeypatch.setattr(enrich, "_fetch_html", _fake_fetch_html)
    monkeypatch.setattr(
        "sys.argv",
        [
            "enrich_olx",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--mode",
            "rent",
            "--pause-ms",
            "0",
        ],
    )

    # When
    enrich.main()

    # Then
    enriched = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(enriched) == 1
    assert enriched[0]["mode"] == "rent"
    assert enriched[0]["area_sqm"] == 52.0
    assert enriched[0]["rooms"] == 2.0
    assert enriched[0]["building_type"] == "Blok"
    assert enriched[0]["furnished"] is True
    assert enriched[0]["detail_params_common"]["powierzchnia"] == "52 m²"
    assert enriched[0]["detail_params_common"]["rodzaj zabudowy"] == "Blok"
    assert enriched[0]["detail_params_rent"] == {}
    assert enriched[0]["detail_params_sale"] == {}
    assert enriched[0]["seller_segment"] == "professional"


def test_given_room_listing_without_liczba_pokoi_when_parsing_then_rooms_fall_back_to_one() -> None:
    # Given
    raw_html = """
    <html><body>
      <script type="application/ld+json">
        {
          "@type": "Product",
          "name": "Pokój do wynajęcia",
          "description": "Spokojna okolica."
        }
      </script>
      <p data-nx-name="P3">Rodzaj pokoju: Dwuosobowy</p>
      <p data-nx-name="P3">.css-1p85e15{display:block;} Ostatnio online wczoraj o 13:06</p>
    </body></html>
    """

    # When
    details = parse_detail_page(raw_html)

    # Then
    assert details["rooms"] == 1.0
    assert ".css-1p85e15{display" not in details["detail_params"]


def test_given_jsonld_text_when_parsing_then_rooms_floor_and_rent_are_inferred() -> None:
    # Given
    raw_html = """
    <html><body>
      <script type="application/ld+json">
        {
          "@type": "Product",
          "name": "Nowoczesny dom 5 pokoi",
          "description": "Mieszkanie na 2 piętrze. Czynsz administracyjny: 850 zł."
        }
      </script>
      <p data-nx-name="P3">Powierzchnia: 120 m²</p>
    </body></html>
    """

    # When
    details = parse_detail_page(raw_html)

    # Then
    assert details["rooms"] == 5.0
    assert details["floor"] == "2"
    assert details["rent_additional"] == 850.0
    assert details["rent_additional_currency"] == "PLN"


def test_given_only_main_rent_phrase_when_parsing_then_additional_rent_stays_null() -> None:
    # Given
    raw_html = """
    <html><body>
      <script type="application/ld+json">
        {
          "@type": "Product",
          "name": "Mieszkanie 2 pokoje",
          "description": "Czynsz najmu: 3200 zł miesięcznie."
        }
      </script>
    </body></html>
    """

    # When
    details = parse_detail_page(raw_html)

    # Then
    assert details["rent_additional"] is None
    assert details["rent_additional_currency"] is None


def test_given_rent_mode_when_enriching_then_mode_specific_params_are_kept_in_rent_track(
    monkeypatch,
    tmp_path: Path,
) -> None:
    # Given
    input_path = tmp_path / "olx_rent_all.json"
    output_path = tmp_path / "olx_rent_all_enriched.json"
    input_path.write_text(
        json.dumps(
            [
                {
                    "source": "olx",
                    "source_listing_id": "olx-2",
                    "source_url": "https://www.olx.pl/nieruchomosci/mieszkania/wynajem/krakow/d/oferta/example-CID3-ID2.html",
                    "title": "Oferta",
                    "seller_segment": "unknown",
                }
            ]
        ),
        encoding="utf-8",
    )

    raw_detail_html = """
    <html><body>
      <p data-nx-name="P3">Powierzchnia: 41 m²</p>
      <p data-nx-name="P3">Czynsz (dodatkowo): 700 zł</p>
      <p data-nx-name="P3">Preferowani: Studenci</p>
    </body></html>
    """

    def _fake_fetch_html(url: str, *_args, **_kwargs) -> str:
        assert "ID2" in url
        return raw_detail_html

    monkeypatch.setattr(enrich, "_fetch_html", _fake_fetch_html)
    monkeypatch.setattr(
        "sys.argv",
        [
            "enrich_olx",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--mode",
            "rent",
            "--pause-ms",
            "0",
        ],
    )

    # When
    enrich.main()

    # Then
    enriched = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(enriched) == 1
    assert enriched[0]["mode"] == "rent"
    assert enriched[0]["detail_params_common"]["powierzchnia"] == "41 m²"
    assert enriched[0]["detail_params_rent"]["czynsz (dodatkowo)"] == "700 zł"
    assert enriched[0]["detail_params_rent"]["preferowani"] == "Studenci"
    assert enriched[0]["detail_params_sale"] == {}


def test_given_detail_403_when_enriching_then_listing_is_kept_and_processing_continues(
    monkeypatch,
) -> None:
    # Given
    first = {
        "source": "olx",
        "source_listing_id": "olx-403",
        "source_url": "https://www.olx.pl/d/oferta/blocked-CID3-ID403.html",
        "title": "Blocked",
        "seller_segment": "unknown",
    }
    second = {
        "source": "olx",
        "source_listing_id": "olx-ok",
        "source_url": "https://www.olx.pl/d/oferta/ok-CID3-ID200.html",
        "title": "OK",
        "seller_segment": "unknown",
    }

    ok_html = """
    <html><body>
      <p data-nx-name="P3">Powierzchnia: 37 m²</p>
      <p data-nx-name="P3">Liczba pokoi: 2</p>
    </body></html>
    """

    def _fake_fetch_html(url: str, *_args, **_kwargs) -> str:
        if "ID403" in url:
            request = httpx.Request("GET", url)
            response = httpx.Response(status_code=403, request=request)
            raise httpx.HTTPStatusError("forbidden", request=request, response=response)
        return ok_html

    monkeypatch.setattr(enrich, "_fetch_html", _fake_fetch_html)

    # When
    enriched = enrich.enrich_listings(
        [first, second],
        save_html_dir=None,
        pause_ms=0,
        timeout_sec=5.0,
        default_mode="rent",
    )

    # Then
    assert len(enriched) == 2
    assert enriched[0]["source_listing_id"] == "olx-403"
    assert "area_sqm" not in enriched[0]
    assert enriched[1]["source_listing_id"] == "olx-ok"
    assert enriched[1]["area_sqm"] == 37.0
    assert enriched[1]["rooms"] == 2.0


def test_given_detail_403_in_cli_when_running_then_job_does_not_fail_and_output_is_written(
    monkeypatch,
    tmp_path: Path,
) -> None:
    # Given
    input_path = tmp_path / "olx_all.json"
    output_path = tmp_path / "olx_all_enriched.json"
    input_path.write_text(
        json.dumps(
            [
                {
                    "source": "olx",
                    "source_listing_id": "olx-403",
                    "source_url": "https://www.olx.pl/d/oferta/blocked-CID3-ID403.html",
                    "title": "Blocked",
                },
                {
                    "source": "olx",
                    "source_listing_id": "olx-ok",
                    "source_url": "https://www.olx.pl/d/oferta/ok-CID3-ID200.html",
                    "title": "OK",
                },
            ]
        ),
        encoding="utf-8",
    )

    ok_html = """
    <html><body>
      <p data-nx-name="P3">Powierzchnia: 41 m²</p>
      <p data-nx-name="P3">Liczba pokoi: 2</p>
    </body></html>
    """

    def _fake_fetch_html(url: str, *_args, **_kwargs) -> str:
        if "ID403" in url:
            request = httpx.Request("GET", url)
            response = httpx.Response(status_code=403, request=request)
            raise httpx.HTTPStatusError("forbidden", request=request, response=response)
        return ok_html

    monkeypatch.setattr(enrich, "_fetch_html", _fake_fetch_html)
    monkeypatch.setattr(
        "sys.argv",
        [
            "enrich_olx",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--pause-ms",
            "0",
            "--mode",
            "rent",
        ],
    )

    # When
    enrich.main()

    # Then
    enriched = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(enriched) == 2
    assert enriched[0]["source_listing_id"] == "olx-403"
    assert enriched[1]["source_listing_id"] == "olx-ok"
    assert enriched[1]["area_sqm"] == 41.0


def test_given_consecutive_403_wall_when_enriching_then_fail_fast_keeps_tail_rows_unchanged(
    monkeypatch,
) -> None:
    # Given
    listings = [
        {"source_listing_id": "id1", "source_url": "https://www.olx.pl/d/oferta/1.html"},
        {"source_listing_id": "id2", "source_url": "https://www.olx.pl/d/oferta/2.html"},
        {"source_listing_id": "id3", "source_url": "https://www.olx.pl/d/oferta/3.html"},
        {"source_listing_id": "id4", "source_url": "https://www.olx.pl/d/oferta/4.html"},
    ]
    calls: list[str] = []

    def _fake_fetch_html(url: str, *_args, **_kwargs) -> str:
        calls.append(url)
        request = httpx.Request("GET", url)
        response = httpx.Response(status_code=403, request=request)
        raise httpx.HTTPStatusError("forbidden", request=request, response=response)

    monkeypatch.setattr(enrich, "_fetch_html", _fake_fetch_html)

    # When
    enriched = enrich.enrich_listings(
        listings,
        save_html_dir=None,
        pause_ms=0,
        timeout_sec=5.0,
        default_mode="rent",
        max_consecutive_403=2,
    )

    # Then
    assert len(calls) == 2
    assert len(enriched) == 4
    assert [row["source_listing_id"] for row in enriched] == ["id1", "id2", "id3", "id4"]


def test_given_save_html_dir_and_empty_url_and_sale_mode_when_enriching(
    monkeypatch, tmp_path: Path
) -> None:
    # Given
    listings = [
        {"source_listing_id": "id1", "source_url": ""},
        {
            "source_listing_id": "id2",
            "source_url": "https://www.olx.pl/d/oferta/mieszkania/sprzedaz/2.html",
        },
        {"source_listing_id": "", "source_url": "https://www.olx.pl/d/oferta/3.html"},
        {
            "source_listing_id": "id4",
            "source_url": "https://www.olx.pl/d/oferta/4.html",
            "mode": "rent",
        },
    ]

    def _fake_fetch_html(url: str, *_args, **_kwargs) -> str:
        if "3.html" in url:
            request = httpx.Request("GET", url)
            response = httpx.Response(status_code=404, request=request)
            raise httpx.HTTPStatusError("not found", request=request, response=response)
        return "<html><body><p data-nx-name='P3'>Powierzchnia: 10 m²</p></body></html>"

    monkeypatch.setattr(enrich, "_fetch_html", _fake_fetch_html)

    # When
    enriched = enrich.enrich_listings(
        listings,
        save_html_dir=tmp_path,
        pause_ms=0,
        timeout_sec=5.0,
        default_mode="unknown_mode",
    )

    # Then
    assert len(enriched) == 4
    assert enriched[0]["source_url"] == ""
    assert enriched[1]["mode"] == "sale"
    assert enriched[1]["area_sqm"] == 10.0
    assert enriched[2]["source_listing_id"] == ""
    assert enriched[3]["mode"] == "rent"

    saved_files = list(tmp_path.glob("*.html"))
    assert len(saved_files) == 2


def test_given_only_new_when_listing_already_known_then_fetch_is_skipped(monkeypatch) -> None:
    # Given
    listings = [
        {
            "source_listing_id": "known-1",
            "source_url": "https://www.olx.pl/d/oferta/known-1.html",
            "title": "Known flat",
        },
        {
            "source_listing_id": "new-2",
            "source_url": "https://www.olx.pl/d/oferta/new-2.html",
            "title": "Brand new flat",
        },
    ]

    fetched_urls = []

    def _fake_fetch_html(url: str, *_args, **_kwargs) -> str:
        fetched_urls.append(url)
        return "<html><body><p data-nx-name='P3'>Powierzchnia: 65 m²</p></body></html>"

    monkeypatch.setattr(enrich, "_fetch_html", _fake_fetch_html)

    # When
    enriched = enrich.enrich_listings(
        listings,
        save_html_dir=None,
        pause_ms=0,
        timeout_sec=5.0,
        default_mode="rent",
        existing_ids={"known-1"},
    )

    # Then
    assert len(enriched) == 2
    assert fetched_urls == ["https://www.olx.pl/d/oferta/new-2.html"]
    # known-1 was skipped and kept unchanged
    assert "area_sqm" not in enriched[0]
    # new-2 was fetched and enriched
    assert enriched[1]["area_sqm"] == 65.0


def test_fetch_existing_listing_ids_from_duckdb(tmp_path: Path) -> None:
    import duckdb

    db_path = str(tmp_path / "test.duckdb")
    con = duckdb.connect(db_path)
    con.execute("CREATE SCHEMA silver;")
    con.execute("CREATE TABLE silver.listing_identity (source VARCHAR, source_listing_id VARCHAR);")
    con.execute("INSERT INTO silver.listing_identity VALUES ('olx', 'id-100'), ('olx', 'id-200');")
    con.execute("CREATE SCHEMA bronze;")
    con.execute("CREATE TABLE bronze.rent_bronze (source VARCHAR, source_listing_id VARCHAR);")
    con.execute("INSERT INTO bronze.rent_bronze VALUES ('olx', 'id-300');")
    con.close()

    ids = enrich.fetch_existing_listing_ids(database=db_path)
    assert ids == {"id-100", "id-200", "id-300"}

    # Test failure fallback
    fallback_ids = enrich.fetch_existing_listing_ids(database="/non/existent/path.duckdb")
    assert fallback_ids == set()


def test_enrich_cli_with_only_new_flag(monkeypatch, tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    input_path.write_text(
        json.dumps(
            [
                {"source_listing_id": "old-1", "source_url": "https://example.com/1"},
                {"source_listing_id": "new-2", "source_url": "https://example.com/2"},
            ]
        ),
        encoding="utf-8",
    )

    def _fake_fetch_existing(*args, **kwargs) -> set[str]:
        return {"old-1"}

    def _fake_fetch(url: str, *_args, **_kwargs) -> str:
        return "<html><body><p data-nx-name='P3'>Powierzchnia: 50 m²</p></body></html>"

    monkeypatch.setattr(enrich, "fetch_existing_listing_ids", _fake_fetch_existing)
    monkeypatch.setattr(enrich, "_fetch_html", _fake_fetch)
    monkeypatch.setattr(
        "sys.argv",
        [
            "enrich_olx",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--only-new",
            "--pause-ms",
            "0",
        ],
    )

    enrich.main()

    res = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(res) == 2
    assert "area_sqm" not in res[0]
    assert res[1]["area_sqm"] == 50.0
