{% macro seed_silver_history() %}
    {% set query %}
        CREATE SCHEMA IF NOT EXISTS silver;

        CREATE OR REPLACE TABLE silver.listing_versions AS
        WITH rent_raw AS (
            SELECT 
                source,
                source_listing_id,
                mode,
                ingested_at,
                raw_json::JSON as j
            FROM bronze.rent_bronze
        ),
        sale_raw AS (
            SELECT 
                source,
                source_listing_id,
                mode,
                ingested_at,
                raw_json::JSON as j
            FROM bronze.sale_bronze
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
                j->>'district' as district,
                j->>'location_approx' as location_approx,
                CAST(j->>'latitude' AS DOUBLE) as latitude,
                CAST(j->>'longitude' AS DOUBLE) as longitude
            FROM combined_raw
        ),
        normalized AS (
            SELECT
                source,
                source_listing_id,
                mode,
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
                        WHEN location_approx ILIKE '%kraków%' OR location_approx ILIKE '%krakow%' THEN 'Kraków'
                        WHEN location_approx ILIKE '%wieliczka%' THEN 'Wieliczka'
                        WHEN location_approx ILIKE '%skawina%' THEN 'Skawina'
                        WHEN location_approx ILIKE '%niepołomice%' OR location_approx ILIKE '%niepolomice%' THEN 'Niepołomice'
                        WHEN location_approx ILIKE '%zabierzów%' OR location_approx ILIKE '%zabierzow%' THEN 'Zabierzów'
                        WHEN location_approx ILIKE '%zielonki%' THEN 'Zielonki'
                        WHEN location_approx ILIKE '%świątniki%' OR location_approx ILIKE '%swiatniki%' THEN 'Świątniki Górne'
                        WHEN district IN (
                            'Stare Miasto', 'Grzegórzki', 'Prądnik Czerwony', 'Prądnik Biały',
                            'Krowodrza', 'Bronowice', 'Zwierzyniec', 'Dębniki',
                            'Łagiewniki-Borek Fałęcki', 'Swoszowice', 'Podgórze Duchackie',
                            'Bieżanów-Prokocim', 'Podgórze', 'Czyżyny', 'Mistrzejowice',
                            'Bieńczyce', 'Wzgórza Krzesławickie', 'Nowa Huta'
                        ) THEN 'Kraków'
                        ELSE NULL
                    END
                ) as city,
                district,
                location_approx,
                latitude,
                longitude
            FROM extracted
        ),
        chronological_chain AS (
            SELECT 
                *,
                lag(price_total) OVER (
                    PARTITION BY source, mode, source_listing_id 
                    ORDER BY ingested_at ASC
                ) as prev_price
            FROM normalized
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
