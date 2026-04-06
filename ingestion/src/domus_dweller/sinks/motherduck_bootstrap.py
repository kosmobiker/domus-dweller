import os

import duckdb


def bootstrap_motherduck(*, database: str = "my_db", token: str | None = None) -> None:
    """
    Bootstrap MotherDuck with Bronze (Raw) schema and tables.
    """
    token = token or os.getenv("MOTHERDUCK_TOKEN")
    if not token:
        raise ValueError("MOTHERDUCK_TOKEN environment variable is not set.")

    # Connect to MotherDuck
    con = duckdb.connect(f"md:{database}?token={token}")

    print(f"Connected to MotherDuck database: {database}")

    # Create schemas
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze;")
    print("Schema ensured: bronze")

    # --- Bronze Layer ---

    for mode in ["rent", "sale"]:
        table_name = f"bronze.{mode}_bronze"
        con.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                source VARCHAR,
                source_listing_id VARCHAR,
                source_url VARCHAR,
                mode VARCHAR,
                snapshot_date DATE,
                layer VARCHAR,
                ingested_at TIMESTAMP,
                payload_hash VARCHAR,
                raw_json JSON,
                PRIMARY KEY (source, source_listing_id, snapshot_date)
            );
        """)
        print(f"Bronze table ensured: {table_name}")

    print("Bronze tables ensured.")
    con.close()


if __name__ == "__main__":
    bootstrap_motherduck()
