#!/usr/bin/env python3
"""Debug the exact failing single factor cases"""

import sys
import random
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from nlp.pipeline import MeridianNLPPipeline
from comprehensive_stress_test import ComprehensiveTestGenerator

def debug_exact_single_cases():
    print("=== Debugging Exact Single Factor Cases ===")

    # Set same random seed as stress test
    random.seed(42)

    generator = ComprehensiveTestGenerator()
    parser = MeridianNLPPipeline()

    # Generate the exact same single factor cases as the stress test
    single_cases = generator._generate_single_factor_cases(20)

    # Look at the first 5 failing cases
    failing_cases = ['single_01', 'single_02', 'single_03', 'single_04', 'single_05']

    for i, case in enumerate(single_cases[:5], 1):
        print(f"\n--- Case: single_{i:02d} ---")
        print(f"Expected factor: {case.expected_factors}")
        print(f"Full HPI text:")
        print(f"'{case.hpi_text}'")

        # Parse and check what happens
        parsed = parser.parse_hpi(case.hpi_text)
        all_extracted = [f.code for f in parsed.features]
        filtered = [f for f in all_extracted if not f.startswith(('ASA_', 'DENTAL_', 'ENT_'))]

        print(f"All extracted features: {all_extracted}")
        print(f"Filtered extracted: {filtered}")
        print(f"Expected: {case.expected_factors}")
        print(f"Missing: {set(case.expected_factors) - set(filtered)}")

        # Test the factor description directly
        if case.expected_factors:
            factor = case.expected_factors[0]
            factor_desc = generator._generate_factor_description(factor)
            print(f"Factor description alone: '{factor_desc}'")

            # Test if the description alone works
            desc_parsed = parser.parse_hpi(factor_desc)
            desc_extracted = [f.code for f in desc_parsed.features]
            print(f"Description alone extracts: {desc_extracted}")

if __name__ == "__main__":
    debug_exact_single_cases()