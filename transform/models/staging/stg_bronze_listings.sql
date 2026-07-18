WITH combined AS (
    SELECT 
        source,
        source_listing_id,
        mode,
        ingested_at,
        raw_json,
        (raw_json::JSON)->>'title' as title,
        CAST((raw_json::JSON)->>'price_total' AS DOUBLE) as price_total,
        CAST((raw_json::JSON)->>'price_per_sqm_source' AS DOUBLE) as price_per_sqm,
        (raw_json::JSON)->>'currency' as currency,
        CAST((raw_json::JSON)->>'area_sqm' AS DOUBLE) as area_sqm,
        CAST((raw_json::JSON)->>'rooms' AS DOUBLE) as rooms,
        (raw_json::JSON)->>'floor' as floor,
        (raw_json::JSON)->>'building_type' as building_type,
        (raw_json::JSON)->>'market_type' as market_type,
        (raw_json::JSON)->>'seller_segment' as seller_segment,
        (raw_json::JSON)->>'city' as city,
        (raw_json::JSON)->>'district' as district
    FROM {{ source('bronze', 'rent_bronze') }}
    UNION ALL
    SELECT 
        source,
        source_listing_id,
        mode,
        ingested_at,
        raw_json,
        (raw_json::JSON)->>'title' as title,
        CAST((raw_json::JSON)->>'price_total' AS DOUBLE) as price_total,
        CAST((raw_json::JSON)->>'price_per_sqm_source' AS DOUBLE) as price_per_sqm,
        (raw_json::JSON)->>'currency' as currency,
        CAST((raw_json::JSON)->>'area_sqm' AS DOUBLE) as area_sqm,
        CAST((raw_json::JSON)->>'rooms' AS DOUBLE) as rooms,
        (raw_json::JSON)->>'floor' as floor,
        (raw_json::JSON)->>'building_type' as building_type,
        (raw_json::JSON)->>'market_type' as market_type,
        (raw_json::JSON)->>'seller_segment' as seller_segment,
        (raw_json::JSON)->>'city' as city,
        (raw_json::JSON)->>'district' as district
    FROM {{ source('bronze', 'sale_bronze') }}
),
deduplicated AS (
    SELECT 
        *, 
        ROW_NUMBER() OVER(PARTITION BY source, source_listing_id, mode ORDER BY ingested_at DESC) as rn,
        MIN(ingested_at) OVER(PARTITION BY source, source_listing_id, mode) as first_seen_at,
        MAX(ingested_at) OVER(PARTITION BY source, source_listing_id, mode) as last_seen_at
    FROM combined
)
SELECT * EXCLUDE(rn) FROM deduplicated WHERE rn = 1
