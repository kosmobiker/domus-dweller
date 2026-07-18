import os
import subprocess
from datetime import datetime

import duckdb
from domus_dweller.sinks.motherduck_bootstrap import bootstrap_motherduck


def test_dbt_silver_layer(tmp_path):
    db_path = str(tmp_path / "test.duckdb")
    
    # 1. Setup Bronze
    bootstrap_motherduck(database=db_path, token="local")
    
    # 2. Insert dummy data into Bronze
    con = duckdb.connect(db_path)
    
    # Day 1: Price is 2000
    con.execute("""
        INSERT INTO bronze.rent_bronze
        (source, source_listing_id, mode, snapshot_date, ingested_at, raw_json)
        VALUES (
            'olx', '123', 'rent', '2026-07-01', '2026-07-01 10:00:00',
            '{"title": "Nice flat", "price_total": 2000, "city": "Krakow"}'::JSON
        )
    """)
    # Day 2: Price changes to 2200
    con.execute("""
        INSERT INTO bronze.rent_bronze
        (source, source_listing_id, mode, snapshot_date, ingested_at, raw_json)
        VALUES (
            'olx', '123', 'rent', '2026-07-02', '2026-07-02 10:00:00',
            '{"title": "Nice flat", "price_total": 2200, "city": "Krakow"}'::JSON
        )
    """)
    # Day 3: No price change, just another observation
    con.execute("""
        INSERT INTO bronze.rent_bronze
        (source, source_listing_id, mode, snapshot_date, ingested_at, raw_json)
        VALUES (
            'olx', '123', 'rent', '2026-07-03', '2026-07-03 10:00:00',
            '{"title": "Nice flat", "price_total": 2200, "city": "Krakow"}'::JSON
        )
    """)
    con.close()

    # 3. Seed history
    env = os.environ.copy()
    env["DEV_DB"] = db_path
    cwd = os.path.join(os.getcwd(), "transform")
    subprocess.run(["uv", "run", "dbt", "deps"], check=True, cwd=cwd, env=env)
    subprocess.run(
        ["uv", "run", "dbt", "run-operation", "seed_silver_history", "--target", "dev"],
        check=True, cwd=cwd, env=env
    )
    
    # Verify initial seeding works
    con = duckdb.connect(db_path)
    versions = con.execute(
        "SELECT * FROM silver.listing_versions ORDER BY dbt_valid_from"
    ).fetchall()
    assert len(versions) == 2, (
        "Should have 2 versions: 2000 -> 2200. "
        "The duplicate on Day 3 should not create a new version."
    )
    
    con.close()

    # 4. Add Day 4 data (Price drops to 2100)
    con = duckdb.connect(db_path)
    con.execute("""
        INSERT INTO bronze.rent_bronze
        (source, source_listing_id, mode, snapshot_date, ingested_at, raw_json)
        VALUES (
            'olx', '123', 'rent', '2026-07-04', '2026-07-04 10:00:00',
            '{"title": "Nice flat", "price_total": 2100, "city": "Krakow"}'::JSON
        )
    """)
    con.close()
    
    # 5. Run dbt to catch the new increment
    env = os.environ.copy()
    env["DEV_DB"] = db_path
    
    # Run deps, snapshot, run
    cwd = os.path.join(os.getcwd(), "transform")
    subprocess.run(["uv", "run", "dbt", "deps"], check=True, cwd=cwd, env=env)
    
    subprocess.run(["uv", "run", "dbt", "build", "--target", "dev"], check=True, cwd=cwd, env=env)

    # 6. Verify dbt correctly appended the Day 4 version
    con = duckdb.connect(db_path)
    versions = con.execute(
        "SELECT price_total, dbt_valid_from, dbt_valid_to "
        "FROM silver.listing_versions ORDER BY dbt_valid_from"
    ).fetchall()
    
    assert len(versions) == 3
    assert versions[0][0] == 2000.0
    assert versions[1][0] == 2200.0
    assert versions[2][0] == 2100.0
    assert versions[2][2] is None
    
    # Check identity
    identity = con.execute(
        "SELECT first_seen_at, last_seen_at FROM silver.listing_identity"
    ).fetchall()
    assert len(identity) == 1
    assert identity[0][0] == datetime.strptime("2026-07-01 10:00:00", "%Y-%m-%d %H:%M:%S")
    assert identity[0][1] == datetime.strptime("2026-07-04 10:00:00", "%Y-%m-%d %H:%M:%S")
    
    con.close()
