import json

from domus_dweller.sources.olx.parser import (
    _extract_area_sqm,
    _extract_building_floors,
    _extract_floor_from_text,
    _extract_price_fields,
    _extract_price_per_sqm,
    _extract_rooms,
    _extract_rooms_from_text,
    _extract_yes_no,
    _seller_segment_from_text,
    parse_search_results,
)


def test_given_olx_seller_labels_when_parsing_then_segments_are_normalized() -> None:
    # Given
    raw_html = """
    <section>
      <article data-cy="l-card" data-id="olx-1">
        <a href="https://www.olx.pl/d/oferta/1/">Oferta 1</a>
        <p>Firma</p>
      </article>
      <article data-cy="l-card" data-id="olx-2">
        <a href="https://www.olx.pl/d/oferta/2/">Oferta 2</a>
        <p>Osoba prywatna</p>
      </article>
      <article data-cy="l-card" data-id="olx-3">
        <a href="https://www.olx.pl/d/oferta/3/">Oferta 3</a>
        <p>Sprzedawca</p>
      </article>
    </section>
    """

    # When
    listings = parse_search_results(raw_html)

    # Then
    segments = [listing["seller_segment"] for listing in listings]
    assert segments == ["professional", "private", "unknown"]


def test_given_duplicate_cards_when_parsing_then_results_are_deduplicated() -> None:
    # Given
    raw_html = """
    <section>
      <article data-cy="l-card" data-id="olx-1">
        <a href="https://www.olx.pl/d/oferta/1/">Oferta 1</a>
        <p>Firma</p>
      </article>
      <article data-cy="l-card" data-id="olx-1">
        <a href="https://www.olx.pl/d/oferta/1/">Oferta 1 duplicate</a>
        <p>Firma</p>
      </article>
      <article data-cy="l-card" data-id="olx-2">
        <a href="https://www.olx.pl/d/oferta/2/">Oferta 2</a>
        <p>Osoba prywatna</p>
      </article>
    </section>
    """

    # When
    listings = parse_search_results(raw_html)

    # Then
    assert [listing["source_listing_id"] for listing in listings] == ["olx-1", "olx-2"]


def test_given_olx_jsonld_offers_when_parsing_then_listings_are_extracted() -> None:
    # Given
    raw_html = """
    <html><body>
      <script type="application/ld+json">
        {
          "@type": "WebPage",
          "contentLocation": {"@type": "City", "name": "Kraków"}
        }
      </script>
      <script type="application/ld+json">
        {
          "@type": "Product",
          "offers": {
            "@type": "AggregateOffer",
            "offers": [
              {
                "@type": "Offer",
                "name": "Kawalerka prywatna",
                "url": "https://www.olx.pl/d/oferta/kawalerka-CID3-ID19ShY0.html",
                "price": 2000,
                "priceCurrency": "PLN",
                "priceValidUntil": "2026-04-19T17:28:39+02:00",
                "areaServed": {"@type": "AdministrativeArea", "name": "Stare Miasto"},
                "image": ["https://cdn.example/1.jpg", "https://cdn.example/2.jpg"]
              },
              {
                "@type": "Offer",
                "name": "Mieszkanie od firmy",
                "url": "https://www.olx.pl/d/oferta/mieszkanie-CID3-ID19SDJ0.html",
                "price": 2500,
                "priceCurrency": "PLN"
              }
            ]
          }
        }
      </script>
    </body></html>
    """

    # When
    listings = parse_search_results(raw_html)

    # Then
    assert [listing["source_listing_id"] for listing in listings] == ["olx-19ShY0", "olx-19SDJ0"]
    assert [listing["source_url"] for listing in listings] == [
        "https://www.olx.pl/d/oferta/kawalerka-CID3-ID19ShY0.html",
        "https://www.olx.pl/d/oferta/mieszkanie-CID3-ID19SDJ0.html",
    ]
    assert [listing["title"] for listing in listings] == [
        "Kawalerka prywatna",
        "Mieszkanie od firmy",
    ]
    assert listings[0]["price_total"] == 2000.0
    assert listings[0]["currency"] == "PLN"
    assert listings[0]["district"] == "Stare Miasto"
    assert listings[0]["city"] == "Kraków"
    assert listings[0]["municipality"] == "Kraków"
    assert listings[0]["location_approx"] == "Kraków, Stare Miasto"
    assert listings[0]["images"] == ["https://cdn.example/1.jpg", "https://cdn.example/2.jpg"]
    assert listings[0]["price_valid_until"] == "2026-04-19T17:28:39+02:00"


def test_given_olx_cards_and_jsonld_when_parsing_then_rows_are_enriched_by_id() -> None:
    # Given
    raw_html = """
    <html><body>
      <section>
        <article data-cy="l-card" data-id="olx-19ShY0">
          <a href="https://www.olx.pl/d/oferta/mieszkanie-kawalerka-CID3-ID19ShY0.html">
            Placeholder title
          </a>
          <p>Firma</p>
        </article>
      </section>
      <script type="application/ld+json">
        {
          "@type": "WebPage",
          "contentLocation": {"@type": "City", "name": "Kraków"}
        }
      </script>
      <script type="application/ld+json">
        {
          "@type": "Product",
          "offers": {
            "@type": "AggregateOffer",
            "offers": [
              {
                "@type": "Offer",
                "name": "Final title",
                "url": "https://www.olx.pl/d/oferta/mieszkanie-kawalerka-CID3-ID19ShY0.html",
                "price": 2100,
                "priceCurrency": "PLN",
                "priceValidUntil": "2026-04-20T10:00:00+02:00",
                "areaServed": {"name": "Stare Miasto"},
                "image": ["https://cdn.example/1.jpg"]
              }
            ]
          }
        }
      </script>
    </body></html>
    """

    # When
    listings = parse_search_results(raw_html)

    # Then
    assert len(listings) == 1
    assert listings[0]["title"] == "Final title"
    assert listings[0]["price_total"] == 2100.0
    assert listings[0]["district"] == "Stare Miasto"
    assert listings[0]["location_approx"] == "Kraków, Stare Miasto"
    assert listings[0]["images"] == ["https://cdn.example/1.jpg"]


def test_extractor_edge_cases() -> None:
    assert _extract_area_sqm(None) is None
    assert _extract_area_sqm("") is None
    assert _extract_area_sqm("invalid text") is None

    assert _extract_rooms(None) is None
    assert _extract_rooms("") is None

    assert _extract_rooms_from_text(None) is None
    assert _extract_rooms_from_text("") is None
    assert _extract_rooms_from_text("no rooms here") is None

    assert _extract_floor_from_text(None) is None
    assert _extract_floor_from_text("") is None
    assert _extract_floor_from_text("no floor") is None

    assert _extract_yes_no(None) is None
    assert _extract_yes_no("") is None
    assert _extract_yes_no("unknown") is None
    assert _extract_yes_no("tak") is True
    assert _extract_yes_no("nie") is False

    assert _extract_building_floors(None) is None
    assert _extract_building_floors("") is None
    assert _extract_building_floors("dwupiętrowy") == 2
    assert _extract_building_floors("jednopiętrowy") == 1
    assert _extract_building_floors("parterowy z użytkowym poddaszem") == 1
    assert _extract_building_floors("parterowy") == 0
    assert _extract_building_floors("unknown") is None

    assert _extract_price_per_sqm(None) is None
    assert _extract_price_per_sqm("") is None
    assert _extract_price_per_sqm("no price") is None

    assert _seller_segment_from_text("") == "unknown"


def test_given_olx_prerendered_state_when_parsing_then_rows_are_enriched() -> None:
    state_dict = {
        "listing": {
            "listing": {
                "ads": [
                    {
                        "id": "19ShY0",
                        "title": "Title from state",
                        "description": "Desc from state<br />newline",
                        "params": [
                            {"name": "Powierzchnia", "value": "50 m²"},
                            {"name": "Liczba pokoi", "value": "2 pokoje"},
                            {"name": "Poziom", "value": "3"},
                            {"name": "Cena za m²", "value": "100 zł/m²"},
                        ],
                    }
                ]
            }
        }
    }
    # Escape quotes for the JS string literal
    state_json = json.dumps(state_dict).replace('"', '\\"')
    raw_html = f'''
    <html><body>
      <section>
        <article data-cy="l-card" data-id="olx-19ShY0">
          <a href="https://www.olx.pl/d/oferta/mieszkanie-kawalerka-CID3-ID19ShY0.html"></a>
          <p>Firma</p>
        </article>
      </section>
      <script>
        window.__PRERENDERED_STATE__ = "{state_json}";
      </script>
    </body></html>
    '''

    listings = parse_search_results(raw_html)
    assert len(listings) == 1
    assert listings[0]["title"] == "Title from state"
    assert listings[0]["description"] == "Desc from state\nnewline"


def test_given_bad_jsonld_when_parsing_then_ignores() -> None:
    raw_html = """
    <html><body>
        <script type='application/ld+json'></script>
        <script type='application/ld+json'>{bad json}</script>
        <script type='application/ld+json'>{"offers": "not a dict"}</script>
        <script type='application/ld+json'>{"offers": {"offers": "not a list"}}</script>
        <script type='application/ld+json'>{"offers": {"offers": ["not a dict"]}}</script>
    </body></html>
    """
    listings = parse_search_results(raw_html)
    assert len(listings) == 0


def test_given_modern_div_cards_and_numeric_id_state_when_parsing_then_enriched() -> None:
    state_dict = {
        "listing": {
            "listing": {
                "ads": [
                    {
                        "id": 1082650130,
                        "url": "https://www.olx.pl/d/oferta/mieszkanie-krakow-CID3-ID1bgGKS.html",
                        "title": "Modern Title",
                        "description": "Modern Description",
                        "isBusiness": False,
                        "params": [
                            {"name": "Powierzchnia", "value": "45 m²"},
                            {"name": "Liczba pokoi", "value": "2 pokoje"},
                            {"name": "Poziom", "value": "2"},
                        ],
                    }
                ]
            }
        }
    }
    state_json = json.dumps(state_dict).replace('"', '\\"')
    raw_html = f"""
    <html><body>
      <div data-cy="l-card" id="1082650130">
        <div data-testid="ad-card-title">
          <a data-testid="card-title-link" href="/d/oferta/mieszkanie-krakow-CID3-ID1bgGKS.html">
            <style>.css-fake {{ color: red; }}</style>
            <h4>Modern Title</h4>
          </a>
        </div>
        <p data-testid="ad-price">2 500 zł</p>
      </div>
      <script>
        window.__PRERENDERED_STATE__ = "{state_json}";
      </script>
    </body></html>
    """

    listings = parse_search_results(raw_html)
    assert len(listings) == 1
    assert listings[0]["source_listing_id"] == "olx-1bgGKS"
    assert listings[0]["title"] == "Modern Title"
    assert listings[0]["price_total"] == 2500.0
    assert listings[0]["area_sqm"] == 45.0
    assert listings[0]["rooms"] == 2.0
    assert listings[0]["seller_segment"] == "private"
    assert "source_numeric_id" not in listings[0]


def test_extract_price_fields_with_decimals_and_unit_prices() -> None:
    # Standard formats
    assert _extract_price_fields("639 000 zł") == (639000.0, "PLN")
    assert _extract_price_fields("620 000 zl") == (620000.0, "PLN")
    assert _extract_price_fields("1 099 000 zł") == (1099000.0, "PLN")
    assert _extract_price_fields("500 PLN") == (500.0, "PLN")

    # In sale ads, price per sqm often precedes total price
    # Crucially, 13040.82 zł/m² must NOT split at the decimal into 82.0 zł
    assert _extract_price_fields("49 m² - 13040.82 zł/m² 639 000 zł") == (639000.0, "PLN")
    assert _extract_price_fields("73,50 m² - 14952.38 zł/m² 1 099 000 zł") == (1099000.0, "PLN")
    assert _extract_price_fields("54 m² - 12500 zł/m² 675 000 zł") == (675000.0, "PLN")

    # Pure unit prices without total price must not be treated as total price
    assert _extract_price_fields("13040.82 zł/m²") == (None, None)
    assert _extract_price_fields("12500 zł/m2") == (None, None)
    assert _extract_price_fields("15000 zł za m²") == (None, None)


def test_extract_price_per_sqm_distinguishes_unit_and_total_price() -> None:
    # Must NOT extract total price as price per sqm
    assert _extract_price_per_sqm("639 000 zł") is None
    assert _extract_price_per_sqm("1 099 000 zł do negocjacji") is None

    # Must extract unit price when combined with total price
    assert _extract_price_per_sqm("49 m² - 13040.82 zł/m² 639 000 zł") == 13040.82
    assert _extract_price_per_sqm("639 000 zł 49 m² - 13040.82 zł/m²") == 13040.82
    assert _extract_price_per_sqm("54 m² - 12500 zł/m² 675 000 zł") == 12500.0

    # Explicit unit price strings from params
    assert _extract_price_per_sqm("16966.02 zł/m²") == 16966.02
    assert _extract_price_per_sqm("100 zł/m²") == 100.0
    assert _extract_price_per_sqm("12 500 zł/m²") == 12500.0
    assert _extract_price_per_sqm("16966.02") == 16966.02


def test_given_sale_card_with_price_per_sqm_when_parsing_then_extracted_accurately() -> None:
    raw_html = """
    <html><body>
      <div data-cy="l-card" id="1064509351">
        <a data-testid="card-title-link" href="/d/oferta/krakow-bronowice-CID3-ID1a2zwF.html">
          <h4>Kraków Bronowice sprzedaż mieszkania</h4>
        </a>
        <p data-testid="ad-price">639 000 zł</p>
        <span class="css-h59g4b">49 m² - 13040.82 zł/m²</span>
      </div>
    </body></html>
    """
    listings = parse_search_results(raw_html)
    assert len(listings) == 1
    assert listings[0]["price_total"] == 639000.0
    assert listings[0]["currency"] == "PLN"
    assert listings[0]["price_per_sqm_source"] == 13040.82
    assert listings[0]["area_sqm"] == 49.0


def test_given_prerendered_state_with_price_when_parsing_then_enriched() -> None:
    state_dict = {
        "listing": {
            "listing": {
                "ads": [
                    {
                        "id": 1064310626,
                        "url": "https://www.olx.pl/d/oferta/okazja-CID3-ID4AKsb.html",
                        "title": "OKAZJA gotowe",
                        "price": {
                            "regularPrice": {
                                "value": 699000,
                                "currencyCode": "PLN",
                            },
                            "displayValue": "699 000 zł",
                        },
                        "params": [
                            {"name": "Powierzchnia", "value": "41.2 m²"},
                            {"name": "Cena za m²", "value": "16966.02 zł/m²"},
                        ],
                    }
                ]
            }
        }
    }
    state_json = json.dumps(state_dict).replace('"', '\\"')
    raw_html = f"""
    <html><body>
      <div data-cy="l-card" id="1064310626">
        <a data-testid="card-title-link" href="/d/oferta/okazja-CID3-ID4AKsb.html">
          <h4>OKAZJA gotowe</h4>
        </a>
        <p data-testid="ad-price">699 000 zł</p>
        <span>41,20 m² - 16966.02 zł/m²</span>
      </div>
      <script>
        window.__PRERENDERED_STATE__ = "{state_json}";
      </script>
    </body></html>
    """
    listings = parse_search_results(raw_html)
    assert len(listings) == 1
    assert listings[0]["price_total"] == 699000.0
    assert listings[0]["currency"] == "PLN"
    assert listings[0]["price_per_sqm_source"] == 16966.02


def test_given_prerendered_display_value_when_card_has_no_price_then_fills_price() -> None:
    state_dict = {
        "listing": {
            "listing": {
                "ads": [
                    {
                        "id": 12345,
                        "url": "https://www.olx.pl/d/oferta/test-CID3-ID12345.html",
                        "price": {
                            "displayValue": "550 000 zł",
                        },
                    }
                ]
            }
        }
    }
    state_json = json.dumps(state_dict).replace('"', '\\"')
    raw_html = f"""
    <html><body>
      <div data-cy="l-card" id="12345">
        <a data-testid="card-title-link" href="/d/oferta/test-CID3-ID12345.html">
          <h4>Title</h4>
        </a>
      </div>
      <script>
        window.__PRERENDERED_STATE__ = "{state_json}";
      </script>
    </body></html>
    """
    listings = parse_search_results(raw_html)
    assert len(listings) == 1
    assert listings[0]["price_total"] == 550000.0
    assert listings[0]["currency"] == "PLN"


def test_given_prerendered_state_with_location_and_map_when_parsing_then_enriched() -> None:
    state_dict = {
        "listing": {
            "listing": {
                "ads": [
                    {
                        "id": 88888,
                        "url": "https://www.olx.pl/d/oferta/geo-CID3-ID88888.html",
                        "location": {
                            "cityName": "Kraków",
                            "districtName": "Krowodrza",
                            "pathName": "Małopolskie, Kraków, Krowodrza",
                        },
                        "map": {
                            "lat": 50.075,
                            "lon": 19.925,
                        },
                    }
                ]
            }
        }
    }
    state_json = json.dumps(state_dict).replace('"', '\\"')
    raw_html = f"""
    <html><body>
      <div data-cy="l-card" id="88888">
        <a data-testid="card-title-link" href="/d/oferta/geo-CID3-ID88888.html">
          <h4>Mieszkanie Krowodrza</h4>
        </a>
      </div>
      <script>
        window.__PRERENDERED_STATE__ = "{state_json}";
      </script>
    </body></html>
    """
    listings = parse_search_results(raw_html)
    assert len(listings) == 1
    assert listings[0]["city"] == "Kraków"
    assert listings[0]["district"] == "Krowodrza"
    assert listings[0]["location_approx"] == "Małopolskie, Kraków, Krowodrza"
    assert listings[0]["latitude"] == 50.075
    assert listings[0]["longitude"] == 19.925


def test_given_year_in_card_title_and_kawalerka_in_params_when_parsing_then_rooms_is_one() -> None:
    state_dict = {
        "listing": {
            "listing": {
                "ads": [
                    {
                        "id": 191919,
                        "url": "https://www.olx.pl/d/oferta/pokoj-CID3-ID191919.html",
                        "params": [
                            {"name": "Liczba pokoi", "value": "Kawalerka"},
                            {"name": "Powierzchnia", "value": "12 m²"},
                        ],
                    }
                ]
            }
        }
    }
    state_json = json.dumps(state_dict).replace('"', '\\"')
    raw_html = f"""
    <html><body>
      <div data-cy="l-card" id="191919">
        <a data-testid="card-title-link" href="/d/oferta/pokoj-CID3-ID191919.html">
          <h4>Pokój do wynajęcia</h4>
        </a>
        <p>Kraków - 12 marca 2026 Pokój do wynajęcia</p>
      </div>
      <script>
        window.__PRERENDERED_STATE__ = "{state_json}";
      </script>
    </body></html>
    """
    listings = parse_search_results(raw_html)
    assert len(listings) == 1
    assert listings[0]["rooms"] == 1.0


def test_given_breadcrumb_when_content_location_missing_then_city_extracted() -> None:
    breadcrumb_data = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Strona główna"},
            {"@type": "ListItem", "position": 2, "name": "Nieruchomości"},
            {"@type": "ListItem", "position": 3, "name": "Mieszkania"},
            {"@type": "ListItem", "position": 4, "name": "Wynajem"},
            {"@type": "ListItem", "position": 5, "name": "Wynajem - Małopolskie"},
            {"@type": "ListItem", "position": 6, "name": "Wynajem - Kraków"},
        ],
    }
    offers_data = {
        "@context": "https://schema.org",
        "@type": "Product",
        "offers": {
            "@type": "AggregateOffer",
            "offers": [
                {
                    "@type": "Offer",
                    "url": "https://www.olx.pl/d/oferta/mieszkanie-krakow-CID3-ID999.html",
                    "name": "Mieszkanie w centrum",
                    "price": 2500,
                    "priceCurrency": "PLN",
                }
            ],
        },
    }
    raw_html = f"""
    <html><body>
      <script type="application/ld+json">
        {json.dumps(breadcrumb_data)}
      </script>
      <script type="application/ld+json">
        {json.dumps(offers_data)}
      </script>
    </body></html>
    """
    listings = parse_search_results(raw_html)
    assert len(listings) == 1
    assert listings[0]["city"] == "Kraków"

