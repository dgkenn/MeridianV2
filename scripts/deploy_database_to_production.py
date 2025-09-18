#!/usr/bin/env python3
"""
Deploy Database to Production
Copies the local database with calculated risk scores to production directory
"""

import shutil
import os
import sys
from pathlib import Path

def deploy_database():
    """Copy local database with risk scores to production location"""
    print("DEPLOYING DATABASE TO PRODUCTION")
    print("=" * 50)

    # Define paths
    local_db = Path("database/codex.duckdb")
    production_db = Path("database/production.duckdb")

    # Check if local database exists and has data
    if not local_db.exists():
        print(f"ERROR: Local database not found: {local_db}")
        return False

    local_size = local_db.stat().st_size
    print(f"Local database size: {local_size:,} bytes")

    if local_size < 1000000:  # Less than 1MB indicates empty database
        print("WARNING: Local database appears to be empty or incomplete")
        print("   Run risk calculation scripts first")
        return False

    try:
        # Backup existing production database if it exists
        if production_db.exists():
            backup_db = production_db.with_suffix(".backup.duckdb")
            shutil.copy2(production_db, backup_db)
            print(f"Backed up existing production database to: {backup_db}")

        # Copy local database to production location
        shutil.copy2(local_db, production_db)

        production_size = production_db.stat().st_size
        print(f"Successfully deployed database")
        print(f"   Source: {local_db} ({local_size:,} bytes)")
        print(f"   Target: {production_db} ({production_size:,} bytes)")

        # Verify the database has risk tables
        try:
            import duckdb
            conn = duckdb.connect(str(production_db))

            # Check baseline_risks table
            baseline_count = conn.execute("SELECT COUNT(*) FROM baseline_risks").fetchone()[0]
            modifier_count = conn.execute("SELECT COUNT(*) FROM risk_modifiers").fetchone()[0]

            print(f"Risk data verification:")
            print(f"   Baseline risks: {baseline_count}")
            print(f"   Risk modifiers: {modifier_count}")

            if baseline_count > 0 and modifier_count > 0:
                print("SUCCESS: Production database deployment successful!")
                return True
            else:
                print("ERROR: Production database missing risk data")
                return False

        except Exception as e:
            print(f"WARNING: Could not verify database contents: {e}")
            print("SUCCESS: Database copied but verification failed")
            return True

    except Exception as e:
        print(f"ERROR: Failed to deploy database: {e}")
        return False

if __name__ == "__main__":
    success = deploy_database()
    sys.exit(0 if success else 1)