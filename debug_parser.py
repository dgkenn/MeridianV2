#!/usr/bin/env python3
"""Debug the parser to understand ASA_2 extraction issue"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from nlp.pipeline import MeridianNLPPipeline

def debug_parser():
    print("Debugging parser ASA_2 extraction issue...")

    processor = MeridianNLPPipeline()

    # Test cases that are failing
    test_cases = [
        "7 year old healthy child for dental procedure",
        "3 year old with asthma for ENT surgery",
        "Child with recent URI for tonsillectomy",
        "Patient with diabetes for cardiac surgery"
    ]

    for i, text in enumerate(test_cases, 1):
        print(f"\n=== Test Case {i} ===")
        print(f"Input: {text}")

        try:
            result = processor.parse_hpi(text)
            print(f"Extracted factors: {[f.code for f in result.features]}")

            for feature in result.features:
                print(f"  - {feature.code}: '{feature.text}' (source: {feature.source}, confidence: {feature.confidence})")

        except Exception as e:
            print(f"Error: {e}")

    # Test specific ASA patterns
    print(f"\n=== Testing ASA patterns ===")
    asa_test_cases = [
        "ASA 2 patient",
        "ASA II classification",
        "No ASA mentioned",
        "asthma patient",  # This might be triggering ASA_2
        "Recent upper respiratory infection"
    ]

    for text in asa_test_cases:
        print(f"\nInput: '{text}'")
        result = processor.parse_hpi(text)
        extracted = [f.code for f in result.features]
        print(f"Extracted: {extracted}")

if __name__ == "__main__":
    debug_parser()