#!/usr/bin/env python3
"""
Unit tests for Meridian Medication Engine
"""

import unittest
import json
from pathlib import Path
import sys

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from services.meds_engine import MeridianMedsEngine, PatientParameters, DoseCalculation
from nlp.pipeline import parse_hpi

class TestMeridianMedsEngine(unittest.TestCase):
    """Test cases for medication recommendation engine"""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures"""
        cls.engine = MeridianMedsEngine()

        # Load test cases
        fixtures_path = Path(__file__).parent / "fixtures" / "meds" / "sample_cases.json"
        with open(fixtures_path, 'r') as f:
            cls.test_data = json.load(f)

    def test_dose_calculations(self):
        """Test dose calculation accuracy"""
        for test_case in self.test_data['dose_calculation_tests']:
            with self.subTest(agent=test_case['agent']):
                agent = test_case['agent']
                patient_data = test_case['patient']

                patient_params = PatientParameters(
                    age_years=patient_data['age_years'],
                    weight_kg=patient_data['weight_kg']
                )

                dose_info = self.engine.dosing_rules.get('dosing_rules', {}).get(agent, {})
                self.assertIsNotNone(dose_info, f"No dosing info found for {agent}")

                calc = self.engine._calculate_dose(agent, dose_info, patient_params)
                self.assertIsNotNone(calc, f"Dose calculation failed for {agent}")

                # Check dose accuracy (within 10% tolerance)
                if 'expected_dose_mg' in test_case:
                    expected_mg = test_case['expected_dose_mg']
                    self.assertAlmostEqual(calc.mg, expected_mg, delta=expected_mg * 0.1,
                                         msg=f"Dose calculation for {agent}: expected {expected_mg}, got {calc.mg}")

                # Check volume calculation
                if 'expected_volume_ml' in test_case:
                    expected_vol = test_case['expected_volume_ml']
                    self.assertAlmostEqual(calc.volume_ml, expected_vol, delta=expected_vol * 0.1,
                                         msg=f"Volume calculation for {agent}: expected {expected_vol}, got {calc.volume_ml}")

    def test_contraindication_screening(self):
        """Test contraindication detection"""
        for test_case in self.test_data['contraindication_tests']:
            with self.subTest(scenario=test_case['scenario']):
                features = test_case['features']
                allergies = test_case['allergies']

                patient_params = PatientParameters(
                    age_years=25,
                    weight_kg=70,
                    allergies=allergies
                )

                expected_contraindicated = test_case['expected_contraindicated']

                for agent in expected_contraindicated:
                    # Find medication class
                    med_class = None
                    for class_name, class_info in self.engine.formulary.get('medication_classes', {}).items():
                        if agent in class_info.get('agents', {}):
                            med_class = class_name
                            break

                    if med_class:
                        is_contra, reason = self.engine._check_contraindications(
                            agent, med_class, features, patient_params
                        )
                        self.assertTrue(is_contra, f"{agent} should be contraindicated in {test_case['scenario']}")
                        self.assertIsNotNone(reason, f"No reason provided for {agent} contraindication")

    def test_pediatric_vs_adult_dosing(self):
        """Test age-appropriate dosing selection"""
        # Test pediatric dosing
        pediatric_params = PatientParameters(age_years=4, weight_kg=18)

        ondansetron_info = self.engine.dosing_rules.get('dosing_rules', {}).get('Ondansetron', {})
        calc_peds = self.engine._calculate_dose('Ondansetron', ondansetron_info, pediatric_params)

        self.assertIsNotNone(calc_peds)
        self.assertLessEqual(calc_peds.mg, 4.0, "Pediatric ondansetron dose should not exceed 4mg")

        # Test adult dosing
        adult_params = PatientParameters(age_years=45, weight_kg=70)
        calc_adult = self.engine._calculate_dose('Ondansetron', ondansetron_info, adult_params)

        self.assertIsNotNone(calc_adult)
        self.assertEqual(calc_adult.mg, 4.0, "Adult ondansetron dose should be 4mg")

    def test_renal_hepatic_adjustments(self):
        """Test organ function dose adjustments"""
        base_params = PatientParameters(age_years=65, weight_kg=70)

        # Test with normal function
        normal_calc = self.engine._apply_organ_adjustments(
            'Ondansetron', 4.0, 2.0, base_params
        )

        # Test with renal impairment
        renal_params = PatientParameters(age_years=65, weight_kg=70, renal_function='severe')
        renal_dose, renal_vol = self.engine._apply_organ_adjustments(
            'Dexmedetomidine', 70.0, 0.7, renal_params  # Agent with renal adjustment
        )

        # Should be reduced for renally cleared drugs
        self.assertLess(renal_dose, 70.0, "Dose should be reduced with renal impairment")

    def test_comprehensive_recommendation_generation(self):
        """Test end-to-end recommendation generation"""
        for test_case in self.test_data['test_cases']:
            with self.subTest(case_id=test_case['case_id']):
                # Parse HPI
                parsed_hpi = parse_hpi(test_case['hpi_text'])

                # Create patient parameters
                patient_data = test_case['patient_params']
                patient_params = PatientParameters(**patient_data)

                # Mock risk summary (would come from risk engine in real implementation)
                risk_summary = self._create_mock_risk_summary(test_case['expected_elevated_risks'])

                # Generate recommendations
                recommendations = self.engine.generate_recommendations(
                    parsed_hpi=parsed_hpi,
                    risk_summary=risk_summary,
                    patient_params=patient_params
                )

                # Verify response structure
                self.assertIn('patient', recommendations)
                self.assertIn('context', recommendations)
                self.assertIn('meds', recommendations)
                self.assertIn('summary', recommendations)

                # Verify medication buckets
                meds = recommendations['meds']
                self.assertIn('draw_now', meds)
                self.assertIn('standard', meds)
                self.assertIn('consider', meds)
                self.assertIn('contraindicated', meds)

                # Check for expected medications (if specified)
                if test_case.get('expected_draw_now'):
                    draw_now_agents = [med['agent'] for med in meds['draw_now']]
                    for expected_agent in test_case['expected_draw_now']:
                        self.assertIn(expected_agent, draw_now_agents,
                                    f"Expected {expected_agent} in draw_now for {test_case['case_id']}")

                # Verify contraindicated medications
                if test_case.get('expected_contraindicated'):
                    contraindicated_agents = [med['agent'] for med in meds['contraindicated']]
                    for expected_contra in test_case['expected_contraindicated']:
                        self.assertIn(expected_contra, contraindicated_agents,
                                    f"Expected {expected_contra} to be contraindicated for {test_case['case_id']}")

    def test_class_deduplication(self):
        """Test that duplicate medication classes are properly handled"""
        # Create multiple candidates from same class
        candidates = [
            {
                'agent': 'Ondansetron',
                'class': '5HT3_Antagonist',
                'priority': 1,
                'confidence': 'A',
                'timing': 'pre_emergence',
                'indication': 'PONV prophylaxis',
                'evidence': []
            },
            {
                'agent': 'Granisetron',
                'class': '5HT3_Antagonist',
                'priority': 2,
                'confidence': 'B',
                'timing': 'pre_emergence',
                'indication': 'PONV prophylaxis',
                'evidence': []
            }
        ]

        deduplicated = self.engine._deduplicate_candidates(candidates)

        # Should keep only the higher priority (lower number) agent
        self.assertEqual(len(deduplicated), 1)
        self.assertEqual(deduplicated[0]['agent'], 'Ondansetron')

    def test_evidence_confidence_mapping(self):
        """Test that evidence levels are properly assigned"""
        # Create a candidate with high-quality evidence
        candidate = {
            'agent': 'Ondansetron',
            'class': '5HT3_Antagonist',
            'confidence': 'A',
            'evidence': ['ASA PONV Guidelines 2020']
        }

        patient_params = PatientParameters(age_years=25, weight_kg=70)

        recommendation = self.engine._create_full_recommendation(candidate, patient_params)

        self.assertIsNotNone(recommendation)
        self.assertEqual(recommendation.confidence, 'A')
        self.assertGreater(len(recommendation.citations), 0)

    def test_safety_bounds(self):
        """Test that dose calculations respect safety bounds"""
        # Test with very low weight
        tiny_patient = PatientParameters(age_years=0.1, weight_kg=3.0)

        ondansetron_info = self.engine.dosing_rules.get('dosing_rules', {}).get('Ondansetron', {})
        calc = self.engine._calculate_dose('Ondansetron', ondansetron_info, tiny_patient)

        self.assertIsNotNone(calc)
        # Should respect minimum dose
        self.assertGreaterEqual(calc.mg, 1.0, "Should respect minimum dose bounds")

        # Test with very high weight
        large_patient = PatientParameters(age_years=25, weight_kg=150)
        calc_large = self.engine._calculate_dose('Ondansetron', ondansetron_info, large_patient)

        self.assertIsNotNone(calc_large)
        # Should respect maximum dose
        self.assertLessEqual(calc_large.mg, 4.0, "Should respect maximum dose bounds")

    def test_volume_rounding(self):
        """Test that volumes are rounded to practical increments"""
        calc = DoseCalculation(mg=1.847, volume_ml=0.923, concentration="2 mg/mL")

        rounded_volume = self.engine._round_volume(calc.volume_ml)
        self.assertEqual(rounded_volume, 0.9, "Volume should be rounded to 0.1 mL increments")

        rounded_dose = self.engine._round_dose(calc.mg)
        self.assertEqual(rounded_dose, 2.0, "Dose should be rounded to 0.5 mg increments")

    def _create_mock_risk_summary(self, elevated_risks):
        """Create mock risk summary for testing"""
        risks = {}

        risk_values = {
            'BRONCHOSPASM': 0.06,
            'LARYNGOSPASM': 0.04,
            'PONV': 0.45,
            'HYPOTENSION': 0.30,
            'EMERGENCE_AGITATION': 0.25
        }

        for risk in elevated_risks:
            risks[risk] = {
                'absolute_risk': risk_values.get(risk, 0.05),
                'delta_vs_baseline': 0.02,
                'confidence': 'B'
            }

        return {'risks': risks}

if __name__ == '__main__':
    unittest.main()