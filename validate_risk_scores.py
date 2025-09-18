#!/usr/bin/env python3
"""Sample a few test cases and validate their risk scores are clinically realistic"""

import sys
import random
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from nlp.pipeline import parse_hpi
from risk_engine.baseline import BaselineRiskEngine
from risk_engine.schema import RiskConfig, AgeBand, SurgeryType, Urgency, TimeWindow
from comprehensive_stress_test import ComprehensiveTestGenerator

def validate_risk_scores():
    print("=== Validating Risk Scores for Clinical Realism ===")

    # Set seed for consistency
    random.seed(42)

    # Initialize components
    generator = ComprehensiveTestGenerator()
    config = RiskConfig()
    baseline_engine = BaselineRiskEngine(config)

    # Sample representative cases
    test_cases = []
    test_cases.extend(generator._generate_healthy_cases(3))
    test_cases.extend(generator._generate_single_factor_cases(5))
    test_cases.extend(generator._generate_multiple_factor_cases(3))

    print(f"Testing {len(test_cases)} representative cases for risk score validation...\n")

    for i, case in enumerate(test_cases):
        print(f"--- Case {i+1}: {case.case_id} ---")
        print(f"Patient: {case.hpi_text[:80]}...")
        print(f"Expected factors: {case.expected_factors}")

        # Parse HPI
        parsed_hpi = parse_hpi(case.hpi_text)
        extracted_factors = parsed_hpi.get_feature_codes(include_negated=False)

        print(f"Extracted factors: {extracted_factors}")

        try:
            # Get baseline risk
            age_band = AgeBand(case.expected_age_band) if case.expected_age_band != "varies" else AgeBand.SEVEN_TO_12
            surgery_type = SurgeryType(case.expected_surgery_type)
            urgency = Urgency(case.expected_urgency)

            baseline = baseline_engine.get_baseline_risk(
                outcome="LARYNGOSPASM",
                window=TimeWindow.INTRAOP,
                age_band=age_band,
                surgery=surgery_type,
                urgency=urgency
            )

            if baseline:
                risk_percent = baseline.p0 * 100
                print(f"Baseline laryngospasm risk: {risk_percent:.2f}%")

                # Clinical validation
                if risk_percent > 50:
                    print("  CONCERN: Risk >50% seems unrealistically high")
                elif risk_percent > 20:
                    print("  CAUTION: Risk >20% is very high")
                elif risk_percent > 10:
                    print("  HIGH: Risk >10% warrants attention")
                elif risk_percent > 5:
                    print("  MODERATE: Risk 5-10% is reasonable")
                elif risk_percent > 1:
                    print("  LOW: Risk 1-5% is typical")
                else:
                    print("  MINIMAL: Risk <1% is very low")

                # Age-specific validation
                if "infant" in case.expected_age_band or "neonate" in case.expected_age_band:
                    if risk_percent < 2:
                        print("  NOTE: Infants typically have higher laryngospasm risk")

                # Surgery-specific validation
                if case.expected_surgery_type == "ENT" and risk_percent < 3:
                    print("  NOTE: ENT procedures typically have higher laryngospasm risk")

            else:
                print("  ERROR: No baseline risk found")

        except Exception as e:
            print(f"  ERROR: Risk calculation error: {e}")

        print()

if __name__ == "__main__":
    validate_risk_scores()