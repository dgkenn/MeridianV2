#!/usr/bin/env python3
"""
HPI Text Analysis Engine
Analyzes complete HPI text to extract clinical entities, timeline, and context
"""

import re
import json
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import duckdb
import os

class HPIAnalyzer:
    """Analyzes HPI text to extract medical entities and clinical context"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join('database', 'codex.duckdb')

        # Medical terminology patterns
        self.medical_patterns = {
            'symptoms': [
                r'\b(?:pain|ache|discomfort|soreness)\b',
                r'\b(?:nausea|vomiting|emesis)\b',
                r'\b(?:dyspnea|shortness of breath|sob)\b',
                r'\b(?:chest pain|angina)\b',
                r'\b(?:palpitations|arrhythmia)\b',
                r'\b(?:syncope|fainting|passed out)\b',
                r'\b(?:fever|chills|rigors)\b',
                r'\b(?:headache|cephalgia)\b',
                r'\b(?:fatigue|weakness|malaise)\b',
                r'\b(?:cough|wheeze|stridor)\b'
            ],
            'medications': [
                r'\b(?:aspirin|acetaminophen|ibuprofen|naproxen)\b',
                r'\b(?:metoprolol|atenolol|propranolol)\b',
                r'\b(?:lisinopril|enalapril|losartan)\b',
                r'\b(?:metformin|insulin|glipizide)\b',
                r'\b(?:warfarin|heparin|enoxaparin)\b',
                r'\b(?:prednisone|prednisolone|methylprednisolone)\b',
                r'\b(?:albuterol|inhaler|nebulizer)\b'
            ],
            'procedures': [
                r'\b(?:surgery|operation|procedure)\b',
                r'\b(?:appendectomy|cholecystectomy|mastectomy)\b',
                r'\b(?:catheterization|angioplasty|stent)\b',
                r'\b(?:intubation|mechanical ventilation)\b',
                r'\b(?:dialysis|hemodialysis|peritoneal dialysis)\b',
                r'\b(?:biopsy|resection|excision)\b'
            ],
            'temporal_markers': [
                r'\b(?:today|yesterday|this morning|this evening)\b',
                r'\b(?:last week|last month|last year)\b',
                r'\b(?:\d+\s*(?:days?|weeks?|months?|years?)\s*ago)\b',
                r'\b(?:since|for the past|over the last)\b',
                r'\b(?:acute|chronic|subacute)\b',
                r'\b(?:sudden|gradual|progressive)\b'
            ],
            'severity_indicators': [
                r'\b(?:severe|mild|moderate|intense)\b',
                r'\b(?:10/10|9/10|8/10|7/10|6/10)\b',
                r'\b(?:worst|better|worse|improving|worsening)\b',
                r'\b(?:debilitating|incapacitating|tolerable)\b'
            ],
            'risk_factors': [
                r'\b(?:diabetes|diabetic|dm)\b',
                r'\b(?:hypertension|htn|high blood pressure)\b',
                r'\b(?:heart failure|chf|cardiomyopathy)\b',
                r'\b(?:copd|asthma|emphysema)\b',
                r'\b(?:renal failure|kidney disease|ckd)\b',
                r'\b(?:obesity|obese|bmi)\b',
                r'\b(?:smoking|smoker|tobacco)\b',
                r'\b(?:alcohol|drinking|etoh)\b'
            ]
        }

        # Load ontology for mapping terms
        self.ontology_mapping = self._load_ontology()

    def _load_ontology(self) -> Dict[str, str]:
        """Load medical ontology for term standardization"""
        try:
            conn = duckdb.connect(self.db_path)
            result = conn.execute("SELECT token, synonyms FROM ontology").fetchall()
            conn.close()

            mapping = {}
            for token, synonyms_str in result:
                if synonyms_str:
                    try:
                        synonyms = json.loads(synonyms_str) if isinstance(synonyms_str, str) else synonyms_str
                        if isinstance(synonyms, list):
                            for synonym in synonyms:
                                mapping[synonym.lower()] = token
                    except (json.JSONDecodeError, TypeError):
                        pass
                mapping[token.lower()] = token

            return mapping
        except Exception as e:
            print(f"Warning: Could not load ontology: {e}")
            return {}

    def clean_hpi_text(self, raw_text: str) -> str:
        """Clean and normalize HPI text"""
        if not raw_text:
            return ""

        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', raw_text.strip())

        # Normalize common abbreviations
        abbreviations = {
            r'\bpt\b': 'patient',
            r'\bc/o\b': 'complains of',
            r'\bh/o\b': 'history of',
            r'\bs/p\b': 'status post',
            r'\bw/\b': 'with',
            r'\bw/o\b': 'without',
            r'\by/o\b': 'year old',
            r'\byo\b': 'year old'
        }

        for abbrev, full_form in abbreviations.items():
            cleaned = re.sub(abbrev, full_form, cleaned, flags=re.IGNORECASE)

        return cleaned

    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract medical entities from HPI text"""
        entities = {}

        for category, patterns in self.medical_patterns.items():
            matches = []
            for pattern in patterns:
                found = re.findall(pattern, text, re.IGNORECASE)
                matches.extend([match.lower() for match in found])

            # Remove duplicates and map to ontology
            unique_matches = list(set(matches))
            mapped_terms = []
            for match in unique_matches:
                if match in self.ontology_mapping:
                    mapped_terms.append(self.ontology_mapping[match])
                else:
                    mapped_terms.append(match)

            entities[category] = mapped_terms

        return entities

    def extract_timeline(self, text: str) -> List[Dict[str, Any]]:
        """Extract temporal information and create clinical timeline"""
        timeline_events = []

        # Look for temporal patterns with associated content
        temporal_patterns = [
            (r'(\d+)\s*(days?|weeks?|months?|years?)\s*ago\s*([^.!?]*)', 'relative_past'),
            (r'(yesterday|last\s*(?:week|month|year))\s*([^.!?]*)', 'recent_past'),
            (r'(today|this\s*(?:morning|afternoon|evening))\s*([^.!?]*)', 'current'),
            (r'(since|for\s*the\s*past)\s*(\d+\s*(?:days?|weeks?|months?|years?))\s*([^.!?]*)', 'duration')
        ]

        for pattern, event_type in temporal_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                groups = match.groups()
                if len(groups) >= 2:
                    event = {
                        'type': event_type,
                        'time_reference': groups[0],
                        'content': groups[-1].strip() if groups[-1] else '',
                        'position': match.start()
                    }
                    timeline_events.append(event)

        # Sort by position in text
        timeline_events.sort(key=lambda x: x['position'])

        return timeline_events

    def calculate_confidence_score(self, entities: Dict[str, List[str]],
                                 timeline: List[Dict[str, Any]],
                                 text_length: int) -> float:
        """Calculate confidence score for HPI analysis"""
        score = 0.0

        # Base score from entity extraction
        total_entities = sum(len(entity_list) for entity_list in entities.values())
        if total_entities > 0:
            score += min(0.4, total_entities * 0.05)

        # Timeline information adds confidence
        if timeline:
            score += min(0.3, len(timeline) * 0.1)

        # Text length factor (longer HPIs generally more complete)
        if text_length > 100:
            score += 0.2
        elif text_length > 50:
            score += 0.1

        # Presence of key categories
        key_categories = ['symptoms', 'risk_factors', 'temporal_markers']
        for category in key_categories:
            if entities.get(category):
                score += 0.1

        return min(1.0, score)

    def analyze_hpi(self, case_session_id: str, raw_hpi_text: str) -> str:
        """Analyze HPI text and store results in database"""

        if not raw_hpi_text or not raw_hpi_text.strip():
            raise ValueError("HPI text cannot be empty")

        # Generate unique analysis ID
        analysis_id = f"hpi_analysis_{case_session_id}_{uuid.uuid4().hex[:8]}"

        # Clean text
        cleaned_text = self.clean_hpi_text(raw_hpi_text)

        # Extract entities
        entities = self.extract_entities(cleaned_text)

        # Extract timeline
        timeline = self.extract_timeline(cleaned_text)

        # Calculate confidence
        confidence = self.calculate_confidence_score(entities, timeline, len(cleaned_text))

        # Prepare structured data
        analysis_data = {
            'analysis_id': analysis_id,
            'case_session_id': case_session_id,
            'raw_hpi_text': raw_hpi_text,
            'cleaned_hpi_text': cleaned_text,
            'extracted_entities': json.dumps(entities),
            'clinical_timeline': json.dumps(timeline),
            'identified_symptoms': json.dumps(entities.get('symptoms', [])),
            'risk_factors_detected': json.dumps(entities.get('risk_factors', [])),
            'medical_history': json.dumps(self._extract_medical_history(cleaned_text)),
            'medications': json.dumps(entities.get('medications', [])),
            'procedures': json.dumps(entities.get('procedures', [])),
            'severity_indicators': json.dumps(entities.get('severity_indicators', [])),
            'temporal_markers': json.dumps(entities.get('temporal_markers', [])),
            'analysis_confidence': confidence,
            'nlp_model_version': 'codex_v2_1.0'
        }

        # Store in database
        self._store_analysis(analysis_data)

        return analysis_id

    def _extract_medical_history(self, text: str) -> List[str]:
        """Extract medical history information"""
        history_patterns = [
            r'history\s*of\s*([^.!?,]+)',
            r'past\s*medical\s*history[:\s]*([^.!?]+)',
            r'h/o\s*([^.!?,]+)',
            r'previously\s*diagnosed\s*with\s*([^.!?,]+)'
        ]

        history_items = []
        for pattern in history_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            history_items.extend(matches)

        # Clean and deduplicate
        cleaned_items = []
        for item in history_items:
            cleaned = item.strip().lower()
            if cleaned and cleaned not in cleaned_items:
                cleaned_items.append(cleaned)

        return cleaned_items

    def _store_analysis(self, analysis_data: Dict[str, Any]):
        """Store HPI analysis in database"""
        try:
            conn = duckdb.connect(self.db_path)

            # Insert analysis
            conn.execute("""
                INSERT INTO hpi_analysis (
                    analysis_id, case_session_id, raw_hpi_text, cleaned_hpi_text,
                    extracted_entities, clinical_timeline, identified_symptoms,
                    risk_factors_detected, medical_history, medications, procedures,
                    severity_indicators, temporal_markers, analysis_confidence,
                    nlp_model_version, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                analysis_data['analysis_id'],
                analysis_data['case_session_id'],
                analysis_data['raw_hpi_text'],
                analysis_data['cleaned_hpi_text'],
                analysis_data['extracted_entities'],
                analysis_data['clinical_timeline'],
                analysis_data['identified_symptoms'],
                analysis_data['risk_factors_detected'],
                analysis_data['medical_history'],
                analysis_data['medications'],
                analysis_data['procedures'],
                analysis_data['severity_indicators'],
                analysis_data['temporal_markers'],
                analysis_data['analysis_confidence'],
                analysis_data['nlp_model_version'],
                datetime.now(),
                datetime.now()
            ])

            conn.close()

        except Exception as e:
            raise Exception(f"Failed to store HPI analysis: {e}")

    def get_analysis(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve HPI analysis from database"""
        try:
            conn = duckdb.connect(self.db_path)
            result = conn.execute("""
                SELECT * FROM hpi_analysis WHERE analysis_id = ?
            """, [analysis_id]).fetchone()
            conn.close()

            if not result:
                return None

            # Convert to dictionary
            columns = [
                'analysis_id', 'case_session_id', 'raw_hpi_text', 'cleaned_hpi_text',
                'extracted_entities', 'clinical_timeline', 'identified_symptoms',
                'risk_factors_detected', 'medical_history', 'medications', 'procedures',
                'severity_indicators', 'temporal_markers', 'analysis_confidence',
                'nlp_model_version', 'created_at', 'updated_at'
            ]

            analysis = dict(zip(columns, result))

            # Parse JSON fields
            json_fields = [
                'extracted_entities', 'clinical_timeline', 'identified_symptoms',
                'risk_factors_detected', 'medical_history', 'medications', 'procedures',
                'severity_indicators', 'temporal_markers'
            ]

            for field in json_fields:
                if analysis[field]:
                    try:
                        analysis[field] = json.loads(analysis[field])
                    except json.JSONDecodeError:
                        analysis[field] = []

            return analysis

        except Exception as e:
            print(f"Error retrieving HPI analysis: {e}")
            return None

# Example usage and testing
if __name__ == "__main__":
    # Test the HPI analyzer
    analyzer = HPIAnalyzer()

    sample_hpi = """
    65 year old male with history of diabetes, hypertension, and COPD presents with
    acute onset chest pain that started 2 hours ago. Patient describes the pain as
    crushing, 8/10 severity, radiating to left arm. Associated with nausea and
    diaphoresis. Patient has been taking metoprolol and lisinopril. No prior surgeries.
    Smoking history of 30 pack-years, quit 5 years ago.
    """

    print("Testing HPI Analyzer...")
    print(f"Sample HPI: {sample_hpi}")

    try:
        # First create a test case session
        import duckdb
        conn = duckdb.connect(analyzer.db_path)
        conn.execute("""
            INSERT OR IGNORE INTO case_sessions (session_id, hpi_text, created_at)
            VALUES ('test_session_001', ?, ?)
        """, [sample_hpi, datetime.now()])
        conn.close()

        # Analyze the sample HPI
        analysis_id = analyzer.analyze_hpi("test_session_001", sample_hpi)
        print(f"Analysis ID: {analysis_id}")

        # Retrieve and display results
        analysis = analyzer.get_analysis(analysis_id)
        if analysis:
            print(f"Confidence Score: {analysis['analysis_confidence']:.2f}")
            print(f"Symptoms: {analysis['identified_symptoms']}")
            print(f"Risk Factors: {analysis['risk_factors_detected']}")
            print(f"Medications: {analysis['medications']}")
            print(f"Timeline Events: {len(analysis['clinical_timeline'])}")

        print("HPI Analyzer test completed successfully!")

    except Exception as e:
        print(f"Error testing HPI analyzer: {e}")