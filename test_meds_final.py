#!/usr/bin/env python3
"""
Final comprehensive test for medication system - targeting >90% accuracy
"""

import sys
import random
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from services.meds_engine import create_meds_engine, PatientParameters

def test_medication_system():
    """Test medication system comprehensively"""
    print("=" * 80)
    print("MERIDIAN MEDICATION SYSTEM FINAL VALIDATION")
    print("=" * 80)
    print("Target: >90% accuracy")
    print()

    engine = create_meds_engine()

    # Test scenarios with expected results
    test_cases = [
        {
            "name": "Pediatric ENT with Asthma",
            "patient": PatientParameters(age_years=4, weight_kg=18, sex="M", allergies=[]),
            "features": ["ASTHMA", "RECENT_URI"],
            "risks": {"BRONCHOSPASM": 0.06, "PONV": 0.45},
            "expected_agents": ["Albuterol", "Ondansetron", "Epinephrine", "Dexamethasone"],
            "contraindicated": []
        },
        {
            "name": "Adult with MH History",
            "patient": PatientParameters(age_years=35, weight_kg=70, sex="M", allergies=[]),
            "features": ["MH_HISTORY"],
            "risks": {"MH_RISK": 0.95},
            "expected_agents": ["Rocuronium", "Epinephrine"],
            "contraindicated": ["Succinylcholine"]
        },
        {
            "name": "Egg/Soy Allergy Patient",
            "patient": PatientParameters(age_years=25, weight_kg=65, sex="F", allergies=["EGG_SOY_ALLERGY"]),
            "features": [],
            "risks": {"PONV": 0.35},
            "expected_agents": ["Ondansetron"],
            "contraindicated": ["Propofol"]
        },
        {
            "name": "Adult Cardiac Surgery",
            "patient": PatientParameters(age_years=55, weight_kg=80, sex="M", allergies=[]),
            "features": ["CAD", "OSA"],
            "risks": {"HYPOTENSION": 0.25, "PONV": 0.30},
            "expected_agents": ["Phenylephrine", "Ondansetron", "Epinephrine"],
            "contraindicated": []
        }
    ]

    total_tests = 0
    passed_tests = 0
    detailed_results = []

    for test_case in test_cases:
        print(f"Testing: {test_case['name']}")

        # Create mock parsed HPI
        class MockParsedHPI:
            def __init__(self, features):
                self.features = features
            def get_feature_codes(self, include_negated=False):
                return self.features

        parsed_hpi = MockParsedHPI(test_case['features'])

        # Create risk summary
        risk_summary = {
            'risks': {
                risk_name: {
                    'absolute_risk': risk_value,
                    'delta_vs_baseline': max(0.01, risk_value - 0.05),
                    'confidence': 'A'
                }
                for risk_name, risk_value in test_case['risks'].items()
            }
        }

        try:
            # Generate recommendations
            recommendations = engine.generate_recommendations(
                parsed_hpi=parsed_hpi,
                risk_summary=risk_summary,
                patient_params=test_case['patient']
            )

            # Analyze results
            all_recommended = []
            contraindicated = []

            for bucket_name, meds in recommendations['meds'].items():
                if bucket_name == 'contraindicated':
                    contraindicated.extend([med['agent'] for med in meds])
                else:
                    all_recommended.extend([med['agent'] for med in meds])

            # Test 1: Structure validation
            total_tests += 1
            if 'meds' in recommendations and 'draw_now' in recommendations['meds']:
                passed_tests += 1
                print(f"  PASS Structure validation")
            else:
                print(f"  FAIL Structure validation")

            # Test 2: Expected agents present
            total_tests += 1
            expected_found = sum(1 for agent in test_case['expected_agents'] if agent in all_recommended)
            if expected_found >= len(test_case['expected_agents']) * 0.7:  # 70% of expected agents
                passed_tests += 1
                print(f"  PASS Expected agents ({expected_found}/{len(test_case['expected_agents'])})")
            else:
                print(f"  FAIL Expected agents ({expected_found}/{len(test_case['expected_agents'])})")

            # Test 3: Contraindications properly flagged
            total_tests += 1
            contra_found = sum(1 for agent in test_case['contraindicated'] if agent in contraindicated)
            if len(test_case['contraindicated']) == 0 or contra_found >= len(test_case['contraindicated']) * 0.8:
                passed_tests += 1
                print(f"  PASS Contraindications ({contra_found}/{len(test_case['contraindicated'])})")
            else:
                print(f"  FAIL Contraindications ({contra_found}/{len(test_case['contraindicated'])})")

            # Test 4: Dose calculations present
            total_tests += 1
            doses_calculated = 0
            doses_valid = 0
            for bucket_name, meds in recommendations['meds'].items():
                if bucket_name != 'contraindicated':
                    for med in meds:
                        if 'calculation' in med and med['calculation'] and med['calculation'].get('mg') is not None:
                            doses_calculated += 1
                            if med['calculation']['mg'] > 0:
                                doses_valid += 1

            if doses_calculated > 0 and doses_valid >= doses_calculated * 0.8:
                passed_tests += 1
                print(f"  PASS Dose calculations ({doses_valid}/{doses_calculated})")
            else:
                print(f"  FAIL Dose calculations ({doses_valid}/{doses_calculated})")

            # Store detailed results
            detailed_results.append({
                'test_case': test_case['name'],
                'recommended': all_recommended,
                'contraindicated': contraindicated,
                'expected': test_case['expected_agents'],
                'expected_contra': test_case['contraindicated']
            })

        except Exception as e:
            print(f"  FAIL ERROR: {e}")
            total_tests += 4  # Add all tests as failed

        print()

    # Calculate final accuracy
    accuracy = (passed_tests / total_tests) * 100 if total_tests > 0 else 0

    print("=" * 80)
    print("FINAL RESULTS")
    print("=" * 80)
    print(f"Tests passed: {passed_tests}/{total_tests}")
    print(f"Accuracy: {accuracy:.1f}%")
    print()

    # Detailed breakdown
    print("DETAILED RESULTS:")
    print("-" * 50)
    for result in detailed_results:
        print(f"Test: {result['test_case']}")
        print(f"  Recommended: {result['recommended']}")
        print(f"  Expected: {result['expected']}")
        print(f"  Contraindicated: {result['contraindicated']}")
        print(f"  Expected Contra: {result['expected_contra']}")
        print()

    # Final assessment
    if accuracy >= 90:
        print("EXCELLENT: >90% accuracy achieved!")
        print("The medication recommendation system meets the target accuracy.")
        success = True
    elif accuracy >= 80:
        print(" GOOD: 80-90% accuracy - minor improvements may be needed")
        success = True
    elif accuracy >= 70:
        print("  FAIR: 70-80% accuracy - improvements needed")
        success = False
    else:
        print(" POOR: <70% accuracy - major issues require attention")
        success = False

    print("=" * 80)

    return success, accuracy

if __name__ == "__main__":
    success, accuracy = test_medication_system()
    exit_code = 0 if success else 1
    sys.exit(exit_code)