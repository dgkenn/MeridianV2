#!/usr/bin/env python3

import duckdb

def check_database():
    conn = duckdb.connect('evidence_base.db')

    print("=== DATABASE AUDIT ===")
    print("\nTABLES IN DATABASE:")
    tables = conn.execute('SHOW TABLES').fetchall()
    for table in tables:
        print(f"  {table[0]}")

    print(f"\nTotal tables: {len(tables)}")

    # Check each expected table
    expected_tables = ['baseline_risks', 'risk_modifiers', 'outcome_tokens']
    for table_name in expected_tables:
        print(f"\n--- {table_name.upper()} ---")
        try:
            count = conn.execute(f'SELECT COUNT(*) FROM {table_name}').fetchone()[0]
            print(f"✅ Exists with {count} rows")

            # Show sample data
            if count > 0:
                print("Sample data:")
                sample = conn.execute(f'SELECT * FROM {table_name} LIMIT 3').fetchall()
                columns = [desc[0] for desc in conn.execute(f'DESCRIBE {table_name}').fetchall()]
                print(f"Columns: {columns}")
                for row in sample:
                    print(f"  {row}")
        except Exception as e:
            print(f"❌ ERROR: {e}")

    conn.close()

if __name__ == "__main__":
    check_database()