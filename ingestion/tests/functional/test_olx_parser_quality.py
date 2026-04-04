from domus_dweller.sources.olx.parser import parse_search_results


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
