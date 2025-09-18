#!/usr/bin/env python3
"""Debug the exact single factor cases with detailed output"""

import sys
import random
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from nlp.pipeline import parse_hpi
from comprehensive_stress_test import ComprehensiveTestGenerator

def debug_detailed_single_cases():
    print("=== Debugging Single Factor Cases with Detailed Output ===")

    # Set same random seed as stress test
    random.seed(42)

    generator = ComprehensiveTestGenerator()

    # Generate the exact same single factor cases as the stress test
    single_cases = generator._generate_single_factor_cases(20)

    # Look at the first 5 failing cases
    for i, case in enumerate(single_cases[:5], 1):
        print(f"\n--- Case: single_{i:02d} ---")
        print(f"Expected factor: {case.expected_factors}")
        print(f"Full HPI text:")
        print(f"'{case.hpi_text}'")

        # Parse exactly like the stress test does
        parsed_hpi = parse_hpi(case.hpi_text)

        # Extract results exactly like stress test
        extracted_factors = parsed_hpi.get_feature_codes(include_negated=False)

        # Filter exactly like stress test
        filtered_extracted = [f for f in extracted_factors if not f.startswith(('ASA_', 'DENTAL_', 'ENT_'))]

        print(f"All extracted features: {extracted_factors}")
        print(f"Filtered extracted: {filtered_extracted}")
        print(f"Expected: {case.expected_factors}")
        print(f"Missing: {set(case.expected_factors) - set(filtered_extracted)}")

        # Check if this would pass the stress test validation
        parsing_correct = True
        for expected_factor in case.expected_factors:
            if expected_factor not in filtered_extracted:
                parsing_correct = False
                print(f"STRESS TEST FAIL: Missing expected factor {expected_factor}")
                break

        if parsing_correct:
            print("STRESS TEST PASS")

if __name__ == "__main__":
    debug_detailed_single_cases()