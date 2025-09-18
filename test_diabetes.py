#!/usr/bin/env python3
"""Test diabetes patterns"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from nlp.pipeline import MeridianNLPPipeline

def test_diabetes():
    parser = MeridianNLPPipeline()

    test_cases = [
        "diabetes mellitus",
        "diabetes",
        "diabetic",
        "Type 1 diabetes",
        "T1DM",
        "insulin dependent"
    ]

    print("Testing diabetes patterns:")
    for text in test_cases:
        parsed = parser.parse_hpi(text)
        extracted = [f.code for f in parsed.features]
        print(f"  '{text}' -> {extracted}")

if __name__ == "__main__":
    test_diabetes()