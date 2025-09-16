"""
Comprehensive anesthesia ontology with outcomes, risk factors, and medications.
Based on master prompt specifications for exhaustive coverage.
"""

from typing import Dict, List, Any
from dataclasses import dataclass
import json

@dataclass
class OntologyTerm:
    token: str
    type: str  # risk_factor, outcome, med, drug_class, context
    plain_label: str
    synonyms: List[str]
    category: str
    severity_weight: float = 1.0
    notes: str = ""
    icd10_codes: List[str] = None
    mesh_codes: List[str] = None
    parent_token: str = None
    children_tokens: List[str] = None

class AnesthesiaOntology:
    """
    Comprehensive anesthesia ontology with all outcomes, risk factors,
    medications, and contexts as specified in master prompt.
    """

    def __init__(self):
        self.terms = {}
        self._build_ontology()

    def _build_ontology(self):
        """Build complete ontology from specifications."""

        # ============ OUTCOMES (Exhaustive) ============

        # Airway Complications
        airway_outcomes = [
            OntologyTerm("BRONCHOSPASM", "outcome", "Bronchospasm",
                        ["bronchospasm", "wheeze", "bronchial spasm"], "airway", 2.0),
            OntologyTerm("LARYNGOSPASM", "outcome", "Laryngospasm",
                        ["laryngospasm", "laryngeal spasm", "vocal cord spasm"], "airway", 3.0),
            OntologyTerm("DIFFICULT_MASK_VENTILATION", "outcome", "Difficult mask ventilation",
                        ["difficult mask ventilation", "DMV", "mask ventilation difficulty"], "airway", 2.5),
            OntologyTerm("DIFFICULT_LARYNGOSCOPY", "outcome", "Difficult laryngoscopy",
                        ["difficult laryngoscopy", "DL", "Cormack-Lehane 3-4"], "airway", 2.0),
            OntologyTerm("DIFFICULT_INTUBATION", "outcome", "Difficult intubation",
                        ["difficult intubation", "failed intubation", "multiple attempts"], "airway", 3.0),
            OntologyTerm("FAILED_INTUBATION", "outcome", "Failed intubation",
                        ["failed intubation", "cannot intubate"], "airway", 4.0),
            OntologyTerm("ASPIRATION", "outcome", "Pulmonary aspiration",
                        ["aspiration", "gastric aspiration", "Mendelson syndrome"], "airway", 4.0),
            OntologyTerm("AIRWAY_TRAUMA", "outcome", "Airway trauma",
                        ["airway trauma", "dental injury", "lip injury", "pharyngeal trauma"], "airway", 2.0),
            OntologyTerm("DENTAL_INJURY", "outcome", "Dental injury",
                        ["dental injury", "tooth damage", "dental trauma"], "airway", 1.5),
            OntologyTerm("POSTOP_STRIDOR", "outcome", "Postoperative stridor",
                        ["stridor", "postoperative stridor", "airway edema"], "airway", 2.5),
            OntologyTerm("HYPOXEMIA", "outcome", "Hypoxemia/desaturation",
                        ["hypoxemia", "desaturation", "hypoxia", "low oxygen"], "airway", 3.0),
            OntologyTerm("UNPLANNED_INTUBATION", "outcome", "Unplanned intubation",
                        ["unplanned intubation", "emergency intubation"], "airway", 3.0),
            OntologyTerm("REINTUBATION", "outcome", "Reintubation",
                        ["reintubation", "re-intubation"], "airway", 3.0),
        ]

        # Respiratory Complications
        respiratory_outcomes = [
            OntologyTerm("POSTOP_RESP_FAILURE", "outcome", "Postoperative respiratory failure",
                        ["respiratory failure", "ventilatory failure"], "respiratory", 4.0),
            OntologyTerm("PNEUMONIA", "outcome", "Pneumonia",
                        ["pneumonia", "postoperative pneumonia"], "respiratory", 3.0),
            OntologyTerm("ARDS", "outcome", "Acute respiratory distress syndrome",
                        ["ARDS", "acute lung injury", "ALI"], "respiratory", 4.5),
            OntologyTerm("ATELECTASIS", "outcome", "Atelectasis",
                        ["atelectasis", "lung collapse"], "respiratory", 2.0),
            OntologyTerm("BRONCHOPNEUMONIA", "outcome", "Bronchopneumonia",
                        ["bronchopneumonia"], "respiratory", 3.0),
            OntologyTerm("PULMONARY_EDEMA_CARDIOGENIC", "outcome", "Cardiogenic pulmonary edema",
                        ["cardiogenic pulmonary edema", "cardiac pulmonary edema"], "respiratory", 4.0),
            OntologyTerm("PULMONARY_EDEMA_NONCARDIOGENIC", "outcome", "Non-cardiogenic pulmonary edema",
                        ["non-cardiogenic pulmonary edema", "NCPE"], "respiratory", 4.0),
            OntologyTerm("PROLONGED_VENTILATION", "outcome", "Prolonged mechanical ventilation",
                        ["prolonged ventilation", "ventilator dependence"], "respiratory", 3.5),
            OntologyTerm("UNEXPECTED_ICU_RESPIRATORY", "outcome", "Unexpected ICU admission for respiratory issues",
                        ["unexpected ICU", "unplanned ICU"], "respiratory", 3.5),
            OntologyTerm("PULMONARY_EMBOLISM", "outcome", "Pulmonary embolism",
                        ["PE", "pulmonary embolism"], "respiratory", 4.5),
        ]

        # Hemodynamic/Cardiovascular Complications
        cardiac_outcomes = [
            OntologyTerm("INTRAOP_HYPOTENSION", "outcome", "Intraoperative hypotension",
                        ["hypotension", "low blood pressure"], "cardiovascular", 2.0),
            OntologyTerm("INTRAOP_HYPERTENSION", "outcome", "Intraoperative hypertension",
                        ["hypertension", "high blood pressure"], "cardiovascular", 2.0),
            OntologyTerm("BRADYCARDIA", "outcome", "Bradycardia",
                        ["bradycardia", "slow heart rate"], "cardiovascular", 2.0),
            OntologyTerm("TACHYARRHYTHMIA", "outcome", "Tachyarrhythmia",
                        ["tachycardia", "tachyarrhythmia", "fast heart rate"], "cardiovascular", 2.5),
            OntologyTerm("ATRIAL_FIBRILLATION", "outcome", "Atrial fibrillation/flutter",
                        ["atrial fibrillation", "AF", "atrial flutter"], "cardiovascular", 3.0),
            OntologyTerm("VENTRICULAR_ARRHYTHMIA", "outcome", "Ventricular tachycardia/fibrillation",
                        ["VT", "VF", "ventricular tachycardia", "ventricular fibrillation"], "cardiovascular", 4.5),
            OntologyTerm("LOW_OUTPUT_SYNDROME", "outcome", "Low cardiac output syndrome",
                        ["low output", "cardiac output syndrome"], "cardiovascular", 4.0),
            OntologyTerm("CARDIOGENIC_SHOCK", "outcome", "Cardiogenic shock",
                        ["cardiogenic shock"], "cardiovascular", 5.0),
            OntologyTerm("VASOPLEGIA", "outcome", "Vasoplegia",
                        ["vasoplegia", "vasoplegic syndrome"], "cardiovascular", 3.5),
            OntologyTerm("CARDIAC_ARREST", "outcome", "Cardiac arrest",
                        ["cardiac arrest", "cardiopulmonary arrest"], "cardiovascular", 5.0),
        ]

        # Neurologic Complications
        neuro_outcomes = [
            OntologyTerm("STROKE", "outcome", "Stroke/TIA",
                        ["stroke", "CVA", "TIA", "transient ischemic attack"], "neurologic", 4.5),
            OntologyTerm("SEIZURE", "outcome", "Seizure",
                        ["seizure", "convulsion"], "neurologic", 3.0),
            OntologyTerm("AWARENESS_UNDER_ANESTHESIA", "outcome", "Awareness under anesthesia",
                        ["awareness", "intraoperative awareness"], "neurologic", 4.0),
            OntologyTerm("EMERGENCE_AGITATION", "outcome", "Emergence agitation",
                        ["emergence agitation", "emergence delirium"], "neurologic", 2.0),
            OntologyTerm("POSTOP_DELIRIUM", "outcome", "Postoperative delirium",
                        ["POD", "postoperative delirium", "delirium"], "neurologic", 3.0),
            OntologyTerm("POSTOP_COGNITIVE_DYSFUNCTION", "outcome", "Postoperative cognitive dysfunction",
                        ["POCD", "cognitive dysfunction"], "neurologic", 2.5),
            OntologyTerm("PERIPHERAL_NEUROPATHY", "outcome", "Peripheral neuropathy/nerve injury",
                        ["nerve injury", "neuropathy", "peripheral nerve injury"], "neurologic", 2.0),
            OntologyTerm("SPINAL_HEMATOMA", "outcome", "Spinal/epidural hematoma",
                        ["spinal hematoma", "epidural hematoma"], "neurologic", 4.5),
            OntologyTerm("LOCAL_ANESTHETIC_TOXICITY", "outcome", "Local anesthetic systemic toxicity",
                        ["LAST", "local anesthetic toxicity"], "neurologic", 4.0),
        ]

        # Pain/Analgesia Complications
        pain_outcomes = [
            OntologyTerm("SEVERE_ACUTE_PAIN", "outcome", "Severe acute postoperative pain",
                        ["severe pain", "acute pain"], "pain", 2.5),
            OntologyTerm("DIFFICULT_PAIN_CONTROL", "outcome", "Difficult pain control",
                        ["refractory pain", "difficult pain"], "pain", 2.0),
            OntologyTerm("CHRONIC_POSTSURGICAL_PAIN", "outcome", "Chronic postsurgical pain",
                        ["chronic pain", "persistent pain"], "pain", 3.0),
            OntologyTerm("OPIOID_RESPIRATORY_DEPRESSION", "outcome", "Opioid-induced respiratory depression",
                        ["respiratory depression", "opioid depression"], "pain", 4.0),
            OntologyTerm("OPIOID_ILEUS", "outcome", "Opioid-induced ileus",
                        ["ileus", "opioid ileus"], "pain", 2.0),
            OntologyTerm("OPIOID_PRURITUS", "outcome", "Opioid-induced pruritus",
                        ["itching", "pruritus"], "pain", 1.5),
            OntologyTerm("OPIOID_URINARY_RETENTION", "outcome", "Opioid-induced urinary retention",
                        ["urinary retention"], "pain", 2.0),
            OntologyTerm("NEW_PERSISTENT_OPIOID_USE", "outcome", "New persistent opioid use",
                        ["opioid dependence", "persistent opioid use"], "pain", 3.5),
        ]

        # Hemostasis/Bleeding Complications
        bleeding_outcomes = [
            OntologyTerm("SURGICAL_BLEEDING", "outcome", "Surgical site bleeding",
                        ["bleeding", "hemorrhage"], "hemostasis", 3.0),
            OntologyTerm("RETURN_TO_OR_BLEEDING", "outcome", "Return to OR for bleeding",
                        ["return to OR", "re-operation for bleeding"], "hemostasis", 3.5),
            OntologyTerm("BLOOD_TRANSFUSION", "outcome", "Blood transfusion requirement",
                        ["transfusion", "blood transfusion"], "hemostasis", 3.0),
            OntologyTerm("COAGULOPATHY", "outcome", "Coagulopathy",
                        ["coagulopathy", "bleeding disorder"], "hemostasis", 3.5),
            OntologyTerm("DISSEMINATED_INTRAVASCULAR_COAGULATION", "outcome", "Disseminated intravascular coagulation",
                        ["DIC"], "hemostasis", 4.5),
            OntologyTerm("VENOUS_THROMBOEMBOLISM", "outcome", "Venous thromboembolism",
                        ["VTE", "DVT", "deep vein thrombosis"], "hemostasis", 3.5),
        ]

        # Organ Dysfunction
        organ_outcomes = [
            OntologyTerm("ACUTE_KIDNEY_INJURY", "outcome", "Acute kidney injury",
                        ["AKI", "acute renal failure"], "renal", 3.5),
            OntologyTerm("DIALYSIS_INITIATION", "outcome", "Dialysis initiation",
                        ["dialysis", "renal replacement"], "renal", 4.0),
            OntologyTerm("ACUTE_LIVER_INJURY", "outcome", "Acute liver injury",
                        ["liver injury", "hepatic dysfunction"], "hepatic", 3.5),
            OntologyTerm("POSTOP_ILEUS", "outcome", "Postoperative ileus",
                        ["ileus"], "gastrointestinal", 2.0),
            OntologyTerm("MESENTERIC_ISCHEMIA", "outcome", "Mesenteric ischemia",
                        ["mesenteric ischemia"], "gastrointestinal", 4.0),
            OntologyTerm("GI_BLEEDING", "outcome", "Gastrointestinal bleeding",
                        ["GI bleed", "gastrointestinal bleeding"], "gastrointestinal", 3.5),
            OntologyTerm("SEPSIS", "outcome", "Sepsis",
                        ["sepsis", "septic shock"], "systemic", 4.5),
            OntologyTerm("MULTIPLE_ORGAN_DYSFUNCTION", "outcome", "Multiple organ dysfunction syndrome",
                        ["MODS", "multi-organ failure"], "systemic", 5.0),
            OntologyTerm("PROLONGED_ICU_LOS", "outcome", "Prolonged ICU length of stay",
                        ["prolonged ICU"], "systemic", 3.0),
        ]

        # Obstetric Complications
        ob_outcomes = [
            OntologyTerm("FAILED_NEURAXIAL", "outcome", "Failed neuraxial anesthesia",
                        ["failed spinal", "failed epidural"], "obstetric", 2.5),
            OntologyTerm("HIGH_SPINAL", "outcome", "High/total spinal",
                        ["high spinal", "total spinal"], "obstetric", 4.0),
            OntologyTerm("MATERNAL_HYPOTENSION", "outcome", "Maternal hypotension",
                        ["maternal hypotension"], "obstetric", 2.0),
            OntologyTerm("FETAL_DISTRESS", "outcome", "Fetal distress",
                        ["fetal distress", "fetal bradycardia"], "obstetric", 3.5),
            OntologyTerm("UTERINE_ATONY", "outcome", "Uterine atony",
                        ["uterine atony"], "obstetric", 3.0),
            OntologyTerm("POSTPARTUM_HEMORRHAGE", "outcome", "Postpartum hemorrhage",
                        ["PPH", "postpartum bleeding"], "obstetric", 4.0),
            OntologyTerm("PREECLAMPSIA_COMPLICATIONS", "outcome", "Preeclampsia/eclampsia complications",
                        ["preeclampsia", "eclampsia"], "obstetric", 4.0),
            OntologyTerm("AMNIOTIC_FLUID_EMBOLISM", "outcome", "Amniotic fluid embolism",
                        ["AFE"], "obstetric", 5.0),
        ]

        # Pediatric-Specific Complications
        peds_outcomes = [
            OntologyTerm("PEDIATRIC_AIRWAY_OBSTRUCTION", "outcome", "Pediatric airway obstruction",
                        ["airway obstruction"], "pediatric", 3.5),
            OntologyTerm("POST_TONSILLECTOMY_BLEEDING", "outcome", "Post-tonsillectomy bleeding",
                        ["tonsillectomy bleeding"], "pediatric", 3.0),
            OntologyTerm("PEDIATRIC_EMERGENCE_DELIRIUM", "outcome", "Pediatric emergence delirium",
                        ["emergence delirium"], "pediatric", 2.0),
            OntologyTerm("POST_EXTUBATION_CROUP", "outcome", "Post-extubation croup",
                        ["croup", "post-extubation stridor"], "pediatric", 2.5),
        ]

        # Regional/Block Complications
        regional_outcomes = [
            OntologyTerm("BLOCK_FAILURE", "outcome", "Regional block failure",
                        ["block failure", "failed block"], "regional", 2.0),
            OntologyTerm("REGIONAL_HEMATOMA", "outcome", "Regional anesthesia hematoma",
                        ["block hematoma"], "regional", 4.0),
            OntologyTerm("REGIONAL_INFECTION", "outcome", "Regional anesthesia infection",
                        ["block infection"], "regional", 3.0),
            OntologyTerm("REGIONAL_NERVE_DAMAGE", "outcome", "Regional anesthesia nerve damage",
                        ["nerve damage"], "regional", 3.5),
            OntologyTerm("PNEUMOTHORAX_REGIONAL", "outcome", "Pneumothorax from regional block",
                        ["pneumothorax"], "regional", 3.5),
        ]

        # PONV
        ponv_outcomes = [
            OntologyTerm("PONV", "outcome", "Postoperative nausea and vomiting",
                        ["PONV", "nausea", "vomiting"], "gastrointestinal", 2.0),
        ]

        # Mortality
        mortality_outcomes = [
            OntologyTerm("MORTALITY_24H", "outcome", "24-hour mortality",
                        ["24-hour death"], "mortality", 5.0),
            OntologyTerm("MORTALITY_30D", "outcome", "30-day mortality",
                        ["30-day death"], "mortality", 5.0),
            OntologyTerm("MORTALITY_INHOSPITAL", "outcome", "In-hospital mortality",
                        ["in-hospital death"], "mortality", 5.0),
        ]

        # Combine all outcomes
        all_outcomes = (airway_outcomes + respiratory_outcomes + cardiac_outcomes +
                       neuro_outcomes + pain_outcomes + bleeding_outcomes +
                       organ_outcomes + ob_outcomes + peds_outcomes +
                       regional_outcomes + ponv_outcomes + mortality_outcomes)

        # Add outcomes to terms
        for outcome in all_outcomes:
            self.terms[outcome.token] = outcome

        # ============ RISK FACTORS (Exhaustive) ============
        self._add_risk_factors()

        # ============ MEDICATIONS (Comprehensive) ============
        self._add_medications()

        # ============ CONTEXTS ============
        self._add_contexts()

    def _add_risk_factors(self):
        """Add comprehensive risk factors."""

        # Demographics
        demographics = [
            OntologyTerm("AGE_NEONATE", "risk_factor", "Neonate (0-28 days)",
                        ["neonate", "newborn"], "demographics"),
            OntologyTerm("AGE_INFANT", "risk_factor", "Infant (29 days - 1 year)",
                        ["infant"], "demographics"),
            OntologyTerm("AGE_1_5", "risk_factor", "Age 1-5 years",
                        ["toddler", "preschool"], "demographics"),
            OntologyTerm("AGE_6_12", "risk_factor", "Age 6-12 years",
                        ["school age"], "demographics"),
            OntologyTerm("AGE_13_17", "risk_factor", "Age 13-17 years",
                        ["adolescent", "teenager"], "demographics"),
            OntologyTerm("AGE_ADULT_YOUNG", "risk_factor", "Young adult (<40 years)",
                        ["young adult"], "demographics"),
            OntologyTerm("AGE_ADULT_MIDDLE", "risk_factor", "Middle age (40-64 years)",
                        ["middle age"], "demographics"),
            OntologyTerm("AGE_ELDERLY", "risk_factor", "Elderly (65-79 years)",
                        ["elderly"], "demographics"),
            OntologyTerm("AGE_VERY_ELDERLY", "risk_factor", "Very elderly (≥80 years)",
                        ["very elderly"], "demographics"),
            OntologyTerm("SEX_FEMALE", "risk_factor", "Female sex",
                        ["female"], "demographics"),
            OntologyTerm("SEX_MALE", "risk_factor", "Male sex",
                        ["male"], "demographics"),
            OntologyTerm("PREGNANCY", "risk_factor", "Pregnancy",
                        ["pregnant", "gravid"], "demographics"),
            OntologyTerm("PREMATURITY", "risk_factor", "Prematurity",
                        ["premature", "preterm"], "demographics"),
            OntologyTerm("CONGENITAL_SYNDROME", "risk_factor", "Congenital syndrome",
                        ["genetic syndrome", "chromosomal abnormality"], "demographics"),
            OntologyTerm("FRAILTY", "risk_factor", "Frailty",
                        ["frail"], "demographics"),
            OntologyTerm("BMI_UNDERWEIGHT", "risk_factor", "Underweight (BMI <18.5)",
                        ["underweight"], "demographics"),
            OntologyTerm("BMI_OVERWEIGHT", "risk_factor", "Overweight (BMI 25-29.9)",
                        ["overweight"], "demographics"),
            OntologyTerm("BMI_OBESE_I", "risk_factor", "Obese Class I (BMI 30-34.9)",
                        ["obese class 1"], "demographics"),
            OntologyTerm("BMI_OBESE_II", "risk_factor", "Obese Class II (BMI 35-39.9)",
                        ["obese class 2"], "demographics"),
            OntologyTerm("BMI_OBESE_III", "risk_factor", "Obese Class III (BMI ≥40)",
                        ["morbidly obese", "super obese"], "demographics"),
            OntologyTerm("MALNUTRITION", "risk_factor", "Malnutrition",
                        ["malnourished"], "demographics"),
        ]

        # Lifestyle/Functional
        lifestyle = [
            OntologyTerm("SMOKING_CURRENT", "risk_factor", "Current smoking",
                        ["current smoker"], "lifestyle"),
            OntologyTerm("SMOKING_RECENT", "risk_factor", "Recent smoking (quit <8 weeks)",
                        ["recent smoker"], "lifestyle"),
            OntologyTerm("SMOKING_HEAVY", "risk_factor", "Heavy smoking (>20 pack-years)",
                        ["heavy smoker"], "lifestyle"),
            OntologyTerm("ALCOHOL_USE", "risk_factor", "Alcohol use disorder",
                        ["alcoholism", "alcohol dependence"], "lifestyle"),
            OntologyTerm("ILLICIT_DRUG_USE", "risk_factor", "Illicit drug use",
                        ["drug abuse", "substance abuse"], "lifestyle"),
            OntologyTerm("CHRONIC_OPIOID_USE", "risk_factor", "Chronic opioid use",
                        ["opioid dependence"], "lifestyle"),
            OntologyTerm("CHRONIC_BENZODIAZEPINE_USE", "risk_factor", "Chronic benzodiazepine use",
                        ["benzo dependence"], "lifestyle"),
            OntologyTerm("POOR_EXERCISE_TOLERANCE", "risk_factor", "Poor exercise tolerance",
                        ["exercise intolerance"], "lifestyle"),
            OntologyTerm("ADL_LIMITATIONS", "risk_factor", "Activities of daily living limitations",
                        ["ADL dependent"], "lifestyle"),
        ]

        # Airway Predictors
        airway_factors = [
            OntologyTerm("MALLAMPATI_3_4", "risk_factor", "Mallampati class 3-4",
                        ["Mallampati 3", "Mallampati 4"], "airway"),
            OntologyTerm("MOUTH_OPENING_LIMITED", "risk_factor", "Limited mouth opening (<3cm)",
                        ["limited mouth opening"], "airway"),
            OntologyTerm("THYROMENTAL_DISTANCE_SHORT", "risk_factor", "Short thyromental distance (<6cm)",
                        ["short TMD"], "airway"),
            OntologyTerm("NECK_MOBILITY_LIMITED", "risk_factor", "Limited neck mobility",
                        ["limited neck extension"], "airway"),
            OntologyTerm("NECK_CIRCUMFERENCE_LARGE", "risk_factor", "Large neck circumference (>40cm)",
                        ["thick neck"], "airway"),
            OntologyTerm("CRANIOFACIAL_ANOMALY", "risk_factor", "Craniofacial anomaly",
                        ["facial dysmorphism"], "airway"),
            OntologyTerm("PRIOR_DIFFICULT_AIRWAY", "risk_factor", "Prior difficult airway",
                        ["history of difficult intubation"], "airway"),
            OntologyTerm("BEARD", "risk_factor", "Beard (interfering with mask seal)",
                        ["facial hair"], "airway"),
            OntologyTerm("OSA", "risk_factor", "Obstructive sleep apnea",
                        ["sleep apnea", "OSA"], "airway"),
        ]

        # Pulmonary
        pulmonary_factors = [
            OntologyTerm("ASTHMA", "risk_factor", "Asthma",
                        ["bronchial asthma"], "pulmonary"),
            OntologyTerm("ASTHMA_POORLY_CONTROLLED", "risk_factor", "Poorly controlled asthma",
                        ["uncontrolled asthma"], "pulmonary"),
            OntologyTerm("COPD", "risk_factor", "Chronic obstructive pulmonary disease",
                        ["COPD", "emphysema", "chronic bronchitis"], "pulmonary"),
            OntologyTerm("BRONCHIECTASIS", "risk_factor", "Bronchiectasis",
                        ["bronchiectasis"], "pulmonary"),
            OntologyTerm("CYSTIC_FIBROSIS", "risk_factor", "Cystic fibrosis",
                        ["CF"], "pulmonary"),
            OntologyTerm("PULMONARY_HYPERTENSION", "risk_factor", "Pulmonary hypertension",
                        ["pulmonary HTN"], "pulmonary"),
            OntologyTerm("RECENT_URI_2W", "risk_factor", "Recent upper respiratory infection (≤2 weeks)",
                        ["recent URI", "recent cold"], "pulmonary"),
            OntologyTerm("RECENT_URI_2_4W", "risk_factor", "Recent upper respiratory infection (2-4 weeks)",
                        ["URI 2-4 weeks"], "pulmonary"),
            OntologyTerm("ACTIVE_LRTI", "risk_factor", "Active lower respiratory tract infection",
                        ["pneumonia", "bronchitis"], "pulmonary"),
            OntologyTerm("HOME_OXYGEN", "risk_factor", "Home oxygen therapy",
                        ["oxygen dependent"], "pulmonary"),
            OntologyTerm("PRIOR_ICU_VENTILATION", "risk_factor", "Prior ICU mechanical ventilation",
                        ["previous ventilation"], "pulmonary"),
        ]

        # Cardiac
        cardiac_factors = [
            OntologyTerm("CORONARY_ARTERY_DISEASE", "risk_factor", "Coronary artery disease",
                        ["CAD", "ischemic heart disease"], "cardiac"),
            OntologyTerm("PRIOR_MYOCARDIAL_INFARCTION", "risk_factor", "Prior myocardial infarction",
                        ["prior MI", "heart attack"], "cardiac"),
            OntologyTerm("HEART_FAILURE", "risk_factor", "Congestive heart failure",
                        ["CHF", "heart failure"], "cardiac"),
            OntologyTerm("NYHA_CLASS_I", "risk_factor", "NYHA Class I heart failure",
                        ["NYHA I"], "cardiac"),
            OntologyTerm("NYHA_CLASS_II", "risk_factor", "NYHA Class II heart failure",
                        ["NYHA II"], "cardiac"),
            OntologyTerm("NYHA_CLASS_III", "risk_factor", "NYHA Class III heart failure",
                        ["NYHA III"], "cardiac"),
            OntologyTerm("NYHA_CLASS_IV", "risk_factor", "NYHA Class IV heart failure",
                        ["NYHA IV"], "cardiac"),
            OntologyTerm("VALVULAR_DISEASE", "risk_factor", "Valvular heart disease",
                        ["valve disease"], "cardiac"),
            OntologyTerm("ARRHYTHMIAS", "risk_factor", "Cardiac arrhythmias",
                        ["irregular rhythm"], "cardiac"),
            OntologyTerm("PACEMAKER", "risk_factor", "Pacemaker",
                        ["paced rhythm"], "cardiac"),
            OntologyTerm("ICD", "risk_factor", "Implantable cardioverter defibrillator",
                        ["ICD", "defibrillator"], "cardiac"),
            OntologyTerm("HYPERTENSION", "risk_factor", "Hypertension",
                        ["high blood pressure"], "cardiac"),
        ]

        # Add all risk factor categories
        all_risk_factors = demographics + lifestyle + airway_factors + pulmonary_factors + cardiac_factors

        # Continue with remaining categories...
        # (I'll continue with the next batch to stay within response limits)

        for factor in all_risk_factors:
            self.terms[factor.token] = factor

    def _add_medications(self):
        """Add comprehensive medication ontology."""

        # Induction agents
        induction_meds = [
            OntologyTerm("PROPOFOL", "medication", "Propofol",
                        ["propofol", "diprivan"], "induction"),
            OntologyTerm("ETOMIDATE", "medication", "Etomidate",
                        ["etomidate", "amidate"], "induction"),
            OntologyTerm("KETAMINE", "medication", "Ketamine",
                        ["ketamine", "ketalar"], "induction"),
            OntologyTerm("METHOHEXITAL", "medication", "Methohexital",
                        ["methohexital", "brevital"], "induction"),
            OntologyTerm("THIOPENTAL", "medication", "Thiopental",
                        ["thiopental", "pentothal"], "induction"),
        ]

        # Inhaled anesthetics
        inhaled_meds = [
            OntologyTerm("SEVOFLURANE", "medication", "Sevoflurane",
                        ["sevoflurane", "ultane"], "volatile"),
            OntologyTerm("DESFLURANE", "medication", "Desflurane",
                        ["desflurane", "suprane"], "volatile"),
            OntologyTerm("ISOFLURANE", "medication", "Isoflurane",
                        ["isoflurane", "forane"], "volatile"),
            OntologyTerm("NITROUS_OXIDE", "medication", "Nitrous oxide",
                        ["nitrous oxide", "N2O"], "volatile"),
        ]

        # Opioids
        opioid_meds = [
            OntologyTerm("FENTANYL", "medication", "Fentanyl",
                        ["fentanyl", "sublimaze"], "opioid"),
            OntologyTerm("SUFENTANIL", "medication", "Sufentanil",
                        ["sufentanil", "sufenta"], "opioid"),
            OntologyTerm("REMIFENTANIL", "medication", "Remifentanil",
                        ["remifentanil", "ultiva"], "opioid"),
            OntologyTerm("ALFENTANIL", "medication", "Alfentanil",
                        ["alfentanil", "alfenta"], "opioid"),
            OntologyTerm("MORPHINE", "medication", "Morphine",
                        ["morphine"], "opioid"),
            OntologyTerm("HYDROMORPHONE", "medication", "Hydromorphone",
                        ["hydromorphone", "dilaudid"], "opioid"),
            OntologyTerm("METHADONE", "medication", "Methadone",
                        ["methadone"], "opioid"),
            OntologyTerm("OXYCODONE", "medication", "Oxycodone",
                        ["oxycodone", "oxycontin"], "opioid"),
            OntologyTerm("TRAMADOL", "medication", "Tramadol",
                        ["tramadol", "ultram"], "opioid"),
            OntologyTerm("MEPERIDINE", "medication", "Meperidine",
                        ["meperidine", "pethidine"], "opioid"),
        ]

        # Combine medication categories
        all_medications = induction_meds + inhaled_meds + opioid_meds
        # (Continue with remaining medication categories...)

        for med in all_medications:
            self.terms[med.token] = med

    def _add_contexts(self):
        """Add surgical and case contexts."""

        contexts = [
            OntologyTerm("ELECTIVE", "context", "Elective surgery",
                        ["elective"], "urgency"),
            OntologyTerm("URGENT", "context", "Urgent surgery",
                        ["urgent"], "urgency"),
            OntologyTerm("EMERGENCY", "context", "Emergency surgery",
                        ["emergency", "emergent"], "urgency"),
            OntologyTerm("ENT_SURGERY", "context", "ENT surgery",
                        ["ENT", "otolaryngology"], "surgical_specialty"),
            OntologyTerm("TONSILLECTOMY", "context", "Tonsillectomy",
                        ["tonsillectomy"], "surgical_procedure"),
            OntologyTerm("ADENOIDECTOMY", "context", "Adenoidectomy",
                        ["adenoidectomy"], "surgical_procedure"),
            # Continue with all surgical specialties and procedures...
        ]

        for context in contexts:
            self.terms[context.token] = context

    def get_term(self, token: str) -> OntologyTerm:
        """Get ontology term by token."""
        return self.terms.get(token)

    def get_terms_by_type(self, term_type: str) -> List[OntologyTerm]:
        """Get all terms of a specific type."""
        return [term for term in self.terms.values() if term.type == term_type]

    def get_terms_by_category(self, category: str) -> List[OntologyTerm]:
        """Get all terms in a specific category."""
        return [term for term in self.terms.values() if term.category == category]

    def search_terms(self, query: str) -> List[OntologyTerm]:
        """Search terms by label or synonyms."""
        query_lower = query.lower()
        matches = []

        for term in self.terms.values():
            if query_lower in term.plain_label.lower():
                matches.append(term)
            elif any(query_lower in syn.lower() for syn in term.synonyms):
                matches.append(term)

        return matches

    def to_database_records(self) -> List[Dict[str, Any]]:
        """Convert ontology to database insert records."""
        records = []

        for term in self.terms.values():
            record = {
                'token': term.token,
                'type': term.type,
                'plain_label': term.plain_label,
                'synonyms': json.dumps(term.synonyms),
                'category': term.category,
                'severity_weight': term.severity_weight,
                'notes': term.notes,
                'icd10_codes': json.dumps(term.icd10_codes or []),
                'mesh_codes': json.dumps(term.mesh_codes or []),
                'parent_token': term.parent_token,
                'children_tokens': json.dumps(term.children_tokens or [])
            }
            records.append(record)

        return records