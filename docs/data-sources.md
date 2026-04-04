# Data Sources

## Active Source (Now)

1. OLX

Current implementation is OLX-only. Otodom and other portals are deferred.

## Scope Rules (v1)

- Geography: Krakow + ~30 km radius.
- Property scope: residential only.
- Exclude commercial real estate.
- Keep rent and sale as separate tracks.

## Collection Policy

Use the safest path in this order:

1. Official APIs/exports with legitimate access.
2. Public listing pages and public embedded data.
3. Browser automation only as a fallback.

Do not rely on login-gated access or anti-bot bypassing.

## OLX Adapter Contract

Each parsed listing should preserve:

- `source`
- `source_listing_id`
- `source_url`
- `title`
- `description`
- `price_total`
- `currency`
- `mode` (`rent` or `sale`)
- location signals (`city`, `district`, `municipality`, `location_approx`)
- structural fields (`area_sqm`, `rooms`, `floor`)
- seller fields (`seller_segment`, `seller_type`, `seller_name`, `seller_profile_url`)
- `detail_params` (full raw parameter map)
- `images`
- `snapshot_date`
- `layer` (`bronze`)

## Seller Classification

Mandatory normalized labels:

- `seller_segment`: `private`, `professional`, `unknown`
- `seller_type`: `private`, `agency`, `developer`, `unknown`

When uncertain, keep `unknown` and preserve raw evidence in payload fields.

## Dedup/SCD Policy

- Bronze: append everything, no dedup, no SCD.
- Silver: dedup and SCD logic (`is_current`, `valid_from`, `valid_to`).
