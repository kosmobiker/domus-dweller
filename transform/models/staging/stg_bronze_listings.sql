WITH latest_rent AS (
    SELECT MAX(snapshot_date) as max_date FROM {{ source('bronze', 'rent_bronze') }}
),
latest_sale AS (
    SELECT MAX(snapshot_date) as max_date FROM {{ source('bronze', 'sale_bronze') }}
),
rent_raw AS (
    SELECT 
        source,
        source_listing_id,
        mode,
        snapshot_date,
        ingested_at,
        raw_json::JSON as j
    FROM {{ source('bronze', 'rent_bronze') }}
    WHERE snapshot_date = (SELECT max_date FROM latest_rent)
),
sale_raw AS (
    SELECT 
        source,
        source_listing_id,
        mode,
        snapshot_date,
        ingested_at,
        raw_json::JSON as j
    FROM {{ source('bronze', 'sale_bronze') }}
    WHERE snapshot_date = (SELECT max_date FROM latest_sale)
),
combined_raw AS (
    SELECT * FROM rent_raw
    UNION ALL
    SELECT * FROM sale_raw
),
    extracted AS (
    SELECT
        source,
        source_listing_id,
        mode,
        snapshot_date,
        ingested_at,
        j->>'title' as title,
        CAST(j->>'price_total' AS DOUBLE) as price_total,
        CAST(j->>'price_per_sqm_source' AS DOUBLE) as price_per_sqm_source,
        j->>'currency' as currency,
        CAST(j->>'area_sqm' AS DOUBLE) as area_sqm,
        CAST(j->>'rooms' AS DOUBLE) as rooms,
        j->>'floor' as floor,
        COALESCE(j->>'seller_segment', 'unknown') as seller_segment,
        j->>'city' as json_city,
        j->>'municipality' as json_municipality,
        j->>'district' as raw_district,
        j->>'location_approx' as raw_location_approx,
        CAST(j->>'latitude' AS DOUBLE) as latitude,
        CAST(j->>'longitude' AS DOUBLE) as longitude
    FROM combined_raw
),
enriched_location AS (
    SELECT
        *,
        {{ extract_district('raw_district', 'raw_location_approx', 'title') }} as district
    FROM extracted
),
normalized AS (
    SELECT
        source,
        source_listing_id,
        mode,
        snapshot_date,
        ingested_at,
        title,
        price_total,
        COALESCE(
            price_per_sqm_source,
            ROUND(price_total / NULLIF(area_sqm, 0), 2)
        ) as price_per_sqm,
        currency,
        area_sqm,
        rooms,
        floor,
        seller_segment,
        COALESCE(
            json_city,
            json_municipality,
            CASE
                WHEN raw_location_approx ILIKE '%kraków%' OR raw_location_approx ILIKE '%krakow%' THEN 'Kraków'
                WHEN raw_location_approx ILIKE '%wieliczka%' THEN 'Wieliczka'
                WHEN raw_location_approx ILIKE '%skawina%' THEN 'Skawina'
                WHEN raw_location_approx ILIKE '%niepołomice%' OR raw_location_approx ILIKE '%niepolomice%' THEN 'Niepołomice'
                WHEN raw_location_approx ILIKE '%zabierzów%' OR raw_location_approx ILIKE '%zabierzow%' THEN 'Zabierzów'
                WHEN raw_location_approx ILIKE '%zielonki%' THEN 'Zielonki'
                WHEN raw_location_approx ILIKE '%świątniki%' OR raw_location_approx ILIKE '%swiatniki%' THEN 'Świątniki Górne'
                WHEN district IN (
                    'Stare Miasto', 'Grzegórzki', 'Prądnik Czerwony', 'Prądnik Biały',
                    'Krowodrza', 'Bronowice', 'Zwierzyniec', 'Dębniki',
                    'Łagiewniki-Borek Fałęcki', 'Swoszowice', 'Podgórze Duchackie',
                    'Bieżanów-Prokocim', 'Podgórze', 'Czyżyny', 'Mistrzejowice',
                    'Bieńczyce', 'Wzgórza Krzesławickie', 'Nowa Huta'
                ) THEN 'Kraków'
                WHEN district IN (
                    'Wieliczka', 'Skawina', 'Niepołomice', 'Zabierzów', 'Zielonki', 'Świątniki Górne'
                ) THEN district
                ELSE NULL
            END
        ) as city,
        district,
        COALESCE(
            raw_location_approx,
            CASE
                WHEN district IN (
                    'Stare Miasto', 'Grzegórzki', 'Prądnik Czerwony', 'Prądnik Biały',
                    'Krowodrza', 'Bronowice', 'Zwierzyniec', 'Dębniki',
                    'Łagiewniki-Borek Fałęcki', 'Swoszowice', 'Podgórze Duchackie',
                    'Bieżanów-Prokocim', 'Podgórze', 'Czyżyny', 'Mistrzejowice',
                    'Bieńczyce', 'Wzgórza Krzesławickie', 'Nowa Huta'
                ) THEN 'Kraków, ' || district
                WHEN district IS NOT NULL AND (json_city IS NOT NULL OR json_municipality IS NOT NULL)
                THEN COALESCE(json_city, json_municipality) || ', ' || district
                WHEN district IS NOT NULL THEN district
                ELSE NULL
            END
        ) as location_approx,
        latitude,
        longitude
    FROM enriched_location
)
SELECT * EXCLUDE(snapshot_date) FROM normalized
QUALIFY ROW_NUMBER() OVER(PARTITION BY source, source_listing_id, mode ORDER BY ingested_at DESC) = 1

