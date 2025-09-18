#!/usr/bin/env python3
"""Debug negation context window"""

import sys
import re
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from nlp.pipeline import MeridianNLPPipeline

def debug_negation_context():
    print("=== Debugging Negation Context Window ===")

    text = "2-year-old male for parotidectomy. Medical history significant for obstructive sleep apnea. No other significant medical history. No known drug allergies. Vital signs stable. Physical exam appropriate for age. NPO since midnight."

    print(f"Full text: '{text}'")
    print()

    # Find the OSA match
    osa_pattern = r"(?:obstructive )?sleep apnea"
    match = re.search(osa_pattern, text, re.I)

    if match:
        start = match.start()
        end = match.end()
        print(f"OSA match: '{match.group()}' at position {start}-{end}")

        # Replicate the context window logic
        window_start = max(0, start - 50)
        window_end = min(len(text), end + 20)
        context = text[window_start:window_end]

        print(f"Context window (start-50 to end+20): '{context}'")
        print(f"Context window lowercased: '{context.lower()}'")
        print()

        # Test negation patterns
        pipeline = MeridianNLPPipeline()
        negation_patterns = pipeline.rules.get('negation_patterns', [])

        print("Testing negation patterns in context:")
        for pattern in negation_patterns:
            if re.search(pattern, context.lower()):
                print(f"  MATCH: '{pattern}' found in context")
            else:
                print(f"  no match: '{pattern}'")

if __name__ == "__main__":
    debug_negation_context()