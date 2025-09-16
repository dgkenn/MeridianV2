"""
Evidence-based medication recommendation engine.
Generates draw-up lists with contraindications and evidence grades.
"""

import json
import logging
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, asdict
from datetime import datetime

from ..core.database import get_database
from ..ontology.core_ontology import AnesthesiaOntology
from ..core.hpi_parser import ExtractedFactor
from ..core.risk_engine import RiskAssessment

logger = logging.getLogger(__name__)

@dataclass
class MedicationRecommendation:
    medication: str
    generic_name: str
    indication: str
    dose: str
    preparation: str
    evidence_grade: str
    citations: List[str]
    category: str
    urgency: str = "standard"  # standard, high, emergency
    conditions: List[str] = None
    alternatives: List[str] = None
    contraindication_reason: str = None

@dataclass
class DrugInteraction:
    drug1: str
    drug2: str
    interaction: str
    severity: str  # none, mild, moderate, severe
    management: str = ""

@dataclass
class MedicationPlan:
    session_id: str
    recommendations: Dict[str, List[MedicationRecommendation]]
    drug_interactions: List[DrugInteraction]
    total_medications: Dict[str, int]
    generated_at: datetime

class MedicationEngine:
    """
    Comprehensive medication recommendation engine with evidence-based
    drug selection and contraindication checking.
    """

    def __init__(self):
        self.db = get_database()
        self.ontology = AnesthesiaOntology()

        # Load medication database
        self.medications = self._load_medication_database()

        # Define medication categories and priorities
        self.category_priorities = {
            "induction": 10,
            "volatile": 9,
            "opioid": 8,
            "muscle_relaxant": 7,
            "local_anesthetic": 6,
            "antiemetic": 5,
            "vasoactive": 4,
            "bronchodilator": 8,  # High priority for certain conditions
            "steroid": 6,
            "emergency": 10
        }

        # Evidence-based drug selections
        self.evidence_selections = self._build_evidence_selections()

        # Contraindication rules
        self.contraindications = self._build_contraindication_rules()

        # Drug interactions
        self.interactions = self._build_interaction_database()

    def generate_recommendations(self, factors: List[ExtractedFactor],
                               risks: List[RiskAssessment],
                               demographics: Dict[str, Any],
                               preferences: Dict[str, Any] = None) -> MedicationPlan:
        """
        Generate comprehensive medication recommendations based on
        patient factors, risks, and evidence.
        """

        session_id = f"med_{datetime.now().isoformat()}"
        preferences = preferences or {}

        # Initialize recommendation categories
        recommendations = {
            "standard": [],
            "draw_now": [],
            "consider": [],
            "ensure_available": [],
            "contraindicated": []
        }

        # Extract key patient characteristics
        age_years = demographics.get('age_years', 0)
        weight_kg = demographics.get('weight_kg')
        procedure = demographics.get('procedure')
        is_pediatric = age_years < 18

        # Get factor and risk sets for easy lookup
        factor_tokens = {f.token for f in factors}
        risk_tokens = {r.outcome for r in risks}
        high_risks = {r.outcome for r in risks if r.adjusted_risk > 0.05}

        # Generate standard medications
        standard_meds = self._generate_standard_medications(
            factor_tokens, demographics, is_pediatric
        )
        recommendations["standard"].extend(standard_meds)

        # Generate risk-specific medications
        draw_now_meds = self._generate_risk_specific_medications(
            factor_tokens, risk_tokens, high_risks, demographics
        )
        recommendations["draw_now"].extend(draw_now_meds)

        # Generate conditional medications
        consider_meds = self._generate_conditional_medications(
            factor_tokens, demographics
        )
        recommendations["consider"].extend(consider_meds)

        # Generate emergency medications
        emergency_meds = self._generate_emergency_medications(
            factor_tokens, demographics
        )
        recommendations["ensure_available"].extend(emergency_meds)

        # Check contraindications
        contraindicated_meds = self._check_contraindications(
            factor_tokens, demographics, recommendations
        )
        recommendations["contraindicated"].extend(contraindicated_meds)

        # Check drug interactions
        all_recommended = []
        for category in ["standard", "draw_now", "consider"]:
            all_recommended.extend([r.medication for r in recommendations[category]])

        interactions = self._check_interactions(all_recommended)

        # Calculate totals
        totals = {cat: len(meds) for cat, meds in recommendations.items()}

        # Create medication plan
        plan = MedicationPlan(
            session_id=session_id,
            recommendations=recommendations,
            drug_interactions=interactions,
            total_medications=totals,
            generated_at=datetime.now()
        )

        # Store for audit
        self._store_medication_plan(plan)

        return plan

    def _load_medication_database(self) -> Dict[str, Dict[str, Any]]:
        """Load comprehensive medication database."""

        # This would normally load from the database, but for demo we'll use built-in data
        medications = {
            # Induction Agents
            "PROPOFOL": {
                "generic_name": "Propofol",
                "brand_names": ["Diprivan"],
                "drug_class": "induction_agent",
                "indications": ["smooth_induction", "airway_reactivity"],
                "contraindications": ["egg_allergy", "soy_allergy"],
                "adult_dose": "1-2.5 mg/kg IV",
                "peds_dose": "2-3 mg/kg IV",
                "preparation": "10 mg/mL vial",
                "evidence_grade": "A",
                "category": "induction"
            },

            "ETOMIDATE": {
                "generic_name": "Etomidate",
                "brand_names": ["Amidate"],
                "drug_class": "induction_agent",
                "indications": ["hemodynamic_stability"],
                "contraindications": ["adrenal_insufficiency"],
                "adult_dose": "0.2-0.3 mg/kg IV",
                "peds_dose": "0.2-0.3 mg/kg IV",
                "preparation": "2 mg/mL vial",
                "evidence_grade": "B",
                "category": "induction"
            },

            "KETAMINE": {
                "generic_name": "Ketamine",
                "brand_names": ["Ketalar"],
                "drug_class": "induction_agent",
                "indications": ["bronchospasm", "hemodynamic_instability", "pain"],
                "contraindications": ["increased_icp", "schizophrenia"],
                "adult_dose": "1-2 mg/kg IV",
                "peds_dose": "1-2 mg/kg IV",
                "preparation": "10 mg/mL vial",
                "evidence_grade": "B",
                "category": "induction"
            },

            # Volatile Anesthetics
            "SEVOFLURANE": {
                "generic_name": "Sevoflurane",
                "brand_names": ["Ultane"],
                "drug_class": "volatile_anesthetic",
                "indications": ["smooth_emergence", "airway_tolerance"],
                "contraindications": ["malignant_hyperthermia"],
                "adult_dose": "2-3% inspired",
                "peds_dose": "2-3% inspired",
                "evidence_grade": "A",
                "category": "volatile"
            },

            "DESFLURANE": {
                "generic_name": "Desflurane",
                "brand_names": ["Suprane"],
                "drug_class": "volatile_anesthetic",
                "indications": ["fast_emergence"],
                "contraindications": ["asthma", "reactive_airway", "malignant_hyperthermia"],
                "adult_dose": "6-8% inspired",
                "peds_dose": "avoid <2 years",
                "evidence_grade": "B",
                "category": "volatile"
            },

            # Opioids
            "FENTANYL": {
                "generic_name": "Fentanyl",
                "brand_names": ["Sublimaze"],
                "drug_class": "opioid",
                "indications": ["analgesia", "hemodynamic_stability"],
                "contraindications": [],
                "adult_dose": "1-5 mcg/kg IV",
                "peds_dose": "1-3 mcg/kg IV",
                "preparation": "50 mcg/mL vial",
                "evidence_grade": "A",
                "category": "opioid"
            },

            # Muscle Relaxants
            "ROCURONIUM": {
                "generic_name": "Rocuronium",
                "brand_names": ["Zemuron"],
                "drug_class": "muscle_relaxant",
                "indications": ["intubation", "paralysis"],
                "contraindications": [],
                "adult_dose": "0.6-1.2 mg/kg IV",
                "peds_dose": "0.6-1.2 mg/kg IV",
                "preparation": "10 mg/mL vial",
                "evidence_grade": "A",
                "category": "muscle_relaxant"
            },

            "SUCCINYLCHOLINE": {
                "generic_name": "Succinylcholine",
                "brand_names": ["Anectine"],
                "drug_class": "muscle_relaxant",
                "indications": ["rapid_sequence"],
                "contraindications": ["recent_uri", "malignant_hyperthermia", "hyperkalemia"],
                "adult_dose": "1-1.5 mg/kg IV",
                "peds_dose": "1-2 mg/kg IV",
                "preparation": "20 mg/mL vial",
                "evidence_grade": "B",
                "category": "muscle_relaxant"
            },

            # Bronchodilators
            "ALBUTEROL": {
                "generic_name": "Albuterol",
                "brand_names": ["Ventolin"],
                "drug_class": "bronchodilator",
                "indications": ["bronchospasm", "asthma"],
                "contraindications": [],
                "adult_dose": "2.5-5 mg nebulized",
                "peds_dose": "2.5 mg nebulized",
                "preparation": "2.5 mg/3 mL vial",
                "evidence_grade": "A",
                "category": "bronchodilator"
            },

            # Steroids
            "DEXAMETHASONE": {
                "generic_name": "Dexamethasone",
                "brand_names": ["Decadron"],
                "drug_class": "steroid",
                "indications": ["airway_edema", "anti_inflammatory", "ponv"],
                "contraindications": ["systemic_infection"],
                "adult_dose": "4-8 mg IV",
                "peds_dose": "0.15 mg/kg IV (max 8 mg)",
                "preparation": "4 mg/mL vial",
                "evidence_grade": "B",
                "category": "steroid"
            },

            # Antiemetics
            "ONDANSETRON": {
                "generic_name": "Ondansetron",
                "brand_names": ["Zofran"],
                "drug_class": "antiemetic",
                "indications": ["ponv_prevention"],
                "contraindications": ["qt_prolongation"],
                "adult_dose": "4-8 mg IV",
                "peds_dose": "0.15 mg/kg IV (max 4 mg)",
                "preparation": "2 mg/mL vial",
                "evidence_grade": "A",
                "category": "antiemetic"
            },

            # Emergency Medications
            "INTRALIPID_20": {
                "generic_name": "Intralipid 20%",
                "brand_names": ["Intralipid"],
                "drug_class": "lipid_emulsion",
                "indications": ["local_anesthetic_toxicity"],
                "contraindications": [],
                "adult_dose": "1.5 mL/kg bolus, then 0.25 mL/kg/min",
                "peds_dose": "1.5 mL/kg bolus, then 0.25 mL/kg/min",
                "preparation": "20% 500 mL bag",
                "evidence_grade": "B",
                "category": "emergency"
            },

            "DANTROLENE": {
                "generic_name": "Dantrolene",
                "brand_names": ["Dantrium"],
                "drug_class": "antidote",
                "indications": ["malignant_hyperthermia"],
                "contraindications": [],
                "adult_dose": "2.5 mg/kg IV, repeat PRN",
                "peds_dose": "2.5 mg/kg IV, repeat PRN",
                "preparation": "20 mg vial",
                "evidence_grade": "A",
                "category": "emergency"
            }
        }

        return medications

    def _build_evidence_selections(self) -> Dict[str, Dict[str, Any]]:
        """Build evidence-based drug selection rules."""

        return {
            # Induction based on airway concerns
            "airway_reactive": {
                "preferred": ["PROPOFOL", "KETAMINE"],
                "avoid": ["ETOMIDATE"],
                "evidence_grade": "B"
            },

            # Asthma-specific selections
            "asthma": {
                "preferred_volatile": ["SEVOFLURANE", "ISOFLURANE"],
                "avoid_volatile": ["DESFLURANE"],
                "preferred_induction": ["PROPOFOL", "KETAMINE"],
                "evidence_grade": "A"
            },

            # Recent URI considerations
            "recent_uri": {
                "avoid_muscle_relaxant": ["SUCCINYLCHOLINE"],
                "preferred_induction": ["PROPOFOL"],
                "additional_meds": ["DEXAMETHASONE", "ALBUTEROL"],
                "evidence_grade": "B"
            },

            # OSA considerations
            "osa": {
                "preferred_induction": ["PROPOFOL"],
                "avoid_high_dose_opioids": True,
                "monitoring": ["continuous_pulse_oximetry"],
                "evidence_grade": "B"
            },

            # ENT procedures
            "ent_surgery": {
                "standard_meds": ["DEXAMETHASONE", "ONDANSETRON"],
                "airway_concerns": ["deep_extubation"],
                "evidence_grade": "A"
            }
        }

    def _build_contraindication_rules(self) -> Dict[str, List[str]]:
        """Build contraindication checking rules."""

        return {
            "ASTHMA": ["DESFLURANE"],
            "RECENT_URI_2W": ["SUCCINYLCHOLINE"],
            "OSA": [],  # Relative contraindications only
            "MALIGNANT_HYPERTHERMIA_SUSCEPTIBLE": ["SUCCINYLCHOLINE", "SEVOFLURANE", "DESFLURANE"],
            "EGG_ALLERGY": ["PROPOFOL"],
            "SOY_ALLERGY": ["PROPOFOL"],
            "INCREASED_ICP": ["KETAMINE"],
            "HEART_FAILURE": [],  # Context-dependent
            "RENAL_FAILURE": ["MORPHINE"],  # Context-dependent
        }

    def _build_interaction_database(self) -> Dict[Tuple[str, str], Dict[str, str]]:
        """Build drug interaction database."""

        interactions = {}

        # Example interactions (would be much more comprehensive)
        interactions[("PROPOFOL", "FENTANYL")] = {
            "interaction": "Synergistic CNS depression",
            "severity": "moderate",
            "management": "Reduce doses appropriately"
        }

        interactions[("ONDANSETRON", "DROPERIDOL")] = {
            "interaction": "Additive QT prolongation",
            "severity": "moderate",
            "management": "Monitor ECG"
        }

        return interactions

    def _generate_standard_medications(self, factor_tokens: Set[str],
                                     demographics: Dict[str, Any],
                                     is_pediatric: bool) -> List[MedicationRecommendation]:
        """Generate standard medications for typical case."""

        age_years = demographics.get('age_years', 0)
        weight_kg = demographics.get('weight_kg')
        procedure = demographics.get('procedure')

        recommendations = []

        # Standard induction agent
        if "ASTHMA" in factor_tokens or "RECENT_URI_2W" in factor_tokens:
            induction_agent = "PROPOFOL"
        else:
            induction_agent = "PROPOFOL"  # Default choice

        med_data = self.medications[induction_agent]
        dose = med_data["peds_dose"] if is_pediatric else med_data["adult_dose"]

        recommendations.append(MedicationRecommendation(
            medication=induction_agent,
            generic_name=med_data["generic_name"],
            indication="Smooth induction agent",
            dose=dose,
            preparation=med_data.get("preparation", ""),
            evidence_grade=med_data["evidence_grade"],
            citations=["PMID:example"],
            category="induction"
        ))

        # Standard volatile anesthetic
        if "ASTHMA" in factor_tokens:
            volatile = "SEVOFLURANE"
        else:
            volatile = "SEVOFLURANE"  # Default choice

        med_data = self.medications[volatile]
        recommendations.append(MedicationRecommendation(
            medication=volatile,
            generic_name=med_data["generic_name"],
            indication="Maintenance anesthesia",
            dose=med_data["peds_dose"] if is_pediatric else med_data["adult_dose"],
            preparation="",
            evidence_grade=med_data["evidence_grade"],
            citations=["PMID:example"],
            category="volatile"
        ))

        # Standard opioid
        med_data = self.medications["FENTANYL"]
        recommendations.append(MedicationRecommendation(
            medication="FENTANYL",
            generic_name=med_data["generic_name"],
            indication="Perioperative analgesia",
            dose=med_data["peds_dose"] if is_pediatric else med_data["adult_dose"],
            preparation=med_data.get("preparation", ""),
            evidence_grade=med_data["evidence_grade"],
            citations=["PMID:example"],
            category="opioid"
        ))

        # Standard muscle relaxant (if needed)
        if "RECENT_URI_2W" not in factor_tokens:
            med_data = self.medications["ROCURONIUM"]
            recommendations.append(MedicationRecommendation(
                medication="ROCURONIUM",
                generic_name=med_data["generic_name"],
                indication="Muscle relaxation for intubation",
                dose=med_data["peds_dose"] if is_pediatric else med_data["adult_dose"],
                preparation=med_data.get("preparation", ""),
                evidence_grade=med_data["evidence_grade"],
                citations=["PMID:example"],
                category="muscle_relaxant"
            ))

        return recommendations

    def _generate_risk_specific_medications(self, factor_tokens: Set[str],
                                          risk_tokens: Set[str],
                                          high_risks: Set[str],
                                          demographics: Dict[str, Any]) -> List[MedicationRecommendation]:
        """Generate medications for specific risk factors."""

        recommendations = []
        age_years = demographics.get('age_years', 0)
        is_pediatric = age_years < 18

        # Asthma - bronchodilator
        if "ASTHMA" in factor_tokens or "BRONCHOSPASM" in high_risks:
            med_data = self.medications["ALBUTEROL"]
            recommendations.append(MedicationRecommendation(
                medication="ALBUTEROL",
                generic_name=med_data["generic_name"],
                indication="Bronchospasm treatment - asthma history",
                dose=med_data["peds_dose"] if is_pediatric else med_data["adult_dose"],
                preparation=med_data.get("preparation", ""),
                evidence_grade=med_data["evidence_grade"],
                citations=["PMID:example"],
                category="bronchodilator",
                urgency="high"
            ))

        # Recent URI or ENT surgery - steroid
        if ("RECENT_URI_2W" in factor_tokens or
            demographics.get('procedure') in ['TONSILLECTOMY', 'ADENOIDECTOMY'] or
            "LARYNGOSPASM" in high_risks):

            med_data = self.medications["DEXAMETHASONE"]
            recommendations.append(MedicationRecommendation(
                medication="DEXAMETHASONE",
                generic_name=med_data["generic_name"],
                indication="Reduce airway inflammation and edema",
                dose=med_data["peds_dose"] if is_pediatric else med_data["adult_dose"],
                preparation=med_data.get("preparation", ""),
                evidence_grade=med_data["evidence_grade"],
                citations=["PMID:example"],
                category="steroid",
                urgency="high"
            ))

        # PONV risk - antiemetic
        if (demographics.get('procedure') in ['TONSILLECTOMY', 'ADENOIDECTOMY'] or
            "PONV" in risk_tokens):

            med_data = self.medications["ONDANSETRON"]
            recommendations.append(MedicationRecommendation(
                medication="ONDANSETRON",
                generic_name=med_data["generic_name"],
                indication="PONV prevention - ENT surgery",
                dose=med_data["peds_dose"] if is_pediatric else med_data["adult_dose"],
                preparation=med_data.get("preparation", ""),
                evidence_grade=med_data["evidence_grade"],
                citations=["PMID:example"],
                category="antiemetic"
            ))

        return recommendations

    def _generate_conditional_medications(self, factor_tokens: Set[str],
                                        demographics: Dict[str, Any]) -> List[MedicationRecommendation]:
        """Generate conditional/situational medications."""

        recommendations = []
        # Placeholder for conditional medications
        return recommendations

    def _generate_emergency_medications(self, factor_tokens: Set[str],
                                      demographics: Dict[str, Any]) -> List[MedicationRecommendation]:
        """Generate emergency medications to ensure availability."""

        recommendations = []

        # Always ensure LAST treatment available
        med_data = self.medications["INTRALIPID_20"]
        recommendations.append(MedicationRecommendation(
            medication="INTRALIPID_20",
            generic_name=med_data["generic_name"],
            indication="Local anesthetic systemic toxicity treatment",
            dose=med_data["adult_dose"],
            preparation=med_data.get("preparation", ""),
            evidence_grade=med_data["evidence_grade"],
            citations=["PMID:example"],
            category="emergency"
        ))

        return recommendations

    def _check_contraindications(self, factor_tokens: Set[str],
                               demographics: Dict[str, Any],
                               recommendations: Dict[str, List[MedicationRecommendation]]) -> List[MedicationRecommendation]:
        """Check for contraindicated medications."""

        contraindicated = []

        # Check each factor for contraindications
        for factor in factor_tokens:
            if factor in self.contraindications:
                for med_token in self.contraindications[factor]:
                    if med_token in self.medications:
                        med_data = self.medications[med_token]

                        # Create contraindication reason
                        if factor == "ASTHMA" and med_token == "DESFLURANE":
                            reason = "Avoid in asthma - increases airway reactivity"
                            alternatives = ["SEVOFLURANE", "ISOFLURANE"]
                        elif factor == "RECENT_URI_2W" and med_token == "SUCCINYLCHOLINE":
                            reason = "Avoid with recent URI - increased laryngospasm risk"
                            alternatives = ["ROCURONIUM"]
                        else:
                            reason = f"Contraindicated with {factor}"
                            alternatives = []

                        contraindicated.append(MedicationRecommendation(
                            medication=med_token,
                            generic_name=med_data["generic_name"],
                            indication="",
                            dose="",
                            preparation="",
                            evidence_grade=med_data["evidence_grade"],
                            citations=["PMID:example"],
                            category=med_data["category"],
                            contraindication_reason=reason,
                            alternatives=alternatives
                        ))

        return contraindicated

    def _check_interactions(self, medication_list: List[str]) -> List[DrugInteraction]:
        """Check for drug interactions."""

        interactions = []

        for i, med1 in enumerate(medication_list):
            for med2 in medication_list[i+1:]:
                # Check both directions
                for key in [(med1, med2), (med2, med1)]:
                    if key in self.interactions:
                        interaction_data = self.interactions[key]
                        interactions.append(DrugInteraction(
                            drug1=key[0],
                            drug2=key[1],
                            interaction=interaction_data["interaction"],
                            severity=interaction_data["severity"],
                            management=interaction_data.get("management", "")
                        ))
                        break

        return interactions

    def _store_medication_plan(self, plan: MedicationPlan):
        """Store medication plan for audit trail."""
        try:
            # Convert to JSON-serializable format
            plan_data = {
                "recommendations": {
                    cat: [asdict(rec) for rec in recs]
                    for cat, recs in plan.recommendations.items()
                },
                "drug_interactions": [asdict(interaction) for interaction in plan.drug_interactions],
                "total_medications": plan.total_medications
            }

            # Update case session
            self.db.conn.execute("""
                UPDATE case_sessions
                SET medication_recommendations = ?
                WHERE session_id = ?
            """, [json.dumps(plan_data), plan.session_id])

            # Log the action
            self.db.log_action("medication_plans", plan.session_id, "GENERATE", {
                "total_medications": sum(plan.total_medications.values()),
                "contraindications": plan.total_medications.get("contraindicated", 0),
                "interactions": len(plan.drug_interactions)
            })

        except Exception as e:
            logger.error(f"Error storing medication plan {plan.session_id}: {e}")

    def get_medication_database(self, category: str = None, indication: str = None) -> List[Dict[str, Any]]:
        """Query medication database with filters."""

        results = []

        for token, med_data in self.medications.items():
            # Apply filters
            if category and med_data.get("category") != category:
                continue

            if indication and indication not in med_data.get("indications", []):
                continue

            # Add token to result
            result = med_data.copy()
            result["token"] = token
            results.append(result)

        # Sort by evidence grade and category priority
        def sort_key(med):
            grade_score = {"A": 4, "B": 3, "C": 2, "D": 1}.get(med.get("evidence_grade", "D"), 1)
            category_score = self.category_priorities.get(med.get("category", ""), 0)
            return (grade_score, category_score)

        results.sort(key=sort_key, reverse=True)

        return results