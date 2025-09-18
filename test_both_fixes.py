#!/usr/bin/env python3
"""
Test both baseline initialization and enhanced parsing patterns.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

def test_cad_parsing():
    """Test that CAD is now properly extracted."""
    print("=" * 60)
    print("TESTING ENHANCED PARSING PATTERNS")
    print("=" * 60)

    from src.core.hpi_parser import MedicalTextProcessor

    # Create parser
    parser = MedicalTextProcessor()

    # Test cardiac case that previously failed
    cardiac_hpi = """
    65-year-old male with history of coronary artery disease status post cardiac catheterization
    with stent placement 2 years ago, diabetes mellitus type 2 on metformin, hypertension on lisinopril,
    and hyperlipidemia presenting for elective cardiac surgery. Patient has a history of myocardial
    infarction 3 years ago. Currently taking atorvastatin, metoprolol, and aspirin.
    """

    print("Testing cardiac case with CAD, diabetes, and hypertension...")
    print(f"Input: {cardiac_hpi[:100]}...")

    try:
        parsed = parser.parse_hpi(cardiac_hpi)

        print(f"\nExtracted {len(parsed.extracted_factors)} factors:")
        for factor in parsed.extracted_factors:
            print(f"  - {factor.token}: {factor.plain_label} (confidence: {factor.confidence:.2f})")

        # Check if CAD was found
        cad_found = any(factor.token == "CORONARY_ARTERY_DISEASE" for factor in parsed.extracted_factors)
        diabetes_found = any(factor.token == "DIABETES" for factor in parsed.extracted_factors)
        htn_found = any(factor.token == "HYPERTENSION" for factor in parsed.extracted_factors)

        print(f"\nKey conditions detected:")
        print(f"  CAD: {'[YES]' if cad_found else '[NO]'}")
        print(f"  Diabetes: {'[YES]' if diabetes_found else '[NO]'}")
        print(f"  Hypertension: {'[YES]' if htn_found else '[NO]'}")

        if cad_found and diabetes_found and htn_found:
            print("\n[SUCCESS] All major cardiac conditions detected!")
            return True
        else:
            print("\n[FAILED] Some conditions still missing")
            return False

    except Exception as e:
        print(f"[ERROR] {e}")
        return False

def test_baseline_initialization():
    """Test that baseline initialization works."""
    print("\n" + "=" * 60)
    print("TESTING BASELINE INITIALIZATION")
    print("=" * 60)

    try:
        from src.core.baseline_initializer import ensure_baselines_available

        print("Running baseline initialization...")
        success = ensure_baselines_available()

        if success:
            print("[SUCCESS] Baseline initialization completed")

            # Check database
            import duckdb
            try:
                conn = duckdb.connect("database/production.duckdb")
                count = conn.execute("SELECT COUNT(*) FROM baselines_pooled WHERE evidence_version LIKE '%comprehensive%' OR evidence_version LIKE '%auto_init%'").fetchone()[0]
                conn.close()

                print(f"Found {count} comprehensive baselines in database")

                if count >= 100:  # Should have comprehensive baselines
                    print("[SUCCESS] Comprehensive baselines available")
                    return True
                else:
                    print("[WARNING] Limited baselines found")
                    return False

            except Exception as e:
                print(f"[ERROR] Database check failed: {e}")
                return False

        else:
            print("[FAILED] Baseline initialization failed")
            return False

    except Exception as e:
        print(f"[ERROR] {e}")
        return False

if __name__ == "__main__":
    print("Testing comprehensive fixes for Meridian parsing and baseline issues...")

    # Test 1: Enhanced parsing patterns
    parsing_success = test_cad_parsing()

    # Test 2: Baseline initialization
    baseline_success = test_baseline_initialization()

    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)

    if parsing_success and baseline_success:
        print("ALL TESTS PASSED!")
        print("[SUCCESS] Parsing now detects CAD and other cardiac conditions")
        print("[SUCCESS] Baseline warnings should be eliminated")
        print("[SUCCESS] Both production issues resolved")
    else:
        print("SOME TESTS FAILED")
        if not parsing_success:
            print("[FAILED] Parsing patterns still need work")
        if not baseline_success:
            print("[FAILED] Baseline initialization needs fixing")

    print("=" * 60)