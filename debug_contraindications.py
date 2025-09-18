#!/usr/bin/env python3
"""
Debug contraindication detection
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from services.meds_engine import create_meds_engine, PatientParameters

def debug_contraindications():
    """Debug contraindication detection"""
    engine = create_meds_engine()

    # Test MH History
    print("=== Testing MH History Contraindications ===")
    patient_mh = PatientParameters(age_years=35, weight_kg=70, sex="M", allergies=[])

    class MockParsedHPI:
        def get_feature_codes(self, include_negated=False):
            return ["MH_HISTORY"]

    parsed_hpi_mh = MockParsedHPI()
    risk_summary_mh = {'risks': {'MH_RISK': {'absolute_risk': 0.95, 'delta_vs_baseline': 0.90, 'confidence': 'A'}}}

    # Test contraindication check directly
    features = ["MH_HISTORY"]
    is_contra, reason = engine._check_contraindications("Succinylcholine", "Depolarizing_NMBD", features, patient_mh)
    print(f"Direct contraindication check for Succinylcholine: {is_contra}, reason: {reason}")

    # Test full recommendations
    recommendations_mh = engine.generate_recommendations(parsed_hpi_mh, risk_summary_mh, patient_mh)
    print(f"Contraindicated medications: {[med['agent'] for med in recommendations_mh['meds']['contraindicated']]}")

    print()

    # Test Egg/Soy Allergy
    print("=== Testing Egg/Soy Allergy Contraindications ===")
    patient_allergy = PatientParameters(age_years=25, weight_kg=65, sex="F", allergies=["EGG_SOY_ALLERGY"])

    class MockParsedHPI2:
        def get_feature_codes(self, include_negated=False):
            return []

    parsed_hpi_allergy = MockParsedHPI2()
    risk_summary_allergy = {'risks': {'PONV': {'absolute_risk': 0.35, 'delta_vs_baseline': 0.15, 'confidence': 'A'}}}

    # Test contraindication check directly
    is_contra2, reason2 = engine._check_contraindications("Propofol", "Propofol_Bolus", [], patient_allergy)
    print(f"Direct contraindication check for Propofol: {is_contra2}, reason: {reason2}")

    # Test full recommendations
    recommendations_allergy = engine.generate_recommendations(parsed_hpi_allergy, risk_summary_allergy, patient_allergy)
    print(f"Contraindicated medications: {[med['agent'] for med in recommendations_allergy['meds']['contraindicated']]}")

if __name__ == "__main__":
    debug_contraindications()