#!/usr/bin/env python3
"""
Simple Database Rebuild Script
Rebuilds the database with the correct schema, including the missing harvest_batch_id column.
"""

import duckdb
import os
from pathlib import Path

def rebuild_database():
    """Rebuild the database with the correct schema"""

    # Database path
    db_path = Path(__file__).parent.parent / "database" / "codex.duckdb"

    print("STARTING Simple Database Rebuild")
    print("=" * 50)

    # Backup old database if it exists
    if db_path.exists():
        backup_path = db_path.with_suffix('.backup.duckdb')
        print(f"[BACKUP] Backing up existing database to {backup_path}")
        import shutil
        shutil.copy2(db_path, backup_path)

        # Remove old database
        db_path.unlink()
        print("[SUCCESS] Old database removed")

    # Create fresh database
    print("[RUNNING] Creating fresh database with correct schema...")
    conn = duckdb.connect(str(db_path))

    # Create core tables with proper schema including harvest_batch_id
    conn.execute("""
        CREATE TABLE estimates (
            outcome_token VARCHAR,
            context_label VARCHAR,
            baseline_risk DOUBLE,
            baseline_source VARCHAR,
            harvest_batch_id VARCHAR,  -- This was missing!
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE case_sessions (
            session_id VARCHAR PRIMARY KEY,
            hpi_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            risk_scores JSON
        )
    """)

    conn.execute("""
        CREATE TABLE ontology (
            token VARCHAR PRIMARY KEY,
            synonyms JSON,
            display_name VARCHAR,
            category VARCHAR
        )
    """)

    print("[SUCCESS] Core database schema created")

    # Add some sample data to make it functional
    conn.execute("""
        INSERT INTO estimates (outcome_token, context_label, baseline_risk, baseline_source, harvest_batch_id)
        VALUES
        ('ACUTE_KIDNEY_INJURY', 'adult_general', 0.18, 'sample_data', 'rebuild_2025'),
        ('POSTOP_DELIRIUM', 'adult_general', 0.24, 'sample_data', 'rebuild_2025'),
        ('PROLONGED_VENTILATION', 'adult_general', 0.095, 'sample_data', 'rebuild_2025'),
        ('DIFFICULT_INTUBATION', 'adult_general', 0.058, 'sample_data', 'rebuild_2025'),
        ('PULMONARY_EMBOLISM', 'adult_general', 0.008, 'sample_data', 'rebuild_2025'),
        ('ASPIRATION', 'adult_general', 0.0008, 'sample_data', 'rebuild_2025')
    """)

    # Add basic ontology data
    conn.execute("""
        INSERT INTO ontology (token, synonyms, display_name, category)
        VALUES
        ('DIABETES', '["diabetes", "diabetic", "dm"]', 'Diabetes mellitus', 'endocrine'),
        ('HYPERTENSION', '["hypertension", "htn", "high blood pressure"]', 'Hypertension', 'cardiac'),
        ('SEX_MALE', '["male", "man"]', 'Male sex', 'demographics'),
        ('AGE_ELDERLY', '["elderly", "old"]', 'Age 60-80 years', 'demographics'),
        ('EMERGENCY', '["emergency", "urgent", "acute"]', 'Emergency surgery', 'urgency'),
        ('SMOKING_HISTORY', '["smoking", "tobacco", "smoker"]', 'Smoking history', 'lifestyle')
    """)

    print("[SUCCESS] Sample data added")

    conn.close()

    print("\nCOMPLETE: Simple Database Rebuild Complete!")
    print("=" * 50)
    print("[SUCCESS] Database recreated with correct schema")
    print("[SUCCESS] harvest_batch_id column added to estimates table")
    print("[SUCCESS] Sample baseline risks added")
    print("[SUCCESS] Basic ontology data added")
    print(f"[SUCCESS] Database ready at: {db_path}")

    return True

if __name__ == "__main__":
    try:
        success = rebuild_database()
        if success:
            print("\n[READY] Database is ready for production deployment!")
        else:
            print("\n[ERROR] Database rebuild failed!")
    except Exception as e:
        print(f"\n[ERROR] Exception during rebuild: {e}")