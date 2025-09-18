#!/usr/bin/env python3
"""Debug the exact stress test validation logic"""

import sys
import random
import time
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from nlp.pipeline import MeridianNLPPipeline
from comprehensive_stress_test import ComprehensiveTestGenerator
from risk_engine.schema import AgeBand, SurgeryType, Urgency, TimeWindow
from risk_engine.baseline import BaselineRiskEngine
from risk_engine.schema import RiskConfig

def debug_stress_validation_logic():
    print("=== Debugging Stress Test Validation Logic ===")

    # Set same random seed as stress test
    random.seed(42)

    # Initialize same components as stress test
    generator = ComprehensiveTestGenerator()

    # Import parse_hpi from same place as stress test
    from nlp.pipeline import parse_hpi
    print("Using parse_hpi from pipeline")

    # Initialize risk components
    config = RiskConfig()
    baseline_engine = BaselineRiskEngine(config)

    # Generate the exact same single factor cases
    single_cases = generator._generate_single_factor_cases(20)

    # Test the first 5 failing cases with exact stress test logic
    for i, case in enumerate(single_cases[:5], 1):
        print(f"\n--- Testing Case: single_{i:02d} with full stress test logic ---")
        print(f"Expected: {case.expected_factors}")
        print(f"HPI: {case.hpi_text}")

        try:
            # Replicate exact stress test logic
            parsed_hpi = parse_hpi(case.hpi_text)

            # Extract results
            extracted_factors = parsed_hpi.get_feature_codes(include_negated=False)

            # Filter out ASA classifications and procedure-specific codes for validation
            filtered_extracted = [f for f in extracted_factors if not f.startswith(('ASA_', 'DENTAL_', 'ENT_'))]

            # Validate parsing results
            parsing_correct = True

            print(f"All extracted: {extracted_factors}")
            print(f"Filtered: {filtered_extracted}")

            # Check for expected factors
            for expected_factor in case.expected_factors:
                if expected_factor not in filtered_extracted:
                    parsing_correct = False
                    print(f"FAIL: Missing expected factor {expected_factor}")
                    break

            # Check for unexpected factors (major false positives)
            major_false_positives = ["SEPSIS", "FEVER", "HYPOXEMIA", "SEPSIS_RISK"]
            for fp in major_false_positives:
                if fp in filtered_extracted and case.category == "healthy_baseline":
                    parsing_correct = False
                    print(f"FAIL: False positive {fp} for healthy baseline")
                    break

            print(f"Parsing validation: {'PASS' if parsing_correct else 'FAIL'}")

            # Test risk calculation if parsing successful
            if parsing_correct:
                print("Testing risk calculation...")
                try:
                    age_band = AgeBand(case.expected_age_band) if case.expected_age_band != "varies" else AgeBand.SEVEN_TO_12
                    surgery_type = SurgeryType(case.expected_surgery_type)
                    urgency = Urgency(case.expected_urgency)

                    print(f"Risk calc params: age_band={age_band}, surgery={surgery_type}, urgency={urgency}")

                    baseline = baseline_engine.get_baseline_risk(
                        outcome="LARYNGOSPASM",
                        window=TimeWindow.INTRAOP,
                        age_band=age_band,
                        surgery=surgery_type,
                        urgency=urgency
                    )

                    if baseline:
                        print(f"Baseline risk: {baseline.p0:.4f}")
                        # Check for realistic risk levels
                        if baseline.p0 > 0.5:  # >50% is unrealistic
                            parsing_correct = False
                            print(f"FAIL: Unrealistic baseline risk {baseline.p0:.1%}")
                    else:
                        print("FAIL: No baseline risk found")
                        parsing_correct = False

                except Exception as e:
                    print(f"FAIL: Risk calculation error: {e}")
                    parsing_correct = False

            print(f"Final result: {'PASS' if parsing_correct else 'FAIL'}")

        except Exception as e:
            print(f"FAIL: Parser error: {e}")

if __name__ == "__main__":
    debug_stress_validation_logic()