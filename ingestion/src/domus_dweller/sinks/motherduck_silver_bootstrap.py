import os

import duckdb
from dotenv import load_dotenv


def bootstrap_silver(*, database: str = "my_db", token: str | None = None) -> None:
    """
    Bootstrap MotherDuck or Local DuckDB with Silver schema and tables.
    """
    load_dotenv()
    token = token or os.getenv("MOTHERDUCK_TOKEN")
    
    if not token or token.lower() == "local":
        print(f"Connecting to local DuckDB file: {database}")
        con = duckdb.connect(database)
    else:
        print(f"Connecting to MotherDuck database: {database}")
        con = duckdb.connect(f"md:{database}?token={token}")

    # Create schema
    con.execute("CREATE SCHEMA IF NOT EXISTS silver;")
    print("Schema ensured: silver")

    # --- Silver Layer ---

    # Drop existing tables to ensure a clean start with correct schema
    con.execute("DROP TABLE IF EXISTS silver.listing_versions CASCADE;")
    con.execute("DROP TABLE IF EXISTS silver.listing_identity CASCADE;")

    # 1. Identity Table: Lifecycle Tracking
    con.execute("""
        CREATE TABLE silver.listing_identity (
            source VARCHAR,
            source_listing_id VARCHAR,
            mode VARCHAR,
            first_seen_at TIMESTAMP,
            last_seen_at TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (source, source_listing_id, mode)
        );
    """)
    print("Silver table ensured: silver.listing_identity")

    # 2. Versions Table: SCD Type 2 Property History
    con.execute("""
        CREATE TABLE silver.listing_versions (
            source VARCHAR,
            source_listing_id VARCHAR,
            mode VARCHAR,
            valid_from TIMESTAMP,
            valid_to TIMESTAMP,
            is_current BOOLEAN,
            change_hash VARCHAR,
            -- Promoted Property Attributes
            title VARCHAR,
            price_total DOUBLE,
            price_per_sqm DOUBLE,
            currency VARCHAR,
            area_sqm DOUBLE,
            rooms DOUBLE,
            floor VARCHAR,
            building_type VARCHAR,
            market_type VARCHAR,
            seller_segment VARCHAR, -- private vs professional
            city VARCHAR,
            district VARCHAR,
            raw_json JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (source, source_listing_id, mode, valid_from)
        );
    """)
    print("Silver table ensured: silver.listing_versions")

    # 3. Current View: Easy access to latest states
    con.execute("""
        CREATE OR REPLACE VIEW silver.listing_current AS
        SELECT * FROM silver.listing_versions WHERE is_current = TRUE;
    """)
    print("Silver view ensured: silver.listing_current")

    con.close()

if __name__ == "__main__":
    bootstrap_silver()
