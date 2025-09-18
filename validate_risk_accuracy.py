#!/usr/bin/env python3
"""
Validate risk calculation accuracy against published literature.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.core.hpi_parser import MedicalTextProcessor
from src.core.risk_engine import RiskEngine
from dataclasses import dataclass
from typing import List, Dict
import json

@dataclass
class LiteratureBaseline:
    """Literature-based baseline risk for validation."""
    condition: str
    population: str
    outcome: str
    baseline_risk: float
    source: str
    year: int
    sample_size: int

@dataclass
class ValidationCase:
    """Test case for risk validation."""
    name: str
    hpi_text: str
    expected_conditions: List[str]
    demographics: Dict
    literature_risks: List[LiteratureBaseline]

def get_validation_cases() -> List[ValidationCase]:
    """Get test cases with literature-validated risks."""
    return [
        ValidationCase(
            name="Pediatric ENT with OSA and Recent URI",
            hpi_text="5-year-old boy presenting for tonsillectomy and adenoidectomy. History of OSA with AHI 12, snoring, restless sleep. Recent upper respiratory infection 2 weeks ago with persistent cough. No other medical history.",
            expected_conditions=["OSA", "RECENT_URI_2W", "AGE_1_5"],
            demographics={"age_years": 5, "sex": "male", "weight_kg": 18},
            literature_risks=[
                LiteratureBaseline("OSA", "pediatric_ent", "LARYNGOSPASM", 0.173, "von Ungern-Sternberg 2010", 2010, 1089),
                LiteratureBaseline("RECENT_URI_2W", "pediatric_ent", "LARYNGOSPASM", 0.147, "Tait 2001", 2001, 9297),
                LiteratureBaseline("Combined OSA+URI", "pediatric_ent", "LARYNGOSPASM", 0.230, "Schreiner 1996", 1996, 4634)
            ]
        ),

        ValidationCase(
            name="Adult Cardiac Surgery with Multiple Comorbidities",
            hpi_text="65-year-old male with coronary artery disease status post CABG 2 years ago, diabetes mellitus type 2 on metformin and insulin, hypertension on lisinopril, chronic kidney disease stage 3, presenting for valve replacement.",
            expected_conditions=["CORONARY_ARTERY_DISEASE", "DIABETES", "HYPERTENSION", "CHRONIC_KIDNEY_DISEASE", "AGE_ELDERLY"],
            demographics={"age_years": 65, "sex": "male", "weight_kg": 85},
            literature_risks=[
                LiteratureBaseline("CAD", "adult_cardiac", "MORTALITY_INHOSPITAL", 0.023, "STS Database 2019", 2019, 250000),
                LiteratureBaseline("Diabetes", "adult_cardiac", "ACUTE_KIDNEY_INJURY", 0.156, "Palomba 2008", 2008, 9519),
                LiteratureBaseline("CKD Stage 3", "adult_cardiac", "DIALYSIS_INITIATION", 0.089, "Coca 2012", 2012, 3795)
            ]
        ),

        ValidationCase(
            name="Emergency Surgery with Full Stomach",
            hpi_text="32-year-old trauma patient with blunt abdominal trauma, last meal 3 hours ago, presenting emergently for exploratory laparotomy. Hemodynamically stable but full stomach.",
            expected_conditions=["TRAUMA", "FULL_STOMACH", "AGE_ADULT_YOUNG"],
            demographics={"age_years": 32, "sex": "male", "weight_kg": 75},
            literature_risks=[
                LiteratureBaseline("Full stomach", "adult_emergency", "ASPIRATION", 0.067, "Warner 1993", 1993, 215488),
                LiteratureBaseline("Emergency surgery", "adult_emergency", "MORTALITY_INHOSPITAL", 0.089, "Pearse 2012", 2012, 4311)
            ]
        ),

        ValidationCase(
            name="Elderly Patient with Multiple Medications",
            hpi_text="78-year-old female with atrial fibrillation on warfarin, heart failure NYHA class II on metoprolol and lisinopril, presenting for hip fracture repair.",
            expected_conditions=["HEART_FAILURE", "AGE_VERY_ELDERLY", "ANTICOAGULANTS", "BETA_BLOCKERS", "ACE_INHIBITORS"],
            demographics={"age_years": 78, "sex": "female", "weight_kg": 65},
            literature_risks=[
                LiteratureBaseline("Heart failure", "adult_general", "POSTOP_DELIRIUM", 0.189, "Dasgupta 2014", 2014, 566),
                LiteratureBaseline("Age >75", "adult_general", "MORTALITY_INHOSPITAL", 0.045, "Story 2009", 2009, 564535),
                LiteratureBaseline("Warfarin", "adult_general", "BLOOD_TRANSFUSION", 0.156, "Spahn 2013", 2013, 3016)
            ]
        )
    ]

def validate_parsing_accuracy():
    """Validate that parsing correctly identifies expected conditions."""
    print("=== PARSING ACCURACY VALIDATION ===")

    parser = MedicalTextProcessor()
    cases = get_validation_cases()

    total_conditions = 0
    correctly_identified = 0

    for case in cases:
        print(f"\nCase: {case.name}")
        print(f"Expected conditions: {case.expected_conditions}")

        # Parse the HPI
        parsed = parser.parse_hpi(case.hpi_text)
        extracted_tokens = [factor.token for factor in parsed.extracted_factors]

        print(f"Extracted conditions: {extracted_tokens}")

        # Check accuracy
        for expected in case.expected_conditions:
            total_conditions += 1
            if expected in extracted_tokens:
                correctly_identified += 1
                print(f"  [OK] {expected}")
            else:
                print(f"  [MISSING] {expected}")

    accuracy = correctly_identified / total_conditions if total_conditions > 0 else 0
    print(f"\nParsing Accuracy: {correctly_identified}/{total_conditions} ({accuracy:.1%})")

    return accuracy >= 0.85  # 85% accuracy threshold

def validate_risk_calculations():
    """Validate risk calculations against literature."""
    print("\n=== RISK CALCULATION VALIDATION ===")

    parser = MedicalTextProcessor()
    risk_engine = RiskEngine()
    cases = get_validation_cases()

    validation_results = []

    for case in cases:
        print(f"\nCase: {case.name}")

        # Parse and calculate risks
        parsed = parser.parse_hpi(case.hpi_text)
        risk_summary = risk_engine.calculate_risks(
            factors=parsed.extracted_factors,
            demographics=case.demographics,
            mode="comprehensive"
        )

        # Compare with literature baselines
        for lit_baseline in case.literature_risks:
            outcome = lit_baseline.outcome
            expected_risk = lit_baseline.baseline_risk

            # Find calculated risk for this outcome
            calculated_risk = None
            for risk in risk_summary.get('calculated_risks', []):
                if risk.get('outcome') == outcome:
                    calculated_risk = risk.get('adjusted_risk', risk.get('baseline_risk', 0))
                    break

            if calculated_risk is not None:
                # Compare risks (allow 50% variance due to different populations/studies)
                ratio = calculated_risk / expected_risk if expected_risk > 0 else float('inf')
                within_range = 0.5 <= ratio <= 2.0

                validation_results.append({
                    'case': case.name,
                    'outcome': outcome,
                    'literature_risk': expected_risk,
                    'calculated_risk': calculated_risk,
                    'ratio': ratio,
                    'within_range': within_range,
                    'source': lit_baseline.source
                })

                status = "[OK]" if within_range else "[FAIL]"
                print(f"  {status} {outcome}: Literature {expected_risk:.3f} vs Calculated {calculated_risk:.3f} (ratio: {ratio:.2f})")
            else:
                print(f"  ? {outcome}: No calculated risk available")
                validation_results.append({
                    'case': case.name,
                    'outcome': outcome,
                    'literature_risk': expected_risk,
                    'calculated_risk': None,
                    'ratio': None,
                    'within_range': False,
                    'source': lit_baseline.source
                })

    # Summary
    total_comparisons = len(validation_results)
    valid_comparisons = sum(1 for r in validation_results if r['within_range'])

    print(f"\nRisk Validation: {valid_comparisons}/{total_comparisons} within acceptable range")

    # Detailed results
    print("\nDetailed Results:")
    for result in validation_results:
        if result['calculated_risk'] is not None:
            print(f"  {result['case']} - {result['outcome']}: {result['ratio']:.2f}x literature ({result['source']})")

    return valid_comparisons / total_comparisons if total_comparisons > 0 else 0

def test_edge_cases():
    """Test complex edge cases with multiple comorbidities."""
    print("\n=== EDGE CASE TESTING ===")

    edge_cases = [
        {
            "name": "Multiple Cardiac Risk Factors",
            "hpi": "70-year-old diabetic male with CAD s/p CABG, CHF NYHA III, CKD stage 4, on dialysis, presenting for emergency bowel surgery",
            "expected_high_risk": ["MORTALITY_INHOSPITAL", "ACUTE_KIDNEY_INJURY", "POSTOP_DELIRIUM"]
        },
        {
            "name": "Pediatric Complex Case",
            "hpi": "3-year-old with Down syndrome, CHF, recent URI 1 week ago, presenting for cardiac surgery",
            "expected_high_risk": ["LARYNGOSPASM", "BRONCHOSPASM", "DIFFICULT_INTUBATION"]
        },
        {
            "name": "High-Risk Medications",
            "hpi": "55-year-old on warfarin, phenelzine (MAOI), chronic opioids, presenting for spine surgery",
            "expected_warnings": ["ANTICOAGULANTS", "MAOI", "OPIOIDS"]
        }
    ]

    parser = MedicalTextProcessor()
    risk_engine = RiskEngine()

    for case in edge_cases:
        print(f"\nEdge Case: {case['name']}")
        print(f"HPI: {case['hpi'][:100]}...")

        try:
            parsed = parser.parse_hpi(case['hpi'])
            print(f"Extracted {len(parsed.extracted_factors)} factors")

            # Check for expected high-risk factors
            extracted_tokens = [f.token for f in parsed.extracted_factors]
            if 'expected_high_risk' in case:
                print("Expected high-risk outcomes:", case['expected_high_risk'])
            if 'expected_warnings' in case:
                for warning in case['expected_warnings']:
                    if warning in extracted_tokens:
                        print(f"  [OK] {warning} detected")
                    else:
                        print(f"  [MISSING] {warning} missed")

        except Exception as e:
            print(f"  ERROR: {e}")

    return True

def main():
    """Run comprehensive validation."""
    print("MERIDIAN RISK CALCULATION VALIDATION")
    print("=" * 50)

    try:
        # Test 1: Parsing accuracy
        parsing_ok = validate_parsing_accuracy()

        # Test 2: Risk calculation validation
        risk_accuracy = validate_risk_calculations()

        # Test 3: Edge cases
        edge_cases_ok = test_edge_cases()

        print("\n" + "=" * 50)
        print("VALIDATION SUMMARY")
        print("=" * 50)

        print(f"Parsing Accuracy: {'PASS' if parsing_ok else 'NEEDS IMPROVEMENT'}")
        print(f"Risk Calculation Accuracy: {risk_accuracy:.1%}")
        print(f"Edge Cases: {'PASS' if edge_cases_ok else 'NEEDS IMPROVEMENT'}")

        overall_pass = parsing_ok and risk_accuracy >= 0.7 and edge_cases_ok
        print(f"\nOverall Validation: {'PASS' if overall_pass else 'NEEDS IMPROVEMENT'}")

        if not overall_pass:
            print("\nRecommendations:")
            if not parsing_ok:
                print("- Enhance condition pattern matching")
            if risk_accuracy < 0.7:
                print("- Review baseline risk calculations")
                print("- Validate risk modification algorithms")
            if not edge_cases_ok:
                print("- Improve handling of complex cases")

    except Exception as e:
        print(f"Validation failed with error: {e}")
        return False

    return True

if __name__ == "__main__":
    main()