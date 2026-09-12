from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from domus_dweller.sources.olx import fetch, fetch_search


def test_given_valid_url_when_fetching_then_html_content_is_returned() -> None:
    # Given
    fake_html = "<html><body><h1>Listing Page</h1></body></html>"
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = fake_html

    with patch("curl_cffi.requests.get", return_value=mock_resp) as mock_get:
        # When
        result = fetch.fetch_search_page("https://www.olx.pl/nieruchomosci/")

        # Then
        assert result == fake_html
        mock_get.assert_called_once()
        assert mock_get.call_args.kwargs.get("impersonate") == "chrome"


def test_given_transient_error_when_fetching_then_retries_and_succeeds() -> None:
    # Given
    error_resp = MagicMock()
    error_resp.status_code = 503
    error_resp.text = "Service Unavailable"

    success_resp = MagicMock()
    success_resp.status_code = 200
    success_resp.text = "<html>Success</html>"

    with patch("curl_cffi.requests.get", side_effect=[error_resp, success_resp]) as mock_get:
        # When
        result = fetch.fetch_search_page(
            "https://www.olx.pl/nieruchomosci/",
            max_retries=2,
            retry_delay=0.01,
        )

        # Then
        assert result == "<html>Success</html>"
        assert mock_get.call_count == 2


def test_given_persistent_error_when_fetching_then_raises_error() -> None:
    # Given
    error_resp = MagicMock()
    error_resp.status_code = 403
    error_resp.text = "Forbidden"

    with patch("curl_cffi.requests.get", return_value=error_resp) as mock_get:
        # When / Then
        with pytest.raises(RuntimeError, match="HTTP 403"):
            fetch.fetch_search_page(
                "https://www.olx.pl/nieruchomosci/",
                max_retries=2,
                retry_delay=0.01,
            )
        assert mock_get.call_count == 2


def test_given_cli_args_when_running_fetch_search_then_file_is_written(
    monkeypatch,
    tmp_path: Path,
) -> None:
    # Given
    output_path = tmp_path / "raw" / "olx_page.html"
    fake_html = "<html><body>CLI Page</body></html>"

    with patch("domus_dweller.sources.olx.fetch.fetch_search_page", return_value=fake_html):
        monkeypatch.setattr(
            "sys.argv",
            [
                "fetch_search",
                "--url",
                "https://www.olx.pl/nieruchomosci/mieszkania/wynajem/krakow/?page=1",
                "--output",
                str(output_path),
            ],
        )

        # When
        fetch_search.main()

        # Then
        assert output_path.exists()
        assert output_path.read_text(encoding="utf-8") == fake_html


def test_given_cli_args_when_fetch_fails_then_system_exit_is_raised(
    monkeypatch,
    tmp_path: Path,
) -> None:
    # Given
    output_path = tmp_path / "raw" / "olx_page.html"

    with patch(
        "domus_dweller.sources.olx.fetch.fetch_search_page",
        side_effect=RuntimeError("Connection failed"),
    ):
        monkeypatch.setattr(
            "sys.argv",
            [
                "fetch_search",
                "--url",
                "https://www.olx.pl/nieruchomosci/mieszkania/wynajem/krakow/?page=1",
                "--output",
                str(output_path),
            ],
        )

        # When / Then
        with pytest.raises(SystemExit) as exc_info:
            fetch_search.main()
        assert exc_info.value.code == 1
        assert not output_path.exists()
