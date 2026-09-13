{{ config(
    materialized='table'
) }}

WITH bronze_history AS (
    SELECT 
        source, 
        source_listing_id, 
        mode, 
        MIN(ingested_at) as first_seen_at, 
        MAX(ingested_at) as last_seen_at
    FROM {{ source('bronze', 'rent_bronze') }}
    GROUP BY source, source_listing_id, mode
    UNION ALL
    SELECT 
        source, 
        source_listing_id, 
        mode, 
        MIN(ingested_at) as first_seen_at, 
        MAX(ingested_at) as last_seen_at
    FROM {{ source('bronze', 'sale_bronze') }}
    GROUP BY source, source_listing_id, mode
),
combined_history AS (
    SELECT 
        source,
        source_listing_id,
        mode,
        MIN(first_seen_at) as first_seen_at,
        MAX(last_seen_at) as last_seen_at
    FROM bronze_history
    GROUP BY source, source_listing_id, mode
),
active_status AS (
    SELECT 
        source,
        source_listing_id,
        mode,
        (dbt_valid_to IS NULL) as is_active
    FROM {{ ref('listing_versions') }}
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY source, source_listing_id, mode 
        ORDER BY dbt_valid_from DESC
    ) = 1
)
SELECT 
    h.source,
    h.source_listing_id,
    h.mode,
    h.first_seen_at,
    h.last_seen_at,
    COALESCE(a.is_active, FALSE) as is_active
FROM combined_history h
LEFT JOIN active_status a 
    ON h.source = a.source 
    AND h.source_listing_id = a.source_listing_id 
    AND h.mode = a.mode
