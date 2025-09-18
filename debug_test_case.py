#!/usr/bin/env python3
"""Debug specific test case to understand validation issue"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from comprehensive_stress_test import ComprehensiveTestGenerator
from nlp.pipeline import MeridianNLPPipeline

def debug_healthy_baseline():
    print("=== Debugging Healthy Baseline Cases ===")

    generator = ComprehensiveTestGenerator()
    healthy_cases = generator._generate_healthy_cases(3)

    parser = MeridianNLPPipeline()

    for case in healthy_cases:
        print(f"\nCase ID: {case.case_id}")
        print(f"HPI Text: {case.hpi_text}")
        print(f"Expected factors: {case.expected_factors}")

        # Parse the HPI
        parsed = parser.parse_hpi(case.hpi_text)
        extracted_factors = parsed.get_feature_codes(include_negated=False)

        # Filter as the test does
        filtered_extracted = [f for f in extracted_factors if not f.startswith(('ASA_', 'DENTAL_', 'ENT_'))]

        print(f"All extracted: {extracted_factors}")
        print(f"Filtered extracted: {filtered_extracted}")

        # Check validation logic
        parsing_correct = True

        # Check for expected factors
        for expected_factor in case.expected_factors:
            if expected_factor not in filtered_extracted:
                parsing_correct = False
                print(f"  Missing expected factor: {expected_factor}")
                break

        # Check for false positives
        major_false_positives = ["SEPSIS", "FEVER", "HYPOXEMIA"]
        for fp in major_false_positives:
            if fp in filtered_extracted and case.category == "healthy_baseline":
                parsing_correct = False
                print(f"  Found false positive: {fp}")
                break

        print(f"Should pass validation: {parsing_correct}")

def debug_specific_conditions():
    print("\n=== Debugging Specific Medical Conditions ===")

    generator = ComprehensiveTestGenerator()

    # Test specific condition patterns
    test_texts = [
        "congenital heart disease",
        "CHD",
        "diabetes mellitus",
        "Type 1 diabetes",
        "born premature",
        "born at 32 weeks",
        "sleep apnea",
        "OSA"
    ]

    parser = MeridianNLPPipeline()

    for text in test_texts:
        print(f"\nTesting: '{text}'")
        parsed = parser.parse_hpi(text)
        extracted = [f.code for f in parsed.features]
        print(f"  Extracted: {extracted}")

if __name__ == "__main__":
    debug_healthy_baseline()
    debug_specific_conditions()