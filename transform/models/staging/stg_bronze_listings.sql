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
        (raw_json::JSON)->>'city' as city,
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
        (raw_json::JSON)->>'city' as city,
        (raw_json::JSON)->>'district' as district,
        (raw_json::JSON)->>'location_approx' as location_approx,
        CAST((raw_json::JSON)->>'latitude' AS DOUBLE) as latitude,
        CAST((raw_json::JSON)->>'longitude' AS DOUBLE) as longitude
    FROM {{ source('bronze', 'sale_bronze') }}
    WHERE snapshot_date = (SELECT max_date FROM latest_sale)
)
SELECT * EXCLUDE(snapshot_date) FROM combined
QUALIFY ROW_NUMBER() OVER(PARTITION BY source, source_listing_id, mode ORDER BY ingested_at DESC) = 1
