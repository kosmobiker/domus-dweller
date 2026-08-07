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
                (raw_json::JSON)->>'district' as district,
                CAST((raw_json::JSON)->>'furnished' AS BOOLEAN) as furnished,
                CAST((raw_json::JSON)->>'pets_allowed' AS BOOLEAN) as pets_allowed,
                CAST((raw_json::JSON)->>'elevator' AS BOOLEAN) as elevator,
                TRY_CAST((raw_json::JSON)->>'parking' AS BOOLEAN) as parking,
                CAST((raw_json::JSON)->>'balcony' AS BOOLEAN) as balcony,
                CAST((raw_json::JSON)->>'rent_additional' AS DOUBLE) as additional_rent_pln,
                (raw_json::JSON)->>'building_material' as building_material,
                CAST((raw_json::JSON)->>'year_built' AS INTEGER) as year_built,
                (raw_json::JSON)->>'ownership_type' as ownership_type
            FROM bronze.rent_bronze
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
                (raw_json::JSON)->>'district' as district,
                CAST((raw_json::JSON)->>'furnished' AS BOOLEAN) as furnished,
                CAST((raw_json::JSON)->>'pets_allowed' AS BOOLEAN) as pets_allowed,
                CAST((raw_json::JSON)->>'elevator' AS BOOLEAN) as elevator,
                TRY_CAST((raw_json::JSON)->>'parking' AS BOOLEAN) as parking,
                CAST((raw_json::JSON)->>'balcony' AS BOOLEAN) as balcony,
                CAST((raw_json::JSON)->>'rent_additional' AS DOUBLE) as additional_rent_pln,
                (raw_json::JSON)->>'building_material' as building_material,
                CAST((raw_json::JSON)->>'year_built' AS INTEGER) as year_built,
                (raw_json::JSON)->>'ownership_type' as ownership_type
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
            title,
            price_total,
            price_per_sqm,
            currency,
            area_sqm,
            rooms,
            floor,
            building_type,
            market_type,
            seller_segment,
            city,
            district,
            furnished,
            pets_allowed,
            elevator,
            parking,
            balcony,
            additional_rent_pln,
            building_material,
            year_built,
            ownership_type,
            raw_json,
            ingested_at as dbt_updated_at,
            ingested_at as dbt_valid_from,
            next_valid_from as dbt_valid_to
        FROM chained;
    {% endset %}

    {% do run_query(query) %}
    {{ print("Historical seeding complete.") }}
{% endmacro %}
