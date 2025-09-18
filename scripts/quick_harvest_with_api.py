#!/usr/bin/env python3
"""
Quick evidence harvest with proper API key setup
"""
import os
import sys
import time
from pathlib import Path

# Set API key first
os.environ['NCBI_API_KEY'] = '75080d5c230ad16abe97b1b3a27051e02908'

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.evidence.pubmed_harvester import PubMedHarvester
from src.core.database import init_database

def main():
    print("Starting quick evidence harvest with API key...")
    print(f"API key set: {os.environ.get('NCBI_API_KEY', 'NOT SET')[:8]}...")

    # Initialize fresh database
    db_path = "database/codex_local_quick.duckdb"
    db = init_database(db_path)

    # Initialize harvester with API key
    harvester = PubMedHarvester(api_key=os.environ['NCBI_API_KEY'])

    print(f"Harvester rate limit: {harvester.requests_per_second} requests/second")

    # Test with one high-priority outcome
    test_outcomes = ['MORTALITY_24H', 'FAILED_INTUBATION']

    total_papers = 0
    total_effects = 0

    for outcome in test_outcomes:
        print(f"\n--- Testing {outcome} ---")

        start_time = time.time()

        try:
            # Harvest for adult population only
            papers, effects = harvester.harvest_outcome_evidence(
                outcome_token=outcome,
                population='adult',
                max_papers=25,  # Small batch to test
                batch_id=f"quick_test_{outcome}"
            )

            duration = time.time() - start_time
            total_papers += len(papers)
            total_effects += len(effects)

            print(f"Harvested {len(papers)} papers, extracted {len(effects)} effects in {duration:.1f}s")

            # Add delay between outcomes
            time.sleep(2)

        except Exception as e:
            print(f"Error harvesting {outcome}: {e}")
            continue

    print(f"\n=== QUICK HARVEST RESULTS ===")
    print(f"Total papers: {total_papers}")
    print(f"Total effects: {total_effects}")
    print(f"Database: {db_path}")

    if total_papers > 0:
        print("\n✅ API key is working! Ready for full harvest.")
    else:
        print("\n❌ No papers harvested. Check API key or rate limits.")

if __name__ == "__main__":
    main()