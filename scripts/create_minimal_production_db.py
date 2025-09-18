#!/usr/bin/env python3
"""
Create Minimal Production Database
Extract only the calculated risk results (baseline_risks + risk_modifiers)
from the full database into a tiny production database (~50KB instead of 109MB)
"""

import sys
import duckdb
from pathlib import Path

def create_minimal_production_db():
    """Create minimal production database with only risk calculation results"""

    source_db = "database/production.duckdb"  # Full database with evidence
    target_db = "database/minimal_production.duckdb"  # Tiny database with just risks

    if not Path(source_db).exists():
        print(f"ERROR: Source database not found: {source_db}")
        return False

    print("Creating minimal production database...")

    # Remove existing target database if it exists
    if Path(target_db).exists():
        Path(target_db).unlink()
        print(f"Removed existing target database: {target_db}")

    try:
        # Connect to source database
        source_conn = duckdb.connect(source_db)

        # Create new minimal database
        target_conn = duckdb.connect(target_db)

        # Copy only the risk calculation tables
        print("Copying baseline_risks table...")
        baseline_data = source_conn.execute("""
            SELECT outcome_token, baseline_risk, confidence_interval_lower,
                   confidence_interval_upper, evidence_grade, studies_count,
                   last_updated, population
            FROM baseline_risks
        """).fetchall()

        # Create baseline_risks table
        target_conn.execute("""
            CREATE TABLE baseline_risks (
                outcome_token TEXT PRIMARY KEY,
                baseline_risk REAL NOT NULL,
                confidence_interval_lower REAL,
                confidence_interval_upper REAL,
                evidence_grade TEXT,
                studies_count INTEGER,
                last_updated TEXT,
                population TEXT DEFAULT 'mixed'
            )
        """)

        # Insert baseline risk data
        for row in baseline_data:
            target_conn.execute("""
                INSERT INTO baseline_risks VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, row)

        print("Copying risk_modifiers table...")
        modifier_data = source_conn.execute("""
            SELECT id, outcome_token, modifier_token, effect_estimate,
                   confidence_interval_lower, confidence_interval_upper,
                   evidence_grade, studies_count, last_updated
            FROM risk_modifiers
        """).fetchall()

        # Create risk_modifiers table
        target_conn.execute("""
            CREATE TABLE risk_modifiers (
                id TEXT PRIMARY KEY,
                outcome_token TEXT NOT NULL,
                modifier_token TEXT NOT NULL,
                effect_estimate REAL NOT NULL,
                confidence_interval_lower REAL,
                confidence_interval_upper REAL,
                evidence_grade TEXT,
                studies_count INTEGER,
                last_updated TEXT
            )
        """)

        # Insert modifier data
        for row in modifier_data:
            target_conn.execute("""
                INSERT INTO risk_modifiers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, row)

        target_conn.commit()
        target_conn.close()
        source_conn.close()

        # Check file sizes
        source_size = Path(source_db).stat().st_size
        target_size = Path(target_db).stat().st_size

        print(f"SUCCESS: Minimal production database created")
        print(f"  Source: {source_db} ({source_size:,} bytes)")
        print(f"  Target: {target_db} ({target_size:,} bytes)")
        print(f"  Size reduction: {(1 - target_size/source_size)*100:.1f}%")

        # Verify data
        verify_conn = duckdb.connect(target_db)
        baseline_count = verify_conn.execute("SELECT COUNT(*) FROM baseline_risks").fetchone()[0]
        modifier_count = verify_conn.execute("SELECT COUNT(*) FROM risk_modifiers").fetchone()[0]
        verify_conn.close()

        print(f"  Data verification: {baseline_count} baseline risks, {modifier_count} modifiers")

        return True

    except Exception as e:
        print(f"ERROR: Failed to create minimal database: {e}")
        return False

if __name__ == "__main__":
    success = create_minimal_production_db()
    sys.exit(0 if success else 1)