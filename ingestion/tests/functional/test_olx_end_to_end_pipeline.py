import json
from datetime import date, datetime, UTC
from unittest.mock import MagicMock, patch

from domus_dweller.sources.olx.parser import parse_search_results
from domus_dweller.sinks.bigquery import load_rows_to_bigquery


def test_olx_end_to_end_pipeline_logic() -> None:
    """
    Verifies the logical flow from raw OLX search HTML to BigQuery-ready rows.
    This is a functional test that covers:
    1. Parsing search results (cards + JSON-LD)
    2. Merging and normalization
    3. BigQuery row preparation (payload hashing, raw_json inclusion)
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

    # 4. When: Preparing for BigQuery (using the actual logic but mocking the client)
    mock_client = MagicMock()
    # Mocking the load job result
    mock_job = MagicMock()
    mock_job.result.return_value = None
    mock_job.errors = None
    mock_job.output_rows = 1
    mock_client.load_table_from_json.return_value = mock_job

    snapshot_date = date(2026, 4, 5)
    ingested_at = datetime(2026, 4, 5, 12, 0, 0, tzinfo=UTC)

    # We call the sink logic which performs the final normalization
    with patch("domus_dweller.sinks.bigquery._build_client", return_value=mock_client):
        inserted = load_rows_to_bigquery(
            listings,
            mode="rent",
            project="test-project",
            dataset="test_dataset",
            snapshot_date=snapshot_date,
            ingested_at=ingested_at,
        )

    # 5. Then: Verify the data sent to BigQuery
    assert inserted == 1
    mock_client.load_table_from_json.assert_called_once()
    args, kwargs = mock_client.load_table_from_json.call_args
    sent_rows = args[0]
    destination = args[1]

    assert destination == "test-project.test_dataset.rent_bronze"
    assert len(sent_rows) == 1
    bq_row = sent_rows[0]

    # Verify BigQuery-specific metadata
    assert bq_row["mode"] == "rent"
    assert bq_row["layer"] == "bronze"
    assert bq_row["snapshot_date"] == "2026-04-05"
    assert bq_row["ingested_at"] == "2026-04-05T12:00:00+00:00"
    
    # Verify raw_json preservation
    assert "raw_json" in bq_row
    assert bq_row["raw_json"]["source_listing_id"] == "olx-123"
    
    # Verify payload hashing (reproducibility)
    assert "payload_hash" in bq_row
    assert len(bq_row["payload_hash"]) == 64  # SHA-256

    # Verify that the original data is intact in the flat structure
    assert bq_row["price_total"] == 3500.0
    assert bq_row["seller_segment"] == "private"
