import json
import re

from selectolax.parser import HTMLParser


def _seller_segment_from_text(seller_text: str) -> str:
    normalized = seller_text.casefold()
    if "osoba prywatna" in normalized or "prywat" in normalized:
        return "private"
    if "firma" in normalized or "biuro" in normalized or "agenc" in normalized:
        return "professional"
    return "unknown"


def parse_search_results(raw_html: str) -> list[dict]:
    tree = HTMLParser(raw_html)
    page_city = _extract_page_city(tree)
    card_listings = _parse_card_listings(tree)
    jsonld_listings = _parse_jsonld_offers(tree, page_city=page_city)
    return _merge_card_and_jsonld(card_listings, jsonld_listings)


def _parse_card_listings(tree: HTMLParser) -> list[dict]:
    listings: list[dict] = []
    seen_ids: set[str] = set()

    for card in tree.css("article[data-cy='l-card']"):
        source_listing_id = (card.attributes.get("data-id") or "").strip()

        link = card.css_first("a[href]")
        source_url = ""
        title = ""
        if link is not None:
            source_url = (link.attributes.get("href") or "").strip()
            title = link.text(separator=" ", strip=True)
        if not source_listing_id or not source_url or source_listing_id in seen_ids:
            continue
        seen_ids.add(source_listing_id)

        seller_text = " ".join(
            node.text(separator=" ", strip=True) for node in card.css("span, p, div")
        ).strip()
        price_total, currency = _extract_price_fields(seller_text)

        listings.append(
            {
                "source": "olx",
                "source_listing_id": source_listing_id,
                "source_url": source_url,
                "title": title,
                "price_total": price_total,
                "currency": currency,
                "district": None,
                "city": None,
                "municipality": None,
                "location_approx": None,
                "images": [],
                "price_valid_until": None,
                "seller_segment": _seller_segment_from_text(seller_text),
            }
        )

    return listings


def _parse_jsonld_offers(tree: HTMLParser, *, page_city: str | None) -> list[dict]:
    listings: list[dict] = []
    seen_ids: set[str] = set()

    for script in tree.css("script[type='application/ld+json']"):
        raw_json = (script.text() or "").strip()
        if not raw_json:
            continue
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError:
            continue

        offers_block = payload.get("offers")
        if not isinstance(offers_block, dict):
            continue
        nested_offers = offers_block.get("offers")
        if not isinstance(nested_offers, list):
            continue

        for offer in nested_offers:
            if not isinstance(offer, dict):
                continue
            source_url = str(offer.get("url", "")).strip()
            source_listing_id = _extract_olx_listing_id(source_url)
            if not source_listing_id or source_listing_id in seen_ids:
                continue
            seen_ids.add(source_listing_id)

            evidence = " ".join(
                [
                    str(offer.get("name", "")),
                    str(offer.get("description", "")),
                    str(offer.get("seller", "")),
                ]
            )
            price_value = offer.get("price")
            price_total = float(price_value) if isinstance(price_value, int | float) else None
            price_currency = str(offer.get("priceCurrency", "")).strip() or "PLN"
            district = _extract_district(offer.get("areaServed"))
            location_approx = _build_location_approx(city=page_city, district=district)
            images = _extract_images(offer.get("image"))
            price_valid_until = str(offer.get("priceValidUntil", "")).strip() or None
            listings.append(
                {
                    "source": "olx",
                    "source_listing_id": source_listing_id,
                    "source_url": source_url,
                    "title": str(offer.get("name", "")).strip(),
                    "price_total": price_total,
                    "currency": price_currency,
                    "district": district,
                    "city": page_city,
                    "municipality": page_city,
                    "location_approx": location_approx,
                    "images": images,
                    "price_valid_until": price_valid_until,
                    "seller_segment": _seller_segment_from_text(evidence),
                }
            )

    return listings


def _extract_olx_listing_id(source_url: str) -> str:
    marker = "-ID"
    marker_index = source_url.find(marker)
    if marker_index == -1:
        return ""
    suffix = source_url[marker_index + len(marker) :]
    raw_id = suffix.split(".html", 1)[0].split("/", 1)[0].strip()
    if not raw_id:
        return ""
    return f"olx-{raw_id}"


def _extract_price_fields(text: str) -> tuple[float | None, str | None]:
    normalized = text.replace("\xa0", " ")
    match = re.search(r"(\d[\d\s]*)\s*(zł|pln)", normalized, flags=re.IGNORECASE)
    if not match:
        return None, None
    digits = re.sub(r"\D", "", match.group(1))
    if not digits:
        return None, None
    return float(digits), "PLN"


def _extract_district(area_served: object) -> str | None:
    if isinstance(area_served, dict):
        value = str(area_served.get("name", "")).strip()
        return value or None
    if isinstance(area_served, str):
        value = area_served.strip()
        return value or None
    return None


def _extract_images(image_value: object) -> list[str]:
    if isinstance(image_value, list):
        return [str(item).strip() for item in image_value if str(item).strip()]
    if isinstance(image_value, str):
        value = image_value.strip()
        return [value] if value else []
    return []


def _extract_page_city(tree: HTMLParser) -> str | None:
    for script in tree.css("script[type='application/ld+json']"):
        raw_json = (script.text() or "").strip()
        if not raw_json:
            continue
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError:
            continue
        content_location = payload.get("contentLocation")
        if isinstance(content_location, dict):
            city = str(content_location.get("name", "")).strip()
            if city:
                return city
    return None


def _build_location_approx(*, city: str | None, district: str | None) -> str | None:
    if city and district:
        return f"{city}, {district}"
    return city or district


def _merge_card_and_jsonld(card_listings: list[dict], jsonld_listings: list[dict]) -> list[dict]:
    if not card_listings:
        return jsonld_listings
    if not jsonld_listings:
        return card_listings

    by_id = {
        str(item.get("source_listing_id", "")).strip(): item
        for item in jsonld_listings
        if str(item.get("source_listing_id", "")).strip()
    }
    merged: list[dict] = []
    seen: set[str] = set()

    for card in card_listings:
        listing_id = str(card.get("source_listing_id", "")).strip()
        if not listing_id or listing_id in seen:
            continue
        seen.add(listing_id)
        enriched = dict(card)
        if listing_id in by_id:
            jsonld = by_id[listing_id]
            enriched["title"] = jsonld.get("title") or enriched.get("title")
            enriched["price_total"] = jsonld.get("price_total") or enriched.get("price_total")
            enriched["currency"] = jsonld.get("currency") or enriched.get("currency")
            enriched["district"] = jsonld.get("district")
            enriched["city"] = jsonld.get("city")
            enriched["municipality"] = jsonld.get("municipality")
            enriched["location_approx"] = jsonld.get("location_approx")
            enriched["images"] = jsonld.get("images") or []
            enriched["price_valid_until"] = jsonld.get("price_valid_until")
        merged.append(enriched)

    for item in jsonld_listings:
        listing_id = str(item.get("source_listing_id", "")).strip()
        if listing_id and listing_id not in seen:
            seen.add(listing_id)
            merged.append(item)

    return merged
