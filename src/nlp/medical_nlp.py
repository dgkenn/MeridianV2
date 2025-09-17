#!/usr/bin/env python3
"""
Unified Medical NLP Engine for CODEX v2
Combines advanced medical text analysis capabilities for all features
"""

import re
import json
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, asdict, field
from enum import Enum
import duckdb
import os

logger = logging.getLogger(__name__)

class ConfidenceLevel(Enum):
    """Confidence levels for NLP extractions"""
    HIGH = "high"        # 0.8-1.0
    MEDIUM = "medium"    # 0.5-0.8
    LOW = "low"          # 0.2-0.5
    VERY_LOW = "very_low"  # 0.0-0.2

class ClinicalSeverity(Enum):
    """Clinical severity classifications"""
    CRITICAL = "critical"
    SEVERE = "severe"
    MODERATE = "moderate"
    MILD = "mild"
    MINIMAL = "minimal"

class TemporalContext(Enum):
    """Temporal context for clinical events"""
    ACUTE = "acute"           # <24 hours
    SUBACUTE = "subacute"     # 24h - 7 days
    CHRONIC = "chronic"       # >7 days
    HISTORICAL = "historical" # Past medical history
    UNKNOWN = "unknown"

@dataclass
class ClinicalEntity:
    """Enhanced clinical entity with full context"""
    # Core identification
    raw_text: str                    # Original text found
    normalized_term: str             # Standardized medical term
    ontology_code: str              # Standard medical code (ICD-10, SNOMED, etc.)
    category: str                   # Entity category (symptom, medication, etc.)

    # Clinical context
    severity: ClinicalSeverity      # Clinical severity
    temporal_context: TemporalContext  # When it occurred
    confidence: float               # Extraction confidence (0.0-1.0)

    # Detailed attributes
    modifiers: Dict[str, Any] = field(default_factory=dict)  # Additional qualifiers
    relationships: List[str] = field(default_factory=list)   # Related entities
    evidence_spans: List[Tuple[int, int]] = field(default_factory=list)  # Text positions

    # Medical specifics
    duration: Optional[str] = None   # How long present
    frequency: Optional[str] = None  # How often occurs
    triggers: List[str] = field(default_factory=list)  # What causes it
    relievers: List[str] = field(default_factory=list)  # What helps it

@dataclass
class MedicationEntity(ClinicalEntity):
    """Specialized entity for medications"""
    dose: Optional[str] = None
    frequency: Optional[str] = None
    route: Optional[str] = None
    indication: Optional[str] = None
    duration_therapy: Optional[str] = None
    compliance: Optional[str] = None
    effectiveness: Optional[str] = None

@dataclass
class SymptomEntity(ClinicalEntity):
    """Specialized entity for symptoms"""
    pain_scale: Optional[int] = None
    character_descriptors: List[str] = field(default_factory=list)
    location: Optional[str] = None
    radiation: Optional[str] = None
    associated_symptoms: List[str] = field(default_factory=list)

@dataclass
class RiskFactorEntity(ClinicalEntity):
    """Specialized entity for risk factors"""
    risk_type: str = ""  # modifiable, non-modifiable, acquired
    impact_level: ClinicalSeverity = ClinicalSeverity.MODERATE
    controlled_status: Optional[str] = None  # well-controlled, poorly-controlled
    complications: List[str] = field(default_factory=list)

@dataclass
class ClinicalTimeline:
    """Timeline of clinical events"""
    events: List[Dict[str, Any]] = field(default_factory=list)

    def add_event(self, entity: ClinicalEntity, timestamp: str):
        """Add an event to the timeline"""
        self.events.append({
            'entity': entity,
            'timestamp': timestamp,
            'confidence': entity.confidence
        })

    def get_recent_events(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get events within specified time window"""
        # Implementation for temporal filtering
        return [e for e in self.events if e['entity'].temporal_context == TemporalContext.ACUTE]

@dataclass
class HPIAnalysis:
    """Complete HPI analysis with structured medical insights"""
    # Core identification
    analysis_id: str
    session_id: str
    raw_hpi_text: str
    cleaned_hpi_text: str

    # Extracted entities by category
    symptoms: List[SymptomEntity] = field(default_factory=list)
    medications: List[MedicationEntity] = field(default_factory=list)
    risk_factors: List[RiskFactorEntity] = field(default_factory=list)
    procedures: List[ClinicalEntity] = field(default_factory=list)
    allergies: List[ClinicalEntity] = field(default_factory=list)

    # Clinical insights
    timeline: ClinicalTimeline = field(default_factory=ClinicalTimeline)
    chief_complaint: Optional[str] = None
    clinical_impression: Optional[str] = None

    # Quality metrics
    overall_confidence: float = 0.0
    completeness_score: float = 0.0
    complexity_score: float = 0.0

    # Metadata
    analysis_timestamp: datetime = field(default_factory=datetime.now)
    nlp_model_version: str = "2.0.1"

class UnifiedMedicalNLP:
    """
    Unified Medical NLP Engine
    Single analysis pipeline for all CODEX v2 features
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join('database', 'codex.duckdb')

        # Enhanced medical pattern recognition
        self.medical_patterns = self._initialize_patterns()

        # Load ontology mapping for standardization
        self.ontology_mapping = self._load_ontology()

        # Analysis caching for performance
        self._analysis_cache = {}

        logger.info("Unified Medical NLP Engine initialized")

    def _initialize_patterns(self) -> Dict[str, Dict[str, List[str]]]:
        """Initialize comprehensive medical pattern recognition"""
        return {
            'symptoms': {
                'pain': [
                    r'\b(?:pain|ache|discomfort|soreness|hurt|burning|stabbing|crushing|sharp|dull)\b',
                    r'\b(?:chest pain|abdominal pain|back pain|headache|joint pain)\b',
                    r'\b(?:\d+/10|[0-9]/10)\s*(?:pain|scale)\b'
                ],
                'cardiovascular': [
                    r'\b(?:palpitations|arrhythmia|irregular heartbeat|tachycardia|bradycardia)\b',
                    r'\b(?:chest pain|angina|chest tightness|chest pressure)\b',
                    r'\b(?:dyspnea|shortness of breath|sob|breathing difficulty)\b'
                ],
                'gastrointestinal': [
                    r'\b(?:nausea|vomiting|emesis|retching)\b',
                    r'\b(?:diarrhea|constipation|bowel changes)\b',
                    r'\b(?:abdominal pain|stomach pain|belly pain)\b'
                ],
                'neurological': [
                    r'\b(?:headache|cephalgia|migraine|tension headache)\b',
                    r'\b(?:dizziness|vertigo|lightheaded|unsteady)\b',
                    r'\b(?:syncope|fainting|passed out|lost consciousness)\b'
                ],
                'respiratory': [
                    r'\b(?:cough|wheeze|stridor|hemoptysis)\b',
                    r'\b(?:dyspnea|shortness of breath|sob|tachypnea)\b',
                    r'\b(?:chest pain|pleuritic pain)\b'
                ]
            },
            'medications': {
                'cardiac': [
                    r'\b(?:metoprolol|atenolol|propranolol|carvedilol|bisoprolol)\b',  # Beta-blockers
                    r'\b(?:lisinopril|enalapril|captopril|losartan|valsartan)\b',     # ACE/ARB
                    r'\b(?:amlodipine|nifedipine|diltiazem|verapamil)\b',             # CCB
                    r'\b(?:digoxin|amiodarone|flecainide)\b'                         # Antiarrhythmics
                ],
                'diabetes': [
                    r'\b(?:metformin|glipizide|glyburide|pioglitazone)\b',
                    r'\b(?:insulin|lantus|humalog|novolog|levemir)\b'
                ],
                'pain': [
                    r'\b(?:acetaminophen|tylenol|paracetamol)\b',
                    r'\b(?:ibuprofen|advil|motrin|naproxen|aleve)\b',
                    r'\b(?:morphine|oxycodone|hydrocodone|fentanyl|tramadol)\b'
                ],
                'anticoagulation': [
                    r'\b(?:warfarin|coumadin|heparin|enoxaparin|lovenox)\b',
                    r'\b(?:rivaroxaban|xarelto|apixaban|eliquis|dabigatran)\b'
                ]
            },
            'risk_factors': {
                'cardiac': [
                    r'\b(?:hypertension|htn|high blood pressure)\b',
                    r'\b(?:coronary artery disease|cad|heart disease)\b',
                    r'\b(?:heart failure|chf|cardiomyopathy)\b',
                    r'\b(?:prior mi|previous heart attack|myocardial infarction)\b'
                ],
                'metabolic': [
                    r'\b(?:diabetes|diabetic|dm|type 1|type 2|t1dm|t2dm)\b',
                    r'\b(?:obesity|obese|overweight|high bmi)\b',
                    r'\b(?:metabolic syndrome|insulin resistance)\b'
                ],
                'pulmonary': [
                    r'\b(?:copd|emphysema|chronic bronchitis)\b',
                    r'\b(?:asthma|reactive airway disease|rad)\b',
                    r'\b(?:sleep apnea|osa|obstructive sleep apnea)\b'
                ],
                'lifestyle': [
                    r'\b(?:smoking|smoker|tobacco|cigarettes|pack year)\b',
                    r'\b(?:alcohol|drinking|etoh|alcoholism)\b',
                    r'\b(?:sedentary|inactive|poor exercise tolerance)\b'
                ]
            },
            'temporal_markers': {
                'acute': [
                    r'\b(?:now|currently|today|this morning|this afternoon|tonight)\b',
                    r'\b(?:sudden|acute|abrupt|rapid onset)\b',
                    r'\b(?:\d+\s*(?:minutes?|hours?)\s*ago)\b'
                ],
                'subacute': [
                    r'\b(?:yesterday|last night|past day|24 hours)\b',
                    r'\b(?:\d+\s*days?\s*ago)\b',
                    r'\b(?:this week|past week|recent)\b'
                ],
                'chronic': [
                    r'\b(?:chronic|long-standing|ongoing|persistent)\b',
                    r'\b(?:months?|years?)\s*(?:ago|duration|history)\b',
                    r'\b(?:since|for the past)\s*\d+\s*(?:months?|years?)\b'
                ]
            },
            'severity_indicators': {
                'quantitative': [
                    r'\b(?:10/10|9/10|8/10|7/10|6/10|5/10|4/10|3/10|2/10|1/10)\b',
                    r'\b(?:severe|moderate|mild|minimal|slight)\b'
                ],
                'qualitative': [
                    r'\b(?:excruciating|unbearable|agonizing|intense)\b',  # Severe
                    r'\b(?:crushing|stabbing|sharp|burning|throbbing)\b',   # Character
                    r'\b(?:tolerable|manageable|bearable|comfortable)\b'    # Mild
                ]
            }
        }

    def _load_ontology(self) -> Dict[str, Any]:
        """Load medical ontology for term standardization"""
        try:
            db = duckdb.connect(self.db_path)
            ontology_data = db.execute("""
                SELECT token, synonyms, display_name, category
                FROM ontology
            """).fetchall()
            db.close()

            ontology = {}
            for token, synonyms, display_name, category in ontology_data:
                ontology[token] = {
                    'display_name': display_name,
                    'category': category,
                    'synonyms': json.loads(synonyms) if synonyms else []
                }
            return ontology

        except Exception as e:
            logger.warning(f"Could not load ontology: {e}")
            return {}

    def analyze_hpi(self, hpi_text: str, session_id: str = None) -> HPIAnalysis:
        """
        Main analysis entry point
        Single comprehensive analysis for all downstream features
        """
        if not hpi_text or not hpi_text.strip():
            raise ValueError("HPI text cannot be empty")

        # Generate unique analysis ID
        analysis_id = str(uuid.uuid4())
        session_id = session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Check cache first
        cache_key = f"{session_id}_{hash(hpi_text)}"
        if cache_key in self._analysis_cache:
            logger.info(f"Returning cached analysis for session {session_id}")
            return self._analysis_cache[cache_key]

        logger.info(f"Starting comprehensive HPI analysis for session {session_id}")

        # Clean and normalize text
        cleaned_text = self._clean_text(hpi_text)

        # Extract all entity types
        symptoms = self._extract_symptoms(cleaned_text)
        medications = self._extract_medications(cleaned_text)
        risk_factors = self._extract_risk_factors(cleaned_text)
        procedures = self._extract_procedures(cleaned_text)
        allergies = self._extract_allergies(cleaned_text)

        # Build clinical timeline
        timeline = self._build_timeline(symptoms + medications + risk_factors + procedures)

        # Calculate quality metrics
        overall_confidence = self._calculate_overall_confidence([symptoms, medications, risk_factors])
        completeness_score = self._calculate_completeness(hpi_text, symptoms, medications, risk_factors)
        complexity_score = self._calculate_complexity(symptoms, medications, risk_factors, timeline)

        # Create comprehensive analysis
        analysis = HPIAnalysis(
            analysis_id=analysis_id,
            session_id=session_id,
            raw_hpi_text=hpi_text,
            cleaned_hpi_text=cleaned_text,
            symptoms=symptoms,
            medications=medications,
            risk_factors=risk_factors,
            procedures=procedures,
            allergies=allergies,
            timeline=timeline,
            chief_complaint=self._extract_chief_complaint(cleaned_text, symptoms),
            overall_confidence=overall_confidence,
            completeness_score=completeness_score,
            complexity_score=complexity_score
        )

        # Cache the analysis
        self._analysis_cache[cache_key] = analysis

        logger.info(f"Analysis complete - Confidence: {overall_confidence:.2f}, "
                   f"Entities: {len(symptoms + medications + risk_factors + procedures)}")

        return analysis

    def _clean_text(self, text: str) -> str:
        """Clean and normalize HPI text"""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())

        # Normalize common abbreviations
        abbreviations = {
            r'\byo\b': 'year old',
            r'\bYO\b': 'year old',
            r'\bw/\b': 'with',
            r'\bw/o\b': 'without',
            r'\bh/o\b': 'history of',
            r'\bp/w\b': 'presents with',
            r'\bc/o\b': 'complains of',
            r'\bCAD\b': 'coronary artery disease',
            r'\bCHF\b': 'heart failure',
            r'\bHTN\b': 'hypertension',
            r'\bDM\b': 'diabetes mellitus',
            r'\bCOPD\b': 'chronic obstructive pulmonary disease'
        }

        for abbrev, expansion in abbreviations.items():
            text = re.sub(abbrev, expansion, text, flags=re.IGNORECASE)

        return text

    def _extract_symptoms(self, text: str) -> List[SymptomEntity]:
        """Extract symptom entities with clinical context"""
        symptoms = []

        for category, patterns in self.medical_patterns['symptoms'].items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    symptom = self._create_symptom_entity(match, text, category)
                    if symptom:
                        symptoms.append(symptom)

        return self._deduplicate_entities(symptoms)

    def _extract_medications(self, text: str) -> List[MedicationEntity]:
        """Extract medication entities with dosing context"""
        medications = []

        for category, patterns in self.medical_patterns['medications'].items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    medication = self._create_medication_entity(match, text, category)
                    if medication:
                        medications.append(medication)

        return self._deduplicate_entities(medications)

    def _extract_risk_factors(self, text: str) -> List[RiskFactorEntity]:
        """Extract risk factor entities with control status"""
        risk_factors = []

        for category, patterns in self.medical_patterns['risk_factors'].items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    risk_factor = self._create_risk_factor_entity(match, text, category)
                    if risk_factor:
                        risk_factors.append(risk_factor)

        return self._deduplicate_entities(risk_factors)

    def _extract_procedures(self, text: str) -> List[ClinicalEntity]:
        """Extract procedure/surgical history"""
        # Implementation for procedure extraction
        return []

    def _extract_allergies(self, text: str) -> List[ClinicalEntity]:
        """Extract allergy information"""
        # Implementation for allergy extraction
        return []

    def _create_symptom_entity(self, match, text: str, category: str) -> Optional[SymptomEntity]:
        """Create detailed symptom entity from text match"""
        raw_text = match.group(0)

        # Extract context around the match
        start, end = match.span()
        context_start = max(0, start - 50)
        context_end = min(len(text), end + 50)
        context = text[context_start:context_end]

        # Determine severity
        severity = self._determine_severity(context)

        # Determine temporal context
        temporal = self._determine_temporal_context(context)

        # Extract pain scale if present
        pain_scale = self._extract_pain_scale(context)

        # Calculate confidence
        confidence = self._calculate_entity_confidence(raw_text, context, category)

        return SymptomEntity(
            raw_text=raw_text,
            normalized_term=self._normalize_term(raw_text, 'symptom'),
            ontology_code=self._get_ontology_code(raw_text, 'symptom'),
            category=f"symptom_{category}",
            severity=severity,
            temporal_context=temporal,
            confidence=confidence,
            pain_scale=pain_scale,
            evidence_spans=[(start, end)]
        )

    def _create_medication_entity(self, match, text: str, category: str) -> Optional[MedicationEntity]:
        """Create detailed medication entity from text match"""
        raw_text = match.group(0)

        # Extract context around the match
        start, end = match.span()
        context_start = max(0, start - 100)
        context_end = min(len(text), end + 100)
        context = text[context_start:context_end]

        # Extract dosing information
        dose = self._extract_dose(context)
        frequency = self._extract_frequency(context)

        # Determine temporal context
        temporal = self._determine_temporal_context(context)

        # Calculate confidence
        confidence = self._calculate_entity_confidence(raw_text, context, category)

        return MedicationEntity(
            raw_text=raw_text,
            normalized_term=self._normalize_term(raw_text, 'medication'),
            ontology_code=self._get_ontology_code(raw_text, 'medication'),
            category=f"medication_{category}",
            severity=ClinicalSeverity.MODERATE,  # Default for medications
            temporal_context=temporal,
            confidence=confidence,
            dose=dose,
            frequency=frequency,
            evidence_spans=[(start, end)]
        )

    def _create_risk_factor_entity(self, match, text: str, category: str) -> Optional[RiskFactorEntity]:
        """Create detailed risk factor entity from text match"""
        raw_text = match.group(0)

        # Extract context around the match
        start, end = match.span()
        context_start = max(0, start - 100)
        context_end = min(len(text), end + 100)
        context = text[context_start:context_end]

        # Determine control status
        controlled_status = self._determine_control_status(context)

        # Determine severity/impact
        severity = self._determine_risk_severity(raw_text, context)

        # Determine temporal context
        temporal = self._determine_temporal_context(context)

        # Calculate confidence
        confidence = self._calculate_entity_confidence(raw_text, context, category)

        return RiskFactorEntity(
            raw_text=raw_text,
            normalized_term=self._normalize_term(raw_text, 'risk_factor'),
            ontology_code=self._get_ontology_code(raw_text, 'risk_factor'),
            category=f"risk_factor_{category}",
            severity=severity,
            temporal_context=temporal,
            confidence=confidence,
            risk_type=category,
            impact_level=severity,
            controlled_status=controlled_status,
            evidence_spans=[(start, end)]
        )

    # Helper methods for entity creation and analysis
    def _determine_severity(self, context: str) -> ClinicalSeverity:
        """Determine clinical severity from context"""
        context_lower = context.lower()

        if any(word in context_lower for word in ['severe', 'excruciating', '9/10', '10/10', 'unbearable']):
            return ClinicalSeverity.SEVERE
        elif any(word in context_lower for word in ['moderate', '6/10', '7/10', '8/10']):
            return ClinicalSeverity.MODERATE
        elif any(word in context_lower for word in ['mild', '3/10', '4/10', '5/10', 'tolerable']):
            return ClinicalSeverity.MILD
        elif any(word in context_lower for word in ['minimal', '1/10', '2/10', 'slight']):
            return ClinicalSeverity.MINIMAL
        else:
            return ClinicalSeverity.MODERATE  # Default

    def _determine_temporal_context(self, context: str) -> TemporalContext:
        """Determine temporal context from surrounding text"""
        context_lower = context.lower()

        if any(word in context_lower for word in ['acute', 'sudden', 'hours ago', 'minutes ago', 'now', 'currently']):
            return TemporalContext.ACUTE
        elif any(word in context_lower for word in ['days ago', 'yesterday', 'recent', 'past week']):
            return TemporalContext.SUBACUTE
        elif any(word in context_lower for word in ['chronic', 'long-standing', 'months', 'years', 'history of']):
            return TemporalContext.CHRONIC
        elif any(word in context_lower for word in ['history', 'prior', 'previous', 'past']):
            return TemporalContext.HISTORICAL
        else:
            return TemporalContext.UNKNOWN

    def _extract_pain_scale(self, context: str) -> Optional[int]:
        """Extract numeric pain scale from context"""
        pain_match = re.search(r'(\d+)/10', context)
        if pain_match:
            return int(pain_match.group(1))
        return None

    def _extract_dose(self, context: str) -> Optional[str]:
        """Extract medication dose from context"""
        dose_patterns = [
            r'(\d+(?:\.\d+)?)\s*(?:mg|mcg|g|units?)',
            r'(\d+(?:\.\d+)?)\s*(?:milligrams?|micrograms?|grams?)'
        ]

        for pattern in dose_patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if match:
                return match.group(0)
        return None

    def _extract_frequency(self, context: str) -> Optional[str]:
        """Extract medication frequency from context"""
        freq_patterns = [
            r'(?:once|twice|three times?|four times?)\s*(?:daily|a day|per day)',
            r'(?:bid|tid|qid|qd|q\d+h)',
            r'every\s*\d+\s*hours?'
        ]

        for pattern in freq_patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if match:
                return match.group(0)
        return None

    def _determine_control_status(self, context: str) -> Optional[str]:
        """Determine if a condition is well-controlled or not"""
        context_lower = context.lower()

        if any(phrase in context_lower for phrase in ['well-controlled', 'well controlled', 'stable', 'managed']):
            return 'well-controlled'
        elif any(phrase in context_lower for phrase in ['poorly controlled', 'uncontrolled', 'unstable']):
            return 'poorly-controlled'
        else:
            return None

    def _determine_risk_severity(self, term: str, context: str) -> ClinicalSeverity:
        """Determine the severity/impact of a risk factor"""
        # Risk factor specific severity mapping
        high_impact_conditions = ['heart failure', 'copd', 'dialysis', 'prior mi']
        moderate_impact_conditions = ['diabetes', 'hypertension', 'asthma']

        term_lower = term.lower()

        if any(condition in term_lower for condition in high_impact_conditions):
            return ClinicalSeverity.SEVERE
        elif any(condition in term_lower for condition in moderate_impact_conditions):
            return ClinicalSeverity.MODERATE
        else:
            return ClinicalSeverity.MILD

    def _calculate_entity_confidence(self, term: str, context: str, category: str) -> float:
        """Calculate confidence score for entity extraction"""
        confidence = 0.5  # Base confidence

        # Boost confidence for exact medical term matches
        if term.lower() in ['diabetes', 'hypertension', 'asthma', 'copd']:
            confidence += 0.3

        # Boost confidence for context clues
        if any(word in context.lower() for word in ['diagnosed', 'history of', 'known']):
            confidence += 0.2

        # Boost confidence for quantitative measures
        if re.search(r'\d+', context):
            confidence += 0.1

        return min(confidence, 1.0)

    def _normalize_term(self, term: str, entity_type: str) -> str:
        """Normalize medical term to standard form"""
        # Check ontology mapping first
        for ontology_term, data in self.ontology_mapping.items():
            if term.lower() in [syn.lower() for syn in data.get('synonyms', [])]:
                return data['display_name']

        # Default normalization
        return term.lower().strip()

    def _get_ontology_code(self, term: str, entity_type: str) -> str:
        """Get standardized medical code for term"""
        # For now, return a placeholder - could integrate with SNOMED, ICD-10
        return f"{entity_type}_{term.lower().replace(' ', '_')}"

    def _build_timeline(self, entities: List[ClinicalEntity]) -> ClinicalTimeline:
        """Build clinical timeline from extracted entities"""
        timeline = ClinicalTimeline()

        # Sort entities by temporal context
        temporal_order = {
            TemporalContext.ACUTE: 1,
            TemporalContext.SUBACUTE: 2,
            TemporalContext.CHRONIC: 3,
            TemporalContext.HISTORICAL: 4,
            TemporalContext.UNKNOWN: 5
        }

        sorted_entities = sorted(entities, key=lambda e: temporal_order[e.temporal_context])

        for entity in sorted_entities:
            timeline.add_event(entity, entity.temporal_context.value)

        return timeline

    def _extract_chief_complaint(self, text: str, symptoms: List[SymptomEntity]) -> Optional[str]:
        """Extract the primary chief complaint"""
        if not symptoms:
            return None

        # Find the most prominent symptom (highest confidence, most severe)
        primary_symptom = max(symptoms, key=lambda s: s.confidence * (5 - list(ClinicalSeverity).index(s.severity)))

        return primary_symptom.normalized_term

    def _calculate_overall_confidence(self, entity_lists: List[List[ClinicalEntity]]) -> float:
        """Calculate overall analysis confidence"""
        all_entities = [entity for sublist in entity_lists for entity in sublist]

        if not all_entities:
            return 0.0

        return sum(entity.confidence for entity in all_entities) / len(all_entities)

    def _calculate_completeness(self, hpi_text: str, symptoms: List, medications: List, risk_factors: List) -> float:
        """Calculate how complete the analysis appears to be"""
        completeness = 0.0

        # Check for key components
        if symptoms:
            completeness += 0.4
        if medications:
            completeness += 0.3
        if risk_factors:
            completeness += 0.3

        # Bonus for detailed HPI
        if len(hpi_text.split()) > 50:
            completeness += 0.1

        return min(completeness, 1.0)

    def _calculate_complexity(self, symptoms: List, medications: List, risk_factors: List, timeline: ClinicalTimeline) -> float:
        """Calculate case complexity score"""
        complexity = 0.0

        # Number of entities
        total_entities = len(symptoms) + len(medications) + len(risk_factors)
        complexity += min(total_entities * 0.1, 0.5)

        # Number of timeline events
        complexity += min(len(timeline.events) * 0.05, 0.3)

        # Severity of conditions
        severe_conditions = [e for e in symptoms + risk_factors if e.severity == ClinicalSeverity.SEVERE]
        complexity += min(len(severe_conditions) * 0.1, 0.2)

        return min(complexity, 1.0)

    def _deduplicate_entities(self, entities: List[ClinicalEntity]) -> List[ClinicalEntity]:
        """Remove duplicate entities based on normalized terms"""
        seen_terms = set()
        unique_entities = []

        for entity in entities:
            if entity.normalized_term not in seen_terms:
                seen_terms.add(entity.normalized_term)
                unique_entities.append(entity)

        return unique_entities

    def get_analysis_summary(self, analysis: HPIAnalysis) -> Dict[str, Any]:
        """Get a summary of the analysis for reporting"""
        return {
            'analysis_id': analysis.analysis_id,
            'session_id': analysis.session_id,
            'confidence': analysis.overall_confidence,
            'completeness': analysis.completeness_score,
            'complexity': analysis.complexity_score,
            'entity_counts': {
                'symptoms': len(analysis.symptoms),
                'medications': len(analysis.medications),
                'risk_factors': len(analysis.risk_factors),
                'procedures': len(analysis.procedures),
                'allergies': len(analysis.allergies)
            },
            'chief_complaint': analysis.chief_complaint,
            'timeline_events': len(analysis.timeline.events)
        }

    # Backward compatibility methods for existing system integration
    def get_extracted_factors_legacy(self, analysis: HPIAnalysis) -> List[Dict[str, Any]]:
        """
        Convert comprehensive analysis to legacy ExtractedFactor format
        For backward compatibility with existing risk calculation system
        """
        legacy_factors = []

        # Convert symptoms to legacy format
        for symptom in analysis.symptoms:
            legacy_factors.append(self._entity_to_legacy_factor(symptom))

        # Convert risk factors to legacy format
        for risk_factor in analysis.risk_factors:
            legacy_factors.append(self._entity_to_legacy_factor(risk_factor))

        # Convert medications to legacy format
        for medication in analysis.medications:
            legacy_factors.append(self._entity_to_legacy_factor(medication))

        return legacy_factors

    def _entity_to_legacy_factor(self, entity: ClinicalEntity) -> Dict[str, Any]:
        """Convert a ClinicalEntity to legacy factor format"""
        return {
            'token': entity.ontology_code,
            'plain_label': entity.normalized_term,
            'confidence': entity.confidence,
            'evidence_text': entity.raw_text,
            'factor_type': entity.category,
            'category': entity.category,
            'severity_weight': self._severity_to_weight(entity.severity),
            'context': ' '.join([entity.raw_text, str(entity.temporal_context.value)])
        }

    def _severity_to_weight(self, severity: ClinicalSeverity) -> float:
        """Convert ClinicalSeverity to numeric weight for legacy system"""
        severity_weights = {
            ClinicalSeverity.CRITICAL: 1.0,
            ClinicalSeverity.SEVERE: 0.8,
            ClinicalSeverity.MODERATE: 0.6,
            ClinicalSeverity.MILD: 0.4,
            ClinicalSeverity.MINIMAL: 0.2
        }
        return severity_weights.get(severity, 0.6)

    def parse_hpi_legacy(self, hpi_text: str, session_id: str = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Legacy interface that returns factors and demographics in old format
        Maintains compatibility with existing app_simple.py integration
        """
        # Perform comprehensive analysis
        analysis = self.analyze_hpi(hpi_text, session_id)

        # Convert to legacy factors format
        factors = self.get_extracted_factors_legacy(analysis)

        # Extract demographics in legacy format
        demographics = self._extract_demographics_legacy(hpi_text)

        return factors, demographics

    def _extract_demographics_legacy(self, text: str) -> Dict[str, Any]:
        """Extract demographics in legacy format for backward compatibility"""
        demographics = {
            'age': None,
            'age_category': None,
            'weight': None,
            'gender': None
        }

        # Age extraction
        age_patterns = [
            r'(\d+)\s*(?:year|yr|y)[\s-]?old',
            r'age:?\s*(\d+)',
            r'(\d{1,2})\s*(?:years?|yrs?)'
        ]

        for pattern in age_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                age = int(match.group(1))
                demographics['age'] = age
                demographics['age_category'] = self._get_age_category(age)
                break

        # Weight extraction
        weight_patterns = [
            r'weight:?\s*(\d+(?:\.\d+)?)\s*(?:kg|kilograms?)',
            r'(\d+(?:\.\d+)?)\s*(?:kg|kilograms?)',
            r'wt:?\s*(\d+(?:\.\d+)?)'
        ]

        for pattern in weight_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                demographics['weight'] = float(match.group(1))
                break

        # Gender extraction (basic)
        if re.search(r'\bmale\b', text, re.IGNORECASE) and not re.search(r'\bfemale\b', text, re.IGNORECASE):
            demographics['gender'] = 'male'
        elif re.search(r'\bfemale\b', text, re.IGNORECASE):
            demographics['gender'] = 'female'

        return demographics

    def _get_age_category(self, age: int) -> str:
        """Categorize age for risk calculation compatibility"""
        if age < 1:
            return 'AGE_NEONATE'
        elif 1 <= age <= 5:
            return 'AGE_1_5'
        elif 6 <= age <= 12:
            return 'AGE_6_12'
        elif 13 <= age <= 17:
            return 'AGE_13_17'
        elif 18 <= age <= 64:
            return 'AGE_ADULT'
        else:  # age >= 65
            return 'AGE_ELDERLY'

    def store_analysis(self, analysis: HPIAnalysis) -> bool:
        """Store comprehensive analysis in database"""
        try:
            db = duckdb.connect(self.db_path)

            # Store main analysis record
            db.execute("""
                INSERT OR REPLACE INTO hpi_analysis_v2 (
                    analysis_id, session_id, raw_hpi_text, cleaned_hpi_text,
                    overall_confidence, completeness_score, complexity_score,
                    chief_complaint, clinical_impression,
                    symptoms_json, medications_json, risk_factors_json,
                    procedures_json, allergies_json, timeline_json,
                    analysis_timestamp, nlp_model_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                analysis.analysis_id,
                analysis.session_id,
                analysis.raw_hpi_text,
                analysis.cleaned_hpi_text,
                analysis.overall_confidence,
                analysis.completeness_score,
                analysis.complexity_score,
                analysis.chief_complaint,
                analysis.clinical_impression,
                json.dumps([asdict(s) for s in analysis.symptoms], default=str),
                json.dumps([asdict(m) for m in analysis.medications], default=str),
                json.dumps([asdict(r) for r in analysis.risk_factors], default=str),
                json.dumps([asdict(p) for p in analysis.procedures], default=str),
                json.dumps([asdict(a) for a in analysis.allergies], default=str),
                json.dumps(asdict(analysis.timeline), default=str),
                analysis.analysis_timestamp,
                analysis.nlp_model_version
            ])

            db.close()
            logger.info(f"Stored comprehensive analysis {analysis.analysis_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to store analysis: {e}")
            return False

# Example usage and testing
if __name__ == "__main__":
    # Test the unified NLP engine
    nlp = UnifiedMedicalNLP()

    sample_hpi = """
    65 year old male with history of diabetes mellitus type 2, hypertension, and COPD presents with
    acute onset chest pain that started 2 hours ago. Patient describes the pain as crushing,
    8/10 severity, radiating to left arm. Associated with nausea and diaphoresis.
    Patient takes metoprolol 50mg twice daily and lisinopril 10mg daily.
    No prior surgeries. Smoking history of 30 pack-years, quit 5 years ago.
    """

    print("Testing Unified Medical NLP Engine...")
    print(f"Sample HPI: {sample_hpi}")

    try:
        # Test comprehensive analysis
        analysis = nlp.analyze_hpi(sample_hpi, "test_session_unified")

        print(f"\\nAnalysis Results:")
        print(f"Overall Confidence: {analysis.overall_confidence:.2f}")
        print(f"Completeness: {analysis.completeness_score:.2f}")
        print(f"Complexity: {analysis.complexity_score:.2f}")
        print(f"Chief Complaint: {analysis.chief_complaint}")
        print(f"\\nExtracted Entities:")
        print(f"- Symptoms: {len(analysis.symptoms)}")
        print(f"- Medications: {len(analysis.medications)}")
        print(f"- Risk Factors: {len(analysis.risk_factors)}")
        print(f"- Timeline Events: {len(analysis.timeline.events)}")

        # Test legacy compatibility
        factors, demographics = nlp.parse_hpi_legacy(sample_hpi, "test_session_legacy")
        print(f"\\nLegacy Compatibility:")
        print(f"- Legacy Factors: {len(factors)}")
        print(f"- Demographics: {demographics}")

        # Store analysis
        stored = nlp.store_analysis(analysis)
        print(f"Analysis stored: {stored}")

        print("\\nUnified Medical NLP Engine test completed successfully!")

    except Exception as e:
        print(f"Error testing unified NLP engine: {e}")
        import traceback
        traceback.print_exc()