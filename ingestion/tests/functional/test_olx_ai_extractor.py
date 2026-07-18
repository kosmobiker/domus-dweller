from unittest.mock import MagicMock

import pytest
from domus_dweller.sources.olx.ai_extractor import enrich_with_ai


def test_enrich_with_ai_extracts_and_merges_rent_amenities(monkeypatch):
    # Given: A mock Gemini API client that returns structured JSON
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '''{
        "results": [
            {
                "listing_id": "olx-123",
                "area_sqm": 45.0,
                "rooms": 2,
                "furnished": true,
                "floor": 2,
                "pets_allowed": true,
                "elevator": false,
                "parking": true,
                "additional_rent_pln": 500
            }
        ]
    }'''
    mock_client.models.generate_content.return_value = mock_response
    monkeypatch.setattr("domus_dweller.sources.olx.ai_extractor.get_client", lambda: mock_client)

    # Given: A raw parsed row missing `area_sqm` and `rooms`
    rows = [
        {
            "source_listing_id": "olx-123",
            "description": (
                "Przytulne 2 pokoje, 45 m2, meble są. Można z psem. Winda zepsuta. "
                "Miejsce parkingowe w cenie. Czynsz dodatkowo 500zł."
            ),
            "area_sqm": None,
            "rooms": None
        }
    ]

    # When: We run the AI enrichment
    enrich_with_ai(rows, mode="rent")

    # Then: The AI client should have been called
    mock_client.models.generate_content.assert_called_once()
    
    # Then: The core columns should be dynamically populated
    assert rows[0]["area_sqm"] == 45.0
    assert rows[0]["rooms"] == 2
    
    # Then: The full structured JSON should be safely stored in detail_params
    assert "detail_params" in rows[0]
    ai_data = rows[0]["detail_params"]["ai_extracted"]
    assert ai_data["furnished"] is True
    assert ai_data["pets_allowed"] is True
    assert ai_data["elevator"] is False
    assert ai_data["additional_rent_pln"] == 500


def test_enrich_with_ai_skips_when_no_descriptions(monkeypatch):
    # Given: A mock client
    mock_client = MagicMock()
    monkeypatch.setattr("domus_dweller.sources.olx.ai_extractor.get_client", lambda: mock_client)

    # Given: Rows that have no description or empty descriptions
    rows = [
        {"source_listing_id": "olx-000", "description": ""},
        {"source_listing_id": "olx-999", "description": None},
        {"source_listing_id": "olx-555"}  # Missing key entirely
    ]

    # When: We run the AI enrichment
    enrich_with_ai(rows, mode="sale")

    # Then: The API should never be called
    mock_client.models.generate_content.assert_not_called()
    
    # Then: detail_params should not be mutated
    for row in rows:
        assert "detail_params" not in row

def test_enrich_with_ai_does_not_override_existing_core_metrics(monkeypatch):
    # Given: A mock client that returns different AI values for area and rooms
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '''{
        "results": [
            {
                "listing_id": "olx-777",
                "area_sqm": 99.0,
                "rooms": 9,
                "furnished": true,
                "floor": 1,
                "pets_allowed": null,
                "elevator": null,
                "parking": null,
                "additional_rent_pln": null
            }
        ]
    }'''
    mock_client.models.generate_content.return_value = mock_response
    monkeypatch.setattr("domus_dweller.sources.olx.ai_extractor.get_client", lambda: mock_client)

    # Given: A row where the regex successfully parsed area_sqm and rooms
    rows = [
        {
            "source_listing_id": "olx-777",
            "description": "Some long description",
            "area_sqm": 45.0,  # Regex found this
            "rooms": 2.0       # Regex found this
        }
    ]

    # When: We run AI enrichment
    enrich_with_ai(rows, mode="rent")

    # Then: Existing values are NOT overridden
    assert rows[0]["area_sqm"] == 45.0
    assert rows[0]["rooms"] == 2.0
    
    # But the AI values are still recorded in detail_params!
    assert rows[0]["detail_params"]["ai_extracted"]["area_sqm"] == 99.0

@pytest.mark.skipif(not __import__("os").getenv("GEMINI_API_KEY"), reason="Requires GEMINI_API_KEY")
def test_live_enrich_with_ai_no_degradation():
    """Live test to ensure Gemini 3.1 Flash-Lite hasn't degraded in quality."""
    rows = [
        {
            "source_listing_id": "olx-live-1",
            "description": (
                "Do wynajęcia od zaraz kawalerka 30m2 w centrum Krakowa. "
                "W pełni umeblowane, niestety bez zwierząt. Winda w bloku jest. "
                "Brak parkingu."
            ),
            "area_sqm": None,
            "rooms": None
        },
        {
            "source_listing_id": "olx-live-2",
            "description": (
                "Sprzedam piękny dom 120m2. 4 pokoje. Zbudowany z pustaka w 2010 roku. "
                "Duży balkon, miejsce parkingowe w garażu podziemnym."
            ),
            "area_sqm": None,
            "rooms": None
        }
    ]

    # Test Rent extraction
    rent_rows = [rows[0].copy()]
    enrich_with_ai(rent_rows, mode="rent")
    rent_ai = rent_rows[0]["detail_params"]["ai_extracted"]
    
    assert rent_rows[0]["area_sqm"] == 30.0
    assert rent_rows[0]["rooms"] == 1
    assert rent_ai["furnished"] is True
    assert rent_ai["pets_allowed"] is False
    assert rent_ai["elevator"] is True
    assert rent_ai["parking"] is False

    # Test Sale extraction
    sale_rows = [rows[1].copy()]
    enrich_with_ai(sale_rows, mode="sale")
    sale_ai = sale_rows[0]["detail_params"]["ai_extracted"]
    
    assert sale_rows[0]["area_sqm"] == 120.0
    assert sale_rows[0]["rooms"] == 4
    assert sale_ai["year_built"] == 2010
    assert sale_ai["balcony"] is True
    assert sale_ai["parking"] is True
