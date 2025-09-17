#!/usr/bin/env python3
"""
Production Database Rebuild Script
Completely rebuilds the production database with the latest schema and fresh evidence data.
"""

import os
import sys
import subprocess
from pathlib import Path

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"\n[RUNNING] {description}...")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, cwd=Path(__file__).parent.parent)
        if result.returncode != 0:
            print(f"[ERROR] {result.stderr}")
            return False
        if result.stdout:
            print(f"[SUCCESS] {result.stdout.strip()}")
        return True
    except Exception as e:
        print(f"[ERROR] Exception: {e}")
        return False

def main():
    """Rebuild the production database"""

    print("STARTING Production Database Rebuild")
    print("=" * 50)

    # Step 1: Initialize fresh database schema
    if not run_command("python scripts/setup_codex.py", "Initializing fresh database schema"):
        print("[ERROR] Failed to initialize database schema")
        return False

    # Step 2: Rebuild evidence database with comprehensive harvest
    if not run_command("python scripts/comprehensive_evidence_harvest.py --max-outcomes 5", "Rebuilding evidence database"):
        print("[ERROR] Failed to rebuild evidence database")
        return False

    # Step 3: Initialize Q&A and Learning schema
    if not run_command("python scripts/qna_learning_schema.py", "Adding Q&A and Learning tables"):
        print("[ERROR] Failed to add Q&A and Learning schema")
        return False

    # Step 4: Test the rebuilt database
    if not run_command("python -c \"from src.core.database import Database; db = Database(); print(f'Database ready with {len(db.conn.execute(\\\"SELECT * FROM estimates\\\").fetchall())} evidence estimates')\"", "Testing rebuilt database"):
        print("[ERROR] Failed to validate rebuilt database")
        return False

    print("\nCOMPLETE: Production Database Rebuild Complete!")
    print("=" * 50)
    print("[SUCCESS] Fresh database schema initialized")
    print("[SUCCESS] Evidence database rebuilt with latest data")
    print("[SUCCESS] Q&A and Learning tables added")
    print("[SUCCESS] Database validated and ready for deployment")
    print("\nNext steps:")
    print("1. Commit and push these changes to GitHub")
    print("2. Your production website will automatically redeploy")
    print("3. Test the live website after deployment completes")

if __name__ == "__main__":
    main()