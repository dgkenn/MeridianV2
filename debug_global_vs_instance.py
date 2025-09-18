#!/usr/bin/env python3
"""Compare global parse_hpi vs instance method"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from nlp.pipeline import MeridianNLPPipeline, parse_hpi

def debug_global_vs_instance():
    print("=== Comparing Global vs Instance Parsing ===")

    text = "2-year-old male for parotidectomy. Medical history significant for obstructive sleep apnea. No other significant medical history. No known drug allergies. Vital signs stable. Physical exam appropriate for age. NPO since midnight."

    print(f"Input text: '{text}'")
    print()

    # Method 1: Instance method (like debug_exact_single_case.py)
    print("Method 1: Fresh pipeline instance")
    pipeline = MeridianNLPPipeline()
    result1 = pipeline.parse_hpi(text)
    features1 = result1.get_feature_codes(include_negated=False)
    print(f"Instance method extracted: {features1}")
    print()

    # Method 2: Global function (like comprehensive stress test)
    print("Method 2: Global parse_hpi function")
    result2 = parse_hpi(text)
    features2 = result2.get_feature_codes(include_negated=False)
    print(f"Global function extracted: {features2}")
    print()

    # Compare
    print("=== Comparison ===")
    if features1 == features2:
        print("Both methods give identical results")
    else:
        print("Methods give DIFFERENT results!")
        print(f"  Instance method: {features1}")
        print(f"  Global function: {features2}")
        print(f"  Only in instance: {set(features1) - set(features2)}")
        print(f"  Only in global: {set(features2) - set(features1)}")

    # Apply stress test filtering to both
    filtered1 = [f for f in features1 if not f.startswith(('ASA_', 'DENTAL_', 'ENT_'))]
    filtered2 = [f for f in features2 if not f.startswith(('ASA_', 'DENTAL_', 'ENT_'))]

    print()
    print("After stress test filtering:")
    print(f"  Instance method filtered: {filtered1}")
    print(f"  Global function filtered: {filtered2}")

if __name__ == "__main__":
    debug_global_vs_instance()