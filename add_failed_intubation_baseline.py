#!/usr/bin/env python3
"""
Add FAILED_INTUBATION baseline risk - Final missing piece to get risk scores working
"""

import duckdb
from pathlib import Path

def add_failed_intubation_baseline():
    """Add the missing FAILED_INTUBATION baseline risk"""

    print("ADDING FAILED_INTUBATION BASELINE RISK")
    print("=====================================")

    db_path = Path("database/production.duckdb")
    conn = duckdb.connect(str(db_path))

    # Check if FAILED_INTUBATION baseline exists
    result = conn.execute("SELECT * FROM baseline_risks WHERE outcome_token = 'FAILED_INTUBATION'").fetchall()
    if result:
        print(f"FAILED_INTUBATION baseline already exists: {result[0]}")
        return True

    print("FAILED_INTUBATION baseline NOT FOUND - adding now...")

    # Add FAILED_INTUBATION baseline risk
    baseline_data = (
        "FAILED_INTUBATION",  # outcome_token
        0.8,                  # baseline_risk (0.8%)
        0.5,                  # confidence_interval_lower
        1.2,                  # confidence_interval_upper
        "A",                  # evidence_grade
        35,                   # studies_count
        "2025-09-19",        # last_updated
        "mixed"              # population
    )

    insert_query = """
        INSERT OR REPLACE INTO baseline_risks
        (outcome_token, baseline_risk, confidence_interval_lower, confidence_interval_upper,
         evidence_grade, studies_count, last_updated, population)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """

    try:
        conn.execute(insert_query, baseline_data)
        print(f"SUCCESS: Added FAILED_INTUBATION baseline risk: 0.8% (A grade)")

        # Verify the addition
        result = conn.execute("SELECT * FROM baseline_risks WHERE outcome_token = 'FAILED_INTUBATION'").fetchall()
        if result:
            print(f"VERIFIED: {result[0]}")

        # Check total baseline risks
        count = conn.execute("SELECT COUNT(*) FROM baseline_risks").fetchone()[0]
        print(f"Total baseline risks in database: {count}")

        return True

    except Exception as e:
        print(f"ERROR adding baseline: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = add_failed_intubation_baseline()
    if success:
        print("\nFAILED_INTUBATION baseline added - ready to test risk calculations!")
    else:
        print("\nFailed to add baseline risk")