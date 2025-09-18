#!/usr/bin/env python3
"""
Comprehensive Stress Test for Meridian Risk Engine
Tests 100+ diverse cases with noise, typos, and edge cases
"""

import sys
import random
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
import time

# Add project root to path
sys.path.append(str(Path(__file__).parent))

@dataclass
class TestCase:
    """A test case with expected results"""
    hpi_text: str
    case_id: str
    category: str
    subspecialty: str
    expected_age_band: str
    expected_surgery_type: str
    expected_urgency: str
    expected_factors: List[str]
    expected_negated_factors: List[str]
    expected_risk_flags: List[str]
    complexity_level: str  # simple, moderate, complex, extreme
    noise_level: str  # clean, typos, awkward, garbled

class ComprehensiveTestGenerator:
    """Generates diverse, realistic test cases with controlled noise"""

    def __init__(self):
        self.case_counter = 0

        # Age distributions
        self.age_bands = {
            "neonate": ("<1y", ["0-day-old", "2-week-old", "3-week-old"]),
            "infant": ("1-3", ["6-month-old", "18-month-old", "2-year-old"]),
            "preschool": ("4-6", ["4-year-old", "5-year-old", "6-year-old"]),
            "school": ("7-12", ["7-year-old", "9-year-old", "12-year-old"]),
            "teen": ("13-17", ["14-year-old", "16-year-old", "17-year-old"]),
            "young_adult": ("18-39", ["25-year-old", "32-year-old", "38-year-old"]),
            "middle": ("40-64", ["45-year-old", "55-year-old", "62-year-old"]),
            "elderly": ("65-79", ["68-year-old", "74-year-old", "78-year-old"]),
            "very_elderly": ("≥80", ["83-year-old", "87-year-old", "92-year-old"])
        }

        # Surgical subspecialties with realistic procedures
        self.subspecialties = {
            "ENT": {
                "procedures": ["tonsillectomy and adenoidectomy", "myringotomy with PE tubes",
                             "functional endoscopic sinus surgery", "thyroidectomy", "parotidectomy"],
                "surgery_type": "ENT",
                "common_factors": ["OSA", "RECENT_URI_2W", "ASTHMA"]
            },
            "Dental": {
                "procedures": ["dental rehabilitation under general anesthesia", "multiple extractions",
                             "oral surgery", "dental implants", "wisdom tooth removal"],
                "surgery_type": "Dental",
                "common_factors": ["AUTISM_SPECTRUM_DISORDER", "DENTAL_ANXIETY", "DEVELOPMENTAL_DELAY"]
            },
            "Cardiac": {
                "procedures": ["cardiac catheterization", "ASD closure", "VSD repair",
                             "coronary artery bypass", "valve replacement"],
                "surgery_type": "Cardiac",
                "common_factors": ["CHD", "CHF", "ARRHYTHMIA", "PULM_HTN"]
            },
            "Neurosurgery": {
                "procedures": ["craniotomy for tumor resection", "VP shunt placement",
                             "spine fusion", "brain tumor biopsy", "hydrocephalus repair"],
                "surgery_type": "Neuro",
                "common_factors": ["SEIZURE_DISORDER", "CP", "INCREASED_ICP"]
            },
            "Orthopedic": {
                "procedures": ["fracture repair", "scoliosis correction", "hip replacement",
                             "knee arthroscopy", "spinal fusion"],
                "surgery_type": "Ortho",
                "common_factors": ["MUSCULAR_DYSTROPHY", "CHRONIC_PAIN", "PREVIOUS_SURGERY"]
            },
            "General": {
                "procedures": ["laparoscopic cholecystectomy", "appendectomy", "hernia repair",
                             "bowel resection", "fundoplication"],
                "surgery_type": "General",
                "common_factors": ["GERD", "FULL_STOMACH", "OBESITY"]
            },
            "Urology": {
                "procedures": ["hypospadias repair", "orchiopexy", "nephrectomy",
                             "bladder reconstruction", "kidney transplant"],
                "surgery_type": "Uro",
                "common_factors": ["CHRONIC_KIDNEY_DISEASE", "UTI_RECURRENT"]
            },
            "Ophthalmology": {
                "procedures": ["cataract extraction", "retinal detachment repair", "strabismus correction",
                             "glaucoma surgery", "corneal transplant"],
                "surgery_type": "Ophtho",
                "common_factors": ["PREMATURITY", "CONGENITAL_ANOMALIES"]
            },
            "Plastics": {
                "procedures": ["cleft lip and palate repair", "burn reconstruction", "breast reconstruction",
                             "facial reconstruction", "hand surgery"],
                "surgery_type": "Plastics",
                "common_factors": ["PREVIOUS_SURGERY", "SYNDROMIC_CONDITIONS"]
            },
            "OB": {
                "procedures": ["cesarean section", "cerclage placement", "fetal surgery",
                             "VBAC", "operative delivery"],
                "surgery_type": "OB",
                "common_factors": ["PREECLAMPSIA", "GESTATIONAL_DIABETES", "PREVIOUS_CS"]
            },
            "Thoracic": {
                "procedures": ["lobectomy", "mediastinal mass resection", "diaphragmatic hernia repair",
                             "lung transplant", "esophageal atresia repair"],
                "surgery_type": "Thoracic",
                "common_factors": ["PULM_HTN", "CF", "BRONCHOPULMONARY_DYSPLASIA"]
            },
            "Vascular": {
                "procedures": ["arterial bypass", "aneurysm repair", "carotid endarterectomy",
                             "vascular malformation repair", "dialysis access"],
                "surgery_type": "Vascular",
                "common_factors": ["HYPERTENSION", "DIABETES", "SMOKING_ACTIVE"]
            }
        }

        # Risk factors with realistic combinations
        self.risk_factors = {
            # Respiratory
            "ASTHMA": {
                "phrases": ["asthma", "asthmatic", "reactive airway disease", "RAD", "bronchial asthma"],
                "modifiers": ["well-controlled", "poorly controlled", "exercise-induced", "severe persistent"],
                "medications": ["albuterol", "fluticasone", "budesonide", "montelukast"]
            },
            "RECENT_URI_2W": {
                "phrases": ["recent upper respiratory infection", "recent URI", "cold 10 days ago", "runny nose last week"],
                "contexts": ["treated with", "resolved", "ongoing", "persistent cough"]
            },
            "OSA": {
                "phrases": ["obstructive sleep apnea", "OSA", "sleep apnea", "sleep study"],
                "severity": ["mild", "moderate", "severe"],
                "ahi_values": [8, 12, 18, 25, 35]
            },
            # Cardiac
            "CHD": {
                "phrases": ["congenital heart disease", "CHD", "heart defect", "ventricular septal defect", "atrial septal defect"],
                "types": ["VSD", "ASD", "TOF", "HLHS", "coarctation"]
            },
            "ARRHYTHMIA": {
                "phrases": ["arrhythmia", "irregular heart rhythm", "SVT", "atrial fibrillation", "heart block"],
                "treatments": ["beta-blockers", "pacemaker", "ablation"]
            },
            # Other conditions
            "DIABETES": {
                "phrases": ["diabetes", "diabetic", "type 1 diabetes", "type 2 diabetes", "insulin-dependent"],
                "control": ["well-controlled", "poorly controlled", "brittle"],
                "meds": ["insulin", "metformin", "glipizide"]
            },
            "PREMATURITY": {
                "phrases": ["born at {} weeks".format(w) for w in range(24, 37)],
                "complications": ["NICU stay", "BPD", "ROP", "IVH"]
            }
        }

        # Noise generators
        self.typo_map = {
            'the': ['teh', 'th', 'hte'],
            'and': ['adn', 'an', 'nd'],
            'with': ['wiht', 'wth', 'wit'],
            'patient': ['pateint', 'patint', 'pt'],
            'history': ['hisotry', 'histoy', 'hx'],
            'surgery': ['sugery', 'surgey', 'surg'],
            'asthma': ['asma', 'athma', 'astma'],
            'year': ['yr', 'yrs', 'year'],
            'old': ['yo', 'y/o', 'old']
        }

    def generate_all_test_cases(self) -> List[TestCase]:
        """Generate comprehensive test suite"""
        test_cases = []

        # 1. Healthy baseline cases (10 cases)
        test_cases.extend(self._generate_healthy_cases(10))

        # 2. Single factor cases (20 cases)
        test_cases.extend(self._generate_single_factor_cases(20))

        # 3. Multiple factor cases (20 cases)
        test_cases.extend(self._generate_multiple_factor_cases(20))

        # 4. Complex medical histories (15 cases)
        test_cases.extend(self._generate_complex_cases(15))

        # 5. Negation test cases (10 cases)
        test_cases.extend(self._generate_negation_cases(10))

        # 6. Edge cases and extremes (10 cases)
        test_cases.extend(self._generate_edge_cases(10))

        # 7. Emergency/urgent cases (8 cases)
        test_cases.extend(self._generate_urgent_cases(8))

        # 8. Noise and typo cases (12 cases)
        test_cases.extend(self._generate_noisy_cases(12))

        # 9. Cross-subspecialty coverage (5 cases)
        test_cases.extend(self._generate_coverage_cases(5))

        return test_cases

    def _generate_healthy_cases(self, count: int) -> List[TestCase]:
        """Generate healthy baseline cases across age groups"""
        cases = []

        age_groups = list(self.age_bands.keys())
        subspecialties = list(self.subspecialties.keys())

        for i in range(count):
            age_group = random.choice(age_groups)
            subspecialty = random.choice(subspecialties)

            age_band, age_examples = self.age_bands[age_group]
            age_text = random.choice(age_examples)
            sex = random.choice(["male", "female"])

            sub_info = self.subspecialties[subspecialty]
            procedure = random.choice(sub_info["procedures"])

            # Healthy case template
            hpi = f"{age_text} {sex} presenting for {procedure}. Medical history unremarkable. " \
                  f"No known allergies. Denies asthma, sleep apnea, or other medical conditions. " \
                  f"Vital signs stable with oxygen saturation 99% on room air. " \
                  f"Physical examination within normal limits. NPO since midnight. ASA I."

            cases.append(TestCase(
                hpi_text=hpi,
                case_id=f"healthy_{i+1:02d}",
                category="healthy_baseline",
                subspecialty=subspecialty,
                expected_age_band=age_band,
                expected_surgery_type=sub_info["surgery_type"],
                expected_urgency="elective",
                expected_factors=[],  # No risk factors
                expected_negated_factors=["ASTHMA", "OSA"],
                expected_risk_flags=["LOW_BASELINE_RISK"],
                complexity_level="simple",
                noise_level="clean"
            ))

        return cases

    def _generate_single_factor_cases(self, count: int) -> List[TestCase]:
        """Generate cases with single risk factors"""
        cases = []

        major_factors = ["ASTHMA", "OSA", "CHD", "DIABETES", "PREMATURITY", "RECENT_URI_2W"]

        for i in range(count):
            factor = random.choice(major_factors)
            age_group = random.choice(list(self.age_bands.keys()))
            subspecialty = self._get_appropriate_subspecialty(factor)

            age_band, age_examples = self.age_bands[age_group]
            age_text = random.choice(age_examples)
            sex = random.choice(["male", "female"])

            sub_info = self.subspecialties[subspecialty]
            procedure = random.choice(sub_info["procedures"])

            # Generate factor description
            factor_text = self._generate_factor_description(factor)

            hpi = f"{age_text} {sex} for {procedure}. Medical history significant for {factor_text}. " \
                  f"No other significant medical history. No known drug allergies. " \
                  f"Vital signs stable. Physical exam appropriate for age. NPO since midnight."

            expected_flags = self._get_expected_flags(factor, age_group, subspecialty)

            cases.append(TestCase(
                hpi_text=hpi,
                case_id=f"single_{i+1:02d}",
                category="single_factor",
                subspecialty=subspecialty,
                expected_age_band=age_band,
                expected_surgery_type=sub_info["surgery_type"],
                expected_urgency="elective",
                expected_factors=[factor],
                expected_negated_factors=[],
                expected_risk_flags=expected_flags,
                complexity_level="simple",
                noise_level="clean"
            ))

        return cases

    def _generate_multiple_factor_cases(self, count: int) -> List[TestCase]:
        """Generate cases with multiple interacting risk factors"""
        cases = []

        # Known high-risk combinations
        combinations = [
            (["ASTHMA", "RECENT_URI_2W"], "respiratory_high_risk"),
            (["OSA", "OBESITY"], "airway_high_risk"),
            (["CHD", "PULM_HTN"], "cardiac_high_risk"),
            (["PREMATURITY", "BRONCHOPULMONARY_DYSPLASIA"], "neonatal_high_risk"),
            (["DIABETES", "CHRONIC_KIDNEY_DISEASE"], "metabolic_high_risk"),
            (["CP", "SEIZURE_DISORDER"], "neurologic_high_risk"),
            (["ASTHMA", "OSA", "GERD"], "triple_threat"),
        ]

        for i in range(count):
            factors, risk_profile = random.choice(combinations)

            # Choose appropriate age and subspecialty
            age_group = self._get_appropriate_age_for_factors(factors)
            subspecialty = self._get_appropriate_subspecialty(factors[0])

            age_band, age_examples = self.age_bands[age_group]
            age_text = random.choice(age_examples)
            sex = random.choice(["male", "female"])

            sub_info = self.subspecialties[subspecialty]
            procedure = random.choice(sub_info["procedures"])

            # Generate complex medical history
            factor_descriptions = [self._generate_factor_description(f) for f in factors]
            history_text = ", ".join(factor_descriptions)

            hpi = f"{age_text} {sex} presenting for {procedure}. Medical history significant for " \
                  f"{history_text}. Currently managed by multiple specialists. " \
                  f"No known drug allergies. Recent stable condition per primary care. " \
                  f"Vital signs stable but complex medical status. ASA III."

            expected_flags = self._get_multiple_factor_flags(factors, risk_profile)

            cases.append(TestCase(
                hpi_text=hpi,
                case_id=f"multi_{i+1:02d}",
                category="multiple_factors",
                subspecialty=subspecialty,
                expected_age_band=age_band,
                expected_surgery_type=sub_info["surgery_type"],
                expected_urgency="elective",
                expected_factors=factors,
                expected_negated_factors=[],
                expected_risk_flags=expected_flags,
                complexity_level="complex",
                noise_level="clean"
            ))

        return cases

    def _generate_complex_cases(self, count: int) -> List[TestCase]:
        """Generate complex cases with extensive medical histories"""
        cases = []

        for i in range(count):
            # Choose complex subspecialties
            subspecialty = random.choice(["Cardiac", "Neurosurgery", "Thoracic"])
            age_group = random.choice(["infant", "preschool", "school", "young_adult"])

            age_band, age_examples = self.age_bands[age_group]
            age_text = random.choice(age_examples)
            sex = random.choice(["male", "female"])

            sub_info = self.subspecialties[subspecialty]
            procedure = random.choice(sub_info["procedures"])

            # Generate extensive history
            primary_factors = random.sample(sub_info["common_factors"], 2)
            secondary_factors = random.sample(["GERD", "DEVELOPMENTAL_DELAY", "PREVIOUS_SURGERY"], 1)
            all_factors = primary_factors + secondary_factors

            # Create realistic complex narrative
            hpi = f"{age_text} {sex} with complex medical history including " \
                  f"{', '.join([self._generate_factor_description(f) for f in all_factors])} " \
                  f"presenting for {procedure}. Patient followed by cardiology, pulmonology, " \
                  f"and neurology. Multiple previous hospitalizations. Current medications include " \
                  f"multiple cardiac and respiratory drugs. Family history significant for " \
                  f"genetic syndromes. Social history notable for frequent medical visits. " \
                  f"Physical exam shows multiple syndromic features. ASA IV."

            cases.append(TestCase(
                hpi_text=hpi,
                case_id=f"complex_{i+1:02d}",
                category="complex_medical",
                subspecialty=subspecialty,
                expected_age_band=age_band,
                expected_surgery_type=sub_info["surgery_type"],
                expected_urgency="elective",
                expected_factors=all_factors,
                expected_negated_factors=[],
                expected_risk_flags=["HIGH_COMPLEXITY", "MULTIPLE_COMORBIDITIES", "ASA_4"],
                complexity_level="extreme",
                noise_level="clean"
            ))

        return cases

    def _generate_negation_cases(self, count: int) -> List[TestCase]:
        """Generate cases specifically testing negation detection"""
        cases = []

        negation_phrases = [
            "denies", "no history of", "without", "negative for", "rules out",
            "no evidence of", "free of", "clear of", "absence of"
        ]

        for i in range(count):
            age_group = random.choice(list(self.age_bands.keys()))
            subspecialty = random.choice(list(self.subspecialties.keys()))

            age_band, age_examples = self.age_bands[age_group]
            age_text = random.choice(age_examples)
            sex = random.choice(["male", "female"])

            sub_info = self.subspecialties[subspecialty]
            procedure = random.choice(sub_info["procedures"])

            # Choose factors to negate
            factors_to_negate = random.sample(["asthma", "sleep apnea", "diabetes", "heart disease"], 2)
            negation = random.choice(negation_phrases)

            hpi = f"{age_text} {sex} for {procedure}. Patient {negation} {', '.join(factors_to_negate)}. " \
                  f"No significant past medical history. No medications. No allergies. " \
                  f"Family history non-contributory. Vital signs within normal limits. " \
                  f"Physical examination unremarkable. NPO since midnight. ASA I."

            # Determine expected negated factors
            expected_negated = []
            if "asthma" in factors_to_negate:
                expected_negated.append("ASTHMA")
            if "sleep apnea" in factors_to_negate:
                expected_negated.append("OSA")
            if "diabetes" in factors_to_negate:
                expected_negated.append("DIABETES")
            if "heart disease" in factors_to_negate:
                expected_negated.append("CHD")

            cases.append(TestCase(
                hpi_text=hpi,
                case_id=f"negation_{i+1:02d}",
                category="negation_test",
                subspecialty=subspecialty,
                expected_age_band=age_band,
                expected_surgery_type=sub_info["surgery_type"],
                expected_urgency="elective",
                expected_factors=[],
                expected_negated_factors=expected_negated,
                expected_risk_flags=["EXPLICIT_NEGATION"],
                complexity_level="moderate",
                noise_level="clean"
            ))

        return cases

    def _generate_edge_cases(self, count: int) -> List[TestCase]:
        """Generate edge cases and extreme scenarios"""
        cases = []

        edge_scenarios = [
            ("extreme_premature", "24-week gestation", ["PREMATURITY", "BRONCHOPULMONARY_DYSPLASIA"]),
            ("centenarian", "101-year-old", ["MULTIPLE_COMORBIDITIES"]),
            ("morbid_obesity", "BMI 55", ["OBESITY", "OSA", "DIABETES"]),
            ("organ_transplant", "heart transplant recipient", ["IMMUNOSUPPRESSION", "CHF"]),
            ("genetic_syndrome", "Down syndrome", ["CHD", "OSA", "DEVELOPMENTAL_DELAY"]),
        ]

        for i, (scenario, descriptor, factors) in enumerate(edge_scenarios):
            subspecialty = random.choice(list(self.subspecialties.keys()))
            sex = random.choice(["male", "female"])

            sub_info = self.subspecialties[subspecialty]
            procedure = random.choice(sub_info["procedures"])

            hpi = f"Patient is a {descriptor} {sex} presenting for {procedure}. " \
                  f"Extremely complex medical history with multiple organ system involvement. " \
                  f"Managed by multidisciplinary team including multiple specialists. " \
                  f"Extensive previous surgical history. High-risk anesthetic candidate. " \
                  f"Family counseled regarding significant perioperative risks. ASA V."

            cases.append(TestCase(
                hpi_text=hpi,
                case_id=f"edge_{scenario}",
                category="edge_case",
                subspecialty=subspecialty,
                expected_age_band="varies",
                expected_surgery_type=sub_info["surgery_type"],
                expected_urgency="elective",
                expected_factors=factors,
                expected_negated_factors=[],
                expected_risk_flags=["EXTREME_RISK", "ASA_5", "MULTIDISCIPLINARY"],
                complexity_level="extreme",
                noise_level="clean"
            ))

        return cases[:count]

    def _generate_urgent_cases(self, count: int) -> List[TestCase]:
        """Generate urgent and emergency cases"""
        cases = []

        urgent_scenarios = [
            ("appendicitis", "General", "urgent", ["FULL_STOMACH", "SEPSIS_RISK"]),
            ("trauma", "Orthopedic", "emergency", ["HYPOVOLEMIA", "FULL_STOMACH"]),
            ("airway_obstruction", "ENT", "emergency", ["DIFFICULT_AIRWAY", "HYPOXEMIA"]),
            ("cardiac_arrest", "Cardiac", "emergency", ["CARDIAC_ARREST", "CPR"]),
        ]

        for i, (condition, subspecialty, urgency, factors) in enumerate(urgent_scenarios):
            age_group = random.choice(["school", "young_adult", "middle"])

            age_band, age_examples = self.age_bands[age_group]
            age_text = random.choice(age_examples)
            sex = random.choice(["male", "female"])

            sub_info = self.subspecialties[subspecialty]

            if urgency == "emergency":
                hpi = f"{age_text} {sex} presents emergently with {condition}. " \
                      f"Acute onset symptoms. Hemodynamically unstable. " \
                      f"Full stomach. Unable to complete full evaluation. " \
                      f"Emergent surgery indicated. High-risk case. ASA E."
            else:
                hpi = f"{age_text} {sex} with {condition} requiring urgent surgery. " \
                      f"Symptoms developed over past 12 hours. Currently stable but " \
                      f"requires expedited surgical intervention. ASA III E."

            cases.append(TestCase(
                hpi_text=hpi,
                case_id=f"urgent_{condition}",
                category="urgent_emergency",
                subspecialty=subspecialty,
                expected_age_band=age_band,
                expected_surgery_type=sub_info["surgery_type"],
                expected_urgency=urgency,
                expected_factors=factors,
                expected_negated_factors=[],
                expected_risk_flags=["URGENT_SURGERY", "HIGH_ACUITY"],
                complexity_level="complex",
                noise_level="clean"
            ))

        return cases[:count]

    def _generate_noisy_cases(self, count: int) -> List[TestCase]:
        """Generate cases with typos, awkward phrasing, and real-world noise"""
        cases = []

        # Base case templates
        clean_cases = self._generate_single_factor_cases(count)

        for i, clean_case in enumerate(clean_cases):
            # Apply different types of noise
            noise_type = random.choice(["typos", "awkward", "abbreviations", "garbled"])

            if noise_type == "typos":
                noisy_text = self._add_typos(clean_case.hpi_text)
            elif noise_type == "awkward":
                noisy_text = self._make_awkward_phrasing(clean_case.hpi_text)
            elif noise_type == "abbreviations":
                noisy_text = self._add_medical_abbreviations(clean_case.hpi_text)
            else:  # garbled
                noisy_text = self._garble_text(clean_case.hpi_text)

            cases.append(TestCase(
                hpi_text=noisy_text,
                case_id=f"noisy_{noise_type}_{i+1:02d}",
                category="noise_test",
                subspecialty=clean_case.subspecialty,
                expected_age_band=clean_case.expected_age_band,
                expected_surgery_type=clean_case.expected_surgery_type,
                expected_urgency=clean_case.expected_urgency,
                expected_factors=clean_case.expected_factors,
                expected_negated_factors=clean_case.expected_negated_factors,
                expected_risk_flags=clean_case.expected_risk_flags + ["NOISY_TEXT"],
                complexity_level="moderate",
                noise_level=noise_type
            ))

        return cases

    def _generate_coverage_cases(self, count: int) -> List[TestCase]:
        """Generate cases to ensure complete subspecialty coverage"""
        cases = []

        # Ensure we test all subspecialties
        subspecialties = list(self.subspecialties.keys())

        for subspecialty in subspecialties[:count]:
            age_group = random.choice(list(self.age_bands.keys()))
            age_band, age_examples = self.age_bands[age_group]
            age_text = random.choice(age_examples)
            sex = random.choice(["male", "female"])

            sub_info = self.subspecialties[subspecialty]
            procedure = random.choice(sub_info["procedures"])
            factors = random.sample(sub_info["common_factors"], min(2, len(sub_info["common_factors"])))

            hpi = f"{age_text} {sex} for {procedure}. Medical history includes " \
                  f"{', '.join([self._generate_factor_description(f) for f in factors])}. " \
                  f"Followed by {subspecialty.lower()} team. Stable for surgery. ASA II."

            cases.append(TestCase(
                hpi_text=hpi,
                case_id=f"coverage_{subspecialty.lower()}",
                category="subspecialty_coverage",
                subspecialty=subspecialty,
                expected_age_band=age_band,
                expected_surgery_type=sub_info["surgery_type"],
                expected_urgency="elective",
                expected_factors=factors,
                expected_negated_factors=[],
                expected_risk_flags=["SUBSPECIALTY_SPECIFIC"],
                complexity_level="moderate",
                noise_level="clean"
            ))

        return cases

    # Helper methods for generating realistic content
    def _get_appropriate_subspecialty(self, factor: str) -> str:
        """Get appropriate subspecialty for a risk factor"""
        factor_to_subspecialty = {
            "ASTHMA": "ENT",
            "OSA": "ENT",
            "CHD": "Cardiac",
            "DIABETES": "General",
            "PREMATURITY": "Thoracic",
            "RECENT_URI_2W": "ENT",
            "CP": "Neurosurgery",
            "SEIZURE_DISORDER": "Neurosurgery"
        }
        return factor_to_subspecialty.get(factor, "General")

    def _get_appropriate_age_for_factors(self, factors: List[str]) -> str:
        """Get appropriate age group for given factors"""
        if "PREMATURITY" in factors:
            return random.choice(["neonate", "infant"])
        elif "CHD" in factors:
            return random.choice(["infant", "preschool", "school"])
        elif "DIABETES" in factors:
            return random.choice(["teen", "young_adult", "middle"])
        else:
            return random.choice(list(self.age_bands.keys()))

    def _generate_factor_description(self, factor: str) -> str:
        """Generate realistic description for a risk factor"""
        if factor == "ASTHMA":
            severity = random.choice(["mild", "moderate", "well-controlled"])
            med = random.choice(["albuterol PRN", "daily fluticasone", "budesonide inhaler"])
            return f"{severity} asthma on {med}"
        elif factor == "OSA":
            ahi = random.choice([8, 12, 18, 25])
            return f"obstructive sleep apnea with AHI of {ahi}"
        elif factor == "CHD":
            defect = random.choice(["VSD", "ASD", "TOF"])
            return f"congenital heart disease ({defect})"
        elif factor == "DIABETES":
            type_dm = random.choice(["type 1", "type 2"])
            return f"{type_dm} diabetes on insulin"
        elif factor == "RECENT_URI_2W":
            days = random.choice([7, 10, 12, 14])
            return f"upper respiratory infection {days} days ago"
        else:
            return factor.lower().replace("_", " ")

    def _get_expected_flags(self, factor: str, age_group: str, subspecialty: str) -> List[str]:
        """Get expected risk flags for a factor"""
        flags = []

        if factor in ["ASTHMA", "OSA"]:
            flags.append("AIRWAY_RISK")
        if factor in ["CHD", "ARRHYTHMIA"]:
            flags.append("CARDIAC_RISK")
        if age_group in ["neonate", "infant"]:
            flags.append("PEDIATRIC_HIGH_RISK")
        if subspecialty == "Cardiac":
            flags.append("CARDIAC_SURGERY")

        return flags

    def _get_multiple_factor_flags(self, factors: List[str], risk_profile: str) -> List[str]:
        """Get expected flags for multiple factors"""
        flags = ["MULTIPLE_FACTORS"]

        if risk_profile == "respiratory_high_risk":
            flags.extend(["AIRWAY_HIGH_RISK", "RESPIRATORY_INTERACTION"])
        elif risk_profile == "cardiac_high_risk":
            flags.extend(["CARDIAC_HIGH_RISK", "HEMODYNAMIC_RISK"])
        elif risk_profile == "triple_threat":
            flags.extend(["COMPLEX_INTERACTIONS", "HIGH_RISK_COMBINATION"])

        return flags

    def _add_typos(self, text: str) -> str:
        """Add realistic typos to text"""
        words = text.split()

        # Replace some words with typos
        for i, word in enumerate(words):
            clean_word = word.lower().strip('.,;:')
            if clean_word in self.typo_map and random.random() < 0.1:  # 10% chance
                typo = random.choice(self.typo_map[clean_word])
                words[i] = word.replace(clean_word, typo)

        return ' '.join(words)

    def _make_awkward_phrasing(self, text: str) -> str:
        """Make phrasing awkward but still understandable"""
        # Add some awkward constructions
        text = text.replace("Medical history significant for", "Pt has hx of")
        text = text.replace("No known drug allergies", "NKDA")
        text = text.replace("Physical examination", "PE")
        text = text.replace("within normal limits", "WNL")
        text = text.replace("Vital signs stable", "VS stable")

        return text

    def _add_medical_abbreviations(self, text: str) -> str:
        """Add medical abbreviations"""
        abbrev_map = {
            "patient": "pt",
            "history": "hx",
            "diagnosis": "dx",
            "treatment": "tx",
            "examination": "exam",
            "temperature": "temp",
            "blood pressure": "BP",
            "heart rate": "HR"
        }

        for full, abbrev in abbrev_map.items():
            if random.random() < 0.3:  # 30% chance
                text = text.replace(full, abbrev)

        return text

    def _garble_text(self, text: str) -> str:
        """Slightly garble text while keeping it readable"""
        # Random character swaps, extra spaces, etc.
        if random.random() < 0.3:
            text = text.replace(" the ", " teh ")
        if random.random() < 0.3:
            text = text.replace("surgery", "surgry")
        if random.random() < 0.3:
            text = text.replace("  ", "   ")  # Extra spaces

        return text

    def _generate_factor_description(self, factor_code: str) -> str:
        """Generate realistic clinical descriptions for medical factors"""
        factor_descriptions = {
            "ASTHMA": [
                "mild asthma on albuterol PRN",
                "moderate asthma on daily fluticasone",
                "well-controlled asthma on budesonide inhaler",
                "reactive airway disease",
                "asthma with recent exacerbation"
            ],
            "PREMATURITY": [
                "prematurity",
                "born at 32 weeks gestation",
                "premature birth",
                "born premature at 28 weeks",
                "preterm birth at 34 weeks"
            ],
            "RECENT_URI_2W": [
                "recent upper respiratory infection",
                "upper respiratory infection 10 days ago",
                "recent cold",
                "cold 2 weeks ago",
                "recent runny nose and cough"
            ],
            "CHD": [
                "congenital heart disease (VSD)",
                "congenital heart disease (ASD)",
                "CHD with prior repair",
                "complex congenital heart disease",
                "ventricular septal defect"
            ],
            "DIABETES": [
                "type 1 diabetes on insulin",
                "type 2 diabetes on insulin",
                "diabetes mellitus",
                "well-controlled diabetes",
                "insulin-dependent diabetes"
            ],
            "OSA": [
                "obstructive sleep apnea with AHI of 18",
                "sleep apnea",
                "OSA on CPAP therapy",
                "obstructive sleep apnea",
                "sleep disorder breathing"
            ],
            "OBESITY": [
                "obesity (BMI 35)",
                "morbid obesity",
                "significantly overweight",
                "obesity",
                "BMI over 30"
            ],
            "CHRONIC_KIDNEY_DISEASE": [
                "chronic kidney disease stage 3",
                "CKD on hemodialysis",
                "chronic renal insufficiency",
                "kidney disease",
                "renal failure"
            ],
            "DEVELOPMENTAL_DELAY": [
                "global developmental delay",
                "intellectual disability",
                "developmental delay",
                "cognitive delay",
                "special needs"
            ],
            "INCREASED_ICP": [
                "increased intracranial pressure",
                "elevated ICP",
                "hydrocephalus",
                "intracranial hypertension",
                "increased ICP with VP shunt"
            ],
            "PREVIOUS_SURGERY": [
                "previous surgery",
                "history of multiple surgeries",
                "prior anesthesia complications",
                "extensive surgical history",
                "previous difficult intubation"
            ],
            "AUTISM_SPECTRUM_DISORDER": [
                "autism spectrum disorder",
                "autism",
                "ASD",
                "autistic spectrum disorder",
                "pervasive developmental disorder"
            ],
            "MUSCULAR_DYSTROPHY": [
                "muscular dystrophy",
                "Duchenne muscular dystrophy",
                "DMD",
                "progressive muscle weakness",
                "muscle disease"
            ],
            "CHRONIC_PAIN": [
                "chronic pain syndrome",
                "chronic pain",
                "persistent pain",
                "long-term pain management",
                "chronic pain disorder"
            ],
            "MULTIPLE_COMORBIDITIES": [
                "multiple medical conditions",
                "complex medical history",
                "multiple comorbidities",
                "extensive medical problems",
                "numerous health conditions"
            ],
            "IMMUNOSUPPRESSION": [
                "immunosuppression",
                "immunocompromised state",
                "immune suppression",
                "immunosuppressive therapy",
                "transplant recipient on immunosuppression"
            ],
            "DENTAL_ANXIETY": [
                "dental anxiety",
                "dental phobia",
                "severe anxiety about dental procedures",
                "fear of dental work",
                "dental treatment anxiety"
            ],
            "SEPSIS_RISK": [
                "sepsis risk",
                "risk of sepsis",
                "concern for sepsis",
                "possible sepsis",
                "systemic infection"
            ],
            "HYPOVOLEMIA": [
                "hypovolemia",
                "volume depletion",
                "significant dehydration",
                "blood loss",
                "hemorrhage"
            ],
            "CARDIAC_ARREST": [
                "cardiac arrest",
                "recent cardiac arrest",
                "cardiopulmonary arrest",
                "heart stopped",
                "resuscitated cardiac arrest"
            ],
            "CPR": [
                "recent CPR",
                "cardiopulmonary resuscitation",
                "required resuscitation",
                "chest compressions performed",
                "emergency resuscitation"
            ]
        }

        descriptions = factor_descriptions.get(factor_code, [factor_code.lower().replace('_', ' ')])
        return random.choice(descriptions)

def run_comprehensive_stress_test():
    """Run the comprehensive stress testing suite"""
    # Set random seed for consistent results
    random.seed(42)

    print("=" * 80)
    print("COMPREHENSIVE STRESS TEST FOR MERIDIAN RISK ENGINE")
    print("=" * 80)

    # Generate test cases
    print("\n[PHASE 1] Generating comprehensive test cases...")
    generator = ComprehensiveTestGenerator()
    test_cases = generator.generate_all_test_cases()

    print(f"Generated {len(test_cases)} test cases")

    # Categorize tests
    categories = {}
    for case in test_cases:
        if case.category not in categories:
            categories[case.category] = 0
        categories[case.category] += 1

    print("\nTest case distribution:")
    for category, count in categories.items():
        print(f"  {category}: {count} cases")

    # Run tests
    print(f"\n[PHASE 2] Running stress tests...")

    # Import the NLP pipeline
    try:
        from nlp.pipeline import parse_hpi
        from risk_engine.baseline import BaselineRiskEngine
        from risk_engine.schema import RiskConfig, AgeBand, SurgeryType, Urgency, TimeWindow

        # Initialize components
        config = RiskConfig()
        baseline_engine = BaselineRiskEngine(config)

        print("Successfully initialized NLP and risk components")

    except ImportError as e:
        print(f"Import error: {e}")
        print("Running limited tests without full NLP pipeline...")
        return

    # Test results tracking
    results = {
        "total_cases": len(test_cases),
        "passed": 0,
        "failed": 0,
        "parser_errors": 0,
        "risk_errors": 0,
        "category_results": {},
        "subspecialty_results": {},
        "age_band_results": {},
        "noise_tolerance": {},
        "detailed_failures": []
    }

    # Run each test case
    start_time = time.time()

    for i, case in enumerate(test_cases):
        if (i + 1) % 10 == 0:
            print(f"  Progress: {i+1}/{len(test_cases)} cases tested")

        try:
            # Test NLP parsing
            parsed_hpi = parse_hpi(case.hpi_text)

            # Extract results
            extracted_factors = parsed_hpi.get_feature_codes(include_negated=False)

            # Filter out ASA classifications and procedure-specific codes for validation
            # These are expected but not part of risk factor validation
            filtered_extracted = [f for f in extracted_factors if not f.startswith(('ASA_', 'DENTAL_', 'ENT_'))]

            # Validate parsing results
            parsing_correct = True

            # Check for expected factors
            for expected_factor in case.expected_factors:
                if expected_factor not in filtered_extracted:
                    parsing_correct = False
                    break

            # Check for unexpected factors (major false positives)
            major_false_positives = ["SEPSIS", "FEVER", "HYPOXEMIA", "SEPSIS_RISK"]
            for fp in major_false_positives:
                if fp in filtered_extracted and case.category == "healthy_baseline":
                    parsing_correct = False
                    break

            # Test risk calculation if parsing successful
            if parsing_correct:
                # Test baseline risk retrieval
                try:
                    age_band = AgeBand(case.expected_age_band) if case.expected_age_band != "varies" else AgeBand.SEVEN_TO_12
                    surgery_type = SurgeryType(case.expected_surgery_type)
                    urgency = Urgency(case.expected_urgency)

                    baseline = baseline_engine.get_baseline_risk(
                        outcome="LARYNGOSPASM",
                        window=TimeWindow.INTRAOP,
                        age_band=age_band,
                        surgery=surgery_type,
                        urgency=urgency
                    )

                    # Check for realistic risk levels
                    if baseline and baseline.p0 > 0.5:  # >50% is unrealistic
                        parsing_correct = False
                        results["detailed_failures"].append({
                            "case_id": case.case_id,
                            "issue": "unrealistic_baseline_risk",
                            "value": baseline.p0
                        })

                except Exception as e:
                    results["risk_errors"] += 1
                    parsing_correct = False

            # Update results
            if parsing_correct:
                results["passed"] += 1
            else:
                results["failed"] += 1
                results["detailed_failures"].append({
                    "case_id": case.case_id,
                    "category": case.category,
                    "issue": "parsing_validation_failed",
                    "expected_factors": case.expected_factors,
                    "extracted_factors": filtered_extracted
                })

            # Track by category
            if case.category not in results["category_results"]:
                results["category_results"][case.category] = {"passed": 0, "failed": 0}

            if parsing_correct:
                results["category_results"][case.category]["passed"] += 1
            else:
                results["category_results"][case.category]["failed"] += 1

            # Track by subspecialty
            if case.subspecialty not in results["subspecialty_results"]:
                results["subspecialty_results"][case.subspecialty] = {"passed": 0, "failed": 0}

            if parsing_correct:
                results["subspecialty_results"][case.subspecialty]["passed"] += 1
            else:
                results["subspecialty_results"][case.subspecialty]["failed"] += 1

            # Track noise tolerance
            if case.noise_level not in results["noise_tolerance"]:
                results["noise_tolerance"][case.noise_level] = {"passed": 0, "failed": 0}

            if parsing_correct:
                results["noise_tolerance"][case.noise_level]["passed"] += 1
            else:
                results["noise_tolerance"][case.noise_level]["failed"] += 1

        except Exception as e:
            results["parser_errors"] += 1
            results["failed"] += 1
            results["detailed_failures"].append({
                "case_id": case.case_id,
                "issue": "parser_exception",
                "error": str(e)
            })

    end_time = time.time()

    # Print comprehensive results
    print(f"\n[PHASE 3] COMPREHENSIVE STRESS TEST RESULTS")
    print("=" * 80)

    print(f"\nOVERALL PERFORMANCE:")
    print(f"  Total cases tested: {results['total_cases']}")
    print(f"  Passed: {results['passed']} ({results['passed']/results['total_cases']*100:.1f}%)")
    print(f"  Failed: {results['failed']} ({results['failed']/results['total_cases']*100:.1f}%)")
    print(f"  Parser errors: {results['parser_errors']}")
    print(f"  Risk engine errors: {results['risk_errors']}")
    print(f"  Total time: {end_time - start_time:.1f} seconds")

    print(f"\nPERFORMANCE BY CATEGORY:")
    for category, result in results["category_results"].items():
        total = result["passed"] + result["failed"]
        pass_rate = result["passed"] / total * 100 if total > 0 else 0
        print(f"  {category}: {result['passed']}/{total} ({pass_rate:.1f}%)")

    print(f"\nPERFORMANCE BY SUBSPECIALTY:")
    for subspecialty, result in results["subspecialty_results"].items():
        total = result["passed"] + result["failed"]
        pass_rate = result["passed"] / total * 100 if total > 0 else 0
        print(f"  {subspecialty}: {result['passed']}/{total} ({pass_rate:.1f}%)")

    print(f"\nNOISE TOLERANCE:")
    for noise_level, result in results["noise_tolerance"].items():
        total = result["passed"] + result["failed"]
        pass_rate = result["passed"] / total * 100 if total > 0 else 0
        print(f"  {noise_level}: {result['passed']}/{total} ({pass_rate:.1f}%)")

    # Show detailed failures (first 5)
    if results["detailed_failures"]:
        print(f"\nFIRST 5 DETAILED FAILURES:")
        for failure in results["detailed_failures"][:5]:
            print(f"  Case {failure['case_id']}: {failure['issue']}")
            if 'expected_factors' in failure:
                print(f"    Expected: {failure['expected_factors']}")
                print(f"    Extracted: {failure['extracted_factors']}")

    # Final assessment
    overall_pass_rate = results['passed'] / results['total_cases'] * 100

    print(f"\n" + "=" * 80)
    if overall_pass_rate >= 80:
        print(f"[PASS] STRESS TEST PASSED! Overall accuracy: {overall_pass_rate:.1f}%")
        print("The system demonstrates robust performance across diverse scenarios.")
    elif overall_pass_rate >= 60:
        print(f"[PARTIAL] STRESS TEST PARTIAL PASS. Overall accuracy: {overall_pass_rate:.1f}%")
        print("System shows good performance but needs improvement in some areas.")
    else:
        print(f"[FAIL] STRESS TEST FAILED. Overall accuracy: {overall_pass_rate:.1f}%")
        print("System needs significant improvement before production deployment.")

    # Export detailed results
    with open("stress_test_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nDetailed results exported to: stress_test_results.json")

    return results

if __name__ == "__main__":
    run_comprehensive_stress_test()