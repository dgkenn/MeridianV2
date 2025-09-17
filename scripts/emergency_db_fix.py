#!/usr/bin/env python3
"""
Emergency database fix for production
Adds missing harvest_batch_id column to estimates table
"""

import duckdb
import os
import sys

def fix_production_database():
    """Add missing column to production database"""

    # Use the same database path as the main app
    db_path = os.path.join('database', 'codex.duckdb')

    print(f"[EMERGENCY FIX] Connecting to database: {db_path}")

    try:
        conn = duckdb.connect(db_path)

        # Check if the column exists
        try:
            conn.execute("SELECT harvest_batch_id FROM estimates LIMIT 1").fetchone()
            print("[SUCCESS] harvest_batch_id column already exists!")
            return
        except:
            print("[DETECTED] harvest_batch_id column is missing - adding it now...")

        # Add the missing column
        conn.execute("ALTER TABLE estimates ADD COLUMN harvest_batch_id VARCHAR")
        print("[SUCCESS] Added harvest_batch_id column to estimates table")

        # Verify the fix
        conn.execute("SELECT harvest_batch_id FROM estimates LIMIT 1").fetchone()
        print("[VERIFIED] Column addition successful")

        conn.close()
        print("[COMPLETE] Emergency database fix completed successfully")

    except Exception as e:
        print(f"[ERROR] Emergency fix failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    fix_production_database()