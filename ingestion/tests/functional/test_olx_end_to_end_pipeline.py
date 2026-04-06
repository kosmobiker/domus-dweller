import json
from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch

from domus_dweller.sinks.motherduck import load_rows_to_motherduck
from domus_dweller.sources.olx.parser import parse_search_results


def _pragma_rows_for(columns: list[str]) -> list[tuple[object, ...]]:
    return [(idx, name, "VARCHAR", False, None, False) for idx, name in enumerate(columns)]


def test_olx_end_to_end_pipeline_logic() -> None:
    """
    Verifies the logical flow from raw OLX search HTML to MotherDuck-ready rows.
    This is a functional test that covers:
    1. Parsing search results (cards + JSON-LD)
    2. Merging and normalization
    3. MotherDuck row preparation (payload hashing, raw_json inclusion)
    """
    # 1. Given: Raw OLX Search Results HTML
    raw_html = """
    <html><body>
      <script type="application/ld+json">
        {
          "@type": "WebPage",
          "contentLocation": {"@type": "City", "name": "Kraków"}
        }
      </script>
      <section>
        <article data-cy="l-card" data-id="olx-123">
          <a href="https://www.olx.pl/d/oferta/mieszkanie-krakow-ID123.html">Mieszkanie 2 pokoje</a>
          <p>3500 zł</p>
          <span>Osoba prywatna</span>
        </article>
      </section>
      <script type="application/ld+json">
        {
          "@type": "Product",
          "offers": {
            "@type": "AggregateOffer",
            "offers": [
              {
                "@type": "Offer",
                "name": "Mieszkanie 2 pokoje",
                "url": "https://www.olx.pl/d/oferta/mieszkanie-krakow-ID123.html",
                "price": 3500,
                "priceCurrency": "PLN",
                "areaServed": {"name": "Stare Miasto"}
              }
            ]
          }
        }
      </script>
    </body></html>
    """

    # 2. When: Parsing search results
    listings = parse_search_results(raw_html)

    # 3. Then: Verify parsing results
    assert len(listings) == 1
    listing = listings[0]
    assert listing["source_listing_id"] == "olx-123"
    assert listing["price_total"] == 3500.0
    assert listing["seller_segment"] == "private"
    assert listing["city"] == "Kraków"
    assert listing["district"] == "Stare Miasto"

    # 4. When: Preparing for MotherDuck (using the actual logic but mocking the connection)
    mock_con = MagicMock()
    
    snapshot_date = date(2026, 4, 5)
    ingested_at = datetime(2026, 4, 5, 12, 0, 0, tzinfo=UTC)

    pragma_result = MagicMock()
    pragma_result.fetchall.return_value = _pragma_rows_for(
        [
            "source",
            "source_listing_id",
            "source_url",
            "mode",
            "snapshot_date",
            "layer",
            "ingested_at",
            "payload_hash",
            "raw_json",
            "price_total",
            "seller_segment",
        ]
    )
    insert_result = MagicMock()
    mock_con.execute.side_effect = [pragma_result, insert_result]

    # We call the sink logic which performs the final normalization
    with patch("duckdb.connect", return_value=mock_con), \
         patch("os.getenv", return_value="fake-token"), \
         patch("pyarrow.Table") as mock_table:
        mock_arrow_table = MagicMock()
        mock_arrow_table.column_names = [
            "source",
            "source_listing_id",
            "source_url",
            "mode",
            "snapshot_date",
            "layer",
            "ingested_at",
            "payload_hash",
            "raw_json",
            "price_total",
            "seller_segment",
            "extra_not_in_table",
        ]
        mock_table.from_pylist.return_value = mock_arrow_table
        inserted = load_rows_to_motherduck(
            listings,
            mode="rent",
            database="test_db",
            snapshot_date=snapshot_date,
            ingested_at=ingested_at,
        )

    # 5. Then: Verify the data sent to MotherDuck
    assert inserted == 1
    assert mock_con.execute.call_count == 2
    sql = mock_con.execute.call_args_list[1].args[0]
    assert "INSERT INTO bronze.rent_bronze (" in sql
    assert 'SELECT arrow_table."source"' in sql
    assert "extra_not_in_table" not in sql
    mock_table.from_pylist.assert_called_once()
    sent_rows = mock_table.from_pylist.call_args.args[0]
    assert len(sent_rows) == 1
    md_row = sent_rows[0]

    # Verify MotherDuck-specific metadata
    assert md_row["mode"] == "rent"
    assert md_row["layer"] == "bronze"
    assert md_row["snapshot_date"] == "2026-04-05"
    assert md_row["ingested_at"] == "2026-04-05T12:00:00+00:00"

    # Verify raw_json preservation
    assert "raw_json" in md_row
    raw_json_parsed = json.loads(md_row["raw_json"])
    assert raw_json_parsed["source_listing_id"] == "olx-123"

    # Verify payload hashing (reproducibility)
    assert "payload_hash" in md_row
    assert len(md_row["payload_hash"]) == 64  # SHA-256

    # Verify that the original data is intact in the flat structure
    assert md_row["price_total"] == 3500.0
    assert md_row["seller_segment"] == "private"
