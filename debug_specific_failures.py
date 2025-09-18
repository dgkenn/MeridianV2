#!/usr/bin/env python3
"""Debug specific pattern failures"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from nlp.pipeline import MeridianNLPPipeline
from comprehensive_stress_test import ComprehensiveTestGenerator

def debug_single_factor_failures():
    print("=== Debugging Single Factor Failures ===")

    generator = ComprehensiveTestGenerator()
    parser = MeridianNLPPipeline()

    # Generate some single factor cases to see what's failing
    single_cases = generator._generate_single_factor_cases(5)

    for case in single_cases:
        print(f"\nCase: {case.case_id}")
        print(f"Expected: {case.expected_factors}")
        print(f"Text: {case.hpi_text}")

        parsed = parser.parse_hpi(case.hpi_text)
        extracted = [f.code for f in parsed.features]
        filtered = [f for f in extracted if not f.startswith(('ASA_', 'DENTAL_', 'ENT_'))]

        print(f"All extracted: {extracted}")
        print(f"Filtered: {filtered}")
        print(f"Missing: {set(case.expected_factors) - set(filtered)}")

def test_specific_patterns():
    print("\n=== Testing Specific Medical Condition Patterns ===")

    parser = MeridianNLPPipeline()

    # Test cases for commonly failing patterns
    test_cases = [
        ("PREMATURITY", ["born premature", "premature infant", "born at 32 weeks", "32 week gestation", "preterm birth"]),
        ("RECENT_URI_2W", ["recent upper respiratory infection", "recent URI", "cold 2 weeks ago", "recent cold"]),
        ("OSA", ["sleep apnea", "OSA", "obstructive sleep apnea", "sleep disorder"]),
        ("DIABETES", ["diabetes", "diabetic", "Type 1 diabetes", "insulin dependent"]),
        ("ASTHMA", ["asthma", "reactive airway disease", "wheezing"])
    ]

    for expected_code, test_phrases in test_cases:
        print(f"\nTesting {expected_code}:")
        for phrase in test_phrases:
            parsed = parser.parse_hpi(phrase)
            extracted = [f.code for f in parsed.features]
            found = expected_code in extracted
            print(f"  '{phrase}' -> {extracted} {'[PASS]' if found else '[FAIL]'}")

if __name__ == "__main__":
    debug_single_factor_failures()
    test_specific_patterns()