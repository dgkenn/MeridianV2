#!/usr/bin/env python3
"""Compare the two different ways of calling the parser"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from nlp.pipeline import MeridianNLPPipeline, parse_hpi

def compare_parsing_methods():
    test_text = "2-year-old male for parotidectomy. Medical history significant for obstructive sleep apnea. No other significant medical history."

    print("=== Testing Same Text with Different Methods ===")
    print(f"Text: {test_text}")
    print()

    # Method 1: Direct pipeline instance
    print("Method 1: MeridianNLPPipeline().parse_hpi()")
    pipeline1 = MeridianNLPPipeline()
    result1 = pipeline1.parse_hpi(test_text)
    features1 = [f.code for f in result1.features]
    print(f"Extracted: {features1}")
    print()

    # Method 2: Global parse_hpi function
    print("Method 2: parse_hpi() function")
    result2 = parse_hpi(test_text)
    features2 = [f.code for f in result2.features]
    print(f"Extracted: {features2}")
    print()

    # Compare
    print("=== Comparison ===")
    print(f"Method 1 found {len(features1)} features: {features1}")
    print(f"Method 2 found {len(features2)} features: {features2}")

    if features1 == features2:
        print("✓ Both methods give identical results")
    else:
        print("✗ Methods give different results!")
        print(f"  Only in Method 1: {set(features1) - set(features2)}")
        print(f"  Only in Method 2: {set(features2) - set(features1)}")

if __name__ == "__main__":
    compare_parsing_methods()