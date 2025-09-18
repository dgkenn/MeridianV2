#!/usr/bin/env python3
"""Debug the pipeline in detail to see what's happening"""

import sys
import re
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from nlp.pipeline import MeridianNLPPipeline

def debug_pipeline_detailed():
    print("=== Debugging Pipeline in Detail ===")

    pipeline = MeridianNLPPipeline()

    # Test the failing case
    text = "2-year-old male for parotidectomy. Medical history significant for obstructive sleep apnea. No other significant medical history. No known drug allergies. Vital signs stable. Physical exam appropriate for age. NPO since midnight."

    print(f"Input text: '{text}'")
    print()

    # Check if patterns are loaded
    print("Checking OSA patterns:")
    osa_patterns = pipeline.rules.get('risk_factor_patterns', {}).get('OSA', [])
    print(f"OSA patterns: {osa_patterns}")
    print()

    # Test each OSA pattern individually against the text
    print("Testing OSA patterns against text:")
    for i, pattern in enumerate(osa_patterns):
        matches = list(re.finditer(pattern, text, re.I))
        print(f"Pattern {i+1}: '{pattern}' -> {len(matches)} matches")
        for match in matches:
            print(f"  Match: '{match.group()}' at position {match.start()}-{match.end()}")
    print()

    # Check the cleaned text
    cleaned_text = pipeline._clean_text(text)
    print(f"Cleaned text: '{cleaned_text}'")
    print()

    # Test patterns against cleaned text
    print("Testing OSA patterns against cleaned text:")
    for i, pattern in enumerate(osa_patterns):
        matches = list(re.finditer(pattern, cleaned_text, re.I))
        print(f"Pattern {i+1}: '{pattern}' -> {len(matches)} matches")
        for match in matches:
            print(f"  Match: '{match.group()}' at position {match.start()}-{match.end()}")
    print()

    # Run full parsing and see what happens
    print("Running full parsing:")
    result = pipeline.parse_hpi(text)
    features = [f.code for f in result.features]
    print(f"Final extracted features: {features}")

if __name__ == "__main__":
    debug_pipeline_detailed()