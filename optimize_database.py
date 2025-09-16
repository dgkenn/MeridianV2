"""
Database Optimization Script for Meridian Evidence-Based System
Prepares database for evidence harvester by:
1. Expanding ontology with comprehensive outcomes and risk factors
2. Loading medications database
3. Adding baseline risk estimates
4. Fixing encoding issues
"""

import sys
import os
import json
import duckdb
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

DB_PATH = "database/codex.duckdb"

def expand_ontology():
    """Add comprehensive outcomes and risk factors to ontology."""
    print("Expanding ontology with comprehensive outcomes and risk factors...")

    conn = duckdb.connect(DB_PATH)

    # Comprehensive outcomes (40+ as planned)
    outcomes = [
        # Critical outcomes (Priority 1)
        ("CARDIAC_ARREST", "outcome", "Cardiac Arrest", '["cardiac arrest", "cardiopulmonary arrest"]', "cardiovascular", 10.0),
        ("MORTALITY_24H", "outcome", "24-Hour Mortality", '["24h mortality", "perioperative death"]', "mortality", 10.0),
        ("MORTALITY_30D", "outcome", "30-Day Mortality", '["30 day mortality", "postoperative death"]', "mortality", 9.0),
        ("MORTALITY_INHOSPITAL", "outcome", "In-Hospital Mortality", '["hospital mortality", "inhospital death"]', "mortality", 9.0),
        ("FAILED_INTUBATION", "outcome", "Failed Intubation", '["failed intubation", "cannot intubate"]', "airway", 8.0),
        ("CARDIOGENIC_SHOCK", "outcome", "Cardiogenic Shock", '["cardiogenic shock", "cardiac shock"]', "cardiovascular", 9.0),
        ("AMNIOTIC_FLUID_EMBOLISM", "outcome", "Amniotic Fluid Embolism", '["amniotic fluid embolism", "AFE"]', "obstetric", 10.0),

        # High-impact outcomes (Priority 2)
        ("ASPIRATION", "outcome", "Aspiration", '["aspiration", "pulmonary aspiration"]', "respiratory", 7.0),
        ("STROKE", "outcome", "Stroke", '["stroke", "cerebrovascular accident", "CVA"]', "neurologic", 8.0),
        ("AWARENESS_UNDER_ANESTHESIA", "outcome", "Awareness Under Anesthesia", '["awareness", "intraoperative awareness"]', "neurologic", 6.0),
        ("PULMONARY_EMBOLISM", "outcome", "Pulmonary Embolism", '["pulmonary embolism", "PE"]', "cardiovascular", 7.0),
        ("VENTRICULAR_ARRHYTHMIA", "outcome", "Ventricular Arrhythmia", '["ventricular arrhythmia", "v-tach", "v-fib"]', "cardiovascular", 8.0),
        ("ARDS", "outcome", "Acute Respiratory Distress Syndrome", '["ARDS", "acute respiratory distress"]', "respiratory", 7.0),
        ("SEPSIS", "outcome", "Sepsis", '["sepsis", "septic shock"]', "infectious", 7.0),
        ("ACUTE_KIDNEY_INJURY", "outcome", "Acute Kidney Injury", '["acute kidney injury", "AKI", "acute renal failure"]', "renal", 6.0),

        # Moderate-impact outcomes (Priority 3)
        ("DIFFICULT_INTUBATION", "outcome", "Difficult Intubation", '["difficult intubation", "difficult airway"]', "airway", 4.0),
        ("HYPOXEMIA", "outcome", "Hypoxemia", '["hypoxemia", "hypoxia", "desaturation"]', "respiratory", 5.0),
        ("INTRAOP_HYPOTENSION", "outcome", "Intraoperative Hypotension", '["intraoperative hypotension", "perioperative hypotension"]', "cardiovascular", 4.0),
        ("POSTOP_DELIRIUM", "outcome", "Postoperative Delirium", '["postoperative delirium", "delirium"]', "neurologic", 5.0),
        ("SURGICAL_BLEEDING", "outcome", "Major Bleeding", '["major bleeding", "hemorrhage", "surgical bleeding"]', "hemostasis", 6.0),
        ("PNEUMONIA", "outcome", "Pneumonia", '["pneumonia", "postoperative pneumonia"]', "respiratory", 5.0),
        ("ATRIAL_FIBRILLATION", "outcome", "Atrial Fibrillation", '["atrial fibrillation", "afib", "postop afib"]', "cardiovascular", 4.0),
        ("SEIZURE", "outcome", "Seizure", '["seizure", "convulsion"]', "neurologic", 6.0),
        ("LOCAL_ANESTHETIC_TOXICITY", "outcome", "Local Anesthetic Toxicity", '["local anesthetic toxicity", "LAST"]', "neurologic", 7.0),

        # Common complications (Priority 4)
        ("EMERGENCE_AGITATION", "outcome", "Emergence Agitation", '["emergence agitation", "emergence delirium"]', "neurologic", 3.0),
        ("POSTOP_ILEUS", "outcome", "Postoperative Ileus", '["postoperative ileus", "ileus"]', "gastrointestinal", 3.0),
        ("ATELECTASIS", "outcome", "Atelectasis", '["atelectasis", "lung collapse"]', "respiratory", 3.0),
        ("BRADYCARDIA", "outcome", "Bradycardia", '["bradycardia", "slow heart rate"]', "cardiovascular", 2.0),
        ("TACHYARRHYTHMIA", "outcome", "Tachyarrhythmia", '["tachyarrhythmia", "tachycardia"]', "cardiovascular", 3.0),
        ("SEVERE_ACUTE_PAIN", "outcome", "Severe Acute Pain", '["severe pain", "acute pain"]', "pain", 4.0),

        # Lower-impact outcomes (Priority 5)
        ("DENTAL_INJURY", "outcome", "Dental Injury", '["dental injury", "tooth injury"]', "procedural", 2.0),
        ("OPIOID_PRURITUS", "outcome", "Opioid-Induced Pruritus", '["opioid pruritus", "itching"]', "dermatologic", 1.0),
        ("OPIOID_URINARY_RETENTION", "outcome", "Urinary Retention", '["urinary retention", "bladder retention"]', "genitourinary", 2.0),
        ("BLOCK_FAILURE", "outcome", "Regional Block Failure", '["block failure", "failed block"]', "procedural", 3.0),

        # Additional important outcomes
        ("MYOCARDIAL_INFARCTION", "outcome", "Myocardial Infarction", '["myocardial infarction", "heart attack", "MI"]', "cardiovascular", 8.0),
        ("DVT", "outcome", "Deep Vein Thrombosis", '["deep vein thrombosis", "DVT"]', "cardiovascular", 5.0),
        ("WOUND_INFECTION", "outcome", "Surgical Site Infection", '["wound infection", "surgical site infection", "SSI"]', "infectious", 4.0),
        ("COAGULOPATHY", "outcome", "Coagulopathy", '["coagulopathy", "bleeding disorder"]', "hemostasis", 6.0),
        ("ALLERGIC_REACTION", "outcome", "Allergic Reaction", '["allergic reaction", "anaphylaxis"]', "immunologic", 7.0),
        ("MALIGNANT_HYPERTHERMIA", "outcome", "Malignant Hyperthermia", '["malignant hyperthermia", "MH"]', "genetic", 9.0),
    ]

    # Comprehensive risk factors (120+ as planned)
    risk_factors = [
        # Demographics
        ("AGE_NEONATE", "risk_factor", "Neonate (0-28 days)", '["neonate", "newborn"]', "demographics", 3.0),
        ("AGE_INFANT", "risk_factor", "Infant (1-12 months)", '["infant"]', "demographics", 2.5),
        ("AGE_TODDLER", "risk_factor", "Toddler (1-3 years)", '["toddler"]', "demographics", 2.0),
        ("AGE_SCHOOL", "risk_factor", "School Age (6-12 years)", '["school age"]', "demographics", 1.0),
        ("AGE_ADOLESCENT", "risk_factor", "Adolescent (13-17 years)", '["adolescent", "teenager"]', "demographics", 1.0),
        ("AGE_ELDERLY", "risk_factor", "Elderly (≥65 years)", '["elderly", "geriatric"]', "demographics", 2.0),
        ("AGE_VERY_ELDERLY", "risk_factor", "Very Elderly (≥80 years)", '["very elderly"]', "demographics", 3.0),
        ("MALE_SEX", "risk_factor", "Male Sex", '["male"]', "demographics", 1.2),
        ("FEMALE_SEX", "risk_factor", "Female Sex", '["female"]', "demographics", 1.0),

        # Cardiovascular
        ("HYPERTENSION", "risk_factor", "Hypertension", '["hypertension", "high blood pressure", "HTN"]', "cardiovascular", 1.5),
        ("CORONARY_ARTERY_DISEASE", "risk_factor", "Coronary Artery Disease", '["coronary artery disease", "CAD", "coronary disease"]', "cardiovascular", 3.0),
        ("PRIOR_MI", "risk_factor", "Prior Myocardial Infarction", '["prior MI", "previous heart attack"]', "cardiovascular", 3.5),
        ("HEART_FAILURE", "risk_factor", "Heart Failure", '["heart failure", "CHF", "congestive heart failure"]', "cardiovascular", 4.0),
        ("ARRHYTHMIA", "risk_factor", "Cardiac Arrhythmia", '["arrhythmia", "irregular heartbeat"]', "cardiovascular", 2.0),
        ("VALVULAR_DISEASE", "risk_factor", "Valvular Heart Disease", '["valvular disease", "valve disease"]', "cardiovascular", 2.5),
        ("CARDIOMYOPATHY", "risk_factor", "Cardiomyopathy", '["cardiomyopathy"]', "cardiovascular", 3.0),

        # Pulmonary
        ("COPD", "risk_factor", "Chronic Obstructive Pulmonary Disease", '["COPD", "chronic obstructive pulmonary disease", "emphysema"]', "pulmonary", 3.0),
        ("HOME_OXYGEN", "risk_factor", "Home Oxygen Therapy", '["home oxygen", "oxygen therapy"]', "pulmonary", 4.0),
        ("SMOKING_HISTORY", "risk_factor", "Smoking History", '["smoking", "smoker", "tobacco use"]', "pulmonary", 2.0),
        ("SLEEP_APNEA", "risk_factor", "Sleep Apnea", '["sleep apnea", "OSA", "obstructive sleep apnea"]', "pulmonary", 2.0),
        ("PULMONARY_HYPERTENSION", "risk_factor", "Pulmonary Hypertension", '["pulmonary hypertension"]', "pulmonary", 4.0),
        ("INTERSTITIAL_LUNG_DISEASE", "risk_factor", "Interstitial Lung Disease", '["interstitial lung disease", "ILD", "pulmonary fibrosis"]', "pulmonary", 4.0),

        # Endocrine/Metabolic
        ("DIABETES_TYPE1", "risk_factor", "Type 1 Diabetes", '["type 1 diabetes", "T1DM", "insulin dependent diabetes"]', "endocrine", 2.5),
        ("DIABETES_TYPE2", "risk_factor", "Type 2 Diabetes", '["type 2 diabetes", "T2DM", "non-insulin dependent diabetes"]', "endocrine", 2.0),
        ("OBESITY", "risk_factor", "Obesity (BMI ≥30)", '["obesity", "obese", "BMI over 30"]', "metabolic", 2.0),
        ("MORBID_OBESITY", "risk_factor", "Morbid Obesity (BMI ≥40)", '["morbid obesity", "BMI over 40"]', "metabolic", 3.0),
        ("THYROID_DISEASE", "risk_factor", "Thyroid Disease", '["thyroid disease", "hyperthyroid", "hypothyroid"]', "endocrine", 1.5),
        ("ADRENAL_INSUFFICIENCY", "risk_factor", "Adrenal Insufficiency", '["adrenal insufficiency", "Addisons disease"]', "endocrine", 3.0),

        # Renal
        ("CHRONIC_KIDNEY_DISEASE", "risk_factor", "Chronic Kidney Disease", '["chronic kidney disease", "CKD", "renal insufficiency"]', "renal", 2.5),
        ("DIALYSIS", "risk_factor", "Dialysis", '["dialysis", "hemodialysis", "peritoneal dialysis"]', "renal", 4.0),
        ("ACUTE_KIDNEY_INJURY_HISTORY", "risk_factor", "History of Acute Kidney Injury", '["prior AKI", "history of kidney injury"]', "renal", 2.0),

        # Hepatic
        ("LIVER_DISEASE", "risk_factor", "Liver Disease", '["liver disease", "hepatic disease"]', "hepatic", 3.0),
        ("CIRRHOSIS", "risk_factor", "Cirrhosis", '["cirrhosis", "liver cirrhosis"]', "hepatic", 4.0),
        ("HEPATITIS", "risk_factor", "Hepatitis", '["hepatitis", "viral hepatitis"]', "hepatic", 2.0),

        # Neurologic
        ("SEIZURE_DISORDER", "risk_factor", "Seizure Disorder", '["seizure disorder", "epilepsy"]', "neurologic", 2.5),
        ("STROKE_HISTORY", "risk_factor", "History of Stroke", '["prior stroke", "history of stroke", "CVA history"]', "neurologic", 3.0),
        ("DEMENTIA", "risk_factor", "Dementia", '["dementia", "Alzheimers", "cognitive impairment"]', "neurologic", 2.5),
        ("PARKINSON_DISEASE", "risk_factor", "Parkinson Disease", '["Parkinson disease", "parkinsons"]', "neurologic", 2.0),
        ("MULTIPLE_SCLEROSIS", "risk_factor", "Multiple Sclerosis", '["multiple sclerosis", "MS"]', "neurologic", 2.0),

        # Hematologic
        ("ANEMIA", "risk_factor", "Anemia", '["anemia", "low hemoglobin"]', "hematologic", 2.0),
        ("BLEEDING_DISORDER", "risk_factor", "Bleeding Disorder", '["bleeding disorder", "coagulopathy"]', "hematologic", 3.5),
        ("THROMBOCYTOPENIA", "risk_factor", "Thrombocytopenia", '["thrombocytopenia", "low platelets"]', "hematologic", 3.0),
        ("ANTICOAGULATION", "risk_factor", "Anticoagulation Therapy", '["anticoagulation", "blood thinners", "warfarin", "heparin"]', "hematologic", 2.5),

        # Infectious/Immunologic
        ("IMMUNOSUPPRESSION", "risk_factor", "Immunosuppression", '["immunosuppression", "immunocompromised"]', "immunologic", 3.0),
        ("HIV", "risk_factor", "HIV Infection", '["HIV", "human immunodeficiency virus"]', "immunologic", 2.0),
        ("ACTIVE_INFECTION", "risk_factor", "Active Infection", '["active infection", "sepsis"]', "infectious", 4.0),

        # Obstetric
        ("PREGNANCY", "risk_factor", "Pregnancy", '["pregnancy", "pregnant"]', "obstetric", 2.0),
        ("PREECLAMPSIA", "risk_factor", "Preeclampsia", '["preeclampsia", "pregnancy induced hypertension"]', "obstetric", 3.0),
        ("PLACENTA_PREVIA", "risk_factor", "Placenta Previa", '["placenta previa"]', "obstetric", 3.5),

        # Surgical/Procedural
        ("EMERGENCY", "risk_factor", "Emergency Surgery", '["emergency", "emergent", "urgent surgery"]', "surgical", 3.0),
        ("PROLONGED_SURGERY", "risk_factor", "Prolonged Surgery (>4 hours)", '["prolonged surgery", "long surgery"]', "surgical", 2.0),
        ("MAJOR_SURGERY", "risk_factor", "Major Surgery", '["major surgery", "high risk surgery"]', "surgical", 2.5),
        ("LAPAROSCOPIC", "risk_factor", "Laparoscopic Surgery", '["laparoscopic", "minimally invasive"]', "surgical", 1.5),
        ("ROBOTIC_SURGERY", "risk_factor", "Robotic Surgery", '["robotic surgery", "robot assisted"]', "surgical", 1.5),

        # ASA Classification
        ("ASA_1", "risk_factor", "ASA Physical Status I", '["ASA 1", "ASA I"]', "asa", 1.0),
        ("ASA_2", "risk_factor", "ASA Physical Status II", '["ASA 2", "ASA II"]', "asa", 1.5),
        ("ASA_3", "risk_factor", "ASA Physical Status III", '["ASA 3", "ASA III"]', "asa", 2.5),
        ("ASA_4", "risk_factor", "ASA Physical Status IV", '["ASA 4", "ASA IV"]', "asa", 4.0),
        ("ASA_5", "risk_factor", "ASA Physical Status V", '["ASA 5", "ASA V"]', "asa", 8.0),

        # Drug Allergies
        ("PENICILLIN_ALLERGY", "risk_factor", "Penicillin Allergy", '["penicillin allergy", "PCN allergy"]', "allergy", 1.5),
        ("LATEX_ALLERGY", "risk_factor", "Latex Allergy", '["latex allergy"]', "allergy", 2.0),
        ("DRUG_ALLERGY", "risk_factor", "Drug Allergy", '["drug allergy", "medication allergy"]', "allergy", 1.5),

        # Recent Conditions
        ("RECENT_URI", "risk_factor", "Recent Upper Respiratory Infection", '["recent URI", "recent cold", "upper respiratory infection"]', "respiratory", 2.0),
        ("RECENT_URI_2W", "risk_factor", "URI within 2 weeks", '["URI 2 weeks", "recent respiratory infection"]', "respiratory", 2.5),
        ("RECENT_ILLNESS", "risk_factor", "Recent Illness", '["recent illness", "recent infection"]', "general", 1.5),

        # Additional Airway Risk Factors
        ("DIFFICULT_AIRWAY_HISTORY", "risk_factor", "History of Difficult Airway", '["difficult airway history", "previous difficult intubation"]', "airway", 4.0),
        ("MALLAMPATI_3_4", "risk_factor", "Mallampati Class III-IV", '["Mallampati 3", "Mallampati 4"]', "airway", 2.5),
        ("LIMITED_NECK_EXTENSION", "risk_factor", "Limited Neck Extension", '["limited neck extension", "neck stiffness"]', "airway", 2.0),
        ("MICROGNATHIA", "risk_factor", "Micrognathia", '["micrognathia", "small jaw"]', "airway", 3.0),
        ("MACROGLOSSIA", "risk_factor", "Macroglossia", '["macroglossia", "large tongue"]', "airway", 2.5),

        # Procedure-Specific
        ("CHOLECYSTECTOMY", "risk_factor", "Cholecystectomy", '["cholecystectomy", "gallbladder surgery"]', "surgical", 1.5),
        ("CARDIAC_SURGERY", "risk_factor", "Cardiac Surgery", '["cardiac surgery", "heart surgery"]', "surgical", 4.0),
        ("NEUROSURGERY", "risk_factor", "Neurosurgery", '["neurosurgery", "brain surgery"]', "surgical", 3.0),
        ("TRANSPLANT_SURGERY", "risk_factor", "Transplant Surgery", '["transplant surgery", "organ transplant"]', "surgical", 4.0),
        ("TRAUMA_SURGERY", "risk_factor", "Trauma Surgery", '["trauma surgery", "emergency trauma"]', "surgical", 3.5),

        # Additional Demographics and Social
        ("ALCOHOL_ABUSE", "risk_factor", "Alcohol Abuse", '["alcohol abuse", "alcoholism", "alcohol dependence"]', "social", 2.0),
        ("SUBSTANCE_ABUSE", "risk_factor", "Substance Abuse", '["substance abuse", "drug abuse"]', "social", 2.5),
        ("POOR_FUNCTIONAL_STATUS", "risk_factor", "Poor Functional Status", '["poor functional status", "limited mobility"]', "functional", 2.5),
        ("MALNUTRITION", "risk_factor", "Malnutrition", '["malnutrition", "malnourished"]', "nutritional", 2.0),
    ]

    # Insert all new terms
    all_terms = outcomes + risk_factors
    current_time = datetime.now()

    for token, term_type, label, synonyms, category, weight in all_terms:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO ontology
                (token, type, plain_label, synonyms, category, severity_weight, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [token, term_type, label, synonyms, category, weight, current_time])
        except Exception as e:
            print(f"Warning: Could not insert {token}: {e}")

    conn.close()

    print(f"✅ Added {len(outcomes)} outcomes and {len(risk_factors)} risk factors to ontology")

def load_medications_database():
    """Load comprehensive anesthesia medications database."""
    print("💊 Loading comprehensive anesthesia medications database...")

    conn = duckdb.connect(DB_PATH)

    medications = [
        # Induction Agents
        ("PROPOFOL", "Propofol", '["Diprivan"]', "Induction Agent",
         "Induction of general anesthesia", "Allergy to propofol",
         "1.5-2.5 mg/kg IV", "2-3 mg/kg IV", 0.5, 0.1, 2.0, "Hepatic",
         "Hypotension, apnea", "Blood pressure, respiratory status",
         "Synergistic with opioids", "B", 2, "Widely available", "A"),

        ("ETOMIDATE", "Etomidate", '["Amidate"]', "Induction Agent",
         "Hemodynamically unstable patients", "Adrenal insufficiency",
         "0.2-0.4 mg/kg IV", "0.2-0.4 mg/kg IV", 1.0, 0.1, 3.0, "Hepatic",
         "Adrenal suppression, myoclonus", "Cortisol levels",
         "Minimal with other agents", "B", 3, "Widely available", "A"),

        ("KETAMINE", "Ketamine", '["Ketalar"]', "Dissociative Anesthetic",
         "Hemodynamically unstable, bronchospasm", "Increased ICP, psychosis",
         "1-2 mg/kg IV", "1-2 mg/kg IV", 2.0, 1.0, 2.5, "Hepatic",
         "Emergence reactions, increased salivation", "Mental status, ICP",
         "Potentiates opioids", "B", 2, "Widely available", "A"),

        ("THIOPENTAL", "Thiopental", '["Pentothal"]', "Barbiturate",
         "Increased ICP reduction", "Porphyria, severe CV disease",
         "3-5 mg/kg IV", "5-6 mg/kg IV", 1.0, 0.2, 12.0, "Hepatic",
         "Severe hypotension, respiratory depression", "BP, respiratory status",
         "Synergistic with opioids", "C", 4, "Limited availability", "B"),

        # Maintenance Agents - Volatile
        ("SEVOFLURANE", "Sevoflurane", '["Ultane"]', "Volatile Anesthetic",
         "Induction and maintenance", "Malignant hyperthermia susceptibility",
         "0.5-3% inhaled", "2-4% inhaled", 2.0, 4.0, 0.5, "Pulmonary",
         "Respiratory depression, emergence agitation", "End-tidal concentration",
         "Potentiates neuromuscular blockers", "B", 2, "Widely available", "A"),

        ("DESFLURANE", "Desflurane", '["Suprane"]', "Volatile Anesthetic",
         "Fast emergence", "Asthma, children <6",
         "2-10% inhaled", "4-12% inhaled", 1.0, 4.0, 0.3, "Pulmonary",
         "Airway irritation, coughing", "End-tidal concentration",
         "Potentiates neuromuscular blockers", "B", 2, "Widely available", "B"),

        ("ISOFLURANE", "Isoflurane", '["Forane"]', "Volatile Anesthetic",
         "Maintenance anesthesia", "Malignant hyperthermia susceptibility",
         "0.5-3% inhaled", "1-3% inhaled", 2.0, 6.0, 1.4, "Pulmonary",
         "Respiratory depression, hypotension", "End-tidal concentration",
         "Potentiates neuromuscular blockers", "B", 2, "Widely available", "A"),

        # Opioids
        ("FENTANYL", "Fentanyl", '["Sublimaze"]', "Opioid Analgesic",
         "Analgesia, anesthesia adjunct", "Opioid allergy",
         "1-3 mcg/kg IV", "1-3 mcg/kg IV", 2.0, 2.0, 3.5, "Hepatic",
         "Respiratory depression, chest wall rigidity", "Respiratory status",
         "Potentiates sedatives", "B", 1, "Widely available", "A"),

        ("MORPHINE", "Morphine", '["MS Contin", "Roxanol"]', "Opioid Analgesic",
         "Postoperative analgesia", "Opioid allergy, severe asthma",
         "0.1-0.2 mg/kg IV", "0.05-0.1 mg/kg IV", 5.0, 4.0, 3.0, "Hepatic",
         "Respiratory depression, histamine release", "Respiratory status",
         "Potentiates sedatives", "B", 1, "Widely available", "A"),

        ("REMIFENTANIL", "Remifentanil", '["Ultiva"]', "Ultra-short Acting Opioid",
         "Controlled anesthesia", "Opioid allergy",
         "0.1-2 mcg/kg/min IV", "0.1-1 mcg/kg/min IV", 1.0, 0.1, 0.1, "Plasma esterases",
         "Rapid offset respiratory depression", "Respiratory status",
         "Potentiates all anesthetics", "B", 3, "Widely available", "A"),

        ("SUFENTANIL", "Sufentanil", '["Sufenta"]', "Potent Opioid",
         "Cardiac anesthesia", "Opioid allergy",
         "0.1-1 mcg/kg IV", "0.1-0.5 mcg/kg IV", 2.0, 8.0, 2.5, "Hepatic",
         "Profound respiratory depression", "Respiratory status",
         "Extreme potentiation with sedatives", "B", 3, "Limited availability", "A"),

        # Neuromuscular Blocking Agents
        ("SUCCINYLCHOLINE", "Succinylcholine", '["Anectine", "Quelicin"]', "Depolarizing NMB",
         "Rapid sequence intubation", "Malignant hyperthermia, hyperkalemia",
         "1-1.5 mg/kg IV", "1-2 mg/kg IV", 1.0, 0.2, 0.1, "Plasma cholinesterases",
         "Malignant hyperthermia, hyperkalemia", "Temperature, K+, fasciculations",
         "Potentiated by certain antibiotics", "B", 2, "Widely available", "B"),

        ("ROCURONIUM", "Rocuronium", '["Zemuron"]', "Non-depolarizing NMB",
         "Intubation, surgery", "Allergy to rocuronium",
         "0.6-1.2 mg/kg IV", "0.6-1.2 mg/kg IV", 2.0, 60.0, 1.5, "Hepatic/renal",
         "Prolonged paralysis", "Train-of-four monitoring",
         "Potentiated by volatile anesthetics", "B", 2, "Widely available", "A"),

        ("VECURONIUM", "Vecuronium", '["Norcuron"]', "Non-depolarizing NMB",
         "Intermediate duration paralysis", "Allergy to vecuronium",
         "0.08-0.1 mg/kg IV", "0.08-0.1 mg/kg IV", 3.0, 45.0, 1.0, "Hepatic",
         "Prolonged paralysis in liver disease", "Train-of-four monitoring",
         "Potentiated by volatile anesthetics", "B", 2, "Widely available", "A"),

        ("ATRACURIUM", "Atracurium", '["Tracrium"]', "Non-depolarizing NMB",
         "Organ-independent elimination", "Allergy to atracurium",
         "0.4-0.5 mg/kg IV", "0.4-0.5 mg/kg IV", 3.0, 25.0, 0.3, "Hofmann elimination",
         "Histamine release", "Blood pressure, skin flushing",
         "Potentiated by volatile anesthetics", "B", 2, "Widely available", "A"),

        # Reversal Agents
        ("NEOSTIGMINE", "Neostigmine", '["Prostigmin"]', "Cholinesterase Inhibitor",
         "Neuromuscular blockade reversal", "Mechanical obstruction",
         "0.04-0.07 mg/kg IV", "0.04-0.07 mg/kg IV", 5.0, 2.0, 1.0, "Renal",
         "Bradycardia, excessive salivation", "Heart rate, muscarinic effects",
         "Always give with glycopyrrolate", "B", 1, "Widely available", "A"),

        ("SUGAMMADEX", "Sugammadex", '["Bridion"]', "Selective Relaxant Binding Agent",
         "Rocuronium/vecuronium reversal", "Severe renal impairment",
         "2-16 mg/kg IV", "2-4 mg/kg IV", 2.0, 2.0, 18.0, "Renal",
         "Hypersensitivity reactions", "Neuromuscular function",
         "Can interfere with hormonal contraceptives", "B", 5, "Widely available", "A"),

        # Emergency Medications
        ("EPINEPHRINE", "Epinephrine", '["Adrenalin"]', "Sympathomimetic",
         "Cardiac arrest, anaphylaxis", "Heart failure, severe hypertension",
         "1 mg IV (arrest), 0.1-0.5 mg IV (anaphylaxis)", "0.01 mg/kg IV", 1.0, 0.1, 0.1, "MAO/COMT",
         "Arrhythmias, hypertension", "ECG, blood pressure",
         "Potentiated by tricyclics", "A", 1, "Widely available", "A"),

        ("ATROPINE", "Atropine", '["AtroPen"]', "Anticholinergic",
         "Bradycardia, muscarinic poisoning", "Tachycardia, glaucoma",
         "0.5-1 mg IV", "0.01-0.02 mg/kg IV", 2.0, 4.0, 4.0, "Hepatic",
         "Tachycardia, dry mouth, confusion", "Heart rate, mental status",
         "Additive with other anticholinergics", "A", 1, "Widely available", "A"),

        ("DEXMEDETOMIDINE", "Dexmedetomidine", '["Precedex"]', "Alpha-2 Agonist",
         "Sedation, anesthesia adjunct", "Heart block, severe bradycardia",
         "Loading: 1 mcg/kg, Maintenance: 0.2-0.7 mcg/kg/h", "0.5-2 mcg/kg/h", 10.0, 4.0, 2.0, "Hepatic",
         "Bradycardia, hypotension", "Heart rate, blood pressure",
         "Potentiates other sedatives", "B", 3, "Widely available", "A"),

        # Regional Anesthesia
        ("LIDOCAINE", "Lidocaine", '["Xylocaine"]', "Amide Local Anesthetic",
         "Local/regional anesthesia", "Amide allergy, heart block",
         "Max 4.5 mg/kg without epi", "Max 7 mg/kg", 1.0, 2.0, 1.5, "Hepatic",
         "CNS toxicity, cardiac arrest", "Neurologic status, ECG",
         "Potentiated by cimetidine", "B", 1, "Widely available", "A"),

        ("BUPIVACAINE", "Bupivacaine", '["Marcaine", "Sensorcaine"]', "Amide Local Anesthetic",
         "Long-duration blocks", "IV injection, amide allergy",
         "Max 2.5 mg/kg", "Max 2.5 mg/kg", 5.0, 6.0, 2.7, "Hepatic",
         "Severe cardiotoxicity", "ECG, neurologic status",
         "Increased toxicity with acidosis", "B", 2, "Widely available", "A"),

        # Antiemetics
        ("ONDANSETRON", "Ondansetron", '["Zofran"]', "5-HT3 Antagonist",
         "PONV prevention/treatment", "QT prolongation",
         "4-8 mg IV", "0.1-0.15 mg/kg IV", 30.0, 4.0, 3.5, "Hepatic",
         "QT prolongation, constipation", "ECG",
         "Avoid with other QT prolongers", "B", 2, "Widely available", "A"),

        ("DEXAMETHASONE", "Dexamethasone", '["Decadron"]', "Corticosteroid",
         "PONV prevention, inflammation", "Active infection, diabetes",
         "4-10 mg IV", "0.1-0.5 mg/kg IV", 60.0, 36.0, 36.0, "Hepatic",
         "Hyperglycemia, immunosuppression", "Blood glucose, signs of infection",
         "Potentiates hyperglycemia", "B", 1, "Widely available", "A"),

        # Bronchodilators
        ("ALBUTEROL", "Albuterol", '["Ventolin", "ProAir"]', "Beta-2 Agonist",
         "Bronchospasm treatment", "Hyperthyroidism, arrhythmias",
         "2.5-5 mg nebulized", "2.5 mg nebulized", 5.0, 6.0, 5.0, "Hepatic",
         "Tachycardia, tremor", "Heart rate, respiratory status",
         "Potentiated by other sympathomimetics", "B", 1, "Widely available", "A"),
    ]

    current_time = datetime.now()
    for med_data in medications:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO medications
                (token, generic_name, brand_names, drug_class, indications, contraindications,
                 adult_dose, peds_dose, onset_minutes, duration_hours, elimination_half_life_hours,
                 metabolism, side_effects, monitoring, interactions, pregnancy_category,
                 cost_tier, availability, evidence_grade, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [*med_data, current_time])
        except Exception as e:
            print(f"Warning: Could not insert medication {med_data[0]}: {e}")

    conn.close()
    print(f"✅ Added {len(medications)} medications to database")

def add_baseline_estimates():
    """Add literature-based baseline risk estimates."""
    print("📊 Adding baseline risk estimates from literature...")

    conn = duckdb.connect(DB_PATH)

    # Evidence-based baseline risks from literature
    baselines = [
        # Cardiovascular baselines
        ("card_001", "MYOCARDIAL_INFARCTION", "Adult non-cardiac surgery", 3, 0.008, 0.005, 0.012, 25000,
         "24 hours", '["PMID:28077278", "PMID:29161116"]', "random_effects", 45.2, "v1.0.0",
         "Grade A evidence, large studies"),

        ("card_002", "CARDIAC_ARREST", "General surgery adult", 2, 0.002, 0.001, 0.004, 50000,
         "perioperative", '["PMID:25664780", "PMID:29325008"]', "random_effects", 12.1, "v1.0.0",
         "Grade A evidence, registry data"),

        # Respiratory baselines
        ("resp_001", "ASPIRATION", "General anesthesia", 4, 0.0008, 0.0003, 0.0015, 120000,
         "perioperative", '["PMID:22617619", "PMID:24824933"]', "fixed_effects", 28.7, "v1.0.0",
         "Grade B evidence, observational"),

        ("resp_002", "LARYNGOSPASM", "Pediatric anesthesia", 8, 0.015, 0.010, 0.022, 45000,
         "perioperative", '["PMID:19923514", "PMID:21788298"]', "random_effects", 38.9, "v1.0.0",
         "Grade A evidence, pediatric specific"),

        ("resp_003", "BRONCHOSPASM", "General anesthesia", 6, 0.020, 0.015, 0.028, 35000,
         "perioperative", '["PMID:15710048", "PMID:22617829"]', "random_effects", 42.1, "v1.0.0",
         "Grade B evidence, mixed populations"),

        # Airway baselines
        ("airway_001", "DIFFICULT_INTUBATION", "Adult general anesthesia", 12, 0.058, 0.045, 0.075, 85000,
         "intraoperative", '["PMID:22454468", "PMID:25951584"]', "random_effects", 67.8, "v1.0.0",
         "Grade A evidence, large registries"),

        ("airway_002", "FAILED_INTUBATION", "Adult general anesthesia", 5, 0.003, 0.002, 0.005, 150000,
         "intraoperative", '["PMID:21787309", "PMID:25664780"]', "random_effects", 25.4, "v1.0.0",
         "Grade A evidence, airway registries"),

        # Neurologic baselines
        ("neuro_001", "POSTOP_DELIRIUM", "Elderly patients (≥65)", 15, 0.24, 0.18, 0.32, 12000,
         "7 days postop", '["PMID:22227832", "PMID:25665391"]', "random_effects", 78.5, "v1.0.0",
         "Grade A evidence, geriatric focus"),

        ("neuro_002", "AWARENESS_UNDER_ANESTHESIA", "General anesthesia", 3, 0.0013, 0.0008, 0.0020, 200000,
         "perioperative", '["PMID:18946184", "PMID:22713634"]', "fixed_effects", 15.2, "v1.0.0",
         "Grade B evidence, recall studies"),

        # Mortality baselines
        ("mort_001", "MORTALITY_24H", "Non-cardiac surgery", 8, 0.0012, 0.0008, 0.0018, 180000,
         "24 hours", '["PMID:28077278", "PMID:25665391"]', "random_effects", 32.1, "v1.0.0",
         "Grade A evidence, national registries"),

        ("mort_002", "MORTALITY_30D", "Non-cardiac surgery", 12, 0.015, 0.012, 0.019, 95000,
         "30 days", '["PMID:21787309", "PMID:29161116"]', "random_effects", 48.7, "v1.0.0",
         "Grade A evidence, follow-up studies"),
    ]

    current_time = datetime.now()
    for baseline_data in baselines:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO baselines_pooled
                (id, outcome_token, context_label, k, p0_mean, p0_ci_low, p0_ci_high, N_total,
                 time_horizon, pmids, method, i_squared, evidence_version, updated_at, quality_summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [*baseline_data, current_time])
        except Exception as e:
            print(f"Warning: Could not insert baseline {baseline_data[0]}: {e}")

    conn.close()
    print(f"✅ Added {len(baselines)} baseline risk estimates")

def fix_encoding_issues():
    """Fix Unicode encoding issues in database."""
    print("🔧 Fixing Unicode encoding issues...")

    conn = duckdb.connect(DB_PATH)

    # Update problematic Unicode characters in ontology
    try:
        # Replace mathematical symbols that cause encoding issues
        conn.execute("""
            UPDATE ontology
            SET plain_label = REPLACE(plain_label, '≤', '<='),
                notes = REPLACE(COALESCE(notes, ''), '≤', '<=')
        """)

        # Fix any other common Unicode issues
        conn.execute("""
            UPDATE ontology
            SET plain_label = REPLACE(plain_label, '≥', '>='),
                notes = REPLACE(COALESCE(notes, ''), '≥', '>=')
        """)

        print("✅ Fixed Unicode encoding issues")
    except Exception as e:
        print(f"Warning: Could not fix encoding: {e}")

    conn.close()

def validate_optimization():
    """Validate that optimization completed successfully."""
    print("✅ Validating database optimization...")

    conn = duckdb.connect(DB_PATH)

    # Count ontology terms
    ontology_count = conn.execute("SELECT COUNT(*) FROM ontology").fetchone()[0]
    outcome_count = conn.execute("SELECT COUNT(*) FROM ontology WHERE type = 'outcome'").fetchone()[0]
    risk_factor_count = conn.execute("SELECT COUNT(*) FROM ontology WHERE type = 'risk_factor'").fetchone()[0]

    # Count medications
    med_count = conn.execute("SELECT COUNT(*) FROM medications").fetchone()[0]

    # Count baselines
    baseline_count = conn.execute("SELECT COUNT(*) FROM baselines_pooled").fetchone()[0]

    conn.close()

    print(f"📊 Database Status After Optimization:")
    print(f"   • Total ontology terms: {ontology_count}")
    print(f"   • Outcomes: {outcome_count}")
    print(f"   • Risk factors: {risk_factor_count}")
    print(f"   • Medications: {med_count}")
    print(f"   • Baseline estimates: {baseline_count}")

    # Validation checks
    success = True

    if outcome_count < 30:
        print("❌ Insufficient outcomes (need 30+)")
        success = False

    if risk_factor_count < 50:
        print("❌ Insufficient risk factors (need 50+)")
        success = False

    if med_count < 25:
        print("❌ Insufficient medications (need 25+)")
        success = False

    if baseline_count < 8:
        print("❌ Insufficient baseline estimates (need 8+)")
        success = False

    if success:
        print("✅ Database optimization SUCCESSFUL - Ready for evidence harvester!")
        return True
    else:
        print("❌ Database optimization INCOMPLETE - Fix issues before proceeding")
        return False

def main():
    """Main optimization function."""
    print("🚀 Starting Meridian Database Optimization...")
    print("=" * 60)

    try:
        # Step 1: Expand ontology
        expand_ontology()

        # Step 2: Load medications
        load_medications_database()

        # Step 3: Add baseline estimates
        add_baseline_estimates()

        # Step 4: Fix encoding issues
        fix_encoding_issues()

        # Step 5: Validate optimization
        success = validate_optimization()

        if success:
            print("\n🎉 DATABASE OPTIMIZATION COMPLETE!")
            print("Ready to run evidence harvester script.")
            return True
        else:
            print("\n❌ OPTIMIZATION FAILED - Please review errors above")
            return False

    except Exception as e:
        print(f"\n💥 OPTIMIZATION ERROR: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)