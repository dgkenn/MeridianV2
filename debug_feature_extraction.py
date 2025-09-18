#!/usr/bin/env python3
"""Debug feature extraction methods"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from nlp.pipeline import MeridianNLPPipeline, parse_hpi

def debug_feature_extraction():
    print("=== Debugging Feature Extraction Methods ===")

    text = "2-year-old male for parotidectomy. Medical history significant for obstructive sleep apnea. No other significant medical history. No known drug allergies. Vital signs stable. Physical exam appropriate for age. NPO since midnight."

    print(f"Input text: '{text}'")
    print()

    # Test with fresh pipeline instance
    print("Method 1: Fresh pipeline instance")
    pipeline = MeridianNLPPipeline()
    result1 = pipeline.parse_hpi(text)

    print(f"Raw features: {result1.features}")
    print(f"Number of raw features: {len(result1.features)}")

    if result1.features:
        for i, feature in enumerate(result1.features):
            print(f"  Feature {i}: code='{feature.code}', negated={feature.modifiers.negated}")

    # Test get_feature_codes
    codes1 = result1.get_feature_codes(include_negated=False)
    print(f"get_feature_codes(include_negated=False): {codes1}")

    codes1_with_neg = result1.get_feature_codes(include_negated=True)
    print(f"get_feature_codes(include_negated=True): {codes1_with_neg}")

    # Manual extraction
    manual_codes = [f.code for f in result1.features if not f.negated]
    print(f"Manual extraction (not negated): {manual_codes}")

    manual_all = [f.code for f in result1.features]
    print(f"Manual extraction (all): {manual_all}")

if __name__ == "__main__":
    debug_feature_extraction()