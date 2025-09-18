#!/usr/bin/env python3
"""Debug why single factor cases are still failing"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from nlp.pipeline import MeridianNLPPipeline
from comprehensive_stress_test import ComprehensiveTestGenerator

def debug_single_factor_text_generation():
    print("=== Debugging Single Factor Text Generation ===")

    generator = ComprehensiveTestGenerator()
    parser = MeridianNLPPipeline()

    # Generate many single factor cases to see the actual text
    single_cases = generator._generate_single_factor_cases(10)

    for case in single_cases:
        print(f"\n--- Case: {case.case_id} ---")
        print(f"Expected factor: {case.expected_factors}")
        print(f"Full text: {case.hpi_text}")

        # Look for the factor description specifically
        factor = case.expected_factors[0] if case.expected_factors else "NONE"

        # Parse and check
        parsed = parser.parse_hpi(case.hpi_text)
        extracted = [f.code for f in parsed.features]
        filtered = [f for f in extracted if not f.startswith(('ASA_', 'DENTAL_', 'ENT_'))]

        print(f"All extracted: {extracted}")
        print(f"Filtered: {filtered}")
        print(f"Missing: {set(case.expected_factors) - set(filtered)}")

        # Check what the factor description function generates
        if hasattr(generator, '_generate_factor_description'):
            factor_desc = generator._generate_factor_description(factor)
            print(f"Factor description generated: '{factor_desc}'")

if __name__ == "__main__":
    debug_single_factor_text_generation()