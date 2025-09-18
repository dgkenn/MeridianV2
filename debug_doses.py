#!/usr/bin/env python3
"""
Debug dose calculations to understand what's happening
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from services.meds_engine import create_meds_engine, PatientParameters

def debug_dose_calculations():
    """Debug what's happening with dose calculations"""
    engine = create_meds_engine()

    # Create test patient
    patient_params = PatientParameters(
        age_years=4,
        weight_kg=18,
        height_cm=100,
        sex="M",
        urgency="elective",
        surgery_domain="ENT",
        allergies=[],
        renal_function=None,
        hepatic_function=None
    )

    # Create mock parsed HPI with asthma features
    class MockParsedHPI:
        def get_feature_codes(self, include_negated=False):
            return ["ASTHMA", "RECENT_URI"]

    parsed_hpi = MockParsedHPI()

    # Create risk summary
    risk_summary = {
        'risks': {
            'BRONCHOSPASM': {
                'absolute_risk': 0.06,
                'delta_vs_baseline': 0.03,
                'confidence': 'A'
            },
            'PONV': {
                'absolute_risk': 0.45,
                'delta_vs_baseline': 0.20,
                'confidence': 'A'
            }
        }
    }

    print("Debugging medication recommendations...")
    print(f"Patient: {patient_params.age_years}y {patient_params.weight_kg}kg {patient_params.sex}")
    print()

    try:
        recommendations = engine.generate_recommendations(
            parsed_hpi=parsed_hpi,
            risk_summary=risk_summary,
            patient_params=patient_params
        )

        print("Generated recommendations:")
        print("-" * 50)

        for bucket_name, meds in recommendations['meds'].items():
            print(f"\n{bucket_name.upper()}:")
            if not meds:
                print("  (none)")
                continue

            for med in meds:
                print(f"  Agent: {med.agent if hasattr(med, 'agent') else med.get('agent', 'unknown')}")

                # Check dose information
                if hasattr(med, 'dose'):
                    print(f"    Dose (string): {med.dose}")
                elif 'dose' in med:
                    print(f"    Dose (string): {med['dose']}")
                else:
                    print("    Dose (string): None")

                # Check calculation information
                if hasattr(med, 'calculation'):
                    if med.calculation:
                        print(f"    Calculation: {med.calculation.mg} mg, {med.calculation.volume_ml} mL, {med.calculation.concentration}")
                    else:
                        print("    Calculation: None")
                elif 'calculation' in med:
                    calc = med['calculation']
                    if calc:
                        print(f"    Calculation: {calc.get('mg', 'N/A')} mg, {calc.get('volume_ml', 'N/A')} mL, {calc.get('concentration', 'N/A')}")
                    else:
                        print("    Calculation: None")
                else:
                    print("    Calculation: Not found")

                # Check what type med is
                print(f"    Type: {type(med)}")
                print()

        print("\nRaw recommendations structure:")
        print(f"Type: {type(recommendations['meds'])}")
        for bucket_name, meds in recommendations['meds'].items():
            print(f"{bucket_name}: {len(meds)} items")
            if meds:
                print(f"  First item type: {type(meds[0])}")
                if hasattr(meds[0], '__dict__'):
                    print(f"  First item attrs: {list(vars(meds[0]).keys())}")
                elif isinstance(meds[0], dict):
                    print(f"  First item keys: {list(meds[0].keys())}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_dose_calculations()