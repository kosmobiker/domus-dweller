from datetime import date
from unittest.mock import MagicMock, patch

import httpx
from domus_dweller.sources.olx import ingest_motherduck


def test_build_search_url() -> None:
    # Rent
    url = ingest_motherduck._build_search_url(
        mode="rent", property_type="mieszkania", city="krakow", page=2
    )
    assert "mieszkania/wynajem/krakow" in url
    assert "page=2" in url

    # Sale
    url = ingest_motherduck._build_search_url(
        mode="sale", property_type="domy", city="warszawa", page=1
    )
    assert "domy/sprzedaz/warszawa" in url
    assert "page=1" in url

    # Rooms (special case)
    url = ingest_motherduck._build_search_url(
        mode="rent", property_type="pokoje", city="krakow", page=5
    )
    assert "stancje-pokoje/krakow" in url
    assert "page=5" in url

def test_fetch_html_success() -> None:
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "<html></html>"
    mock_client.get.return_value = mock_response

    html = ingest_motherduck._fetch_html("http://test.com", mock_client, timeout_sec=1.0)
    assert html == "<html></html>"
    mock_response.raise_for_status.assert_called_once()

def test_fetch_html_retry(monkeypatch) -> None:
    # We want to verify it retries. Tenacity is used.
    # To keep it fast, we can mock the wait or just verify multiple calls.
    mock_client = MagicMock()
    mock_client.get.side_effect = [
        httpx.ConnectTimeout("timeout"),
        MagicMock(text="success")
    ]
    
    # Mocking sleep to speed up tests
    monkeypatch.setattr("time.sleep", lambda x: None)

    html = ingest_motherduck._fetch_html("http://test.com", mock_client, timeout_sec=1.0)
    assert html == "success"
    assert mock_client.get.call_count == 2

def test_collect_search_rows_success() -> None:
    # Mock parse_search_results to return some data
    mock_parsed = [
        {"source_listing_id": "1", "price": 100},
        {"source_listing_id": "2", "price": 200},
    ]
    
    with patch("domus_dweller.sources.olx.ingest_motherduck._fetch_html") as mock_fetch, \
         patch("domus_dweller.sources.olx.ingest_motherduck.parse_search_results") as mock_parse:
        
        mock_fetch.return_value = "<html></html>"
        # Return 2 listings on first page, then empty to stop seed
        mock_parse.side_effect = [mock_parsed, []]
        
        rows = ingest_motherduck._collect_search_rows(
            mode="rent",
            cities=["krakow"],
            property_types=["mieszkania"],
            pages=2,
            search_timeout_sec=1.0
        )
        
        assert len(rows) == 2
        assert rows[0]["source_listing_id"] == "1"

def test_collect_search_rows_deduplication() -> None:
    mock_parsed_p1 = [{"source_listing_id": "dup", "price": 100}]
    mock_parsed_p2 = [{"source_listing_id": "dup", "price": 100}]
    
    with patch("domus_dweller.sources.olx.ingest_motherduck._fetch_html") as mock_fetch, \
         patch("domus_dweller.sources.olx.ingest_motherduck.parse_search_results") as mock_parse:
        
        mock_fetch.return_value = "<html></html>"
        mock_parse.side_effect = [mock_parsed_p1, mock_parsed_p2, []]
        
        rows = ingest_motherduck._collect_search_rows(
            mode="rent",
            cities=["krakow"],
            property_types=["mieszkania"],
            pages=3,
            search_timeout_sec=1.0
        )
        
        assert len(rows) == 1

def test_run_olx_mode_to_motherduck() -> None:
    with patch(
        "domus_dweller.sources.olx.ingest_motherduck._collect_search_rows"
    ) as mock_collect, patch(
        "domus_dweller.sources.olx.ingest_motherduck.load_rows_to_motherduck"
    ) as mock_load:
        
        mock_collect.return_value = [{"id": "1"}]
        mock_load.return_value = 1
        
        inserted = ingest_motherduck.run_olx_mode_to_motherduck(
            mode="rent",
            database="db",
            cities=["krakow"],
            property_types=["mieszkania"],
            pages=1,
            search_timeout_sec=1.0,
            snapshot_date=date(2026, 4, 6)
        )
        
        assert inserted == 1
        mock_load.assert_called_once()

def test_main_cli_integration(monkeypatch) -> None:
    # Test main() by mocking the high level run function
    monkeypatch.setattr(
        "sys.argv",
        ["ingest_motherduck", "--mode", "rent", "--pages", "1", "--cities", "krakow"]
    )
    
    with patch(
        "domus_dweller.sources.olx.ingest_motherduck.run_olx_mode_to_motherduck"
    ) as mock_run:
        mock_run.return_value = 5
        ingest_motherduck.main()
        
        assert mock_run.call_count == 1
        args, kwargs = mock_run.call_args
        assert kwargs["mode"] == "rent"
        assert kwargs["pages"] == 1
        assert "krakow" in kwargs["cities"]

def test_build_args_defaults() -> None:
    with patch("sys.argv", ["ingest_motherduck"]):
        args = ingest_motherduck._build_args()
        assert args.mode == "both"
        assert args.database == "my_db"
        assert args.pages == 30
