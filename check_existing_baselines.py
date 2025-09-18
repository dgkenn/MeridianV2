#!/usr/bin/env python3
"""
Check what's in the existing baselines.
"""

import duckdb

def check_baseline_versions():
    """Check what baseline versions exist."""
    print("=" * 60)
    print("CHECKING EXISTING BASELINE VERSIONS")
    print("=" * 60)

    conn = duckdb.connect("database/production.duckdb")

    # Check evidence versions
    versions = conn.execute("""
        SELECT evidence_version, COUNT(*) as count
        FROM baselines_pooled
        GROUP BY evidence_version
        ORDER BY count DESC
    """).fetchall()

    print("Evidence versions in baselines_pooled:")
    for version, count in versions:
        print(f"  {version}: {count} baselines")

    # Check context labels
    contexts = conn.execute("""
        SELECT context_label, COUNT(*) as count
        FROM baselines_pooled
        GROUP BY context_label
        ORDER BY count DESC
        LIMIT 10
    """).fetchall()

    print(f"\nTop 10 context labels:")
    for context, count in contexts:
        print(f"  {context}: {count} baselines")

    # Check if we already have comprehensive coverage
    comprehensive_count = conn.execute("""
        SELECT COUNT(*) FROM baselines_pooled
        WHERE evidence_version LIKE '%comprehensive%' OR evidence_version LIKE '%auto_init%'
    """).fetchone()[0]

    print(f"\nComprehensive baselines: {comprehensive_count}")
    print(f"Total baselines: {len(versions) and sum(count for _, count in versions)}")

    conn.close()

if __name__ == "__main__":
    check_baseline_versions()