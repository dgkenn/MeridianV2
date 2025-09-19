#!/usr/bin/env python3
"""
Immediate Safety Improvements for Meridian
Based on recursive learning analysis results
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.core.hpi_parser import MedicalTextProcessor
from src.core.risk_engine import RiskEngine
import re
import json
from typing import Dict, List, Tuple, Optional

class EnhancedSafetyValidator:
    """Enhanced safety validation with immediate improvements"""

    def __init__(self):
        self.critical_interactions = self._build_critical_interactions()
        self.enhanced_contraindications = self._build_enhanced_contraindications()
        self.pediatric_safety_rules = self._build_pediatric_safety_rules()

    def _build_critical_interactions(self) -> Dict[str, List[Dict]]:
        """Build comprehensive drug interaction database"""
        return {
            "MAOI": [
                {
                    "interacting_drug": "MEPERIDINE",
                    "severity": "contraindicated",
                    "mechanism": "Serotonin syndrome risk",
                    "recommendation": "Use morphine or fentanyl instead"
                },
                {
                    "interacting_drug": "DEXMEDETOMIDINE",
                    "severity": "caution",
                    "mechanism": "Enhanced sedation",
                    "recommendation": "Reduce dexmedetomidine dose by 50%"
                }
            ],
            "WARFARIN": [
                {
                    "interacting_drug": "NSAIDS",
                    "severity": "contraindicated",
                    "mechanism": "Increased bleeding risk",
                    "recommendation": "Use acetaminophen or regional blocks"
                },
                {
                    "interacting_drug": "ASPIRIN",
                    "severity": "high_risk",
                    "mechanism": "Dual antiplatelet effect",
                    "recommendation": "Monitor coagulation closely"
                }
            ],
            "BETA_BLOCKERS": [
                {
                    "interacting_drug": "VERAPAMIL",
                    "severity": "contraindicated",
                    "mechanism": "Heart block risk",
                    "recommendation": "Avoid concurrent use"
                }
            ]
        }

    def _build_enhanced_contraindications(self) -> Dict[str, List[Dict]]:
        """Enhanced contraindication rules"""
        return {
            "SUCCINYLCHOLINE": [
                {
                    "condition": "CHRONIC_KIDNEY_DISEASE",
                    "severity": "contraindicated",
                    "reason": "Hyperkalemia risk in CKD patients",
                    "alternative": "Rocuronium with sugammadex"
                },
                {
                    "condition": "BURN_INJURY",
                    "severity": "contraindicated",
                    "reason": "Massive potassium release",
                    "alternative": "Rocuronium"
                },
                {
                    "condition": "NEUROMUSCULAR_DISEASE",
                    "severity": "contraindicated",
                    "reason": "Hyperkalemic cardiac arrest",
                    "alternative": "Rocuronium or cisatracurium"
                }
            ],
            "MORPHINE": [
                {
                    "condition": "COPD",
                    "severity": "high_risk",
                    "reason": "Respiratory depression in limited reserve",
                    "alternative": "Regional blocks or reduced opioid technique"
                },
                {
                    "condition": "SLEEP_APNEA",
                    "severity": "high_risk",
                    "reason": "Increased airway obstruction risk",
                    "alternative": "Multimodal analgesia with reduced opioids"
                }
            ],
            "DESFLURANE": [
                {
                    "condition": "ASTHMA",
                    "severity": "contraindicated",
                    "reason": "Airway irritation causing bronchospasm",
                    "alternative": "Sevoflurane"
                },
                {
                    "condition": "REACTIVE_AIRWAY_DISEASE",
                    "severity": "contraindicated",
                    "reason": "Bronchial hyperresponsiveness",
                    "alternative": "Sevoflurane or TIVA"
                }
            ]
        }

    def _build_pediatric_safety_rules(self) -> List[Dict]:
        """Pediatric-specific safety rules"""
        return [
            {
                "rule": "weight_based_dosing",
                "description": "All medications must include weight-based dosing for patients <18 years",
                "critical_medications": ["PROPOFOL", "ROCURONIUM", "CISATRACURIUM", "MORPHINE", "FENTANYL"]
            },
            {
                "rule": "emergence_delirium_prevention",
                "description": "Pediatric cases should include emergence delirium prevention strategies",
                "recommendations": ["Dexmedetomidine", "Sevoflurane mask induction", "Parent presence"]
            },
            {
                "rule": "airway_management",
                "description": "Pediatric airway management considerations",
                "special_considerations": ["Smaller endotracheal tubes", "Uncuffed tubes <8 years", "Backup airway plan"]
            }
        ]

    def validate_enhanced_safety(self, result: Dict, case_data: Dict) -> Tuple[bool, List[str], List[Dict]]:
        """Enhanced safety validation with specific improvement recommendations"""
        violations = []
        recommendations = []
        is_safe = True

        # 1. Drug interaction checking
        drug_violations, drug_recommendations = self._check_drug_interactions(result)
        violations.extend(drug_violations)
        recommendations.extend(drug_recommendations)

        # 2. Enhanced contraindication checking
        contra_violations, contra_recommendations = self._check_enhanced_contraindications(result, case_data)
        violations.extend(contra_violations)
        recommendations.extend(contra_recommendations)

        # 3. Pediatric safety checking
        if case_data.get('demographics', {}).get('age_years', 100) < 18:
            ped_violations, ped_recommendations = self._check_pediatric_safety(result, case_data)
            violations.extend(ped_violations)
            recommendations.extend(ped_recommendations)

        # 4. Emergency protocol checking
        emergency_violations, emergency_recommendations = self._check_emergency_protocols(result, case_data)
        violations.extend(emergency_violations)
        recommendations.extend(emergency_recommendations)

        # Determine if critical safety issues exist
        critical_violations = [v for v in violations if 'contraindicated' in v.lower() or 'critical' in v.lower()]
        if critical_violations:
            is_safe = False

        return is_safe, violations, recommendations

    def _check_drug_interactions(self, result: Dict) -> Tuple[List[str], List[Dict]]:
        """Check for critical drug interactions"""
        violations = []
        recommendations = []

        medications = result.get('medications', {})
        all_meds = []

        # Collect all recommended medications
        for category in ['standard', 'consider', 'draw_now']:
            for med in medications.get(category, []):
                all_meds.append(med.get('medication', ''))

        # Check against interaction database
        for med in all_meds:
            if med in self.critical_interactions:
                for interaction in self.critical_interactions[med]:
                    interacting_med = interaction['interacting_drug']
                    if interacting_med in all_meds:
                        if interaction['severity'] == 'contraindicated':
                            violations.append(f"CRITICAL: {med} + {interacting_med} - {interaction['mechanism']}")
                        recommendations.append({
                            "type": "drug_interaction",
                            "severity": interaction['severity'],
                            "drugs": [med, interacting_med],
                            "mechanism": interaction['mechanism'],
                            "recommendation": interaction['recommendation']
                        })

        return violations, recommendations

    def _check_enhanced_contraindications(self, result: Dict, case_data: Dict) -> Tuple[List[str], List[Dict]]:
        """Check enhanced contraindication rules"""
        violations = []
        recommendations = []

        # Extract patient conditions
        conditions = []
        for factor in case_data.get('extracted_factors', []):
            conditions.append(factor.get('token', ''))

        # Check medications against conditions
        medications = result.get('medications', {})
        for category in ['standard', 'consider', 'draw_now']:
            for med in medications.get(category, []):
                med_name = med.get('medication', '')
                if med_name in self.enhanced_contraindications:
                    for contraindication in self.enhanced_contraindications[med_name]:
                        condition = contraindication['condition']
                        if condition in conditions:
                            if contraindication['severity'] == 'contraindicated':
                                violations.append(f"CONTRAINDICATED: {med_name} in {condition} - {contraindication['reason']}")
                            recommendations.append({
                                "type": "contraindication",
                                "medication": med_name,
                                "condition": condition,
                                "severity": contraindication['severity'],
                                "reason": contraindication['reason'],
                                "alternative": contraindication['alternative']
                            })

        return violations, recommendations

    def _check_pediatric_safety(self, result: Dict, case_data: Dict) -> Tuple[List[str], List[Dict]]:
        """Check pediatric safety rules"""
        violations = []
        recommendations = []

        demographics = case_data.get('demographics', {})
        weight = demographics.get('weight_kg')
        age = demographics.get('age_years', 0)

        # Check weight-based dosing
        if not weight:
            violations.append("CRITICAL: Pediatric case missing weight for medication dosing")

        medications = result.get('medications', {})
        for category in ['standard', 'consider', 'draw_now']:
            for med in medications.get(category, []):
                med_name = med.get('medication', '')
                dose = med.get('dose', '')

                if med_name in self.pediatric_safety_rules[0]['critical_medications']:
                    if weight and 'mg/kg' not in dose:
                        violations.append(f"Pediatric medication {med_name} missing weight-based dosing")

        # Add pediatric-specific recommendations
        recommendations.append({
            "type": "pediatric_protocol",
            "age": age,
            "recommendations": [
                "Use age-appropriate equipment",
                "Consider emergence delirium prevention",
                "Family-centered care approach",
                "Temperature monitoring critical"
            ]
        })

        return violations, recommendations

    def _check_emergency_protocols(self, result: Dict, case_data: Dict) -> Tuple[List[str], List[Dict]]:
        """Check emergency protocol requirements"""
        violations = []
        recommendations = []

        hpi_text = case_data.get('hpi_text', '').lower()

        # Check for emergency situations
        emergency_keywords = ['trauma', 'emergency', 'crash', 'unstable', 'arrest', 'hemorrhage']
        is_emergency = any(keyword in hpi_text for keyword in emergency_keywords)

        if is_emergency:
            recs = result.get('recommendations', {})
            intraop = recs.get('intraoperative', [])

            # Check for RSI protocol in trauma
            if 'trauma' in hpi_text:
                rsi_mentioned = any('rapid' in rec.get('action', '').lower() or 'rsi' in rec.get('action', '').lower()
                                  for rec in intraop)
                if not rsi_mentioned:
                    violations.append("Emergency trauma case missing rapid sequence intubation protocol")
                    recommendations.append({
                        "type": "emergency_protocol",
                        "situation": "trauma",
                        "required_protocol": "Rapid Sequence Intubation",
                        "components": ["Pre-oxygenation", "Cricoid pressure", "Fast-acting medications"]
                    })

        return violations, recommendations

class EnhancedMedicalParser(MedicalTextProcessor):
    """Enhanced medical parser with improved pattern recognition"""

    def __init__(self):
        super().__init__()
        self.enhanced_patterns = self._build_enhanced_patterns()

    def _build_enhanced_patterns(self) -> Dict[str, List[re.Pattern]]:
        """Build enhanced pattern recognition"""
        return {
            # Enhanced cardiovascular patterns
            "CORONARY_ARTERY_DISEASE": [
                re.compile(r"\b(?:coronary artery disease|CAD|coronary disease)\b", re.I),
                re.compile(r"\bcabg\b", re.I),  # Previous CABG implies CAD
                re.compile(r"\bstent(?:s|ed|ing)?\b", re.I),
                re.compile(r"\bmyocardial infarction\b", re.I),
                re.compile(r"\bheart attack\b", re.I),
                re.compile(r"\bangina\b", re.I)
            ],

            # Enhanced diabetes patterns
            "DIABETES": [
                re.compile(r"\bdiabetes\b", re.I),
                re.compile(r"\bdiabetic\b", re.I),
                re.compile(r"\bt1dm\b", re.I),
                re.compile(r"\bt2dm\b", re.I),
                re.compile(r"\btype 1 diabetes\b", re.I),
                re.compile(r"\btype 2 diabetes\b", re.I),
                re.compile(r"\bdiabetes mellitus\b", re.I),
                re.compile(r"\binsulin.{0,20}dependent\b", re.I),
                re.compile(r"\bmetformin\b", re.I),  # Common diabetes medication
                re.compile(r"\bglipizide\b", re.I)
            ],

            # Enhanced renal patterns
            "CHRONIC_KIDNEY_DISEASE": [
                re.compile(r"\bchronic kidney disease\b", re.I),
                re.compile(r"\bckd\b", re.I),
                re.compile(r"\brenal insufficiency\b", re.I),
                re.compile(r"\bstage \d+ kidney disease\b", re.I),
                re.compile(r"\bdialysis\b", re.I),
                re.compile(r"\bhemodialysis\b", re.I),
                re.compile(r"\besrd\b", re.I)
            ],

            # Enhanced surgical emergency patterns
            "TRAUMA": [
                re.compile(r"\btrauma\b", re.I),
                re.compile(r"\bmotor vehicle accident\b", re.I),
                re.compile(r"\bmva\b", re.I),
                re.compile(r"\bfall\b", re.I),
                re.compile(r"\binjury\b", re.I),
                re.compile(r"\bfracture\b", re.I),
                re.compile(r"\bblunt.{0,10}trauma\b", re.I),
                re.compile(r"\bpenetrating.{0,10}trauma\b", re.I)
            ],

            # Enhanced obstetric patterns
            "PREECLAMPSIA": [
                re.compile(r"\bpreeclampsia\b", re.I),
                re.compile(r"\bsevere preeclampsia\b", re.I),
                re.compile(r"\bhypertension.{0,20}pregnancy\b", re.I),
                re.compile(r"\bproteinuria\b", re.I),
                re.compile(r"\bpih\b", re.I)  # Pregnancy-induced hypertension
            ]
        }

    def enhanced_parse(self, hpi_text: str) -> Dict:
        """Enhanced parsing with improved accuracy"""
        # Use base parsing first
        base_result = self.parse_hpi(hpi_text)

        # Apply enhanced patterns
        enhanced_factors = []

        for token, patterns in self.enhanced_patterns.items():
            for pattern in patterns:
                matches = pattern.findall(hpi_text)
                if matches:
                    # Check if we already have this factor
                    existing_tokens = [f.token for f in enhanced_factors]
                    if token not in existing_tokens:
                        enhanced_factors.append({
                            'token': token,
                            'evidence_text': matches[0] if matches else '',
                            'confidence': 0.9,
                            'category': self._get_category_for_token(token),
                            'plain_label': self._get_label_for_token(token),
                            'severity_weight': 1.0
                        })

        # Merge with base results, avoiding duplicates
        all_factors = base_result.extracted_factors[:]
        existing_tokens = [f.token for f in all_factors]

        for factor in enhanced_factors:
            if factor['token'] not in existing_tokens:
                all_factors.append(factor)

        # Update result
        base_result.extracted_factors = all_factors
        base_result.confidence_score = min(1.0, base_result.confidence_score + 0.1)

        return base_result

    def _get_category_for_token(self, token: str) -> str:
        """Get category for token"""
        categories = {
            'CORONARY_ARTERY_DISEASE': 'cardiac',
            'DIABETES': 'endocrine',
            'CHRONIC_KIDNEY_DISEASE': 'renal',
            'TRAUMA': 'emergency',
            'PREECLAMPSIA': 'obstetric'
        }
        return categories.get(token, 'general')

    def _get_label_for_token(self, token: str) -> str:
        """Get human-readable label for token"""
        labels = {
            'CORONARY_ARTERY_DISEASE': 'Coronary artery disease',
            'DIABETES': 'Diabetes mellitus',
            'CHRONIC_KIDNEY_DISEASE': 'Chronic kidney disease',
            'TRAUMA': 'Trauma',
            'PREECLAMPSIA': 'Preeclampsia'
        }
        return labels.get(token, token.replace('_', ' ').title())

def test_enhanced_safety_system():
    """Test the enhanced safety system"""
    print("=== TESTING ENHANCED SAFETY SYSTEM ===")

    # Initialize enhanced components
    safety_validator = EnhancedSafetyValidator()
    enhanced_parser = EnhancedMedicalParser()

    # Test case: Complex cardiac patient
    test_case = {
        "hpi_text": "65-year-old male with coronary artery disease status post CABG, diabetes on metformin, chronic kidney disease stage 3, presenting for valve surgery",
        "demographics": {"age_years": 65, "sex": "male", "weight_kg": 85}
    }

    # Test enhanced parsing
    print("\n1. Enhanced Parsing Test:")
    parsed_result = enhanced_parser.enhanced_parse(test_case["hpi_text"])
    print(f"Extracted conditions: {[f['token'] for f in parsed_result.extracted_factors]}")

    # Test safety validation with mock medication result
    mock_result = {
        "medications": {
            "standard": [
                {"medication": "PROPOFOL", "dose": "1-2 mg/kg"},
                {"medication": "SUCCINYLCHOLINE", "dose": "1 mg/kg"}  # Should trigger CKD warning
            ],
            "contraindicated": [],
            "consider": [],
            "draw_now": []
        },
        "recommendations": {
            "intraoperative": []
        }
    }

    print("\n2. Safety Validation Test:")
    case_data = {
        "extracted_factors": parsed_result.extracted_factors,
        "demographics": test_case["demographics"],
        "hpi_text": test_case["hpi_text"]
    }

    is_safe, violations, recommendations = safety_validator.validate_enhanced_safety(mock_result, case_data)
    print(f"Safety Status: {'SAFE' if is_safe else 'UNSAFE'}")
    print(f"Violations: {len(violations)}")
    for violation in violations:
        print(f"  - {violation}")
    print(f"Recommendations: {len(recommendations)}")
    for rec in recommendations[:3]:  # Show first 3
        print(f"  - {rec['type']}: {rec.get('recommendation', rec.get('reason', 'See details'))}")

    return {
        "parsing_improvements": len(parsed_result.extracted_factors),
        "safety_violations": len(violations),
        "safety_recommendations": len(recommendations),
        "is_safe": is_safe
    }

if __name__ == "__main__":
    results = test_enhanced_safety_system()
    print(f"\n=== ENHANCEMENT RESULTS ===")
    print(f"Parsing improvements: {results['parsing_improvements']} conditions detected")
    print(f"Safety violations: {results['safety_violations']} issues identified")
    print(f"Safety recommendations: {results['safety_recommendations']} suggestions provided")
    print(f"Overall safety: {'PASSED' if results['is_safe'] else 'NEEDS ATTENTION'}")