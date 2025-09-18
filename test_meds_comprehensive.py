#!/usr/bin/env python3
"""
Comprehensive recursive testing system for Meridian Medication API
Tests >90% accuracy with random HPI generation and edge cases
"""

import requests
import json
import random
import time
import sys
from typing import Dict, List, Any, Tuple
from pathlib import Path
from dataclasses import dataclass

@dataclass
class TestResult:
    test_name: str
    passed: bool
    expected: Any
    actual: Any
    error: str = ""
    score: float = 0.0

class MedicationTestSuite:
    def __init__(self, base_url="http://localhost:8084"):
        self.base_url = base_url
        self.test_results = []
        self.total_tests = 0
        self.passed_tests = 0

        # Define test scenarios with expected outcomes
        self.test_scenarios = {
            "pediatric_ent_asthma": {
                "weight": 0.15,
                "description": "Pediatric ENT with asthma - should have bronchodilators",
                "expected_draw_now": ["Albuterol", "Epinephrine"],
                "expected_standard": ["Ondansetron", "Dexamethasone"],
                "contraindicated_check": [],
            },
            "adult_cardiac_osa": {
                "weight": 0.15,
                "description": "Adult cardiac with OSA - should have careful airway management",
                "expected_draw_now": ["Succinylcholine", "Epinephrine"],
                "expected_standard": ["Ondansetron", "Phenylephrine"],
                "contraindicated_check": [],
            },
            "mh_history": {
                "weight": 0.2,
                "description": "MH history - should contraindicate succinylcholine",
                "expected_draw_now": ["Rocuronium", "Epinephrine"],
                "expected_standard": [],
                "contraindicated_check": ["Succinylcholine"],
            },
            "egg_soy_allergy": {
                "weight": 0.2,
                "description": "Egg/soy allergy - should contraindicate propofol",
                "expected_draw_now": [],
                "expected_standard": ["Ondansetron"],
                "contraindicated_check": ["Propofol"],
            },
            "pediatric_airway": {
                "weight": 0.1,
                "description": "Pediatric difficult airway - should have emergency meds",
                "expected_draw_now": ["Epinephrine", "Atropine"],
                "expected_standard": ["Succinylcholine"],
                "contraindicated_check": [],
            },
            "adult_trauma": {
                "weight": 0.1,
                "description": "Adult trauma - should have RSI sequence",
                "expected_draw_now": ["Succinylcholine", "Epinephrine"],
                "expected_standard": ["Phenylephrine"],
                "contraindicated_check": [],
            },
            "geriatric_multiple_comorbidities": {
                "weight": 0.1,
                "description": "Geriatric with multiple comorbidities",
                "expected_draw_now": ["Epinephrine"],
                "expected_standard": ["Ondansetron"],
                "contraindicated_check": [],
            }
        }

        # Random HPI templates for diverse testing
        self.hpi_templates = {
            "pediatric_ent_asthma": [
                "{age}-year-old {sex} for tonsillectomy and adenoidectomy. Medical history significant for {comorbidity} with recent {trigger} {timeframe}. Uses {medication} PRN. {allergy_status} Vital signs {vitals}. Physical exam {exam}. NPO since {npo_time}.",
                "{age}-year-old {sex} scheduled for {surgery}. Past medical history notable for {comorbidity} and {additional_condition}. Current medications include {medication}. {allergy_status} Recent {trigger} {timeframe}. Vital signs are {vitals}.",
                "{age} year old {sex} presenting for elective {surgery}. Significant for {comorbidity}, last exacerbation {timeframe} after {trigger}. Takes {medication} as needed. {allergy_status} Preoperative vitals {vitals}."
            ],
            "adult_cardiac_osa": [
                "{age}-year-old {sex} with history of {comorbidity1} and {comorbidity2} scheduled for {surgery}. {medication_history} {allergy_status} {additional_risks} Vital signs {vitals}.",
                "Adult {sex}, age {age}, presenting for {surgery}. PMH significant for {comorbidity1}, {comorbidity2}, and {additional_condition}. {medication_history} {allergy_status} Preop assessment shows {findings}.",
                "{age} y/o {sex} with {comorbidity1} and severe {comorbidity2} for {surgery}. {additional_risks} Current medications {medication_history}. {allergy_status} Physical exam {exam}."
            ],
            "mh_history": [
                "{age}-year-old {sex} with family history of malignant hyperthermia scheduled for {surgery}. {additional_info} {allergy_status} Vital signs {vitals}.",
                "Patient is a {age} year old {sex} with known MH susceptibility presenting for {surgery}. {family_history} {allergy_status} Preoperative vitals {vitals}.",
                "{age} y/o {sex} with personal history of MH reaction during previous surgery. Now scheduled for {surgery}. {precautions} {allergy_status}"
            ],
            "egg_soy_allergy": [
                "{age}-year-old {sex} with severe allergies to eggs and soy scheduled for {surgery}. {additional_info} Previous allergic reactions include {reaction_history}. Vital signs {vitals}.",
                "Patient with documented egg and soy allergy, age {age}, {sex}, presenting for {surgery}. {severity} {additional_allergies} {allergy_management}",
                "{age} y/o {sex} with known food allergies including eggs and soy products for {surgery}. {reaction_history} {allergy_status}"
            ]
        }

        # Randomization options
        self.random_options = {
            "ages": {
                "pediatric": list(range(2, 18)),
                "adult": list(range(18, 80)),
                "geriatric": list(range(65, 90))
            },
            "sex": ["M", "F"],
            "comorbidities": {
                "asthma": ["asthma", "reactive airway disease", "bronchospasm history"],
                "cardiac": ["coronary artery disease", "heart failure", "arrhythmias", "hypertension"],
                "osa": ["obstructive sleep apnea", "sleep-disordered breathing", "OSA with CPAP use"],
                "diabetes": ["diabetes mellitus", "type 2 diabetes", "insulin-dependent diabetes"]
            },
            "surgeries": {
                "ent": ["tonsillectomy and adenoidectomy", "tonsillectomy", "adenoidectomy", "myringotomy"],
                "cardiac": ["coronary bypass", "valve replacement", "cardiac catheterization"],
                "orthopedic": ["total knee replacement", "hip replacement", "arthroscopy"],
                "general": ["cholecystectomy", "appendectomy", "hernia repair"]
            },
            "triggers": ["upper respiratory infection", "cold symptoms", "viral illness", "exercise"],
            "timeframes": ["5 days ago", "1 week ago", "2 weeks ago", "last month"],
            "medications": ["albuterol", "albuterol and fluticasone", "rescue inhaler"],
            "vitals": ["stable", "within normal limits", "BP 110/70, HR 85, O2 sat 98%"],
            "allergy_status": ["No known drug allergies", "NKDA", "Known allergy to eggs and soy", "Multiple food allergies"]
        }

    def generate_random_hpi(self, scenario_type: str) -> Dict[str, Any]:
        """Generate a random HPI for the given scenario type"""
        if scenario_type not in self.hpi_templates:
            scenario_type = "pediatric_ent_asthma"  # default

        template = random.choice(self.hpi_templates[scenario_type])

        # Select appropriate age range
        if "pediatric" in scenario_type:
            age = random.choice(self.random_options["ages"]["pediatric"])
        elif "geriatric" in scenario_type:
            age = random.choice(self.random_options["ages"]["geriatric"])
        else:
            age = random.choice(self.random_options["ages"]["adult"])

        sex = random.choice(self.random_options["sex"])

        # Generate context-appropriate content
        replacements = {
            "age": age,
            "sex": sex,
            "comorbidity": random.choice(self.random_options["comorbidities"]["asthma"]),
            "comorbidity1": random.choice(self.random_options["comorbidities"]["cardiac"]),
            "comorbidity2": random.choice(self.random_options["comorbidities"]["osa"]),
            "trigger": random.choice(self.random_options["triggers"]),
            "timeframe": random.choice(self.random_options["timeframes"]),
            "medication": random.choice(self.random_options["medications"]),
            "vitals": random.choice(self.random_options["vitals"]),
            "surgery": random.choice(self.random_options["surgeries"]["ent"]),
            "allergy_status": "No known drug allergies",
            "npo_time": "midnight",
            "exam": "appropriate for age",
            "additional_condition": "seasonal allergies",
            "medication_history": "Takes lisinopril daily",
            "additional_risks": "BMI 35, neck circumference 18 inches",
            "findings": "Mallampati III airway",
            "additional_info": "Brother had MH reaction",
            "family_history": "Sister and father both MH positive",
            "precautions": "Trigger-free anesthesia planned",
            "reaction_history": "hives and bronchospasm",
            "severity": "Anaphylactic reactions in past",
            "additional_allergies": "Also allergic to shellfish",
            "allergy_management": "Carries epinephrine auto-injector"
        }

        # Handle special cases
        if "allergy" in scenario_type:
            replacements["allergy_status"] = random.choice([
                "Known allergy to eggs and soy",
                "Multiple food allergies including eggs and soy",
                "Severe egg and soy allergy with anaphylaxis history"
            ])

        # Fill in the template
        hpi_text = template.format(**replacements)

        # Generate corresponding patient parameters
        patient_params = {
            "age_years": age,
            "weight_kg": self._calculate_weight(age),
            "height_cm": self._calculate_height(age),
            "sex": sex,
            "urgency": "elective" if "trauma" not in scenario_type else "urgent",
            "surgery_domain": self._get_surgery_domain(scenario_type),
            "allergies": self._get_allergies(scenario_type),
            "renal_function": None,
            "hepatic_function": None
        }

        # Generate risk assessment parameters
        risk_params = {
            "age_band": self._get_age_band(age),
            "surgery_type": patient_params["surgery_domain"],
            "urgency": patient_params["urgency"]
        }

        return {
            "hpi_text": hpi_text,
            "patient_params": patient_params,
            "risk_assessment_params": risk_params
        }

    def _calculate_weight(self, age: int) -> float:
        """Calculate realistic weight based on age"""
        if age < 2:
            return round(10 + age * 2, 1)
        elif age < 18:
            return round(10 + age * 2.5, 1)
        else:
            return round(random.uniform(50, 100), 1)

    def _calculate_height(self, age: int) -> int:
        """Calculate realistic height based on age"""
        if age < 2:
            return int(75 + age * 10)
        elif age < 18:
            return int(80 + age * 5)
        else:
            return random.randint(150, 190)

    def _get_surgery_domain(self, scenario_type: str) -> str:
        """Get surgery domain based on scenario"""
        if "ent" in scenario_type:
            return "ENT"
        elif "cardiac" in scenario_type:
            return "Cardiac"
        elif "trauma" in scenario_type:
            return "Emergency"
        else:
            return "General"

    def _get_allergies(self, scenario_type: str) -> List[str]:
        """Get allergies based on scenario"""
        if "allergy" in scenario_type:
            return ["EGG_SOY_ALLERGY"]
        return []

    def _get_age_band(self, age: int) -> str:
        """Get age band for risk assessment"""
        if age < 2:
            return "0-2"
        elif age < 6:
            return "2-6"
        elif age < 12:
            return "6-12"
        elif age < 18:
            return "12-18"
        elif age < 65:
            return "18-65"
        else:
            return "65+"

    def test_medication_recommendation(self, scenario_name: str, num_iterations: int = 5) -> List[TestResult]:
        """Test medication recommendations for a scenario with multiple random iterations"""
        results = []
        scenario = self.test_scenarios[scenario_name]

        for i in range(num_iterations):
            try:
                # Generate random test case
                test_data = self.generate_random_hpi(scenario_name)

                # Add MH history feature for MH scenarios
                if "mh" in scenario_name:
                    test_data["patient_params"]["features"] = ["MH_HISTORY"]

                # Make API call
                response = requests.post(
                    f"{self.base_url}/api/meds/recommend",
                    json=test_data,
                    timeout=30
                )

                if response.status_code != 200:
                    results.append(TestResult(
                        test_name=f"{scenario_name}_iteration_{i+1}",
                        passed=False,
                        expected="HTTP 200",
                        actual=f"HTTP {response.status_code}",
                        error=response.text
                    ))
                    continue

                data = response.json()

                # Validate response structure
                structure_result = self._validate_response_structure(data, f"{scenario_name}_structure_{i+1}")
                results.append(structure_result)

                if not structure_result.passed:
                    continue

                # Test medication recommendations
                meds_result = self._validate_medication_recommendations(
                    data['meds'], scenario, f"{scenario_name}_meds_{i+1}"
                )
                results.append(meds_result)

                # Test dose calculations
                dose_result = self._validate_dose_calculations(
                    data['meds'], test_data['patient_params'], f"{scenario_name}_doses_{i+1}"
                )
                results.append(dose_result)

                # Test contraindications
                contra_result = self._validate_contraindications(
                    data['meds'], scenario, f"{scenario_name}_contra_{i+1}"
                )
                results.append(contra_result)

            except Exception as e:
                results.append(TestResult(
                    test_name=f"{scenario_name}_iteration_{i+1}_error",
                    passed=False,
                    expected="No exception",
                    actual=str(e),
                    error=str(e)
                ))

        return results

    def _validate_response_structure(self, response_data: Dict, test_name: str) -> TestResult:
        """Validate API response has required structure"""
        required_keys = ['patient', 'context', 'meds', 'summary']
        required_med_buckets = ['draw_now', 'standard', 'consider', 'contraindicated']

        for key in required_keys:
            if key not in response_data:
                return TestResult(
                    test_name=test_name,
                    passed=False,
                    expected=f"Response contains '{key}'",
                    actual=f"Missing '{key}'",
                    error=f"Response structure validation failed: missing {key}"
                )

        meds = response_data.get('meds', {})
        for bucket in required_med_buckets:
            if bucket not in meds:
                return TestResult(
                    test_name=test_name,
                    passed=False,
                    expected=f"Meds contains '{bucket}' bucket",
                    actual=f"Missing '{bucket}' bucket",
                    error=f"Medication bucket validation failed: missing {bucket}"
                )

        return TestResult(
            test_name=test_name,
            passed=True,
            expected="Valid response structure",
            actual="Valid response structure",
            score=1.0
        )

    def _validate_medication_recommendations(self, meds: Dict, scenario: Dict, test_name: str) -> TestResult:
        """Validate medication recommendations match expected patterns"""
        draw_now_agents = [med['agent'] for med in meds.get('draw_now', [])]
        standard_agents = [med['agent'] for med in meds.get('standard', [])]

        expected_draw_now = scenario['expected_draw_now']
        expected_standard = scenario['expected_standard']

        # Calculate scores based on expected vs actual
        draw_now_score = self._calculate_overlap_score(draw_now_agents, expected_draw_now)
        standard_score = self._calculate_overlap_score(standard_agents, expected_standard)

        # Overall score weighted by importance (draw_now is more critical)
        overall_score = (draw_now_score * 0.7) + (standard_score * 0.3)

        passed = overall_score >= 0.6  # 60% threshold for passing

        return TestResult(
            test_name=test_name,
            passed=passed,
            expected=f"Draw now: {expected_draw_now}, Standard: {expected_standard}",
            actual=f"Draw now: {draw_now_agents}, Standard: {standard_agents}",
            score=overall_score,
            error="" if passed else f"Low medication recommendation score: {overall_score:.2f}"
        )

    def _validate_dose_calculations(self, meds: Dict, patient_params: Dict, test_name: str) -> TestResult:
        """Validate dose calculations are realistic"""
        all_meds = meds.get('draw_now', []) + meds.get('standard', [])

        dose_errors = []
        valid_doses = 0
        total_with_doses = 0

        for med in all_meds:
            if 'dose' not in med or not med['dose']:
                continue

            total_with_doses += 1
            agent = med['agent']
            dose_info = med['dose']

            # Validate dose format and reasonableness
            if not self._is_dose_reasonable(agent, dose_info, patient_params):
                dose_errors.append(f"{agent}: {dose_info}")
            else:
                valid_doses += 1

        if total_with_doses == 0:
            return TestResult(
                test_name=test_name,
                passed=False,
                expected="Medications with dose calculations",
                actual="No medications have doses",
                error="No dose calculations found"
            )

        score = valid_doses / total_with_doses
        passed = score >= 0.8  # 80% of doses should be reasonable

        return TestResult(
            test_name=test_name,
            passed=passed,
            expected="Realistic dose calculations",
            actual=f"{valid_doses}/{total_with_doses} doses valid",
            score=score,
            error=f"Invalid doses: {dose_errors}" if dose_errors else ""
        )

    def _validate_contraindications(self, meds: Dict, scenario: Dict, test_name: str) -> TestResult:
        """Validate contraindications are properly flagged"""
        contraindicated_agents = [med['agent'] for med in meds.get('contraindicated', [])]
        expected_contraindicated = scenario['contraindicated_check']

        if not expected_contraindicated:
            # No contraindications expected
            return TestResult(
                test_name=test_name,
                passed=True,
                expected="No specific contraindications",
                actual=f"Contraindicated: {contraindicated_agents}",
                score=1.0
            )

        # Check if expected contraindications are properly flagged
        found_contraindications = set(contraindicated_agents) & set(expected_contraindicated)
        score = len(found_contraindications) / len(expected_contraindicated)
        passed = score >= 0.8  # Should catch 80% of expected contraindications

        return TestResult(
            test_name=test_name,
            passed=passed,
            expected=f"Contraindicated: {expected_contraindicated}",
            actual=f"Contraindicated: {contraindicated_agents}",
            score=score,
            error="" if passed else f"Missed contraindications: {set(expected_contraindicated) - found_contraindications}"
        )

    def _calculate_overlap_score(self, actual: List[str], expected: List[str]) -> float:
        """Calculate overlap score between actual and expected lists"""
        if not expected:
            return 1.0 if not actual else 0.8  # No expectations is OK

        actual_set = set(actual)
        expected_set = set(expected)

        # Score based on how many expected items are found + penalty for unexpected items
        found = len(actual_set & expected_set)
        missed = len(expected_set - actual_set)
        unexpected = len(actual_set - expected_set)

        # Formula: (found / expected) - penalty for unexpected items
        base_score = found / len(expected) if expected else 1.0
        penalty = min(0.3, unexpected * 0.1)  # Max 30% penalty

        return max(0.0, base_score - penalty)

    def _is_dose_reasonable(self, agent: str, dose_info: Dict, patient_params: Dict) -> bool:
        """Check if dose is reasonable for the agent and patient"""
        if not isinstance(dose_info, dict):
            return False

        age = patient_params.get('age_years', 0)
        weight = patient_params.get('weight_kg', 0)

        # Define reasonable dose ranges for common medications
        dose_ranges = {
            "Ondansetron": {"pediatric": (0.5, 4), "adult": (4, 8)},
            "Dexamethasone": {"pediatric": (0.5, 8), "adult": (4, 16)},
            "Albuterol": {"pediatric": (1.25, 5), "adult": (2.5, 5)},
            "Epinephrine": {"pediatric": (0.001, 0.3), "adult": (0.1, 1)},
            "Succinylcholine": {"pediatric": (10, 150), "adult": (50, 200)},
            "Rocuronium": {"pediatric": (5, 60), "adult": (30, 100)},
            "Phenylephrine": {"pediatric": (0.005, 0.1), "adult": (0.05, 0.5)},
            "Atropine": {"pediatric": (0.1, 1), "adult": (0.4, 2)}
        }

        if agent not in dose_ranges:
            return True  # Unknown agent, assume reasonable

        # Get appropriate range
        range_key = "pediatric" if age < 18 else "adult"
        min_dose, max_dose = dose_ranges[agent][range_key]

        # Extract dose value (could be mg, mcg, etc.)
        dose_mg = dose_info.get('mg')
        if dose_mg is not None:
            return min_dose <= dose_mg <= max_dose

        return True  # Couldn't validate, assume OK

    def run_comprehensive_test_suite(self, iterations_per_scenario: int = 10) -> Dict[str, Any]:
        """Run comprehensive test suite with multiple iterations per scenario"""
        print("=" * 80)
        print("MERIDIAN MEDICATION API COMPREHENSIVE TEST SUITE")
        print("=" * 80)
        print(f"Testing {len(self.test_scenarios)} scenarios with {iterations_per_scenario} iterations each")
        print(f"Target accuracy: >90%")
        print()

        start_time = time.time()
        all_results = []
        scenario_scores = {}

        for scenario_name, scenario_info in self.test_scenarios.items():
            print(f"Testing scenario: {scenario_name}")
            print(f"Description: {scenario_info['description']}")
            print(f"Weight: {scenario_info['weight']:.1%}")

            scenario_results = self.test_medication_recommendation(scenario_name, iterations_per_scenario)
            all_results.extend(scenario_results)

            # Calculate scenario score
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

            print(f"  Results: {scenario_passed}/{scenario_total} passed ({scenario_passed/scenario_total*100:.1f}%)")
            print(f"  Average score: {scenario_avg_score:.3f}")
            print()

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

        # Print comprehensive results
        print("=" * 80)
        print("COMPREHENSIVE TEST RESULTS")
        print("=" * 80)
        print(f"Total tests run: {total_tests}")
        print(f"Tests passed: {total_passed}")
        print(f"Overall pass rate: {overall_pass_rate*100:.1f}%")
        print(f"Weighted accuracy: {weighted_accuracy*100:.1f}%")
        print(f"Test duration: {duration:.1f} seconds")
        print()

        # Detailed scenario breakdown
        print("SCENARIO BREAKDOWN:")
        print("-" * 50)
        for scenario_name, scores in scenario_scores.items():
            status = "PASS" if scores['avg_score'] >= 0.8 else "FAIL"
            print(f"{scenario_name:30} {scores['avg_score']*100:5.1f}% ({scores['passed']:2}/{scores['total']:2}) [{status}]")

        print()

        # Failed test details
        failed_tests = [r for r in all_results if not r.passed]
        if failed_tests:
            print("FAILED TEST DETAILS:")
            print("-" * 50)
            for test in failed_tests[:10]:  # Show first 10 failures
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
        elif weighted_accuracy >= 0.8:
            print("GOOD: 80-90% accuracy - some improvements needed")
        elif weighted_accuracy >= 0.7:
            print("FAIR: 70-80% accuracy - significant improvements needed")
        else:
            print("POOR: <70% accuracy - major issues require attention")

        print("=" * 80)

        return {
            'overall_pass_rate': overall_pass_rate,
            'weighted_accuracy': weighted_accuracy,
            'total_tests': total_tests,
            'passed_tests': total_passed,
            'scenario_scores': scenario_scores,
            'failed_tests': failed_tests,
            'duration': duration
        }

def main():
    print("Starting comprehensive medication API testing...")

    # Test server connectivity
    try:
        response = requests.get("http://localhost:8084/", timeout=5)
        print("Server connectivity: OK")
    except Exception as e:
        print(f"ERROR: Cannot connect to server at localhost:8084: {e}")
        print("Please ensure the server is running: python app_simple.py")
        return 1

    # Create test suite and run comprehensive tests
    test_suite = MedicationTestSuite()
    results = test_suite.run_comprehensive_test_suite(iterations_per_scenario=5)

    # Return appropriate exit code
    return 0 if results['weighted_accuracy'] >= 0.9 else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)