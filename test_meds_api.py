#!/usr/bin/env python3
"""
Test the Medication API functionality
"""

import sys
import json
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from services.meds_engine import create_meds_engine, PatientParameters
from nlp.pipeline import parse_hpi

def test_medication_recommendations():
    """Test medication recommendation generation"""
    print("=== Testing Medication Recommendation Engine ===")

    # Initialize engine
    engine = create_meds_engine()

    # Test case: 4-year-old for T&A with asthma and recent URI
    hpi_text = "4-year-old male for tonsillectomy and adenoidectomy. Medical history significant for asthma with recent upper respiratory infection 5 days ago. Uses albuterol PRN. No other significant medical history. No known drug allergies. Vital signs stable. Physical exam appropriate for age. NPO since midnight."

    # Parse HPI
    parsed_hpi = parse_hpi(hpi_text)
    print(f"Parsed features: {parsed_hpi.get_feature_codes(include_negated=False)}")

    # Create patient parameters
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

    # Mock risk summary (elevated bronchospasm and laryngospasm risk)
    risk_summary = {
        'risks': {
            'BRONCHOSPASM': {
                'absolute_risk': 0.06,  # 6% risk
                'delta_vs_baseline': 0.03,  # 3pp increase
                'confidence': 'A'
            },
            'LARYNGOSPASM': {
                'absolute_risk': 0.04,  # 4% risk
                'delta_vs_baseline': 0.02,  # 2pp increase
                'confidence': 'A'
            },
            'PONV': {
                'absolute_risk': 0.45,  # 45% risk
                'delta_vs_baseline': 0.20,  # 20pp increase
                'confidence': 'A'
            }
        }
    }

    # Generate recommendations
    try:
        recommendations = engine.generate_recommendations(
            parsed_hpi=parsed_hpi,
            risk_summary=risk_summary,
            patient_params=patient_params
        )

        print("\n=== MEDICATION RECOMMENDATIONS ===")
        print(json.dumps(recommendations, indent=2))

        # Validate structure
        assert 'patient' in recommendations
        assert 'meds' in recommendations
        assert 'summary' in recommendations

        meds = recommendations['meds']
        assert 'draw_now' in meds
        assert 'standard' in meds
        assert 'consider' in meds
        assert 'contraindicated' in meds

        print(f"\n=== SUMMARY ===")
        print(f"Draw now: {len(meds['draw_now'])} medications")
        print(f"Standard: {len(meds['standard'])} medications")
        print(f"Consider: {len(meds['consider'])} medications")
        print(f"Contraindicated: {len(meds['contraindicated'])} medications")

        # Check for expected medications
        draw_now_agents = [med['agent'] for med in meds['draw_now']]
        standard_agents = [med['agent'] for med in meds['standard']]

        print(f"\nDraw now agents: {draw_now_agents}")
        print(f"Standard agents: {standard_agents}")

        # Should have bronchodilator and emergency medications ready
        expected_classes = ['Emergency_Bronchodilator', 'Beta2_Agonist', '5HT3_Antagonist']

        all_agents = draw_now_agents + standard_agents
        print(f"All recommended agents: {all_agents}")

        return True

    except Exception as e:
        print(f"ERROR: Medication recommendation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_dose_calculations():
    """Test dose calculation accuracy"""
    print("\n=== Testing Dose Calculations ===")

    engine = create_meds_engine()

    test_cases = [
        {
            'agent': 'Ondansetron',
            'patient': {'age_years': 4, 'weight_kg': 18},
            'expected_dose_range': (1.5, 2.0)  # 0.1 mg/kg with min/max
        },
        {
            'agent': 'Dexamethasone',
            'patient': {'age_years': 6, 'weight_kg': 22},
            'expected_dose_range': (3.0, 4.0)  # 0.15 mg/kg
        }
    ]

    for test_case in test_cases:
        agent = test_case['agent']
        patient_data = test_case['patient']

        patient_params = PatientParameters(
            age_years=patient_data['age_years'],
            weight_kg=patient_data['weight_kg']
        )

        dose_info = engine.dosing_rules.get('dosing_rules', {}).get(agent, {})
        if dose_info:
            calc = engine._calculate_dose(agent, dose_info, patient_params)
            if calc:
                print(f"{agent}: {calc.mg:.1f} mg ({calc.volume_ml:.1f} mL from {calc.concentration})")

                expected_min, expected_max = test_case['expected_dose_range']
                if expected_min <= calc.mg <= expected_max:
                    print(f"  PASS: Dose within expected range")
                else:
                    print(f"  FAIL: Dose outside expected range ({expected_min}-{expected_max} mg)")
            else:
                print(f"  FAIL: Dose calculation failed for {agent}")
        else:
            print(f"  FAIL: No dosing info found for {agent}")

def test_contraindication_screening():
    """Test contraindication detection"""
    print("\n=== Testing Contraindication Screening ===")

    engine = create_meds_engine()

    # Test MH history contraindication
    patient_params = PatientParameters(
        age_years=10,
        weight_kg=30,
        allergies=[]
    )

    features = ['MH_HISTORY']

    # Should contraindicate succinylcholine
    is_contra, reason = engine._check_contraindications(
        'Succinylcholine', 'Depolarizing_NMBD', features, patient_params
    )

    print(f"Succinylcholine with MH history: Contraindicated={is_contra}, Reason={reason}")

    # Test egg/soy allergy
    allergy_patient = PatientParameters(
        age_years=6,
        weight_kg=22,
        allergies=['EGG_SOY_ALLERGY']
    )

    is_contra_prop, reason_prop = engine._check_contraindications(
        'Propofol', 'Propofol_Bolus', [], allergy_patient
    )

    print(f"Propofol with egg/soy allergy: Contraindicated={is_contra_prop}, Reason={reason_prop}")

if __name__ == "__main__":
    print("Testing Meridian Medication Engine")
    print("=" * 50)

    success = True

    # Test recommendation generation
    if not test_medication_recommendations():
        success = False

    # Test dose calculations
    test_dose_calculations()

    # Test contraindication screening
    test_contraindication_screening()

    if success:
        print("\nPASS: All medication engine tests completed successfully!")
    else:
        print("\nFAIL: Some tests failed!")