# Data Sources

## Strategy

Do not start with every portal at once. Start with the easiest sources that deliver the most value.

Track only residential listings in v1:

- flats
- houses

Exclude:

- commercial
- land
- rooms, unless added explicitly later

## Collection Policy

The project should use the most defensible collection path available for each source:

1. official APIs and official export mechanisms when legitimately available
2. public listing pages and public embedded data
3. browser automation only as a fallback for public pages

The project should not rely on:

- login-gated access
- CAPTCHA bypassing
- anti-bot circumvention
- undocumented private endpoints as the core ingestion method

Recommended source order:

1. Otodom
2. OLX
3. One additional public portal
4. Facebook Marketplace only if the rest is already stable

## Why This Order

- Otodom and OLX are likely to cover a large share of the market.
- Starting with two sources is enough to validate schema, history, and map analytics.
- Facebook adds disproportionate scraping and maintenance risk.

## Per-Source Adapter Contract

Each adapter should produce:

- `source`
- `source_listing_id`
- `source_url`
- `listing_type`
- `property_type`
- `title`
- `description`
- `price_total`
- `currency`
- `area_sqm`
- `rooms`
- `address_text`
- `district`
- `municipality`
- `lat`
- `lng`
- `seller_type`
- `seller_segment`
- `seller_name`
- `seller_profile_url`
- `images`
- `raw_payload`
- `seller_evidence`

## Important Source Decisions

For every source, document:

- discovery path
- anti-bot risk
- whether login is required
- whether an official API or export path exists
- whether coordinates are present
- how seller classification is determined
- how listing disappearance is detected
- stable fields used for deduplication

## Source-Specific Notes

### OLX

- OLX has a public developer portal for API access.
- OLX `robots.txt` currently disallows many paths but explicitly allows `/api/v1/offers/`, `/api/v1/targeting/`, and `/api/v1/friendly-links/`.
- This suggests the first thing to investigate is whether the available official API access covers the listing data needed for your personal project.
- If the official path is insufficient, fall back to public listing pages rather than undocumented endpoints.

### Otodom

- Otodom is the higher-priority source for v1 because it is more focused on real estate and likely carries richer property metadata.
- Otodom rules for real-estate offices mention XML/API export paths for partners, which is a strong signal that official structured feeds exist in some contexts.
- If you do not have legitimate partner access, the default path should be public listing pages and public embedded data.

## Seller Classification

Seller classification is required from day one.

Minimum normalized fields:

- `seller_segment`: `private`, `professional`, `unknown`
- `seller_type`: `private`, `agency`, `developer`, `unknown`

Common signals:

- agency or office branding
- company profile page
- developer badge
- private-owner wording
- advertiser name and contact section

When classification is ambiguous, keep the raw evidence and mark as `unknown` instead of guessing.

## Deduplication

There are two separate dedup problems.

### Intra-source Deduplication

This is mandatory in v1.

Use:

- source listing id
- canonical source URL
- fingerprint fallback

### Cross-source Deduplication

This is optional in v1.

Only attempt it after the base pipeline is stable.

Candidate signals:

- similar title
- same or very close address
- same area
- same room count
- same images
- same price band

## Legal And Operational Note

Site policies, robots rules, and anti-bot behavior can change. Each source should be reviewed individually before production scraping. Architecture should assume adapters may break and need maintenance.
