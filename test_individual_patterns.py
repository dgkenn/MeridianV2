#!/usr/bin/env python3
"""Test individual pattern matching"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from nlp.pipeline import parse_hpi

def test_individual_patterns():
    print("=== Testing Individual Medical Condition Patterns ===")

    test_cases = [
        ("upper respiratory infection 10 days ago", "RECENT_URI_2W"),
        ("obstructive sleep apnea", "OSA"),
        ("sleep apnea", "OSA"),
        ("born premature at 28 weeks", "PREMATURITY"),
        ("premature", "PREMATURITY"),
        ("asthma", "ASTHMA"),
        ("diabetes", "DIABETES")
    ]

    for text, expected in test_cases:
        parsed = parse_hpi(text)
        extracted = parsed.get_feature_codes(include_negated=False)

        print(f"Text: '{text}'")
        print(f"Expected: {expected}")
        print(f"Extracted: {extracted}")

        if expected in extracted:
            print("PASS")
        else:
            print("FAIL")
        print()

if __name__ == "__main__":
    test_individual_patterns()