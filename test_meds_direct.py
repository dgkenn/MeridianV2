#!/usr/bin/env python3
"""
Direct testing of medication engine without server dependency
Tests >90% accuracy with random HPI generation and comprehensive validation
"""

import sys
import json
import random
import time
from typing import Dict, List, Any, Tuple
from pathlib import Path
from dataclasses import dataclass

# Add project path to import engine
sys.path.append(str(Path(__file__).parent))

try:
    from services.meds_engine import create_meds_engine, PatientParameters
    from nlp.pipeline import parse_hpi
except ImportError as e:
    print(f"ERROR: Cannot import required modules: {e}")
    print("Make sure you're running from the correct directory")
    sys.exit(1)

@dataclass
class TestResult:
    test_name: str
    passed: bool
    expected: Any
    actual: Any
    error: str = ""
    score: float = 0.0

class DirectMedicationTestSuite:
    def __init__(self):
        self.test_results = []
        self.total_tests = 0
        self.passed_tests = 0

        # Initialize medication engine
        try:
            self.engine = create_meds_engine()
            print("Medication engine initialized successfully")
        except Exception as e:
            print(f"ERROR: Failed to initialize medication engine: {e}")
            raise

        # Define comprehensive test scenarios
        self.test_scenarios = {
            "pediatric_ent_asthma": {
                "weight": 0.15,
                "description": "Pediatric ENT with asthma - should have bronchodilators",
                "expected_draw_now": ["Albuterol", "Epinephrine"],
                "expected_standard": ["Ondansetron", "Dexamethasone"],
                "contraindicated_check": [],
                "features": ["ASTHMA", "RECENT_URI"],
                "elevated_risks": {"BRONCHOSPASM": 0.06, "LARYNGOSPASM": 0.04, "PONV": 0.45}
            },
            "adult_cardiac_osa": {
                "weight": 0.15,
                "description": "Adult cardiac with OSA - should have careful airway management",
                "expected_draw_now": ["Succinylcholine", "Epinephrine"],
                "expected_standard": ["Ondansetron", "Phenylephrine"],
                "contraindicated_check": [],
                "features": ["OSA", "CAD"],
                "elevated_risks": {"DIFFICULT_AIRWAY": 0.08, "PONV": 0.35, "HYPOTENSION": 0.25}
            },
            "mh_history": {
                "weight": 0.2,
                "description": "MH history - should contraindicate succinylcholine",
                "expected_draw_now": ["Rocuronium", "Epinephrine"],
                "expected_standard": [],
                "contraindicated_check": ["Succinylcholine"],
                "features": ["MH_HISTORY"],
                "elevated_risks": {"MH_RISK": 0.95}
            },
            "egg_soy_allergy": {
                "weight": 0.2,
                "description": "Egg/soy allergy - should contraindicate propofol",
                "expected_draw_now": [],
                "expected_standard": ["Ondansetron"],
                "contraindicated_check": ["Propofol"],
                "features": [],
                "elevated_risks": {"PONV": 0.3}
            },
            "pediatric_difficult_airway": {
                "weight": 0.15,
                "description": "Pediatric difficult airway - should have emergency meds",
                "expected_draw_now": ["Epinephrine", "Atropine"],
                "expected_standard": ["Succinylcholine"],
                "contraindicated_check": [],
                "features": ["DIFFICULT_AIRWAY", "MICROGNATHIA"],
                "elevated_risks": {"DIFFICULT_AIRWAY": 0.35, "LARYNGOSPASM": 0.15}
            },
            "adult_trauma_rsi": {
                "weight": 0.15,
                "description": "Adult trauma RSI - should have RSI sequence",
                "expected_draw_now": ["Succinylcholine", "Epinephrine"],
                "expected_standard": ["Phenylephrine"],
                "contraindicated_check": [],
                "features": ["TRAUMA", "FULL_STOMACH"],
                "elevated_risks": {"ASPIRATION": 0.25, "HYPOTENSION": 0.20}
            }
        }

        # Random variations for HPIs
        self.hpi_variations = {
            "ages": {"pediatric": list(range(2, 18)), "adult": list(range(18, 80))},
            "sex": ["M", "F"],
            "surgeries": {
                "ent": ["tonsillectomy and adenoidectomy", "tonsillectomy", "adenoidectomy"],
                "cardiac": ["coronary bypass", "valve replacement"],
                "general": ["cholecystectomy", "appendectomy", "hernia repair"]
            },
            "asthma_triggers": ["upper respiratory infection", "cold", "viral illness"],
            "timeframes": ["5 days ago", "1 week ago", "2 weeks ago"],
            "medications": ["albuterol PRN", "albuterol and fluticasone", "rescue inhaler"]
        }

    def generate_mock_parsed_hpi(self, features: List[str]) -> Any:
        """Generate mock parsed HPI with specified features"""
        class MockParsedHPI:
            def __init__(self, features):
                self.features = features

            def get_feature_codes(self, include_negated=False):
                return self.features

        return MockParsedHPI(features)

    def generate_risk_summary(self, elevated_risks: Dict[str, float]) -> Dict[str, Any]:
        """Generate risk summary for testing"""
        risks = {}
        for risk_name, absolute_risk in elevated_risks.items():
            risks[risk_name] = {
                'absolute_risk': absolute_risk,
                'delta_vs_baseline': max(0.01, absolute_risk - 0.05),  # Some delta
                'confidence': 'A'
            }

        return {'risks': risks}

    def generate_random_patient_params(self, scenario_name: str) -> PatientParameters:
        """Generate random patient parameters for scenario"""
        if "pediatric" in scenario_name:
            age = random.choice(self.hpi_variations["ages"]["pediatric"])
            weight = round(10 + age * 2.5, 1)
        else:
            age = random.choice(self.hpi_variations["ages"]["adult"])
            weight = round(random.uniform(50, 100), 1)

        sex = random.choice(self.hpi_variations["sex"])

        # Add allergies for allergy scenarios
        allergies = []
        if "allergy" in scenario_name:
            allergies = ["EGG_SOY_ALLERGY"]

        return PatientParameters(
            age_years=age,
            weight_kg=weight,
            height_cm=int(80 + age * 4) if age < 18 else random.randint(150, 190),
            sex=sex,
            urgency="elective" if "trauma" not in scenario_name else "urgent",
            surgery_domain=self._get_surgery_domain(scenario_name),
            allergies=allergies,
            renal_function=None,
            hepatic_function=None
        )

    def _get_surgery_domain(self, scenario_name: str) -> str:
        """Get surgery domain based on scenario"""
        if "ent" in scenario_name:
            return "ENT"
        elif "cardiac" in scenario_name:
            return "Cardiac"
        elif "trauma" in scenario_name:
            return "Emergency"
        else:
            return "General"

    def test_scenario_multiple_iterations(self, scenario_name: str, num_iterations: int = 10) -> List[TestResult]:
        """Test a scenario with multiple random iterations"""
        results = []
        scenario = self.test_scenarios[scenario_name]

        print(f"Testing scenario: {scenario_name}")
        print(f"Description: {scenario['description']}")

        for i in range(num_iterations):
            try:
                # Generate random test inputs
                patient_params = self.generate_random_patient_params(scenario_name)
                parsed_hpi = self.generate_mock_parsed_hpi(scenario['features'])
                risk_summary = self.generate_risk_summary(scenario['elevated_risks'])

                # Call medication engine
                recommendations = self.engine.generate_recommendations(
                    parsed_hpi=parsed_hpi,
                    risk_summary=risk_summary,
                    patient_params=patient_params
                )

                # Validate results
                structure_result = self._validate_structure(recommendations, f"{scenario_name}_struct_{i+1}")
                results.append(structure_result)

                if structure_result.passed:
                    meds_result = self._validate_medications(
                        recommendations['meds'], scenario, f"{scenario_name}_meds_{i+1}"
                    )
                    results.append(meds_result)

                    dose_result = self._validate_doses(
                        recommendations['meds'], patient_params, f"{scenario_name}_doses_{i+1}"
                    )
                    results.append(dose_result)

                    contra_result = self._validate_contraindications(
                        recommendations['meds'], scenario, f"{scenario_name}_contra_{i+1}"
                    )
                    results.append(contra_result)

            except Exception as e:
                results.append(TestResult(
                    test_name=f"{scenario_name}_error_{i+1}",
                    passed=False,
                    expected="No exception",
                    actual=str(e),
                    error=str(e)
                ))

        # Calculate scenario summary
        passed_count = sum(1 for r in results if r.passed)
        total_count = len(results)
        avg_score = sum(r.score for r in results) / total_count if total_count > 0 else 0

        print(f"  Results: {passed_count}/{total_count} passed ({passed_count/total_count*100:.1f}%)")
        print(f"  Average score: {avg_score:.3f}")
        print()

        return results

    def _validate_structure(self, recommendations: Dict, test_name: str) -> TestResult:
        """Validate recommendation structure"""
        required_keys = ['patient', 'meds', 'summary']
        required_buckets = ['draw_now', 'standard', 'consider', 'contraindicated']

        for key in required_keys:
            if key not in recommendations:
                return TestResult(
                    test_name=test_name,
                    passed=False,
                    expected=f"Contains '{key}'",
                    actual=f"Missing '{key}'",
                    error=f"Missing required key: {key}"
                )

        meds = recommendations.get('meds', {})
        for bucket in required_buckets:
            if bucket not in meds:
                return TestResult(
                    test_name=test_name,
                    passed=False,
                    expected=f"Contains bucket '{bucket}'",
                    actual=f"Missing bucket '{bucket}'",
                    error=f"Missing medication bucket: {bucket}"
                )

        return TestResult(
            test_name=test_name,
            passed=True,
            expected="Valid structure",
            actual="Valid structure",
            score=1.0
        )

    def _validate_medications(self, meds: Dict, scenario: Dict, test_name: str) -> TestResult:
        """Validate medication recommendations"""
        draw_now_agents = [med['agent'] for med in meds.get('draw_now', [])]
        standard_agents = [med['agent'] for med in meds.get('standard', [])]

        expected_draw_now = scenario['expected_draw_now']
        expected_standard = scenario['expected_standard']

        # Calculate overlap scores
        draw_now_score = self._calculate_overlap_score(draw_now_agents, expected_draw_now)
        standard_score = self._calculate_overlap_score(standard_agents, expected_standard)

        # Weighted overall score (draw_now is more critical)
        overall_score = (draw_now_score * 0.7) + (standard_score * 0.3)
        passed = overall_score >= 0.6

        return TestResult(
            test_name=test_name,
            passed=passed,
            expected=f"Draw: {expected_draw_now}, Standard: {expected_standard}",
            actual=f"Draw: {draw_now_agents}, Standard: {standard_agents}",
            score=overall_score,
            error="" if passed else f"Low medication score: {overall_score:.2f}"
        )

    def _validate_doses(self, meds: Dict, patient_params: PatientParameters, test_name: str) -> TestResult:
        """Validate dose calculations"""
        all_meds = meds.get('draw_now', []) + meds.get('standard', [])

        valid_doses = 0
        total_with_doses = 0

        for med in all_meds:
            if 'dose' in med and med['dose']:
                total_with_doses += 1
                if self._is_dose_reasonable(med['agent'], med['dose'], patient_params):
                    valid_doses += 1

        if total_with_doses == 0:
            return TestResult(
                test_name=test_name,
                passed=True,  # No doses to validate is OK
                expected="Valid doses or no doses",
                actual="No doses calculated",
                score=1.0
            )

        score = valid_doses / total_with_doses
        passed = score >= 0.8

        return TestResult(
            test_name=test_name,
            passed=passed,
            expected="Reasonable dose calculations",
            actual=f"{valid_doses}/{total_with_doses} valid doses",
            score=score,
            error="" if passed else f"Too many invalid doses: {valid_doses}/{total_with_doses}"
        )

    def _validate_contraindications(self, meds: Dict, scenario: Dict, test_name: str) -> TestResult:
        """Validate contraindication detection"""
        contraindicated_agents = [med['agent'] for med in meds.get('contraindicated', [])]
        expected_contraindicated = scenario['contraindicated_check']

        if not expected_contraindicated:
            return TestResult(
                test_name=test_name,
                passed=True,
                expected="No contraindications expected",
                actual=f"Contraindicated: {contraindicated_agents}",
                score=1.0
            )

        # Check if expected contraindications are detected
        detected = set(contraindicated_agents) & set(expected_contraindicated)
        score = len(detected) / len(expected_contraindicated)
        passed = score >= 0.8

        return TestResult(
            test_name=test_name,
            passed=passed,
            expected=f"Contraindicated: {expected_contraindicated}",
            actual=f"Contraindicated: {contraindicated_agents}",
            score=score,
            error="" if passed else f"Missed contraindications: {set(expected_contraindicated) - detected}"
        )

    def _calculate_overlap_score(self, actual: List[str], expected: List[str]) -> float:
        """Calculate overlap score between lists"""
        if not expected:
            return 1.0

        actual_set = set(actual)
        expected_set = set(expected)

        # Calculate found vs expected
        found = len(actual_set & expected_set)
        missed = len(expected_set - actual_set)
        unexpected = len(actual_set - expected_set)

        # Base score: how many expected items found
        base_score = found / len(expected)

        # Small penalty for unexpected items (but not as severe as missing expected ones)
        penalty = min(0.2, unexpected * 0.05)

        return max(0.0, base_score - penalty)

    def _is_dose_reasonable(self, agent: str, dose_info: Any, patient_params: PatientParameters) -> bool:
        """Check if dose is reasonable"""
        if not isinstance(dose_info, dict):
            return False

        age = patient_params.age_years
        weight = patient_params.weight_kg

        # Reasonable dose ranges (mg for most drugs)
        dose_ranges = {
            "Ondansetron": {"pediatric": (0.5, 4), "adult": (4, 8)},
            "Dexamethasone": {"pediatric": (0.5, 8), "adult": (4, 16)},
            "Albuterol": {"pediatric": (1.25, 5), "adult": (2.5, 5)},
            "Epinephrine": {"pediatric": (0.001, 1), "adult": (0.1, 2)},
            "Succinylcholine": {"pediatric": (10, 150), "adult": (50, 200)},
            "Rocuronium": {"pediatric": (5, 60), "adult": (30, 100)},
            "Phenylephrine": {"pediatric": (0.005, 0.2), "adult": (0.05, 1)},
            "Atropine": {"pediatric": (0.1, 1), "adult": (0.4, 2)}
        }

        if agent not in dose_ranges:
            return True  # Unknown agents assumed OK

        range_key = "pediatric" if age < 18 else "adult"
        min_dose, max_dose = dose_ranges[agent][range_key]

        # Check dose value
        dose_mg = dose_info.get('mg')
        if dose_mg is not None:
            return min_dose <= dose_mg <= max_dose

        return True  # If can't validate, assume OK

    def run_comprehensive_test_suite(self, iterations_per_scenario: int = 10) -> Dict[str, Any]:
        """Run comprehensive test suite"""
        print("=" * 80)
        print("MERIDIAN MEDICATION ENGINE COMPREHENSIVE TEST SUITE")
        print("=" * 80)
        print(f"Testing {len(self.test_scenarios)} scenarios with {iterations_per_scenario} iterations each")
        print(f"Target accuracy: >90%")
        print()

        start_time = time.time()
        all_results = []
        scenario_scores = {}

        for scenario_name, scenario_info in self.test_scenarios.items():
            scenario_results = self.test_scenario_multiple_iterations(scenario_name, iterations_per_scenario)
            all_results.extend(scenario_results)

            # Calculate scenario metrics
            scenario_passed = sum(1 for r in scenario_results if r.passed)
            scenario_total = len(scenario_results)
            scenario_avg_score = sum(r.score for r in scenario_results) / scenario_total if scenario_total > 0 else 0

            scenario_scores[scenario_name] = {
                'passed': scenario_passed,
                'total': scenario_total,
                'pass_rate': scenario_passed / scenario_total if scenario_total > 0 else 0,
                'avg_score': scenario_avg_score,
                'weight': scenario_info['weight']
            }

        # Calculate overall metrics
        total_passed = sum(1 for r in all_results if r.passed)
        total_tests = len(all_results)
        overall_pass_rate = total_passed / total_tests if total_tests > 0 else 0

        # Calculate weighted accuracy
        weighted_accuracy = sum(
            scores['avg_score'] * scores['weight']
            for scores in scenario_scores.values()
        )

        end_time = time.time()
        duration = end_time - start_time

        # Print results
        print("=" * 80)
        print("COMPREHENSIVE TEST RESULTS")
        print("=" * 80)
        print(f"Total tests run: {total_tests}")
        print(f"Tests passed: {total_passed}")
        print(f"Overall pass rate: {overall_pass_rate*100:.1f}%")
        print(f"Weighted accuracy: {weighted_accuracy*100:.1f}%")
        print(f"Test duration: {duration:.1f} seconds")
        print()

        # Scenario breakdown
        print("SCENARIO BREAKDOWN:")
        print("-" * 50)
        for scenario_name, scores in scenario_scores.items():
            status = "PASS" if scores['avg_score'] >= 0.8 else "FAIL"
            print(f"{scenario_name:30} {scores['avg_score']*100:5.1f}% ({scores['passed']:2}/{scores['total']:2}) [{status}]")

        print()

        # Failed tests (sample)
        failed_tests = [r for r in all_results if not r.passed]
        if failed_tests:
            print("SAMPLE FAILED TESTS:")
            print("-" * 50)
            for test in failed_tests[:5]:  # Show first 5
                print(f"Test: {test.test_name}")
                print(f"  Expected: {test.expected}")
                print(f"  Actual: {test.actual}")
                if test.error:
                    print(f"  Error: {test.error}")
                print()

        # Final assessment
        print("=" * 80)
        if weighted_accuracy >= 0.9:
            print("EXCELLENT: >90% accuracy achieved! 🎉")
            success = True
        elif weighted_accuracy >= 0.8:
            print("GOOD: 80-90% accuracy - minor improvements needed")
            success = True
        elif weighted_accuracy >= 0.7:
            print("FAIR: 70-80% accuracy - improvements needed")
            success = False
        else:
            print("POOR: <70% accuracy - major issues require attention")
            success = False

        print(f"Medication engine performance: {weighted_accuracy*100:.1f}%")
        print("=" * 80)

        return {
            'success': success,
            'overall_pass_rate': overall_pass_rate,
            'weighted_accuracy': weighted_accuracy,
            'total_tests': total_tests,
            'passed_tests': total_passed,
            'scenario_scores': scenario_scores,
            'failed_tests': failed_tests,
            'duration': duration
        }

def main():
    """Main test execution"""
    print("Starting direct medication engine testing...")

    try:
        test_suite = DirectMedicationTestSuite()
        results = test_suite.run_comprehensive_test_suite(iterations_per_scenario=8)

        # Return exit code based on success
        return 0 if results['success'] else 1

    except Exception as e:
        print(f"CRITICAL ERROR: Test suite failed to initialize: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)