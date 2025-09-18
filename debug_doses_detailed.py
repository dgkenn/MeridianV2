#!/usr/bin/env python3
"""
Detailed debug of dose calculations
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from services.meds_engine import create_meds_engine, PatientParameters

def debug_single_drug():
    """Debug a single drug calculation"""
    engine = create_meds_engine()

    # Check Epinephrine dosing configuration
    dosing_rules = engine.dosing_rules.get('dosing_rules', {})
    epi_config = dosing_rules.get('Epinephrine', {})

    print("Epinephrine configuration:")
    print(f"  Full config: {epi_config}")

    pediatric_config = epi_config.get('pediatric', {})
    print(f"  Pediatric: {pediatric_config}")

    iv_config = pediatric_config.get('IV', {})
    print(f"  Pediatric IV: {iv_config}")

    print()

    # Test calculation manually
    patient_params = PatientParameters(
        age_years=4,
        weight_kg=18,
        sex="M"
    )

    print(f"Patient: {patient_params.age_years}y, {patient_params.weight_kg}kg")
    print(f"Is pediatric: {patient_params.is_pediatric}")

    # Try to calculate dose manually using engine logic
    try:
        dose_calc = engine._calculate_dose("Epinephrine", epi_config, patient_params)
        if dose_calc:
            print(f"Calculated dose: {dose_calc.mg} mg, {dose_calc.volume_ml} mL, {dose_calc.concentration}")
        else:
            print("No dose calculation returned")
    except Exception as e:
        print(f"Error calculating dose: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_single_drug()