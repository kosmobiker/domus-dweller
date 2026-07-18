import json
import os
from typing import Any

from google import genai
from google.genai import types
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential


class RentAmenities(BaseModel):
    listing_id: str
    area_sqm: float | None
    rooms: int | None
    furnished: bool | None
    floor: int | str | None
    pets_allowed: bool | None
    elevator: bool | None
    parking: bool | None
    additional_rent_pln: int | None

class SaleAmenities(BaseModel):
    listing_id: str
    area_sqm: float | None
    rooms: int | None
    floor: int | str | None
    elevator: bool | None
    parking: bool | None
    balcony: bool | None
    building_material: str | None
    year_built: int | None
    ownership_type: str | None

class BatchRent(BaseModel):
    results: list[RentAmenities]

class BatchSale(BaseModel):
    results: list[SaleAmenities]

def get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _call_gemini_with_retry(client, prompt: str, schema: Any, mode: str) -> Any:
    return client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.0,
            top_k=1,
            max_output_tokens=65536,
        ),
    )

def enrich_with_ai(rows: list[dict], mode: str) -> None:
    client = get_client()
    if not client or not rows:
        print(f"[olx:{mode}] Skipping AI extraction (GEMINI_API_KEY not set or no rows)")
        return

    # Map ID to Listing Data (Description + Params)
    batch_dict = {}
    for row in rows:
        lid = row.get("source_listing_id")
        desc = row.get("description", "")
        params = row.get("detail_params", {})
        if lid and (desc or params):
            # Limit description length to save tokens, but pass full params
            batch_dict[lid] = {
                "description": str(desc)[:800].strip() if desc else "",
                "detail_params": params
            }
    
    if not batch_dict:
        return

    schema = BatchRent if mode == 'rent' else BatchSale
    clean_batch = batch_dict

    if not clean_batch:
        return

    chunk_size = 100
    items = list(clean_batch.items())
    extracted_features = {}

    for i in range(0, len(items), chunk_size):
        chunk = dict(items[i:i+chunk_size])
        prompt = (
            f"Extract the properties from this batch of Polish {mode} real estate listings.\n"
            f"Listings JSON:\n{json.dumps(chunk, ensure_ascii=False)}"
        )
        
        try:
            print(f"[olx:{mode}] Sending {len(chunk)} items to Gemini 3.1 Flash-Lite...")
            response = _call_gemini_with_retry(client, prompt, schema, mode)
            parsed = schema.model_validate_json(response.text)
            for result in parsed.results:
                extracted_features[result.listing_id] = result.model_dump()
        except Exception as e:
            print(f"[olx:{mode}] Gemini API Error on chunk: {e}")

    # Now merge back into rows
    for row in rows:
        lid = row.get("source_listing_id")
        if lid and lid in extracted_features:
            ai_data = extracted_features[lid]
            
            # Store full AI output in detail_params so it gets saved to Motherduck raw_json
            if "detail_params" not in row or not isinstance(row["detail_params"], dict):
                row["detail_params"] = {}
            row["detail_params"]["ai_extracted"] = ai_data
            
            # Fall back to AI if regex failed for core metrics
            if not row.get("area_sqm") and ai_data.get("area_sqm") is not None:
                row["area_sqm"] = ai_data["area_sqm"]
            if not row.get("rooms") and ai_data.get("rooms") is not None:
                row["rooms"] = ai_data["rooms"]
