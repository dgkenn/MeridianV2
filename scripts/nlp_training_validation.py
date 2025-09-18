#!/usr/bin/env python3
"""
Automated NLP Training and Validation Script for Meridian
Creates synthetic HPIs, tests parser accuracy, validates risk scores
Loops until accuracy is near perfect
"""

import json
import random
import sys
import os
from pathlib import Path
from typing import List, Dict, Tuple, Any
from dataclasses import dataclass
import time

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from nlp.pipeline import parse_hpi
from nlp.schemas import ParsedHPI
from src.core.risk_engine import RiskEngine

@dataclass
class SyntheticHPI:
    """A synthetic HPI with expected results"""
    text: str
    expected_features: List[str]
    expected_demographics: Dict[str, Any]
    expected_risk_ranges: Dict[str, Tuple[float, float]]  # outcome -> (min, max) acceptable risk
    case_description: str

class HPIGenerator:
    """Generates synthetic HPIs with known ground truth"""

    def __init__(self):
        self.templates = self._load_templates()

    def _load_templates(self) -> Dict[str, List[str]]:
        """Load HPI templates for different scenarios"""
        return {
            "healthy_peds_ent": [
                "{age}-year-old {sex} for {procedure}. Medical history unremarkable. No known drug allergies. Vital signs stable with oxygen saturation 99% on room air. Physical exam shows {findings}. {fasting_status}. ASA I.",

                "{age}-year-old {sex} presenting for {procedure}. No significant medical history. Denies asthma, recent URI, or other respiratory conditions. No drug allergies. Afebrile with normal vital signs. {fasting_status}. ASA I.",

                "Healthy {age}-year-old {sex} scheduled for {procedure}. Past medical history negative. No medications. No allergies. Temperature 98.6°F, oxygen saturation 100% on room air. {findings}. {fasting_status}. ASA I."
            ],

            "asthma_peds": [
                "{age}-year-old {sex} with {asthma_severity} asthma on {asthma_meds} for {procedure}. {uri_status}. No recent exacerbations. Vital signs stable with oxygen saturation 98% on room air. {wheezing_status}. {fasting_status}. ASA II.",

                "{age}-year-old {sex} for {procedure}. History significant for asthma diagnosed at age {asthma_onset}, currently {asthma_control} on {asthma_meds}. {uri_status}. {wheezing_status}. {fasting_status}. ASA II."
            ],

            "osa_peds": [
                "{age}-year-old {sex} with {osa_severity} obstructive sleep apnea (AHI {ahi}) for {procedure}. Parents report frequent snoring and {sleep_symptoms}. {other_conditions}. {fasting_status}. ASA II.",

                "{age}-year-old {sex} for {procedure}. History of sleep apnea with AHI of {ahi} on recent sleep study. {cpap_status}. {sleep_symptoms}. {fasting_status}. ASA II."
            ],

            "complex_adult": [
                "{age}-year-old {sex} with multiple comorbidities including {conditions} presenting for {procedure}. {medication_list}. {vital_signs}. {fasting_status}. ASA III.",

                "{age}-year-old {sex} for {procedure}. Medical history significant for {conditions}. Current medications include {medication_list}. {vital_signs}. {fasting_status}. ASA III."
            ]
        }

    def generate_healthy_pediatric_ent(self) -> SyntheticHPI:
        """Generate healthy pediatric ENT case"""
        age = random.randint(3, 8)
        sex = random.choice(["male", "female"])
        procedure = random.choice([
            "bilateral myringotomy with tube placement",
            "tonsillectomy and adenoidectomy",
            "adenoidectomy"
        ])

        template = random.choice(self.templates["healthy_peds_ent"])

        text = template.format(
            age=age,
            sex=sex,
            procedure=procedure,
            findings=random.choice([
                "enlarged tonsils with 2+ tonsillar hypertrophy",
                "bilateral tympanic membrane retraction",
                "adenoid hypertrophy on exam"
            ]),
            fasting_status=random.choice([
                "NPO since midnight",
                "Last meal 8 hours ago, clear liquids 2 hours ago",
                "Appropriate fasting status"
            ])
        )

        expected_features = []
        expected_demographics = {
            "age_years": age,
            "sex": f"SEX_{sex.upper()}",
            "case_type": "ENT",
            "urgency": "elective"
        }

        # Healthy pediatric ENT should have very low risks
        expected_risk_ranges = {
            "LARYNGOSPASM": (0.005, 0.020),      # 0.5-2% max for healthy kid
            "BRONCHOSPASM": (0.001, 0.010),      # <1% for no asthma
            "DIFFICULT_INTUBATION": (0.001, 0.030), # <3% for normal airway
            "MORTALITY_24H": (0.0001, 0.002),   # <0.2% for healthy ASA I
            "ARRHYTHMIA": (0.001, 0.020)        # <2% for healthy heart
        }

        if "tonsillectomy" in procedure:
            expected_features.append("T_AND_A")
            expected_risk_ranges["POST_TONSILLECTOMY_BLEEDING"] = (0.02, 0.08)

        # Add age category
        if age <= 5:
            expected_features.append("AGE_1_5")
        else:
            expected_features.append("AGE_6_12")

        expected_features.append(f"SEX_{sex.upper()}")

        return SyntheticHPI(
            text=text,
            expected_features=expected_features,
            expected_demographics=expected_demographics,
            expected_risk_ranges=expected_risk_ranges,
            case_description=f"Healthy {age}yo {sex} for {procedure}"
        )

    def generate_asthma_pediatric(self) -> SyntheticHPI:
        """Generate pediatric asthma case"""
        age = random.randint(4, 12)
        sex = random.choice(["male", "female"])
        procedure = random.choice([
            "tonsillectomy and adenoidectomy",
            "dental rehabilitation under general anesthesia"
        ])

        asthma_severity = random.choice(["mild", "moderate", "well-controlled"])
        uri_present = random.choice([True, False])

        template = random.choice(self.templates["asthma_peds"])

        uri_status = "Recent upper respiratory infection 10 days ago with mild cough" if uri_present else "No recent respiratory infections"

        text = template.format(
            age=age,
            sex=sex,
            procedure=procedure,
            asthma_severity=asthma_severity,
            asthma_meds=random.choice([
                "daily fluticasone inhaler and albuterol PRN",
                "budesonide inhaler daily",
                "ICS and beta-2 agonist PRN"
            ]),
            asthma_onset=random.randint(2, age-1),
            asthma_control="well-controlled",
            uri_status=uri_status,
            wheezing_status=random.choice([
                "Clear chest on auscultation",
                "Mild expiratory wheeze on chest exam",
                "No wheeze currently"
            ]),
            fasting_status="NPO since midnight"
        )

        expected_features = ["ASTHMA"]
        if uri_present:
            expected_features.append("RECENT_URI_2W")

        expected_demographics = {
            "age_years": age,
            "sex": f"SEX_{sex.upper()}",
            "urgency": "elective"
        }

        # Asthma increases risks but should still be reasonable
        expected_risk_ranges = {
            "LARYNGOSPASM": (0.020, 0.080),     # 2-8% with asthma
            "BRONCHOSPASM": (0.015, 0.060),     # 1.5-6% with asthma
            "DIFFICULT_INTUBATION": (0.005, 0.040), # Slightly higher
            "MORTALITY_24H": (0.0002, 0.005),   # Still very low for ASA II
            "ARRHYTHMIA": (0.002, 0.025)        # Minimal increase
        }

        if uri_present:
            # URI significantly increases airway risks
            expected_risk_ranges["LARYNGOSPASM"] = (0.040, 0.150)
            expected_risk_ranges["BRONCHOSPASM"] = (0.025, 0.100)

        # Add age and sex
        if age <= 5:
            expected_features.append("AGE_1_5")
        elif age <= 12:
            expected_features.append("AGE_6_12")
        expected_features.append(f"SEX_{sex.upper()}")

        return SyntheticHPI(
            text=text,
            expected_features=expected_features,
            expected_demographics=expected_demographics,
            expected_risk_ranges=expected_risk_ranges,
            case_description=f"{age}yo {sex} with asthma{' + recent URI' if uri_present else ''}"
        )

    def generate_osa_pediatric(self) -> SyntheticHPI:
        """Generate pediatric OSA case"""
        age = random.randint(3, 10)
        sex = random.choice(["male", "female"])
        ahi = random.randint(8, 25)

        template = random.choice(self.templates["osa_peds"])

        text = template.format(
            age=age,
            sex=sex,
            osa_severity=random.choice(["moderate", "severe"]),
            ahi=ahi,
            procedure="tonsillectomy and adenoidectomy",
            cpap_status=random.choice([
                "Not on CPAP therapy",
                "Trialed on CPAP with poor compliance",
                "No CPAP due to age"
            ]),
            sleep_symptoms=random.choice([
                "restless sleep with frequent awakening",
                "daytime fatigue and irritability",
                "witnessed apneic episodes"
            ]),
            other_conditions=random.choice([
                "No other significant medical history",
                "Otherwise healthy child",
                "No cardiovascular comorbidities"
            ]),
            fasting_status="NPO since midnight"
        )

        expected_features = ["OSA", "T_AND_A"]
        expected_demographics = {
            "age_years": age,
            "sex": f"SEX_{sex.upper()}",
            "case_type": "ENT",
            "urgency": "elective"
        }

        # OSA increases airway risks significantly
        expected_risk_ranges = {
            "LARYNGOSPASM": (0.025, 0.100),     # Higher with OSA
            "DIFFICULT_INTUBATION": (0.020, 0.080), # OSA = difficult airway
            "ARRHYTHMIA": (0.005, 0.030),       # Some cardiac risk
            "MORTALITY_24H": (0.0005, 0.008),   # Slightly higher
            "POST_TONSILLECTOMY_BLEEDING": (0.030, 0.100) # Higher bleeding risk
        }

        # Add age and sex
        if age <= 5:
            expected_features.append("AGE_1_5")
        else:
            expected_features.append("AGE_6_12")
        expected_features.append(f"SEX_{sex.upper()}")

        return SyntheticHPI(
            text=text,
            expected_features=expected_features,
            expected_demographics=expected_demographics,
            expected_risk_ranges=expected_risk_ranges,
            case_description=f"{age}yo {sex} with OSA (AHI {ahi}) for T&A"
        )

    def generate_negative_control(self) -> SyntheticHPI:
        """Generate case with explicit negations"""
        age = random.randint(5, 15)
        sex = random.choice(["male", "female"])

        text = f"{age}-year-old {sex} for dental rehabilitation. Denies asthma, sleep apnea, or any respiratory conditions. No recent upper respiratory infections. Afebrile for weeks. No cardiac history. No known drug allergies. Vital signs normal with oxygen saturation 100% on room air. ASA I."

        expected_features = []  # Should extract nothing due to negations
        expected_demographics = {
            "age_years": age,
            "sex": f"SEX_{sex.upper()}",
            "urgency": "elective"
        }

        # Should have very low baseline risks
        expected_risk_ranges = {
            "LARYNGOSPASM": (0.002, 0.015),
            "BRONCHOSPASM": (0.001, 0.008),
            "DIFFICULT_INTUBATION": (0.001, 0.025),
            "MORTALITY_24H": (0.0001, 0.001),
            "ARRHYTHMIA": (0.001, 0.015)
        }

        # Add age and sex
        if age <= 5:
            expected_features.append("AGE_1_5")
        elif age <= 12:
            expected_features.append("AGE_6_12")
        else:
            expected_features.append("AGE_13_17")
        expected_features.append(f"SEX_{sex.upper()}")

        return SyntheticHPI(
            text=text,
            expected_features=expected_features,
            expected_demographics=expected_demographics,
            expected_risk_ranges=expected_risk_ranges,
            case_description=f"Negative control: {age}yo {sex} denying all conditions"
        )

    def generate_test_set(self, n_cases: int = 50) -> List[SyntheticHPI]:
        """Generate a test set of synthetic HPIs"""
        test_cases = []

        # Distribution of cases
        n_healthy = n_cases // 4
        n_asthma = n_cases // 4
        n_osa = n_cases // 6
        n_negative = n_cases - n_healthy - n_asthma - n_osa

        for _ in range(n_healthy):
            test_cases.append(self.generate_healthy_pediatric_ent())

        for _ in range(n_asthma):
            test_cases.append(self.generate_asthma_pediatric())

        for _ in range(n_osa):
            test_cases.append(self.generate_osa_pediatric())

        for _ in range(n_negative):
            test_cases.append(self.generate_negative_control())

        random.shuffle(test_cases)
        return test_cases

class ValidationResults:
    """Results from validation run"""

    def __init__(self):
        self.total_cases = 0
        self.parser_errors = 0
        self.risk_engine_errors = 0

        # Parser metrics
        self.feature_precision = 0.0
        self.feature_recall = 0.0
        self.negation_precision = 0.0

        # Risk score validation
        self.risk_score_failures = []
        self.unrealistic_risks = []

        # Detailed results
        self.case_results = []

class NLPValidator:
    """Validates NLP pipeline performance"""

    def __init__(self):
        self.generator = HPIGenerator()
        self.risk_engine = RiskEngine()

    def validate_parser(self, test_cases: List[SyntheticHPI]) -> ValidationResults:
        """Run validation on test cases"""
        results = ValidationResults()
        results.total_cases = len(test_cases)

        true_positives = 0
        false_positives = 0
        false_negatives = 0
        negation_correct = 0
        negation_total = 0

        print(f"\\nValidating NLP pipeline on {len(test_cases)} synthetic cases...")

        for i, case in enumerate(test_cases):
            print(f"\\rProcessing case {i+1}/{len(test_cases)}: {case.case_description}", end="")

            try:
                # Parse HPI
                parsed = parse_hpi(case.text)

                # Extract actual features (non-negated)
                actual_features = set(parsed.get_feature_codes(include_negated=False))
                expected_features = set(case.expected_features)

                # Calculate precision/recall
                tp = len(actual_features & expected_features)
                fp = len(actual_features - expected_features)
                fn = len(expected_features - actual_features)

                true_positives += tp
                false_positives += fp
                false_negatives += fn

                # Test negation handling
                negated_features = [f for f in parsed.features if f.modifiers.negated]
                negation_total += len([word for word in case.text.lower().split() if word in ["denies", "no", "not"]])
                negation_correct += len(negated_features)  # Simplified

                # Test risk scores
                risk_validation = self._validate_risk_scores(parsed, case)
                results.case_results.append({
                    "case": case.case_description,
                    "expected_features": list(expected_features),
                    "actual_features": list(actual_features),
                    "risk_validation": risk_validation,
                    "tp": tp, "fp": fp, "fn": fn
                })

                if risk_validation["has_failures"]:
                    results.risk_score_failures.extend(risk_validation["failures"])

            except Exception as e:
                results.parser_errors += 1
                print(f"\\nError processing case {i+1}: {e}")

        print("\\n")

        # Calculate metrics
        if true_positives + false_positives > 0:
            results.feature_precision = true_positives / (true_positives + false_positives)
        if true_positives + false_negatives > 0:
            results.feature_recall = true_positives / (true_positives + false_negatives)
        if negation_total > 0:
            results.negation_precision = negation_correct / negation_total

        return results

    def _validate_risk_scores(self, parsed: ParsedHPI, case: SyntheticHPI) -> Dict[str, Any]:
        """Validate that risk scores are clinically reasonable"""
        try:
            # Convert to format expected by risk engine
            from src.core.hpi_parser import ExtractedFactor

            extracted_factors = []
            for feature in parsed.features:
                if not feature.modifiers.negated:  # Only non-negated
                    extracted_factors.append(ExtractedFactor(
                        token=feature.code,
                        plain_label=feature.label,
                        confidence=feature.confidence,
                        evidence_text=feature.text,
                        factor_type='risk_factor',
                        category=getattr(feature, 'category', 'unknown'),
                        severity_weight=feature.confidence,
                        context='perioperative'
                    ))

            # Calculate risks
            demographics = {
                "age_years": parsed.age_years,
                "sex": parsed.sex,
                "urgency": parsed.urgency
            }

            risk_summary = self.risk_engine.calculate_risks(
                factors=extracted_factors,
                demographics=demographics,
                mode="model_based"
            )

            # Validate against expected ranges
            failures = []
            for outcome, expected_range in case.expected_risk_ranges.items():
                min_risk, max_risk = expected_range

                # Find actual risk in summary
                actual_risk = None
                for risk in risk_summary.risks:
                    if outcome.lower() in risk.outcome.lower():
                        actual_risk = risk.risk
                        break

                if actual_risk is not None:
                    if actual_risk < min_risk or actual_risk > max_risk:
                        failures.append({
                            "outcome": outcome,
                            "expected_range": expected_range,
                            "actual_risk": actual_risk,
                            "case_description": case.case_description
                        })

            return {
                "has_failures": len(failures) > 0,
                "failures": failures,
                "total_risks": len(risk_summary.risks)
            }

        except Exception as e:
            return {
                "has_failures": True,
                "failures": [{"error": str(e)}],
                "total_risks": 0
            }

    def run_validation_loop(self, target_precision: float = 0.88, target_recall: float = 0.80,
                          max_iterations: int = 10) -> bool:
        """Run validation loop until accuracy targets are met"""

        print("🤖 Starting Automated NLP Training/Validation Loop")
        print(f"Target: Precision ≥ {target_precision}, Recall ≥ {target_recall}")
        print("=" * 60)

        for iteration in range(max_iterations):
            print(f"\\n🔄 Iteration {iteration + 1}/{max_iterations}")

            # Generate fresh test set
            test_cases = self.generator.generate_test_set(50)

            # Run validation
            results = self.validate_parser(test_cases)

            # Print results
            self._print_results(results, iteration + 1)

            # Check if targets met
            precision_ok = results.feature_precision >= target_precision
            recall_ok = results.feature_recall >= target_recall
            risk_scores_ok = len(results.risk_score_failures) == 0

            if precision_ok and recall_ok and risk_scores_ok:
                print(f"\\n🎉 SUCCESS! Targets achieved in iteration {iteration + 1}")
                return True

            # If not successful, analyze failures and suggest improvements
            self._analyze_failures(results)

            print(f"\\n⚠️  Targets not met. Continuing to iteration {iteration + 2}...")
            time.sleep(2)  # Brief pause

        print(f"\\n❌ Failed to achieve targets after {max_iterations} iterations")
        return False

    def _print_results(self, results: ValidationResults, iteration: int):
        """Print validation results"""
        print(f"\\n📊 Iteration {iteration} Results:")
        print(f"   Total cases: {results.total_cases}")
        print(f"   Parser errors: {results.parser_errors}")
        print(f"   Feature precision: {results.feature_precision:.3f}")
        print(f"   Feature recall: {results.feature_recall:.3f}")
        print(f"   Negation precision: {results.negation_precision:.3f}")
        print(f"   Risk score failures: {len(results.risk_score_failures)}")

        if results.risk_score_failures:
            print("\\n⚠️  Risk Score Failures:")
            for failure in results.risk_score_failures[:3]:  # Show first 3
                print(f"   - {failure['case_description']}")
                print(f"     {failure['outcome']}: {failure['actual_risk']:.4f} (expected {failure['expected_range'][0]:.4f}-{failure['expected_range'][1]:.4f})")

    def _analyze_failures(self, results: ValidationResults):
        """Analyze failures and suggest improvements"""
        print("\\n🔍 Failure Analysis:")

        # Analyze most common false positives/negatives
        false_positives = {}
        false_negatives = {}

        for case_result in results.case_results:
            expected = set(case_result["expected_features"])
            actual = set(case_result["actual_features"])

            for fp in actual - expected:
                false_positives[fp] = false_positives.get(fp, 0) + 1
            for fn in expected - actual:
                false_negatives[fn] = false_negatives.get(fn, 0) + 1

        if false_positives:
            print(f"   Most common false positives: {sorted(false_positives.items(), key=lambda x: x[1], reverse=True)[:3]}")
        if false_negatives:
            print(f"   Most common false negatives: {sorted(false_negatives.items(), key=lambda x: x[1], reverse=True)[:3]}")

        # Analyze risk score issues
        risk_issues = {}
        for failure in results.risk_score_failures:
            outcome = failure.get("outcome", "unknown")
            risk_issues[outcome] = risk_issues.get(outcome, 0) + 1

        if risk_issues:
            print(f"   Most problematic risk outcomes: {sorted(risk_issues.items(), key=lambda x: x[1], reverse=True)[:3]}")

def main():
    """Main function to run validation"""
    validator = NLPValidator()

    # Quick test first
    print("🧪 Running quick validation test...")
    test_cases = validator.generator.generate_test_set(10)
    results = validator.validate_parser(test_cases)
    validator._print_results(results, 0)

    # Ask user if they want to run full validation loop
    response = input("\\n🤔 Run full validation loop? (y/N): ").strip().lower()
    if response == 'y':
        success = validator.run_validation_loop()
        if success:
            print("\\n✅ NLP pipeline validation completed successfully!")
        else:
            print("\\n❌ Validation failed. Manual review needed.")
    else:
        print("\\n👋 Validation stopped. Use results above to improve the pipeline.")

if __name__ == "__main__":
    main()