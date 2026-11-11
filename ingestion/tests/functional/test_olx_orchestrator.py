from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from domus_dweller.sources.olx import orchestrator


def _sample_page_html(listing_ids: list[str]) -> str:
    cards_html = ""
    jsonld_offers = []
    for lid in listing_ids:
        cards_html += f"""
        <article data-cy="l-card" data-id="olx-{lid}">
          <a data-testid="card-title-link"
             href="https://www.olx.pl/d/oferta/flat-ID{lid}.html">Mieszkanie {lid}</a>
          <span data-testid="ad-price">2500 zł</span>
          <p data-nx-name="P3">Osoba prywatna</p>
        </article>
        """
        jsonld_offers.append(
            {
                "@type": "Offer",
                "name": f"Mieszkanie {lid}",
                "url": f"https://www.olx.pl/d/oferta/flat-ID{lid}.html",
                "price": 2500,
                "priceCurrency": "PLN",
                "areaServed": {"name": "Krowodrza"},
            }
        )

    jsonld_str = json.dumps(
        {
            "@type": "Product",
            "offers": {
                "@type": "AggregateOffer",
                "offers": jsonld_offers,
            },
        }
    )
    return f"""
    <html><body>
      <script type="application/ld+json">
        {{"@type": "WebPage", "contentLocation": {{"@type": "City", "name": "Kraków"}}}}
      </script>
      <section>{cards_html}</section>
      <script type="application/ld+json">{jsonld_str}</script>
    </body></html>
    """


def test_build_seeds_returns_correct_combinations() -> None:
    # Rent seeds
    rent_seeds = orchestrator.build_seeds(
        mode="rent",
        cities=["krakow", "wieliczka"],
        property_types=["mieszkania", "domy", "pokoje"],
    )
    assert len(rent_seeds) == 6
    names = [s.seed_name for s in rent_seeds]
    assert "mieszkania_krakow" in names
    assert "domy_krakow" in names
    assert "pokoje_krakow" in names
    assert "mieszkania_wieliczka" in names

    # pokoje category slug check
    pokoje_seed = next(s for s in rent_seeds if s.seed_name == "pokoje_krakow")
    assert "/stancje-pokoje/krakow/" in pokoje_seed.base_url

    # mieszkania rent category slug check
    mieszkania_seed = next(s for s in rent_seeds if s.seed_name == "mieszkania_krakow")
    assert "/mieszkania/wynajem/krakow/" in mieszkania_seed.base_url

    # Sale seeds
    sale_seeds = orchestrator.build_seeds(
        mode="sale",
        cities=["krakow"],
        property_types=["mieszkania", "domy"],
    )
    assert len(sale_seeds) == 2
    assert "/mieszkania/sprzedaz/krakow/" in sale_seeds[0].base_url


def test_orchestrator_crawls_and_merges_pages(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    parsed_dir = tmp_path / "parsed"

    def _fake_fetch(url: str, session: MagicMock | None = None) -> str:
        if "page=1" in url:
            return _sample_page_html(["ID1", "ID2"])
        if "page=2" in url:
            return _sample_page_html(["ID3"])
        # page 3 is empty
        return "<html><body><section></section></body></html>"

    with patch.object(orchestrator, "fetch_page", side_effect=_fake_fetch):
        summary = orchestrator.run_crawl(
            mode="rent",
            cities=["krakow"],
            property_types=["mieszkania"],
            max_pages=5,
            workers=1,
            raw_dir=raw_dir,
            parsed_dir=parsed_dir,
            snapshot_date="2026-11-11",
        )

    assert summary.total_unique_listings == 3
    assert summary.pages_fetched == 3  # page 1, 2, and 3 (which had 0 items and stopped)

    # Check raw files exist
    assert (raw_dir / "olx_rent_mieszkania_krakow_page_1.html").exists()
    assert (raw_dir / "olx_rent_mieszkania_krakow_page_2.html").exists()

    # Check merged output file
    merged_file = parsed_dir / "olx_rent_all.json"
    assert merged_file.exists()
    merged_data = json.loads(merged_file.read_text(encoding="utf-8"))
    assert len(merged_data) == 3
    ids = {item["source_listing_id"] for item in merged_data}
    assert ids == {"olx-ID1", "olx-ID2", "olx-ID3"}


def test_orchestrator_detects_pagination_loop_and_stops(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    parsed_dir = tmp_path / "parsed"

    # Simulate OLX returning page 1 items again on page 2 (circular pagination)
    def _fake_fetch(url: str, session: MagicMock | None = None) -> str:
        return _sample_page_html(["ID100", "ID101", "ID102"])

    with patch.object(orchestrator, "fetch_page", side_effect=_fake_fetch):
        summary = orchestrator.run_crawl(
            mode="sale",
            cities=["wieliczka"],
            property_types=["mieszkania"],
            max_pages=10,
            workers=1,
            raw_dir=raw_dir,
            parsed_dir=parsed_dir,
            snapshot_date="2026-11-11",
        )

    # Should have stopped after page 2 detected the 100% duplicate loop!
    assert summary.pages_fetched == 2
    assert summary.total_unique_listings == 3

    merged_file = parsed_dir / "olx_sale_all.json"
    assert merged_file.exists()
    merged_data = json.loads(merged_file.read_text(encoding="utf-8"))
    assert len(merged_data) == 3


def test_orchestrator_multi_worker_execution(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    parsed_dir = tmp_path / "parsed"

    def _fake_fetch(url: str, session: MagicMock | None = None) -> str:
        if "krakow" in url:
            return _sample_page_html(["KR1"])
        return _sample_page_html(["SK1"])

    with patch.object(orchestrator, "fetch_page", side_effect=_fake_fetch):
        summary = orchestrator.run_crawl(
            mode="rent",
            cities=["krakow", "skawina"],
            property_types=["mieszkania"],
            max_pages=1,
            workers=2,
            raw_dir=raw_dir,
            parsed_dir=parsed_dir,
            snapshot_date="2026-11-11",
        )

    assert summary.seeds_processed == 2
    assert summary.total_unique_listings == 2
    merged_file = parsed_dir / "olx_rent_all.json"
    assert merged_file.exists()


def test_orchestrator_handles_fetch_failure(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    parsed_dir = tmp_path / "parsed"

    def _fake_fetch(url: str, session: MagicMock | None = None) -> str:
        raise RuntimeError("Network boom")

    with patch.object(orchestrator, "fetch_page", side_effect=_fake_fetch):
        summary = orchestrator.run_crawl(
            mode="rent",
            cities=["krakow"],
            property_types=["mieszkania"],
            max_pages=3,
            workers=1,
            raw_dir=raw_dir,
            parsed_dir=parsed_dir,
            snapshot_date="2026-11-11",
        )

    assert summary.pages_fetched == 0
    assert summary.total_unique_listings == 0


def test_fetch_page_success_and_retries() -> None:
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html>ok</html>"
    mock_session.get.return_value = mock_response

    res = orchestrator.fetch_page("https://example.com", session=mock_session)
    assert res == "<html>ok</html>"

    # Test retry on HTTP error
    fail_response = MagicMock()
    fail_response.status_code = 500
    mock_session.get.side_effect = [fail_response, mock_response]

    res2 = orchestrator.fetch_page("https://example.com", session=mock_session, retry_delay=0.01)
    assert res2 == "<html>ok</html>"

    # Test exhausted retries
    mock_session.get.side_effect = RuntimeError("DNS failure")
    with pytest.raises(RuntimeError, match="Network error fetching"):
        orchestrator.fetch_page(
            "https://example.com", session=mock_session, max_retries=2, retry_delay=0.01
        )


def test_orchestrator_cli_execution_both_modes(monkeypatch, tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    parsed_dir = tmp_path / "parsed"

    def _fake_fetch(url: str, session: MagicMock | None = None) -> str:
        return _sample_page_html(["IDCLI"])

    monkeypatch.setattr(orchestrator, "fetch_page", _fake_fetch)
    monkeypatch.setattr(
        "sys.argv",
        [
            "orchestrator",
            "--mode",
            "both",
            "--date",
            "2026-11-11",
            "--pages",
            "1",
            "--cities",
            "krakow,skawina",
            "--workers",
            "2",
            "--raw-dir",
            str(raw_dir),
            "--parsed-dir",
            str(parsed_dir),
        ],
    )

    # Put a corrupt file in parsed_dir to test graceful handling of bad json
    corrupt_file = parsed_dir / "olx_rent_corrupt_page_99.json"
    corrupt_file.parent.mkdir(parents=True, exist_ok=True)
    corrupt_file.write_text("NOT_JSON", encoding="utf-8")

    orchestrator.main()

    assert (parsed_dir / "olx_rent_all.json").exists()
    assert (parsed_dir / "olx_sale_all.json").exists()
