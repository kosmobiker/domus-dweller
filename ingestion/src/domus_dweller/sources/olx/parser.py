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


def _seller_type_from_text(seller_text: str) -> str:
    normalized = seller_text.casefold()
    if "osoba prywatna" in normalized or "prywat" in normalized:
        return "private"
    if "deweloper" in normalized:
        return "developer"
    if "firma" in normalized or "biuro" in normalized or "agenc" in normalized:
        return "agency"
    return "unknown"


def parse_search_results(raw_html: str) -> list[dict]:
    tree = HTMLParser(raw_html)
    page_city = _extract_page_city(tree)
    prerendered_state = _parse_prerendered_state(tree)
    card_listings = _parse_card_listings(tree)
    jsonld_listings = _parse_jsonld_offers(tree, page_city=page_city)
    merged = _merge_card_and_jsonld(card_listings, jsonld_listings)
    return _merge_with_prerendered(merged, prerendered_state)


def parse_detail_page(raw_html: str) -> dict:
    tree = HTMLParser(raw_html)
    detail_params, seller_badges = _extract_detail_parameters(tree)
    detail_title = _extract_detail_title(tree)
    seller_name = _extract_seller_name(tree)
    seller_profile_url = _extract_seller_profile_url(tree)
    seller_text = " ".join([*seller_badges, seller_name or ""]).strip()
    description = _extract_detail_description(tree)
    evidence_text = " ".join(part for part in [detail_title, description] if part).strip()
    rooms = _extract_rooms(detail_params.get("liczba pokoi"))
    if rooms is None:
        rooms = _extract_rooms_from_room_type(detail_params.get("rodzaj pokoju"))
    if rooms is None:
        rooms = _extract_rooms_from_text(evidence_text)

    floor = detail_params.get("poziom") or detail_params.get("piętro")
    if not floor:
        floor = _extract_floor_from_text(evidence_text)

    rent_additional, rent_additional_currency = _extract_additional_rent(
        detail_params=detail_params,
        evidence_text=evidence_text,
    )

    return {
        "description": description,
        "area_sqm": _extract_area_sqm(detail_params.get("powierzchnia")),
        "rooms": rooms,
        "floor": floor,
        "rent_additional": rent_additional,
        "rent_additional_currency": rent_additional_currency,
        "building_type": detail_params.get("rodzaj zabudowy"),
        "market_type": detail_params.get("rynek"),
        "furnished": _extract_yes_no(detail_params.get("umeblowane")),
        "elevator": _extract_yes_no(detail_params.get("winda")),
        "pets_allowed": _extract_yes_no(detail_params.get("zwierzęta")),
        "room_type": detail_params.get("rodzaj pokoju"),
        "parking": True if detail_params.get("parking") else None,
        "preferred_tenants": detail_params.get("preferowani"),
        "building_floors": _extract_building_floors(detail_params.get("liczba pięter")),
        "land_area_sqm": _extract_area_sqm(detail_params.get("powierzchnia działki")),
        "price_per_sqm_source": _extract_price_per_sqm(detail_params.get("cena za m²")),
        "seller_segment": _seller_segment_from_text(seller_text),
        "seller_type": _seller_type_from_text(seller_text),
        "seller_name": seller_name,
        "seller_profile_url": seller_profile_url,
        "detail_params": detail_params,
    }


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

        area_sqm = _extract_area_sqm(seller_text)
        rooms = _extract_rooms_from_text(seller_text)
        price_per_sqm_source = _extract_price_per_sqm(seller_text)

        listings.append(
            {
                "source": "olx",
                "source_listing_id": source_listing_id,
                "source_url": source_url,
                "title": title,
                "description": seller_text,
                "price_total": price_total,
                "price_per_sqm_source": price_per_sqm_source,
                "currency": currency,
                "area_sqm": area_sqm,
                "rooms": rooms,
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
            area_sqm = _extract_area_sqm(evidence)
            rooms = _extract_rooms_from_text(evidence)
            price_per_sqm_source = _extract_price_per_sqm(evidence)

            listings.append(
                {
                    "source": "olx",
                    "source_listing_id": source_listing_id,
                    "source_url": source_url,
                    "title": str(offer.get("name", "")).strip(),
                    "description": str(offer.get("description", "")).strip(),
                    "price_total": price_total,
                    "price_per_sqm_source": price_per_sqm_source,
                    "currency": price_currency,
                    "area_sqm": area_sqm,
                    "rooms": rooms,
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


def _extract_detail_description(tree: HTMLParser) -> str | None:
    for script in tree.css("script[type='application/ld+json']"):
        raw_json = (script.text() or "").strip()
        if not raw_json:
            continue
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        description = str(payload.get("description", "")).strip()
        if description:
            return description

    description_node = tree.css_first("[data-cy='ad_description']")
    if description_node is None:
        return None
    text = description_node.text(separator=" ", strip=True)
    return text or None


def _extract_detail_parameters(tree: HTMLParser) -> tuple[dict[str, str], list[str]]:
    parameters: dict[str, str] = {}
    seller_badges: list[str] = []

    for node in tree.css("p[data-nx-name='P3']"):
        text = _clean_p3_text(node.text(separator=" ", strip=True))
        if not text:
            continue

        key_value_match = re.match(r"^([^:]{1,80}):\s+(.+)$", text)
        if key_value_match is not None:
            key = key_value_match.group(1).strip()
            value = key_value_match.group(2).strip()
            normalized_key = key.casefold()
            if _is_valid_parameter_key(normalized_key) and value:
                parameters[normalized_key] = value
                continue
        seller_badges.append(text)

    return parameters, seller_badges


def _clean_p3_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    normalized = re.sub(r"^\s*\.css-[^{]+\{[^}]*\}\s*", "", normalized)
    return normalized.strip()


def _is_valid_parameter_key(key: str) -> bool:
    if not key or key.startswith(".css"):
        return False
    if len(key) > 80:
        return False
    return bool(re.search(r"[a-ząćęłńóśźż]", key, flags=re.IGNORECASE))


def _extract_area_sqm(area_text: str | None) -> float | None:
    if not area_text:
        return None
    normalized = area_text.replace(",", ".")
    match = re.search(r"(\d{1,4}(?:\.\d{1,2})?)\s*(?:m2|m\^2|m²)", normalized, re.IGNORECASE)
    if match is None:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _extract_price_per_sqm(price_per_sqm_text: str | None) -> float | None:
    if not price_per_sqm_text:
        return None
    normalized = price_per_sqm_text.replace("\xa0", " ").replace(",", ".")
    match = re.search(r"(\d[\d\s]*(?:\.\d+)?)\s*(?:zł|pln)", normalized, flags=re.IGNORECASE)
    if match is None:
        return None
    value = re.sub(r"\s+", "", match.group(1))
    try:
        return float(value)
    except ValueError:
        return None


def _extract_rooms(rooms_text: str | None) -> float | None:
    if not rooms_text:
        return None
    normalized = rooms_text.casefold()
    if "kawaler" in normalized:
        return 1.0
    match = re.search(r"(\d+(?:[.,]\d+)?)", normalized)
    if match is None:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


def _extract_rooms_from_room_type(room_type_text: str | None) -> float | None:
    if not room_type_text:
        return None
    return 1.0


def _extract_rooms_from_text(text: str | None) -> float | None:
    if not text:
        return None
    normalized = text.replace("\xa0", " ").casefold()
    match = re.search(
        r"(\d+(?:[.,]\d+)?)\s*(?:pok(?:oi|oje|ój|ojowe)?|pok\.)(?=\W|$)",
        normalized,
    )
    if match is None:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


def _extract_floor_from_text(text: str | None) -> str | None:
    if not text:
        return None
    normalized = text.replace("\xa0", " ").casefold()
    match = re.search(r"\b(\d{1,2})\s*pi(?:e|ę)tr(?:ze|o|a)\b", normalized)
    if match is not None:
        return match.group(1)
    if re.search(r"\bna parterze\b", normalized):
        return "0"
    return None


def _extract_additional_rent(
    *, detail_params: dict[str, str], evidence_text: str | None
) -> tuple[float | None, str | None]:
    for key, value in detail_params.items():
        normalized_key = key.casefold()
        is_additional_czynsz = "czynsz" in normalized_key and (
            "dodatk" in normalized_key or "administr" in normalized_key
        )
        if is_additional_czynsz:
            parsed = _extract_price_fields(value)
            if parsed[0] is not None:
                return parsed
        if "opłat" in normalized_key and "administr" in normalized_key:
            parsed = _extract_price_fields(value)
            if parsed[0] is not None:
                return parsed

    if not evidence_text:
        return None, None

    normalized_text = evidence_text.replace("\xa0", " ")
    match = re.search(
        (
            r"(?:czynsz\s+administracyjny|czynsz\s*\(dodatkowo\)|"
            r"op(?:ł|l)ata\s+administracyjna|op(?:ł|l)aty\s+administracyjne)"
            r"\D{0,20}(\d[\d\s]{1,10})\s*(zł|pln)"
        ),
        normalized_text,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None, None
    digits = re.sub(r"\D", "", match.group(1))
    if not digits:
        return None, None
    return float(digits), "PLN"


def _extract_yes_no(text: str | None) -> bool | None:
    if not text:
        return None
    normalized = text.casefold()
    if normalized.startswith("tak"):
        return True
    if normalized.startswith("nie"):
        return False
    return None


def _extract_building_floors(text: str | None) -> int | None:
    if not text:
        return None
    normalized = text.casefold()
    if "dwupiętrowy" in normalized or "dwu piętrowy" in normalized:
        return 2
    if "jednopiętrowy" in normalized or "jedno piętrowy" in normalized:
        return 1
    if "parterowy z użytkowym poddaszem" in normalized:
        return 1
    if "parterowy" in normalized:
        return 0
    return None


def _extract_seller_name(tree: HTMLParser) -> str | None:
    node = tree.css_first("[data-testid='user-profile-user-name']")
    if node is None:
        return None
    value = node.text(separator=" ", strip=True)
    return value or None


def _extract_seller_profile_url(tree: HTMLParser) -> str | None:
    node = tree.css_first("a[data-testid='user-profile-link'][href]")
    if node is None:
        return None
    raw_url = (node.attributes.get("href") or "").strip()
    if not raw_url:
        return None
    if raw_url.startswith("/"):
        return f"https://www.olx.pl{raw_url}"
    return raw_url


def _extract_detail_title(tree: HTMLParser) -> str | None:
    for script in tree.css("script[type='application/ld+json']"):
        raw_json = (script.text() or "").strip()
        if not raw_json:
            continue
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        title = str(payload.get("name", "")).strip()
        if title:
            return title
    return None


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
            enriched["description"] = jsonld.get("description") or enriched.get("description")
            enriched["price_total"] = jsonld.get("price_total") or enriched.get("price_total")
            enriched["price_per_sqm_source"] = (
                jsonld.get("price_per_sqm_source") or enriched.get("price_per_sqm_source")
            )
            enriched["currency"] = jsonld.get("currency") or enriched.get("currency")
            enriched["area_sqm"] = jsonld.get("area_sqm") or enriched.get("area_sqm")
            enriched["rooms"] = jsonld.get("rooms") or enriched.get("rooms")
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

def _parse_prerendered_state(tree: HTMLParser) -> dict[str, dict]:
    for script in tree.css("script"):
        text = script.text()
        if text and "__PRERENDERED_STATE__" in text:
            match = re.search(r'__PRERENDERED_STATE__\s*=\s*"(.*?)";', text)
            if match:
                try:
                    raw_state = match.group(1).encode("utf-8").decode("unicode_escape")
                    state = json.loads(raw_state)
                    ads = state.get("listing", {}).get("listing", {}).get("ads", [])
                    prerendered_data = {}
                    for ad in ads:
                        ad_id = str(ad.get("id"))
                        if not ad_id:
                            continue
                        olx_id = f"olx-{ad_id}"
                        
                        params_raw = ad.get("params", [])
                        params_dict = {}
                        for p in params_raw:
                            if "name" in p and "value" in p:
                                params_dict[p["name"].casefold()] = str(p["value"]).strip()
                                
                        desc = ad.get("description", "").replace("<br />", "\n").strip()
                        title = ad.get("title", "").strip()
                        
                        prerendered_data[olx_id] = {
                            "detail_params": params_dict,
                            "description": desc,
                            "title": title
                        }
                    return prerendered_data
                except Exception:
                    pass
    return {}

def _merge_with_prerendered(merged: list[dict], prerendered_state: dict[str, dict]) -> list[dict]:
    for item in merged:
        listing_id = item.get("source_listing_id")
        if listing_id and listing_id in prerendered_state:
            data = prerendered_state[listing_id]
            if data.get("description"):
                item["description"] = data["description"]
            if data.get("title") and not item.get("title"):
                item["title"] = data["title"]
            
            # Use parser regexes on detail_params if available!
            params = data.get("detail_params", {})
            if params:
                item["detail_params"] = params
                if not item.get("area_sqm"):
                    item["area_sqm"] = _extract_area_sqm(params.get("powierzchnia"))
                if not item.get("rooms"):
                    item["rooms"] = _extract_rooms(params.get("liczba pokoi"))
                if not item.get("floor"):
                    item["floor"] = params.get("poziom") or params.get("piętro")
                if not item.get("price_per_sqm_source"):
                    item["price_per_sqm_source"] = _extract_price_per_sqm(params.get("cena za m²"))
                    
    return merged
