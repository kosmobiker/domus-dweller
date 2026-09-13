{% macro seed_silver_history() %}
    {% set query %}
        CREATE SCHEMA IF NOT EXISTS silver;

        CREATE OR REPLACE TABLE silver.listing_versions AS
        WITH combined AS (
            SELECT 
                source,
                source_listing_id,
                mode,
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
            FROM bronze.rent_bronze
            UNION ALL
            SELECT 
                source,
                source_listing_id,
                mode,
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
            FROM bronze.sale_bronze
        ),
        chronological_chain AS (
            SELECT 
                *,
                lag(price_total) OVER (
                    PARTITION BY source, mode, source_listing_id 
                    ORDER BY ingested_at ASC
                ) as prev_price
            FROM combined
        ),
        filtered_changes AS (
            SELECT * FROM chronological_chain 
            WHERE prev_price IS NULL OR prev_price != price_total
        ),
        chained AS (
            SELECT 
                *,
                lead(ingested_at) OVER (
                    PARTITION BY source, mode, source_listing_id 
                    ORDER BY ingested_at ASC
                ) as next_valid_from
            FROM filtered_changes
        )
        SELECT 
            source || '-' || source_listing_id || '-' || mode as dbt_scd_id,
            source,
            source_listing_id,
            mode,
            ingested_at,
            title,
            price_total,
            price_per_sqm,
            currency,
            area_sqm,
            rooms,
            floor,
            seller_segment,
            city,
            district,
            location_approx,
            latitude,
            longitude,
            ingested_at as dbt_updated_at,
            ingested_at as dbt_valid_from,
            next_valid_from as dbt_valid_to
        FROM chained;
    {% endset %}

    {% do run_query(query) %}
    {{ print("Historical seeding complete.") }}
{% endmacro %}
