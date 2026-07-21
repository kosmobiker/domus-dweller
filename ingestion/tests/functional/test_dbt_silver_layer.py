import json
import os
import subprocess
from datetime import datetime

import duckdb
from domus_dweller.sinks.motherduck_bootstrap import bootstrap_motherduck

# Realistic raw_json payloads that mirror actual OLX parser output.
# Crucially, 'parking' is a string (e.g. "w garażu"), not a boolean,
# which previously broke the CAST in the staging model.
REALISTIC_RENT_JSON_DAY1 = json.dumps({
    "title": "Mieszkanie 2-pokojowe Krowodrza",
    "price_total": 2000,
    "price_per_sqm_source": 40.0,
    "currency": "PLN",
    "area_sqm": 50.0,
    "rooms": 2,
    "floor": "2",
    "building_type": "blok",
    "market_type": "wtórny",
    "seller_segment": "private",
    "city": "Kraków",
    "district": "Krowodrza",
    "furnished": True,
    "pets_allowed": False,
    "elevator": True,
    "parking": "w garażu",
    "detail_params": {
        "ai_extracted": {
            "balcony": True,
            "additional_rent_pln": 500,
            "building_material": "cegła",
            "year_built": 2015,
            "ownership_type": "własność"
        }
    }
})

REALISTIC_RENT_JSON_DAY2 = json.dumps({
    "title": "Mieszkanie 2-pokojowe Krowodrza",
    "price_total": 2200,
    "price_per_sqm_source": 44.0,
    "currency": "PLN",
    "area_sqm": 50.0,
    "rooms": 2,
    "floor": "2",
    "building_type": "blok",
    "market_type": "wtórny",
    "seller_segment": "private",
    "city": "Kraków",
    "district": "Krowodrza",
    "furnished": True,
    "pets_allowed": False,
    "elevator": True,
    "parking": "w garażu",
    "detail_params": {
        "ai_extracted": {
            "balcony": True,
            "additional_rent_pln": 500,
            "building_material": "cegła",
            "year_built": 2015,
            "ownership_type": "własność"
        }
    }
})

REALISTIC_RENT_JSON_DAY3 = REALISTIC_RENT_JSON_DAY2  # same price, duplicate observation

REALISTIC_RENT_JSON_DAY4 = json.dumps({
    "title": "Mieszkanie 2-pokojowe Krowodrza",
    "price_total": 2100,
    "price_per_sqm_source": 42.0,
    "currency": "PLN",
    "area_sqm": 50.0,
    "rooms": 2,
    "floor": "2",
    "building_type": "blok",
    "market_type": "wtórny",
    "seller_segment": "private",
    "city": "Kraków",
    "district": "Krowodrza",
    "furnished": True,
    "pets_allowed": False,
    "elevator": True,
    "parking": "na ulicy",
    "detail_params": {
        "ai_extracted": {
            "balcony": True,
            "additional_rent_pln": 500,
            "building_material": "cegła",
            "year_built": 2015,
            "ownership_type": "własność"
        }
    }
})


def _insert_bronze_row(con, listing_id, mode, date, raw_json, table="rent_bronze"):
    con.execute(
        f"""
        INSERT INTO bronze.{table}
        (source, source_listing_id, mode, snapshot_date, ingested_at, raw_json)
        VALUES (
            'olx', ?, ?, ?, ? || ' 10:00:00',
            ?::JSON
        )
        """,
        [listing_id, mode, date, date, raw_json],
    )


def test_dbt_silver_layer(tmp_path):
    """Full SCD versioning test with realistic data including amenity fields.

    Uses parking='w garażu' (a string, not boolean) to verify the staging
    model correctly handles non-boolean parking values from the OLX parser.
    """
    db_path = str(tmp_path / "test.duckdb")

    # 1. Setup Bronze
    bootstrap_motherduck(database=db_path, token="local")

    # 2. Insert realistic data into Bronze (Days 1-3)
    con = duckdb.connect(db_path)
    _insert_bronze_row(con, "123", "rent", "2026-07-01", REALISTIC_RENT_JSON_DAY1)
    _insert_bronze_row(con, "123", "rent", "2026-07-02", REALISTIC_RENT_JSON_DAY2)
    _insert_bronze_row(con, "123", "rent", "2026-07-03", REALISTIC_RENT_JSON_DAY3)
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
    _insert_bronze_row(con, "123", "rent", "2026-07-04", REALISTIC_RENT_JSON_DAY4)
    con.close()

    # 5. Run dbt to catch the new increment
    env = os.environ.copy()
    env["DEV_DB"] = db_path

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

    # Verify amenity columns survived the staging + snapshot pipeline
    current = con.execute(
        "SELECT parking, furnished, elevator, balcony, building_material, year_built "
        "FROM silver.listing_current"
    ).fetchall()
    assert len(current) == 1
    row = current[0]
    assert row[0] is None, "parking='na ulicy' should be NULL without AI"
    assert row[1] is True, "furnished should be TRUE"
    assert row[2] is True, "elevator should be TRUE"
    assert row[3] is True, "balcony (from ai_extracted) should be TRUE"
    assert row[4] == "cegła", "building_material should be 'cegła'"
    assert row[5] == 2015, "year_built should be 2015"

    con.close()
