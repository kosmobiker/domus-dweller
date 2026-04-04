import re

from selectolax.parser import HTMLParser


def _seller_segment_from_text(seller_text: str) -> str:
    normalized = seller_text.casefold()
    if "biuro" in normalized or "agenc" in normalized or "deweloper" in normalized:
        return "professional"
    if "prywat" in normalized or "wlasciciel" in normalized:
        return "private"
    return "unknown"


def parse_search_results(raw_html: str) -> list[dict]:
    tree = HTMLParser(raw_html)
    listings: list[dict] = []
    seen_ids: set[str] = set()

    for card in tree.css("article[data-cy='listing-item']"):
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
                "source": "otodom",
                "source_listing_id": source_listing_id,
                "source_url": source_url,
                "title": title,
                "price_total": price_total,
                "currency": currency,
                "seller_segment": _seller_segment_from_text(seller_text),
            }
        )

    return listings


def _extract_price_fields(text: str) -> tuple[float | None, str | None]:
    normalized = text.replace("\xa0", " ")
    match = re.search(r"(\d[\d\s]*)\s*(zł|pln)", normalized, flags=re.IGNORECASE)
    if not match:
        return None, None
    digits = re.sub(r"\D", "", match.group(1))
    if not digits:
        return None, None
    return float(digits), "PLN"
