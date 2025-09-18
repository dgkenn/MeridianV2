#!/usr/bin/env python3
"""
Debug parsing issue - check patterns and ontology.
"""

import sys
from pathlib import Path
import re
sys.path.append(str(Path(__file__).parent))

def debug_patterns():
    """Check if our patterns actually match."""
    print("=" * 60)
    print("DEBUGGING PATTERN MATCHING")
    print("=" * 60)

    from src.core.hpi_parser import MedicalTextProcessor

    # Create parser and check patterns
    parser = MedicalTextProcessor()

    test_text = "coronary artery disease diabetes mellitus hypertension"

    print(f"Test text: {test_text}")
    print(f"\nCondition patterns available: {list(parser.condition_patterns.keys())}")

    print("\nTesting each pattern:")
    for condition_token, patterns in parser.condition_patterns.items():
        print(f"\n{condition_token}:")
        for i, pattern in enumerate(patterns):
            matches = pattern.finditer(test_text)
            match_list = list(matches)
            if match_list:
                print(f"  Pattern {i+1}: MATCH - {[m.group(0) for m in match_list]}")
            else:
                print(f"  Pattern {i+1}: no match - {pattern.pattern}")

def debug_ontology():
    """Check if ontology has CAD term."""
    print("\n" + "=" * 60)
    print("DEBUGGING ONTOLOGY")
    print("=" * 60)

    try:
        from ontology.core_ontology import AnesthesiaOntology

        ontology = AnesthesiaOntology()

        test_tokens = ["CAD", "DIABETES", "HYPERTENSION", "HEART_FAILURE"]

        print("Checking ontology terms:")
        for token in test_tokens:
            term = ontology.get_term(token)
            if term:
                print(f"  {token}: FOUND - {term.plain_label}")
            else:
                print(f"  {token}: NOT FOUND")

    except Exception as e:
        print(f"Error loading ontology: {e}")

def debug_full_parsing():
    """Debug the full parsing process."""
    print("\n" + "=" * 60)
    print("DEBUGGING FULL PARSING PROCESS")
    print("=" * 60)

    from src.core.hpi_parser import MedicalTextProcessor

    parser = MedicalTextProcessor()

    test_cases = [
        "coronary artery disease",
        "CAD",
        "diabetes mellitus",
        "diabetes",
        "hypertension"
    ]

    for test_case in test_cases:
        print(f"\nTesting: '{test_case}'")

        # Test rule-based extraction directly
        rule_factors = parser._extract_rule_based_factors(test_case)
        print(f"  Rule-based factors: {len(rule_factors)}")
        for factor in rule_factors:
            print(f"    - {factor.token}: {factor.plain_label}")

if __name__ == "__main__":
    debug_patterns()
    debug_ontology()
    debug_full_parsing()