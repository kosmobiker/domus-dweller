WITH latest_rent AS (
    SELECT MAX(snapshot_date) as max_date FROM {{ source('bronze', 'rent_bronze') }}
),
latest_sale AS (
    SELECT MAX(snapshot_date) as max_date FROM {{ source('bronze', 'sale_bronze') }}
),
combined AS (
    SELECT 
        source,
        source_listing_id,
        mode,
        snapshot_date,
        ingested_at,
        (raw_json::JSON)->>'title' as title,
        CAST((raw_json::JSON)->>'price_total' AS DOUBLE) as price_total,
        COALESCE(
            CAST((raw_json::JSON)->>'price_per_sqm_source' AS DOUBLE),
            ROUND(CAST((raw_json::JSON)->>'price_total' AS DOUBLE) / NULLIF(CAST((raw_json::JSON)->>'area_sqm' AS DOUBLE), 0), 2)
        ) as price_per_sqm,
        (raw_json::JSON)->>'currency' as currency,
        CAST((raw_json::JSON)->>'area_sqm' AS DOUBLE) as area_sqm,
        CAST((raw_json::JSON)->>'rooms' AS DOUBLE) as rooms,
        (raw_json::JSON)->>'floor' as floor,
        COALESCE((raw_json::JSON)->>'seller_segment', 'unknown') as seller_segment,
        COALESCE(
            (raw_json::JSON)->>'city',
            (raw_json::JSON)->>'municipality',
            CASE
                WHEN (raw_json::JSON)->>'location_approx' ILIKE '%kraków%' OR (raw_json::JSON)->>'location_approx' ILIKE '%krakow%' THEN 'Kraków'
                WHEN (raw_json::JSON)->>'location_approx' ILIKE '%wieliczka%' THEN 'Wieliczka'
                WHEN (raw_json::JSON)->>'location_approx' ILIKE '%skawina%' THEN 'Skawina'
                WHEN (raw_json::JSON)->>'location_approx' ILIKE '%niepołomice%' OR (raw_json::JSON)->>'location_approx' ILIKE '%niepolomice%' THEN 'Niepołomice'
                WHEN (raw_json::JSON)->>'location_approx' ILIKE '%zabierzów%' OR (raw_json::JSON)->>'location_approx' ILIKE '%zabierzow%' THEN 'Zabierzów'
                WHEN (raw_json::JSON)->>'location_approx' ILIKE '%zielonki%' THEN 'Zielonki'
                WHEN (raw_json::JSON)->>'location_approx' ILIKE '%świątniki%' OR (raw_json::JSON)->>'location_approx' ILIKE '%swiatniki%' THEN 'Świątniki Górne'
                WHEN (raw_json::JSON)->>'district' IN (
                    'Stare Miasto', 'Grzegórzki', 'Prądnik Czerwony', 'Prądnik Biały',
                    'Krowodrza', 'Bronowice', 'Zwierzyniec', 'Dębniki',
                    'Łagiewniki-Borek Fałęcki', 'Swoszowice', 'Podgórze Duchackie',
                    'Bieżanów-Prokocim', 'Podgórze', 'Czyżyny', 'Mistrzejowice',
                    'Bieńczyce', 'Wzgórza Krzesławickie', 'Nowa Huta'
                ) THEN 'Kraków'
                ELSE NULL
            END
        ) as city,
        (raw_json::JSON)->>'district' as district,
        (raw_json::JSON)->>'location_approx' as location_approx,
        CAST((raw_json::JSON)->>'latitude' AS DOUBLE) as latitude,
        CAST((raw_json::JSON)->>'longitude' AS DOUBLE) as longitude
    FROM {{ source('bronze', 'rent_bronze') }}
    WHERE snapshot_date = (SELECT max_date FROM latest_rent)
    UNION ALL
    SELECT 
        source,
        source_listing_id,
        mode,
        snapshot_date,
        ingested_at,
        (raw_json::JSON)->>'title' as title,
        CAST((raw_json::JSON)->>'price_total' AS DOUBLE) as price_total,
        COALESCE(
            CAST((raw_json::JSON)->>'price_per_sqm_source' AS DOUBLE),
            ROUND(CAST((raw_json::JSON)->>'price_total' AS DOUBLE) / NULLIF(CAST((raw_json::JSON)->>'area_sqm' AS DOUBLE), 0), 2)
        ) as price_per_sqm,
        (raw_json::JSON)->>'currency' as currency,
        CAST((raw_json::JSON)->>'area_sqm' AS DOUBLE) as area_sqm,
        CAST((raw_json::JSON)->>'rooms' AS DOUBLE) as rooms,
        (raw_json::JSON)->>'floor' as floor,
        COALESCE((raw_json::JSON)->>'seller_segment', 'unknown') as seller_segment,
        COALESCE(
            (raw_json::JSON)->>'city',
            (raw_json::JSON)->>'municipality',
            CASE
                WHEN (raw_json::JSON)->>'location_approx' ILIKE '%kraków%' OR (raw_json::JSON)->>'location_approx' ILIKE '%krakow%' THEN 'Kraków'
                WHEN (raw_json::JSON)->>'location_approx' ILIKE '%wieliczka%' THEN 'Wieliczka'
                WHEN (raw_json::JSON)->>'location_approx' ILIKE '%skawina%' THEN 'Skawina'
                WHEN (raw_json::JSON)->>'location_approx' ILIKE '%niepołomice%' OR (raw_json::JSON)->>'location_approx' ILIKE '%niepolomice%' THEN 'Niepołomice'
                WHEN (raw_json::JSON)->>'location_approx' ILIKE '%zabierzów%' OR (raw_json::JSON)->>'location_approx' ILIKE '%zabierzow%' THEN 'Zabierzów'
                WHEN (raw_json::JSON)->>'location_approx' ILIKE '%zielonki%' THEN 'Zielonki'
                WHEN (raw_json::JSON)->>'location_approx' ILIKE '%świątniki%' OR (raw_json::JSON)->>'location_approx' ILIKE '%swiatniki%' THEN 'Świątniki Górne'
                WHEN (raw_json::JSON)->>'district' IN (
                    'Stare Miasto', 'Grzegórzki', 'Prądnik Czerwony', 'Prądnik Biały',
                    'Krowodrza', 'Bronowice', 'Zwierzyniec', 'Dębniki',
                    'Łagiewniki-Borek Fałęcki', 'Swoszowice', 'Podgórze Duchackie',
                    'Bieżanów-Prokocim', 'Podgórze', 'Czyżyny', 'Mistrzejowice',
                    'Bieńczyce', 'Wzgórza Krzesławickie', 'Nowa Huta'
                ) THEN 'Kraków'
                ELSE NULL
            END
        ) as city,
        (raw_json::JSON)->>'district' as district,
        (raw_json::JSON)->>'location_approx' as location_approx,
        CAST((raw_json::JSON)->>'latitude' AS DOUBLE) as latitude,
        CAST((raw_json::JSON)->>'longitude' AS DOUBLE) as longitude
    FROM {{ source('bronze', 'sale_bronze') }}
    WHERE snapshot_date = (SELECT max_date FROM latest_sale)
)
SELECT * EXCLUDE(snapshot_date) FROM combined
QUALIFY ROW_NUMBER() OVER(PARTITION BY source, source_listing_id, mode ORDER BY ingested_at DESC) = 1
