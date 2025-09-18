#!/usr/bin/env python3
"""
Medication Recommendation Engine for Meridian
Generates evidence-based medication recommendations based on parsed HPI and risk assessment
"""

import json
import yaml
import math
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class MedicationTiming(Enum):
    PRE_INDUCTION = "pre_induction"
    INDUCTION = "induction"
    INTRAOP = "intraop"
    PRE_EMERGENCE = "pre_emergence"
    EMERGENCE = "emergence"
    STANDBY = "standby"
    EMERGENCY_STANDBY = "emergency_standby"
    PREMEDICATION = "premedication"

class MedicationBucket(Enum):
    DRAW_NOW = "draw_now"
    STANDARD = "standard"
    CONSIDER = "consider"
    CONTRAINDICATED = "contraindicated"

@dataclass
class DoseCalculation:
    mg: Optional[float] = None
    mcg: Optional[float] = None
    volume_ml: float = 0.0
    concentration: str = ""
    final_concentration: Optional[str] = None
    requires_dilution: bool = False
    dilution_instructions: Optional[str] = None

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'mg': self.mg,
            'mcg': self.mcg,
            'volume_ml': self.volume_ml,
            'concentration': self.concentration,
            'final_concentration': self.final_concentration,
            'requires_dilution': self.requires_dilution,
            'dilution_instructions': self.dilution_instructions
        }

@dataclass
class MedicationRecommendation:
    agent: str
    medication_class: str
    dose: str
    calculation: DoseCalculation
    route: str
    timing: str
    indication: str
    confidence: str
    citations: List[str]
    notes: Optional[str] = None
    alternatives: Optional[List[str]] = None
    contraindication_reason: Optional[str] = None

@dataclass
class PatientParameters:
    age_years: Optional[float] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    bmi: Optional[float] = None
    sex: Optional[str] = None
    urgency: str = "elective"
    surgery_domain: Optional[str] = None
    allergies: List[str] = None
    renal_function: Optional[str] = None
    hepatic_function: Optional[str] = None
    npo_status: Optional[str] = None

    def __post_init__(self):
        if self.allergies is None:
            self.allergies = []

    @property
    def is_pediatric(self) -> bool:
        return self.age_years is not None and self.age_years < 18

    @property
    def weight_category(self) -> str:
        if not self.weight_kg:
            return "unknown"
        if self.weight_kg < 5:
            return "neonate"
        elif self.weight_kg < 12:
            return "infant"
        elif self.weight_kg < 20:
            return "toddler"
        elif self.weight_kg < 50:
            return "child"
        else:
            return "adult"

class MeridianMedsEngine:
    """Core medication recommendation engine"""

    def __init__(self, config_dir: Path = None):
        if config_dir is None:
            config_dir = Path(__file__).parent.parent / "config"

        self.config_dir = config_dir
        self._load_configurations()

    def _load_configurations(self):
        """Load all configuration files"""
        try:
            # Load medication rules
            with open(self.config_dir / "med_rules.yaml", 'r') as f:
                self.med_rules = yaml.safe_load(f)

            # Load formulary
            with open(self.config_dir / "formulary.json", 'r') as f:
                self.formulary = json.load(f)

            # Load dosing rules
            with open(self.config_dir / "dosing.json", 'r') as f:
                self.dosing_rules = json.load(f)

            # Load guideline mapping
            with open(self.config_dir / "guideline_map.json", 'r') as f:
                self.guideline_map = json.load(f)

            logger.info("Medication engine configurations loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load medication configurations: {e}")
            raise

    def generate_recommendations(
        self,
        parsed_hpi: Any,
        risk_summary: Dict[str, Any],
        patient_params: PatientParameters
    ) -> Dict[str, Any]:
        """
        Generate comprehensive medication recommendations

        Args:
            parsed_hpi: ParsedHPI object from NLP pipeline
            risk_summary: Risk assessment results from risk engine
            patient_params: Patient demographic and clinical parameters

        Returns:
            Complete medication recommendation response
        """
        try:
            # Extract clinical features
            features = self._extract_features(parsed_hpi)

            # Analyze risk patterns
            elevated_risks = self._analyze_risks(risk_summary)

            # Generate medication candidates
            candidates = self._generate_candidates(features, elevated_risks, patient_params)

            # Apply contraindication screening
            screened_candidates = self._screen_contraindications(candidates, features, patient_params)

            # Categorize into buckets
            bucketed_meds = self._categorize_medications(screened_candidates, patient_params)

            # Calculate doses and preparations
            final_recommendations = self._calculate_doses_and_prep(bucketed_meds, patient_params)

            # Generate summary
            summary = self._generate_summary(final_recommendations, elevated_risks)

            return {
                "patient": self._format_patient_summary(patient_params),
                "context": {
                    "features": features,
                    "elevated_risks": elevated_risks
                },
                "meds": final_recommendations,
                "summary": summary
            }

        except Exception as e:
            logger.error(f"Error generating medication recommendations: {e}")
            return self._generate_error_response(str(e))

    def _extract_features(self, parsed_hpi: Any) -> List[str]:
        """Extract relevant clinical features from parsed HPI"""
        if hasattr(parsed_hpi, 'get_feature_codes'):
            return parsed_hpi.get_feature_codes(include_negated=False)
        return []

    def _analyze_risks(self, risk_summary: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze elevated risks and their significance"""
        elevated_risks = []

        if not risk_summary or 'risks' not in risk_summary:
            return elevated_risks

        for outcome, risk_data in risk_summary.get('risks', {}).items():
            absolute_risk = risk_data.get('absolute_risk', 0)
            delta_risk = risk_data.get('delta_vs_baseline', 0)
            confidence = risk_data.get('confidence', 'C')

            # Check if risk meets medication threshold
            outcome_rules = self.med_rules.get('risk_medication_mapping', {}).get(outcome, {})
            threshold = outcome_rules.get('threshold', 0.1)
            delta_threshold = outcome_rules.get('delta_threshold', 0.05)

            if absolute_risk >= threshold or delta_risk >= delta_threshold:
                elevated_risks.append({
                    'outcome': outcome,
                    'absolute_risk': absolute_risk,
                    'delta_risk': delta_risk,
                    'confidence': confidence,
                    'priority': self._calculate_risk_priority(absolute_risk, delta_risk, confidence)
                })

        # Sort by priority (highest first)
        elevated_risks.sort(key=lambda x: x['priority'], reverse=True)
        return elevated_risks

    def _calculate_risk_priority(self, absolute_risk: float, delta_risk: float, confidence: str) -> float:
        """Calculate priority score for risk-based medication selection"""
        confidence_weights = {'A': 1.0, 'B': 0.8, 'C': 0.6, 'D': 0.4}
        confidence_weight = confidence_weights.get(confidence, 0.5)

        # Combine absolute risk, delta risk, and confidence
        priority = (absolute_risk * 100 + delta_risk * 200) * confidence_weight
        return priority

    def _generate_candidates(
        self,
        features: List[str],
        elevated_risks: List[Dict[str, Any]],
        patient_params: PatientParameters
    ) -> List[Dict[str, Any]]:
        """Generate medication candidates based on features and risks"""
        candidates = []

        # Risk-based candidates
        for risk in elevated_risks:
            outcome = risk['outcome']
            med_classes = self.med_rules.get('risk_medication_mapping', {}).get(outcome, {}).get('medication_classes', [])

            for med_class in med_classes:
                candidate = self._create_candidate_from_risk(med_class, risk, patient_params)
                if candidate:
                    candidates.append(candidate)

        # Feature-based candidates
        for feature in features:
            feature_meds = self.med_rules.get('feature_medication_mapping', {}).get(feature, {}).get('medications', [])
            for med_class in feature_meds:
                candidate = self._create_candidate_from_feature(med_class, feature, patient_params)
                if candidate:
                    candidates.append(candidate)

        # Surgery-specific candidates
        if patient_params.surgery_domain:
            surgery_meds = self.med_rules.get('surgery_specific', {}).get(patient_params.surgery_domain, {}).get('baseline_medications', [])
            for med_info in surgery_meds:
                candidate = self._create_candidate_from_surgery(med_info, patient_params)
                if candidate:
                    candidates.append(candidate)

        # Add baseline anesthetic medications that should always be considered
        # (so they can be flagged as contraindicated if appropriate)
        baseline_meds = [
            {'class': 'Depolarizing_NMBD', 'agent': 'Succinylcholine', 'priority': 5, 'indication': 'Neuromuscular blockade'},
            {'class': 'Propofol_Bolus', 'agent': 'Propofol', 'priority': 5, 'indication': 'Emergence agitation'},
            {'class': 'Emergency_Medications', 'agent': 'Epinephrine', 'priority': 2, 'indication': 'Emergency preparedness'}
        ]

        for baseline_med in baseline_meds:
            candidate = {
                'agent': baseline_med['agent'],
                'class': baseline_med['class'],
                'priority': baseline_med['priority'],
                'confidence': 'B',
                'timing': 'standby',
                'indication': baseline_med['indication'],
                'evidence': [],
                'source': 'baseline',
                'conditions': [],
                'contraindications': []
            }
            candidates.append(candidate)

        return candidates

    def _create_candidate_from_risk(self, med_class_info: Dict, risk: Dict, patient_params: PatientParameters) -> Optional[Dict]:
        """Create medication candidate from risk-based rule"""
        med_class = med_class_info.get('class')
        if not med_class:
            return None

        # Check age restrictions
        age_groups = med_class_info.get('age_groups', [])
        if age_groups:
            if patient_params.is_pediatric and 'PEDIATRIC' not in age_groups:
                return None
            if not patient_params.is_pediatric and 'ADULT' not in age_groups:
                return None

        # Get preferred agent for this class
        agent_info = self.formulary.get('medication_classes', {}).get(med_class, {})
        preferred_agent = agent_info.get('preferred_agent')

        if not preferred_agent:
            return None

        return {
            'agent': preferred_agent,
            'class': med_class,
            'priority': med_class_info.get('priority', 5),
            'confidence': med_class_info.get('confidence', 'C'),
            'timing': med_class_info.get('timing', 'induction'),
            'indication': f"Elevated {risk['outcome'].lower()} risk ({risk['absolute_risk']:.1%})",
            'evidence': med_class_info.get('evidence', []),
            'source': 'risk_based',
            'conditions': med_class_info.get('conditions', []),
            'contraindications': med_class_info.get('contraindications', [])
        }

    def _create_candidate_from_feature(self, med_class: str, feature: str, patient_params: PatientParameters) -> Optional[Dict]:
        """Create medication candidate from feature-based rule"""
        # Get preferred agent for this class
        agent_info = self.formulary.get('medication_classes', {}).get(med_class, {})
        preferred_agent = agent_info.get('preferred_agent')

        if not preferred_agent:
            return None

        feature_info = self.med_rules.get('feature_medication_mapping', {}).get(feature, {})

        return {
            'agent': preferred_agent,
            'class': med_class,
            'priority': 3,  # Medium priority for feature-based
            'confidence': 'B',
            'timing': 'pre_induction',
            'indication': f"Clinical feature: {feature}",
            'evidence': [],
            'source': 'feature_based',
            'severity_modifier': feature_info.get('severity_modifier', 1.0)
        }

    def _create_candidate_from_surgery(self, med_info: Dict, patient_params: PatientParameters) -> Optional[Dict]:
        """Create medication candidate from surgery-specific rule"""
        med_class = med_info.get('class')
        if not med_class:
            return None

        # Get preferred agent for this class
        agent_info = self.formulary.get('medication_classes', {}).get(med_class, {})
        preferred_agent = agent_info.get('preferred_agent')

        if not preferred_agent:
            return None

        return {
            'agent': preferred_agent,
            'class': med_class,
            'priority': 2,  # Lower priority for surgery-specific
            'confidence': med_info.get('confidence', 'B'),
            'timing': 'standard',
            'indication': med_info.get('reason', f"Standard for {patient_params.surgery_domain} surgery"),
            'evidence': [],
            'source': 'surgery_specific'
        }

    def _screen_contraindications(
        self,
        candidates: List[Dict[str, Any]],
        features: List[str],
        patient_params: PatientParameters
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Screen candidates for contraindications"""
        safe_candidates = []
        contraindicated = []

        for candidate in candidates:
            agent = candidate['agent']
            med_class = candidate['class']

            # Check absolute contraindications
            is_contraindicated, reason = self._check_contraindications(agent, med_class, features, patient_params)

            if is_contraindicated:
                contraindicated.append({
                    'agent': agent,
                    'reason': reason,
                    'alternatives': self._get_alternatives(med_class, features, patient_params)
                })
            else:
                safe_candidates.append(candidate)

        return safe_candidates, contraindicated

    def _check_contraindications(
        self,
        agent: str,
        med_class: str,
        features: List[str],
        patient_params: PatientParameters
    ) -> Tuple[bool, Optional[str]]:
        """Check if medication is contraindicated"""
        contraindications = self.med_rules.get('contraindications', {})

        # Check absolute contraindications
        absolute_contras = contraindications.get('absolute', {})
        for feature in features:
            if feature in absolute_contras:
                contraindicated_agents = absolute_contras[feature]
                if agent in contraindicated_agents or med_class in contraindicated_agents:
                    return True, f"Absolute contraindication due to {feature}"

        # Check allergy contraindications
        for allergy in patient_params.allergies:
            if self._agent_contains_allergen(agent, allergy):
                return True, f"Allergy to {allergy}"

        # Check relative contraindications
        relative_contras = contraindications.get('relative', {})
        for feature in features:
            if feature in relative_contras:
                contra_info = relative_contras[feature]
                if isinstance(contra_info, list):
                    if agent in contra_info or med_class in contra_info:
                        return True, f"Relative contraindication due to {feature}"
                elif isinstance(contra_info, dict):
                    if contra_info.get('class') == med_class:
                        return True, contra_info.get('reason', f"Contraindicated due to {feature}")

        return False, None

    def _agent_contains_allergen(self, agent: str, allergy: str) -> bool:
        """Check if agent contains known allergen"""
        allergen_mapping = {
            "EGG_SOY_ALLERGY": ["Propofol"],
            "SULFA_ALLERGY": ["Furosemide"],
            "PENICILLIN_ALLERGY": ["Penicillin", "Ampicillin"]
        }

        allergen_agents = allergen_mapping.get(allergy, [])
        return agent in allergen_agents

    def _get_alternatives(self, med_class: str, features: List[str], patient_params: PatientParameters) -> List[str]:
        """Get alternative agents for contraindicated medication class"""
        class_info = self.formulary.get('medication_classes', {}).get(med_class, {})
        agents = class_info.get('agents', {})

        alternatives = []
        for agent_name in agents.keys():
            is_contra, _ = self._check_contraindications(agent_name, med_class, features, patient_params)
            if not is_contra:
                alternatives.append(agent_name)

        return alternatives

    def _categorize_medications(
        self,
        candidates_and_contras: Tuple[List[Dict[str, Any]], List[Dict[str, Any]]],
        patient_params: PatientParameters
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Categorize medications into buckets"""
        safe_candidates, contraindicated = candidates_and_contras

        # Remove duplicates and prioritize
        unique_candidates = self._deduplicate_candidates(safe_candidates)

        buckets = {
            MedicationBucket.DRAW_NOW.value: [],
            MedicationBucket.STANDARD.value: [],
            MedicationBucket.CONSIDER.value: [],
            MedicationBucket.CONTRAINDICATED.value: contraindicated
        }

        for candidate in unique_candidates:
            bucket = self._determine_bucket(candidate, patient_params)
            buckets[bucket.value].append(candidate)

        # Sort each bucket by priority
        for bucket in [MedicationBucket.DRAW_NOW, MedicationBucket.STANDARD, MedicationBucket.CONSIDER]:
            buckets[bucket.value].sort(key=lambda x: x.get('priority', 5))

        return buckets

    def _deduplicate_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate candidates, keeping highest priority"""
        agent_map = {}

        for candidate in candidates:
            agent = candidate['agent']
            if agent not in agent_map or candidate.get('priority', 5) < agent_map[agent].get('priority', 5):
                agent_map[agent] = candidate

        return list(agent_map.values())

    def _determine_bucket(self, candidate: Dict[str, Any], patient_params: PatientParameters) -> MedicationBucket:
        """Determine which bucket a medication belongs in"""
        priority = candidate.get('priority', 5)
        timing = candidate.get('timing', '')
        confidence = candidate.get('confidence', 'C')

        # Emergency/critical medications
        if timing in ['emergency_standby', 'standby'] or priority == 1:
            return MedicationBucket.DRAW_NOW

        # Standard medications for surgery type or high-priority/high-confidence
        if (candidate.get('source') == 'surgery_specific' or
            (priority <= 2 and confidence in ['A', 'B'])):
            return MedicationBucket.STANDARD

        # Everything else goes to consider
        return MedicationBucket.CONSIDER

    def _calculate_doses_and_prep(
        self,
        bucketed_meds: Dict[str, List[Dict[str, Any]]],
        patient_params: PatientParameters
    ) -> Dict[str, List[MedicationRecommendation]]:
        """Calculate doses and preparation instructions"""
        final_recommendations = {}

        for bucket, candidates in bucketed_meds.items():
            if bucket == MedicationBucket.CONTRAINDICATED.value:
                final_recommendations[bucket] = candidates  # Already formatted
                continue

            recommendations = []
            for candidate in candidates:
                try:
                    recommendation = self._create_full_recommendation(candidate, patient_params)
                    if recommendation:
                        recommendations.append(recommendation)
                except Exception as e:
                    logger.error(f"Error calculating dose for {candidate.get('agent', 'unknown')}: {e}")
                    continue

            # Convert recommendations to dictionaries with proper serialization
            rec_dicts = []
            for rec in recommendations:
                rec_dict = rec.__dict__.copy()
                rec_dict['calculation'] = rec.calculation.to_dict()
                rec_dicts.append(rec_dict)
            final_recommendations[bucket] = rec_dicts

        return final_recommendations

    def _create_full_recommendation(
        self,
        candidate: Dict[str, Any],
        patient_params: PatientParameters
    ) -> Optional[MedicationRecommendation]:
        """Create complete medication recommendation with dose calculations"""
        agent = candidate['agent']
        med_class = candidate['class']

        # Get dosing information
        dose_info = self.dosing_rules.get('dosing_rules', {}).get(agent, {})
        if not dose_info:
            logger.warning(f"No dosing information found for {agent}")
            return None

        # Calculate dose
        dose_calculation = self._calculate_dose(agent, dose_info, patient_params)
        if not dose_calculation:
            return None

        # Get preparation instructions
        prep_instructions = self._get_preparation_instructions(agent, dose_calculation, patient_params)

        # Get evidence and citations
        citations = self._get_citations(med_class, candidate.get('evidence', []))

        # Format dose string
        dose_string = self._format_dose_string(dose_calculation, dose_info, patient_params)

        return MedicationRecommendation(
            agent=agent,
            medication_class=med_class,
            dose=dose_string,
            calculation=dose_calculation,
            route=self._get_preferred_route(agent, dose_info, patient_params),
            timing=self._format_timing(candidate.get('timing', 'induction')),
            indication=candidate.get('indication', ''),
            confidence=candidate.get('confidence', 'C'),
            citations=citations,
            notes=prep_instructions
        )

    def _calculate_dose(
        self,
        agent: str,
        dose_info: Dict[str, Any],
        patient_params: PatientParameters
    ) -> Optional[DoseCalculation]:
        """Calculate medication dose and volume"""
        try:
            # Determine age category
            age_category = "pediatric" if patient_params.is_pediatric else "adult"
            age_dosing = dose_info.get(age_category, {})

            if not age_dosing:
                logger.warning(f"No {age_category} dosing found for {agent}")
                return None

            # Get preferred route dosing
            route_dosing = None
            for route in ['IV', 'IV_bolus', 'nebulizer']:
                if route in age_dosing:
                    route_dosing = age_dosing[route]
                    break

            if not route_dosing:
                logger.warning(f"No suitable route found for {agent}")
                return None

            # Calculate dose
            if 'dose_mg_kg' in route_dosing and patient_params.weight_kg:
                dose_mg = route_dosing['dose_mg_kg'] * patient_params.weight_kg
                # Apply min/max bounds
                dose_mg = max(dose_mg, route_dosing.get('min_dose', 0))
                if 'max_dose' in route_dosing:
                    dose_mg = min(dose_mg, route_dosing['max_dose'])
            elif 'dose_mcg_kg' in route_dosing and patient_params.weight_kg:
                dose_mcg = route_dosing['dose_mcg_kg'] * patient_params.weight_kg
                dose_mcg = max(dose_mcg, route_dosing.get('min_dose', 0))
                if 'max_dose' in route_dosing:
                    dose_mcg = min(dose_mcg, route_dosing['max_dose'])
                dose_mg = dose_mcg / 1000
            elif 'dose_mg' in route_dosing:
                dose_mg = route_dosing['dose_mg']
            elif 'dose_mcg' in route_dosing:
                dose_mg = route_dosing['dose_mcg'] / 1000
            else:
                logger.warning(f"No valid dose calculation method for {agent}")
                return None

            # Get concentration and calculate volume
            volume_ml, concentration = self._calculate_volume(agent, dose_mg)

            # Apply renal/hepatic adjustments
            dose_mg, volume_ml = self._apply_organ_adjustments(
                agent, dose_mg, volume_ml, patient_params
            )

            # Round to practical values
            dose_mg = self._round_dose(dose_mg)
            volume_ml = self._round_volume(volume_ml)

            return DoseCalculation(
                mg=dose_mg,
                mcg=dose_mg * 1000 if dose_mg < 1 else None,
                volume_ml=volume_ml,
                concentration=concentration
            )

        except Exception as e:
            logger.error(f"Error calculating dose for {agent}: {e}")
            return None

    def _calculate_volume(self, agent: str, dose_mg: float) -> Tuple[float, str]:
        """Calculate volume needed based on available concentrations"""
        agent_info = None

        # Find agent in formulary
        for med_class_info in self.formulary.get('medication_classes', {}).values():
            if agent in med_class_info.get('agents', {}):
                agent_info = med_class_info['agents'][agent]
                break

        if not agent_info:
            logger.warning(f"Agent {agent} not found in formulary")
            return 1.0, "unknown concentration"

        # Use first IV concentration
        concentrations = agent_info.get('concentrations', [])
        iv_conc = None
        for conc in concentrations:
            if conc.get('route') in ['IV', 'IV_bolus']:
                iv_conc = conc
                break

        if not iv_conc:
            logger.warning(f"No IV concentration found for {agent}")
            return 1.0, "unknown concentration"

        # Parse concentration (e.g., "10 mg/mL")
        strength = iv_conc.get('strength', '')
        try:
            if 'mg/mL' in strength:
                mg_per_ml = float(strength.split(' mg/mL')[0])
                volume_ml = dose_mg / mg_per_ml
                return volume_ml, strength
            elif 'mcg/mL' in strength:
                mcg_per_ml = float(strength.split(' mcg/mL')[0])
                volume_ml = (dose_mg * 1000) / mcg_per_ml
                return volume_ml, strength
            else:
                logger.warning(f"Cannot parse concentration: {strength}")
                return 1.0, strength
        except (ValueError, IndexError):
            logger.warning(f"Error parsing concentration: {strength}")
            return 1.0, strength

    def _apply_organ_adjustments(
        self,
        agent: str,
        dose_mg: float,
        volume_ml: float,
        patient_params: PatientParameters
    ) -> Tuple[float, float]:
        """Apply renal and hepatic dose adjustments"""
        adjustment_factor = 1.0

        # Get adjustment rules for this agent
        dose_info = self.dosing_rules.get('dosing_rules', {}).get(agent, {})

        # Renal adjustment
        if patient_params.renal_function in ['moderate', 'severe']:
            renal_adj = dose_info.get('renal_adjustment')
            if renal_adj == 'reduce_dose':
                adjustment_factor *= 0.5
            elif renal_adj == 'reduce_dose_severe' and patient_params.renal_function == 'severe':
                adjustment_factor *= 0.5

        # Hepatic adjustment
        if patient_params.hepatic_function in ['moderate', 'severe']:
            hepatic_adj = dose_info.get('hepatic_adjustment')
            if hepatic_adj == 'reduce_dose':
                adjustment_factor *= 0.75
            elif hepatic_adj == 'reduce_dose_severe' and patient_params.hepatic_function == 'severe':
                adjustment_factor *= 0.5

        # Age adjustment for elderly
        if patient_params.age_years and patient_params.age_years >= 65:
            age_rules = self.med_rules.get('age_specific', {}).get('GERIATRIC', {})
            age_factor = age_rules.get('dose_reduction_factor', 1.0)
            adjustment_factor *= age_factor

        adjusted_dose = dose_mg * adjustment_factor
        adjusted_volume = volume_ml * adjustment_factor

        return adjusted_dose, adjusted_volume

    def _round_dose(self, dose_mg: float) -> float:
        """Round dose to practical increment"""
        rounding_rules = self.dosing_rules.get('dose_calculation_rules', {}).get('safety_bounds', {}).get('rounding_rules', {})

        # Use smaller increments for small doses
        if dose_mg < 0.1:
            dose_increment = 0.01  # 0.01 mg increments for very small doses
        elif dose_mg < 1.0:
            dose_increment = 0.05  # 0.05 mg increments for small doses
        else:
            dose_increment = rounding_rules.get('dose_mg', 0.1)  # Default to 0.1 mg increments

        return round(dose_mg / dose_increment) * dose_increment

    def _round_volume(self, volume_ml: float) -> float:
        """Round volume to practical increment"""
        rounding_rules = self.dosing_rules.get('dose_calculation_rules', {}).get('safety_bounds', {}).get('rounding_rules', {})
        volume_increment = rounding_rules.get('volume_ml', 0.1)

        return round(volume_ml / volume_increment) * volume_increment

    def _get_preferred_route(self, agent: str, dose_info: Dict, patient_params: PatientParameters) -> str:
        """Get preferred route for administration"""
        age_category = "pediatric" if patient_params.is_pediatric else "adult"
        age_dosing = dose_info.get(age_category, {})

        # Prefer IV routes
        route_priority = ['IV', 'IV_bolus', 'nebulizer', 'PO', 'patch']
        for route in route_priority:
            if route in age_dosing:
                return route

        return "IV"  # Default

    def _format_timing(self, timing: str) -> str:
        """Format timing for display"""
        timing_map = {
            'pre_induction': 'pre-induction',
            'induction': 'at induction',
            'intraop': 'intraoperatively',
            'pre_emergence': '30 min before emergence',
            'emergence': 'at emergence',
            'standby': 'prepare on standby',
            'emergency_standby': 'prepare for emergency use',
            'premedication': 'premedication'
        }
        return timing_map.get(timing, timing)

    def _format_dose_string(
        self,
        calc: DoseCalculation,
        dose_info: Dict,
        patient_params: PatientParameters
    ) -> str:
        """Format dose string for display"""
        if calc.mcg and calc.mcg < 1000:
            dose_str = f"{calc.mcg:.0f} mcg"
        else:
            dose_str = f"{calc.mg:.1f} mg"

        if patient_params.weight_kg:
            mg_per_kg = calc.mg / patient_params.weight_kg
            if mg_per_kg >= 1:
                dose_str += f" ({mg_per_kg:.1f} mg/kg)"
            else:
                mcg_per_kg = mg_per_kg * 1000
                dose_str += f" ({mcg_per_kg:.0f} mcg/kg)"

        return dose_str

    def _get_preparation_instructions(
        self,
        agent: str,
        calc: DoseCalculation,
        patient_params: PatientParameters
    ) -> Optional[str]:
        """Get preparation and administration notes"""
        notes = []

        # Volume and concentration notes
        if calc.volume_ml:
            notes.append(f"Draw {calc.volume_ml:.1f} mL from {calc.concentration}")

        # Dilution requirements
        if calc.requires_dilution:
            notes.append("Requires dilution before administration")

        # Special preparation notes
        special_notes = {
            'Dexmedetomidine': 'Dilute to 4 mcg/mL in NS or D5W',
            'Phenylephrine': 'Typical dilution to 100 mcg/mL for boluses',
            'Epinephrine': 'Use 1:10,000 concentration for IV administration'
        }

        if agent in special_notes:
            notes.append(special_notes[agent])

        return '; '.join(notes) if notes else None

    def _get_citations(self, med_class: str, evidence: List[str]) -> List[str]:
        """Get citations for medication recommendation"""
        citations = evidence.copy()

        # Add guideline citations
        for outcome, guideline_info in self.guideline_map.get('guideline_mapping', {}).items():
            guidelines = guideline_info.get('primary_guidelines', [])
            for guideline in guidelines:
                recommendations = guideline.get('recommendations', {})
                if med_class in recommendations:
                    citation = f"{guideline['organization']} {guideline['title']} {guideline['year']}"
                    if 'pmid' in guideline:
                        citation += f" (PMID:{guideline['pmid']})"
                    citations.append(citation)

        return list(set(citations))  # Remove duplicates

    def _generate_summary(
        self,
        recommendations: Dict[str, List],
        elevated_risks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate summary of medication plan"""
        total_syringes = 0
        for bucket in [MedicationBucket.DRAW_NOW.value, MedicationBucket.STANDARD.value]:
            total_syringes += len(recommendations.get(bucket, []))

        # Generate rationale
        risk_descriptions = []
        for risk in elevated_risks[:3]:  # Top 3 risks
            risk_desc = f"{risk['outcome'].replace('_', ' ').title()} risk {risk['absolute_risk']:.1%}"
            if risk['delta_risk'] > 0:
                risk_desc += f" (Δ+{risk['delta_risk']:.1%})"
            risk_descriptions.append(risk_desc)

        rationale = "; ".join(risk_descriptions) if risk_descriptions else "Standard anesthetic management"

        return {
            'rationale': rationale,
            'syringe_count': total_syringes,
            'estimated_prep_time_min': min(max(total_syringes * 0.5, 2), 10)  # 0.5 min per syringe, 2-10 min range
        }

    def _format_patient_summary(self, patient_params: PatientParameters) -> Dict[str, Any]:
        """Format patient summary for response"""
        return {
            'age': patient_params.age_years,
            'weight_kg': patient_params.weight_kg,
            'urgency': patient_params.urgency,
            'domain': patient_params.surgery_domain
        }

    def _generate_error_response(self, error_message: str) -> Dict[str, Any]:
        """Generate error response"""
        return {
            'error': True,
            'message': error_message,
            'meds': {
                'draw_now': [],
                'standard': [],
                'consider': [],
                'contraindicated': []
            },
            'summary': {
                'rationale': 'Error in medication recommendation generation',
                'syringe_count': 0,
                'estimated_prep_time_min': 0
            }
        }


def create_meds_engine(config_dir: Path = None) -> MeridianMedsEngine:
    """Factory function to create medication engine"""
    return MeridianMedsEngine(config_dir)