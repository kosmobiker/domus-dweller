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
    for s in tree.css("style"):
        s.decompose()
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

    for card in tree.css("[data-cy='l-card'], article[data-cy='l-card']"):
        link = card.css_first("a[data-testid='card-title-link']") or card.css_first("a[href]")
        source_url = ""
        title = ""
        if link is not None:
            source_url = (link.attributes.get("href") or "").strip()
            if source_url.startswith("/"):
                source_url = f"https://www.olx.pl{source_url}"
            title = link.text(separator=" ", strip=True)

        h4 = card.css_first("h4")
        if h4 is not None:
            title = h4.text(strip=True)
        elif link is not None and link.attributes.get("aria-label"):
            title = link.attributes.get("aria-label", "").strip()

        source_listing_id = (card.attributes.get("data-id") or "").strip()
        if not source_listing_id and source_url:
            source_listing_id = _extract_olx_listing_id(source_url)
        if not source_listing_id:
            raw_card_id = (card.attributes.get("id") or "").strip()
            if raw_card_id:
                source_listing_id = f"olx-{raw_card_id}"

        if not source_listing_id or not source_url or source_listing_id in seen_ids:
            continue
        seen_ids.add(source_listing_id)

        raw_id = (card.attributes.get("id") or "").strip()
        source_numeric_id = f"olx-{raw_id}" if raw_id and raw_id.isdigit() else None

        seller_text = " ".join(
            node.text(separator=" ", strip=True) for node in card.css("span, p, div")
        ).strip()
        seller_text = _clean_p3_text(seller_text)
        price_node = card.css_first('[data-testid="ad-price"]')
        if price_node:
            price_total, currency = _extract_price_fields(price_node.text(strip=True))
        else:
            price_total, currency = _extract_price_fields(seller_text)
        if price_total is None and seller_text:
            price_total, currency = _extract_price_fields(seller_text)

        area_sqm = _extract_area_sqm(seller_text)
        rooms = _extract_rooms_from_text(seller_text)
        price_per_sqm_source = _extract_price_per_sqm(seller_text)

        item = {
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
            "latitude": None,
            "longitude": None,
            "images": [],
            "price_valid_until": None,
            "seller_segment": _seller_segment_from_text(seller_text),
        }
        if source_numeric_id:
            item["source_numeric_id"] = source_numeric_id
        listings.append(item)

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
                    "latitude": None,
                    "longitude": None,
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
    if not text:
        return None, None
    normalized = text.replace("\xa0", " ")
    match = re.search(
        r"(\d[\d\s]*(?:[.,]\d+)?)\s*(zł|pln|zl)(?![\s]*(?:/|za\s*)m(?:²|2|\b))",
        normalized,
        flags=re.IGNORECASE,
    )
    if not match:
        return None, None
    raw_num = match.group(1).replace(" ", "").replace(",", ".")
    try:
        return float(raw_num), "PLN"
    except ValueError:
        return None, None


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
    normalized = price_per_sqm_text.replace("\xa0", " ")
    match = re.search(
        r"(\d[\d\s]*(?:[.,]\d+)?)\s*(?:zł|pln|zl)?[\s]*(?:/|za\s*)m(?:²|2|\b)",
        normalized,
        flags=re.IGNORECASE,
    )
    if match is None:
        match = re.search(r"^\s*(\d[\d\s]*(?:[.,]\d+)?)\s*$", normalized)
    if match is None:
        return None
    value = match.group(1).replace(" ", "").replace(",", ".")
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
        r"\b(\d{1,2}(?:[.,]\d+)?)\s*(?:pok(?:oi|oje|ój|ojowe)?|pok\.)(?=\W|$)",
        normalized,
    )
    if match is not None:
        try:
            val = float(match.group(1).replace(",", "."))
            if 1.0 <= val <= 20.0:
                return val
        except ValueError:
            pass
    if re.search(r"\b(kawalerka|kawalerk[aęi]|garsoniera|garsonier[aęi])\b", normalized):
        return 1.0
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
    breadcrumb_city = None
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

        if payload.get("@type") == "BreadcrumbList":
            items = payload.get("itemListElement", [])
            for item in reversed(items):
                name = str(item.get("name", "")).strip()
                if " - " in name:
                    candidate = name.split(" - ")[-1].strip()
                    if candidate and candidate not in {"Małopolskie", "Polska"}:
                        breadcrumb_city = candidate
                        break
                elif name in {
                    "Kraków",
                    "Wieliczka",
                    "Skawina",
                    "Niepołomice",
                    "Zabierzów",
                    "Zielonki",
                    "Świątniki Górne",
                }:
                    breadcrumb_city = name
                    break

    return breadcrumb_city


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
            enriched["price_per_sqm_source"] = jsonld.get("price_per_sqm_source") or enriched.get(
                "price_per_sqm_source"
            )
            enriched["currency"] = jsonld.get("currency") or enriched.get("currency")
            enriched["area_sqm"] = jsonld.get("area_sqm") or enriched.get("area_sqm")
            enriched["district"] = jsonld.get("district") or enriched.get("district")
            enriched["city"] = jsonld.get("city") or enriched.get("city")
            enriched["municipality"] = jsonld.get("municipality") or enriched.get("municipality")
            enriched["location_approx"] = (
                jsonld.get("location_approx") or enriched.get("location_approx")
            )
            enriched["latitude"] = (
                jsonld.get("latitude")
                if jsonld.get("latitude") is not None
                else enriched.get("latitude")
            )
            enriched["longitude"] = (
                jsonld.get("longitude")
                if jsonld.get("longitude") is not None
                else enriched.get("longitude")
            )
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
                raw_s = match.group(1)
                state = None
                try:
                    decoded_js = json.loads('"' + raw_s + '"')
                    state = json.loads(decoded_js)
                except Exception:
                    try:
                        raw_state = raw_s.encode("utf-8").decode("unicode_escape")
                        state = json.loads(raw_state)
                    except Exception:
                        pass
                if not state or not isinstance(state, dict):
                    continue

                ads = state.get("listing", {}).get("listing", {}).get("ads", [])
                prerendered_data = {}
                for ad in ads:
                    ad_id = str(ad.get("id") or "").strip()
                    url = str(ad.get("url") or ad.get("urlPath") or "").strip()
                    short_id = _extract_olx_listing_id(url)
                    if not ad_id and not short_id:
                        continue

                    params_raw = ad.get("params", [])
                    params_dict = {}
                    for p in params_raw:
                        if isinstance(p, dict) and "name" in p and "value" in p:
                            params_dict[str(p["name"]).casefold()] = str(p["value"]).strip()

                    desc = str(ad.get("description") or "").replace("<br />", "\n").strip()
                    title = str(ad.get("title") or "").strip()
                    is_business = ad.get("isBusiness")
                    seller_segment = None
                    if is_business is False:
                        seller_segment = "private"
                    elif is_business is True:
                        seller_segment = "professional"

                    price_obj = ad.get("price")
                    price_total = None
                    currency = None
                    if isinstance(price_obj, dict):
                        regular_price = price_obj.get("regularPrice")
                        if isinstance(regular_price, dict):
                            val = regular_price.get("value")
                            if isinstance(val, (int, float)):
                                price_total = float(val)
                            curr_code = regular_price.get("currencyCode")
                            if curr_code:
                                currency = str(curr_code).strip()
                        if price_total is None and price_obj.get("displayValue"):
                            p_tot, curr = _extract_price_fields(str(price_obj["displayValue"]))
                            price_total = p_tot
                            currency = curr or currency

                    loc = ad.get("location") or {}
                    city = loc.get("cityName")
                    district = loc.get("districtName")
                    path_name = loc.get("pathName")
                    map_obj = ad.get("map") or {}
                    lat = map_obj.get("lat")
                    lon = map_obj.get("lon")

                    entry = {
                        "detail_params": params_dict,
                        "description": desc,
                        "title": title,
                        "seller_segment": seller_segment,
                        "price_total": price_total,
                        "currency": currency,
                        "city": str(city).strip() if city else None,
                        "district": str(district).strip() if district else None,
                        "location_approx": str(path_name).strip() if path_name else None,
                        "latitude": float(lat) if isinstance(lat, (int, float)) else None,
                        "longitude": float(lon) if isinstance(lon, (int, float)) else None,
                    }
                    if ad_id:
                        prerendered_data[f"olx-{ad_id}"] = entry
                        prerendered_data[ad_id] = entry
                    if short_id:
                        prerendered_data[short_id] = entry

                return prerendered_data
    return {}


def _merge_with_prerendered(merged: list[dict], prerendered_state: dict[str, dict]) -> list[dict]:
    for item in merged:
        listing_id = item.get("source_listing_id")
        numeric_id = item.get("source_numeric_id")
        data = prerendered_state.get(listing_id)
        if not data and numeric_id:
            data = prerendered_state.get(numeric_id)
        if data:
            if data.get("description"):
                item["description"] = data["description"]
            if data.get("title") and not item.get("title"):
                item["title"] = data["title"]
            needs_seller = not item.get("seller_segment") or item.get("seller_segment") == "unknown"
            if data.get("seller_segment") and needs_seller:
                item["seller_segment"] = data["seller_segment"]

            if data.get("city") and not item.get("city"):
                item["city"] = data["city"]
            if data.get("district") and not item.get("district"):
                item["district"] = data["district"]
            if data.get("location_approx") and (
                not item.get("location_approx") or item.get("location_approx") == item.get("city")
            ):
                item["location_approx"] = data["location_approx"]
            if data.get("latitude") is not None and item.get("latitude") is None:
                item["latitude"] = data["latitude"]
            if data.get("longitude") is not None and item.get("longitude") is None:
                item["longitude"] = data["longitude"]

            if data.get("price_total") is not None and (
                item.get("price_total") is None or item.get("price_total") < 100
            ):
                item["price_total"] = data["price_total"]
                if data.get("currency"):
                    item["currency"] = data["currency"]

            if data.get("city") and not item.get("municipality"):
                item["municipality"] = data["city"]

            # Use parser regexes on detail_params if available!
            params = data.get("detail_params", {})
            if params:
                item["detail_params"] = params
                prerendered_area = _extract_area_sqm(params.get("powierzchnia"))
                if prerendered_area is not None:
                    item["area_sqm"] = prerendered_area
                prerendered_rooms = _extract_rooms(params.get("liczba pokoi"))
                if prerendered_rooms is not None:
                    item["rooms"] = prerendered_rooms
                prerendered_floor = params.get("poziom") or params.get("piętro")
                if prerendered_floor:
                    item["floor"] = prerendered_floor
                prerendered_sqm = _extract_price_per_sqm(
                    params.get("cena za m²") or params.get("price_per_m")
                )
                if prerendered_sqm is not None:
                    item["price_per_sqm_source"] = prerendered_sqm

        item.pop("source_numeric_id", None)

    return merged
