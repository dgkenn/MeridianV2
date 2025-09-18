#!/usr/bin/env python3
"""Test the exact failing HPI texts"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from nlp.pipeline import parse_hpi

def test_full_hpi_texts():
    print("=== Testing Full HPI Texts That Are Failing ===")

    failing_texts = [
        # Case single_01
        ("6-month-old female for myringotomy with PE tubes. Medical history significant for upper respiratory infection 10 days ago. No other significant medical history. No known drug allergies. Vital signs stable. Physical exam appropriate for age. NPO since midnight.", "RECENT_URI_2W"),

        # Case single_02
        ("2-year-old male for parotidectomy. Medical history significant for obstructive sleep apnea. No other significant medical history. No known drug allergies. Vital signs stable. Physical exam appropriate for age. NPO since midnight.", "OSA"),

        # Case single_04
        ("3-week-old male for esophageal atresia repair. Medical history significant for born premature at 28 weeks. No other significant medical history. No known drug allergies. Vital signs stable. Physical exam appropriate for age. NPO since midnight.", "PREMATURITY"),

        # Case single_05
        ("78-year-old female for tonsillectomy and adenoidectomy. Medical history significant for sleep apnea. No other significant medical history. No known drug allergies. Vital signs stable. Physical exam appropriate for age. NPO since midnight.", "OSA")
    ]

    for i, (text, expected) in enumerate(failing_texts, 1):
        print(f"\n--- Full HPI Test {i} ---")
        print(f"Text: '{text}'")
        print(f"Expected: {expected}")

        parsed = parse_hpi(text)
        extracted = parsed.get_feature_codes(include_negated=False)

        print(f"All extracted: {extracted}")

        # Apply stress test filtering
        filtered = [f for f in extracted if not f.startswith(('ASA_', 'DENTAL_', 'ENT_'))]
        print(f"Filtered: {filtered}")

        if expected in filtered:
            print("PASS")
        else:
            print("FAIL")

            # Try to isolate the medical history part
            if "Medical history significant for " in text:
                medical_part = text.split("Medical history significant for ")[1].split(".")[0]
                print(f"Medical history part: '{medical_part}'")
                parsed_medical = parse_hpi(medical_part)
                medical_extracted = parsed_medical.get_feature_codes(include_negated=False)
                print(f"Medical part alone extracts: {medical_extracted}")

if __name__ == "__main__":
    test_full_hpi_texts()