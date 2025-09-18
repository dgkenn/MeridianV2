#!/usr/bin/env python3
"""Debug risk calculation for healthy baseline cases"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from comprehensive_stress_test import ComprehensiveTestGenerator
from risk_engine.schema import AgeBand, SurgeryType, Urgency, TimeWindow
from risk_engine.baseline import BaselineRiskEngine
from risk_engine.schema import RiskConfig

def debug_risk_calculation():
    print("=== Debugging Risk Calculation for Healthy Cases ===")

    generator = ComprehensiveTestGenerator()
    healthy_cases = generator._generate_healthy_cases(3)

    # Initialize risk engine
    config = RiskConfig()
    baseline_engine = BaselineRiskEngine(config)

    for case in healthy_cases:
        print(f"\nCase ID: {case.case_id}")
        print(f"Expected age_band: {case.expected_age_band}")
        print(f"Expected surgery_type: {case.expected_surgery_type}")
        print(f"Expected urgency: {case.expected_urgency}")

        try:
            # Test the same logic as the stress test
            age_band = AgeBand(case.expected_age_band) if case.expected_age_band != "varies" else AgeBand.SEVEN_TO_12
            surgery_type = SurgeryType(case.expected_surgery_type)
            urgency = Urgency(case.expected_urgency)

            print(f"Parsed enums: age_band={age_band}, surgery={surgery_type}, urgency={urgency}")

            baseline = baseline_engine.get_baseline_risk(
                outcome="LARYNGOSPASM",
                window=TimeWindow.INTRAOP,
                age_band=age_band,
                surgery=surgery_type,
                urgency=urgency
            )

            if baseline:
                print(f"Baseline risk: {baseline.p0:.4f} ({baseline.p0:.1%})")
                if baseline.p0 > 0.5:
                    print("  ISSUE: Baseline risk > 50% (unrealistic)")
                else:
                    print("  OK: Baseline risk realistic")
            else:
                print("  ISSUE: No baseline risk found")

        except Exception as e:
            print(f"  ERROR in risk calculation: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    debug_risk_calculation()