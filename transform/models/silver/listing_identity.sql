{{ config(
    materialized='incremental',
    unique_key=['source', 'source_listing_id', 'mode']
) }}

SELECT 
    source, 
    source_listing_id, 
    mode, 
    first_seen_at, 
    last_seen_at,
    TRUE as is_active
FROM {{ ref('stg_bronze_listings') }}
