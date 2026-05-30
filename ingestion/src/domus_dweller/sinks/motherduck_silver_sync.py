import os

import duckdb
from dotenv import load_dotenv


def sync_silver(*, database: str = "my_db", token: str | None = None) -> None:
    """
    Sync Bronze to Silver using a strictly chronological SCD Type 2 strategy.
    Change hash is focused on core numeric and structural fields (Price, Area, Rooms)
    to eliminate any residual metadata noise.
    """
    load_dotenv()
    token = token or os.getenv("MOTHERDUCK_TOKEN")
    
    if not token or token.lower() == "local":
        print(f"Connecting to local DuckDB file: {database}")
        con = duckdb.connect(database)
    else:
        print(f"Connecting to MotherDuck database: {database}")
        con = duckdb.connect(f"md:{database}?token={token}")

    # 1. Promote fields and detect real changes chronologically
    con.execute("""
        CREATE OR REPLACE TEMP TABLE bronze_functional_states AS
        WITH combined AS (
            SELECT * FROM bronze.rent_bronze
            UNION ALL
            SELECT * FROM bronze.sale_bronze
        ),
        promoted AS (
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
                -- Hashing ONLY the "Triple Crown" of property data: Price, Area, Rooms.
                -- This ensures that only structural or financial changes trigger a new version.
                md5(concat_ws('|', 
                    (raw_json::JSON)->>'price_total',
                    (raw_json::JSON)->>'area_sqm',
                    (raw_json::JSON)->>'rooms'
                )) as change_hash
            FROM combined
        ),
        chronological_chain AS (
            SELECT 
                *,
                lag(change_hash) OVER (
                    PARTITION BY source, mode, source_listing_id 
                    ORDER BY ingested_at ASC
                ) as prev_hash
            FROM promoted
        )
        -- Only keep rows where the financial or structural state actually CHANGED
        SELECT * EXCLUDE (prev_hash) FROM chronological_chain 
        WHERE prev_hash IS NULL OR change_hash != prev_hash;
    """)

    # 2. Merge into silver.listing_identity
    print("Merging into silver.listing_identity...")
    con.execute("""
        MERGE INTO silver.listing_identity AS target
        USING (
            SELECT 
                source, source_listing_id, mode, 
                min(ingested_at) as first_seen_at, 
                max(ingested_at) as last_seen_at
            FROM bronze_functional_states
            GROUP BY 1, 2, 3
        ) AS src
        ON target.source = src.source 
           AND target.source_listing_id = src.source_listing_id 
           AND target.mode = src.mode
        WHEN MATCHED THEN
            UPDATE SET 
                last_seen_at = src.last_seen_at, 
                is_active = TRUE, 
                updated_at = CURRENT_TIMESTAMP
        WHEN NOT MATCHED THEN
            INSERT (source, source_listing_id, mode, first_seen_at, last_seen_at, is_active)
            VALUES (src.source, src.source_listing_id, src.mode, src.first_seen_at, 
                    src.last_seen_at, TRUE);
    """)

    # 3. Strictly chain silver.listing_versions (SCD Type 2)
    print("Processing SCD Type 2 historical versions...")
    
    # Identify ONLY versions that aren't already in Silver
    con.execute("""
        CREATE OR REPLACE TEMP TABLE silver_batch_versions AS
        SELECT b.*
        FROM bronze_functional_states b
        LEFT JOIN silver.listing_versions s 
          ON b.source = s.source AND b.source_listing_id = s.source_listing_id 
          AND b.mode = s.mode AND b.ingested_at = s.valid_from
        WHERE s.source_listing_id IS NULL;
    """)

    # Close current active versions if the batch contains a NEWER version
    con.execute("""
        UPDATE silver.listing_versions
        SET valid_to = batch.min_valid_from, is_current = FALSE
        FROM (
            SELECT source, source_listing_id, mode, min(ingested_at) as min_valid_from
            FROM silver_batch_versions GROUP BY 1, 2, 3
        ) batch
        WHERE silver.listing_versions.source = batch.source
          AND silver.listing_versions.source_listing_id = batch.source_listing_id
          AND silver.listing_versions.mode = batch.mode
          AND silver.listing_versions.is_current = TRUE
          AND batch.min_valid_from > silver.listing_versions.valid_from;
    """)

    # Insert batch versions with proper chaining
    con.execute("""
        INSERT INTO silver.listing_versions (
            source, source_listing_id, mode, valid_from, valid_to, is_current, 
            change_hash, title, price_total, price_per_sqm, currency, area_sqm, 
            rooms, floor, building_type, market_type, seller_segment, city, district, raw_json
        )
        WITH chained AS (
            SELECT 
                *,
                lead(ingested_at) OVER (
                    PARTITION BY source, mode, source_listing_id 
                    ORDER BY ingested_at ASC
                ) as next_valid_from
            FROM silver_batch_versions
        )
        SELECT 
            source, source_listing_id, mode, ingested_at as valid_from, 
            next_valid_from as valid_to,
            CASE WHEN next_valid_from IS NULL THEN TRUE ELSE FALSE END as is_current,
            change_hash, title, price_total, price_per_sqm, currency, area_sqm, 
            rooms, floor, building_type, market_type, seller_segment, city, district, raw_json
        FROM chained;
    """)

    print("Silver Merge ETL complete.")
    con.close()


if __name__ == "__main__":
    sync_silver()
