#!/usr/bin/env python3
"""
Debug baseline initialization issue.
"""

import duckdb
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

def check_database_tables():
    """Check what tables exist and their counts."""
    print("=" * 60)
    print("CHECKING DATABASE TABLES")
    print("=" * 60)

    db_path = "database/production.duckdb"

    try:
        conn = duckdb.connect(db_path)

        # List all tables
        tables = conn.execute("SHOW TABLES").fetchall()
        print(f"Tables in {db_path}:")
        for table in tables:
            table_name = table[0]
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                print(f"  {table_name}: {count} records")
            except Exception as e:
                print(f"  {table_name}: ERROR - {e}")

        # Check if baselines_pooled table exists
        try:
            conn.execute("SELECT * FROM baselines_pooled LIMIT 1")
            print("\nbaselines_pooled table exists")

            # Check for auto-initialized baselines
            auto_count = conn.execute("""
                SELECT COUNT(*) FROM baselines_pooled
                WHERE evidence_version LIKE '%auto_init%'
            """).fetchone()[0]
            print(f"Auto-initialized baselines: {auto_count}")

        except Exception as e:
            print(f"\nbaselines_pooled table issue: {e}")

        conn.close()

    except Exception as e:
        print(f"Database error: {e}")

def test_baseline_init_directly():
    """Test baseline initialization directly."""
    print("\n" + "=" * 60)
    print("TESTING BASELINE INITIALIZATION DIRECTLY")
    print("=" * 60)

    try:
        from src.core.baseline_initializer import initialize_baseline_database

        db_path = "database/production.duckdb"
        print(f"Running baseline initialization on: {db_path}")

        success = initialize_baseline_database(db_path)
        print(f"Initialization result: {success}")

        # Check results
        conn = duckdb.connect(db_path)
        auto_count = conn.execute("""
            SELECT COUNT(*) FROM baselines_pooled
            WHERE evidence_version LIKE '%auto_init%'
        """).fetchone()[0]
        print(f"Auto-initialized baselines after init: {auto_count}")
        conn.close()

    except Exception as e:
        print(f"Initialization error: {e}")

if __name__ == "__main__":
    check_database_tables()
    test_baseline_init_directly()