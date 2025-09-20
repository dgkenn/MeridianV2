"""
Patient context extraction from app state for learning module
"""

import re
import logging
from typing import Dict, List, Optional, Any
from .schemas import PatientContext, Citation

logger = logging.getLogger(__name__)

class PatientContextExtractor:
    """Extracts patient context from parsed HPI, risk assessments, and medication plans"""

    def extract_from_app_state(self,
                             parsed_hpi: Dict[str, Any],
                             risk_assessments: List[Dict[str, Any]],
                             medication_plan: Dict[str, Any],
                             guidelines: List[Dict[str, Any]] = None) -> PatientContext:
        """
        Extract patient context from current app state

        Args:
            parsed_hpi: Result from HPI parser
            risk_assessments: List of risk assessment results
            medication_plan: Medication recommendations
            guidelines: Attached guidelines/citations

        Returns:
            PatientContext object for learning item generation
        """
        context = PatientContext()

        # Extract demographics from HPI
        demographics = parsed_hpi.get('demographics', {})
        context.age = demographics.get('age')
        context.weight_kg = demographics.get('weight_kg')
        context.height_cm = demographics.get('height_cm')
        context.bmi = demographics.get('bmi')

        # Extract surgery information
        context.surgery_domain = self._extract_surgery_domain(parsed_hpi.get('raw_text', ''))
        context.procedure_keywords = self._extract_procedure_keywords(parsed_hpi.get('raw_text', ''))
        context.urgency = self._extract_urgency(parsed_hpi.get('raw_text', ''))

        # Extract parsed features
        context.extracted_factors = parsed_hpi.get('extracted_factors', [])

        # Sort and extract top risk outcomes
        context.top_outcomes = self._extract_top_outcomes(risk_assessments)

        # Extract medication plan buckets
        context.medication_plan = self._organize_medication_plan(medication_plan)

        # Extract guidelines and citations
        if guidelines:
            context.case_guidelines = guidelines
            context.evidence_citations = self._extract_citations(guidelines)

        return context

    def _extract_surgery_domain(self, hpi_text: str) -> Optional[str]:
        """Extract surgery domain from HPI text"""
        domain_patterns = {
            'dental': r'\b(dental|tooth|teeth|orthodontic|oral surgery)\b',
            'ent': r'\b(tonsillectomy|adenoidectomy|ear|nose|throat|sinus|ENT)\b',
            'orthopedic': r'\b(orthopedic|bone|joint|fracture|ACL|knee|hip)\b',
            'cardiac': r'\b(cardiac|heart|bypass|valve|coronary)\b',
            'obstetric': r'\b(cesarean|c-section|delivery|labor|obstetric)\b',
            'pediatric': r'\b(pediatric|child|infant|newborn)\b',
            'general': r'\b(general surgery|laparoscopic|appendectomy|hernia)\b',
            'neurosurgery': r'\b(neurosurgery|brain|spine|craniotomy)\b'
        }

        hpi_lower = hpi_text.lower()
        for domain, pattern in domain_patterns.items():
            if re.search(pattern, hpi_lower):
                return domain

        return 'general'  # Default

    def _extract_procedure_keywords(self, hpi_text: str) -> List[str]:
        """Extract specific procedure keywords"""
        procedure_patterns = [
            r'\b(tonsillectomy|adenoidectomy)\b',
            r'\b(dental extraction|tooth extraction)\b',
            r'\b(cesarean|c-section)\b',
            r'\b(laparoscopy|laparoscopic)\b',
            r'\b(arthroscopy|arthroscopic)\b',
            r'\b(endoscopy|colonoscopy)\b'
        ]

        keywords = []
        hpi_lower = hpi_text.lower()
        for pattern in procedure_patterns:
            matches = re.findall(pattern, hpi_lower)
            keywords.extend(matches)

        return list(set(keywords))

    def _extract_urgency(self, hpi_text: str) -> str:
        """Extract urgency level from HPI"""
        hpi_lower = hpi_text.lower()

        if re.search(r'\b(emergency|urgent|trauma|acute|emergent)\b', hpi_lower):
            return 'emergency'
        elif re.search(r'\b(urgent|same day|stat)\b', hpi_lower):
            return 'urgent'
        else:
            return 'elective'

    def _extract_top_outcomes(self, risk_assessments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract and sort top risk outcomes by absolute risk and delta"""
        if not risk_assessments:
            return []

        # Sort by adjusted risk (highest first) and take top 5
        sorted_risks = sorted(
            risk_assessments,
            key=lambda x: x.get('adjusted_risk', 0),
            reverse=True
        )

        top_outcomes = []
        for risk in sorted_risks[:5]:
            outcome_data = {
                'outcome': risk.get('outcome'),
                'outcome_label': risk.get('outcome_label'),
                'baseline_risk': risk.get('baseline_risk'),
                'adjusted_risk': risk.get('adjusted_risk'),
                'risk_ratio': risk.get('risk_ratio'),
                'risk_difference': risk.get('risk_difference'),
                'evidence_grade': risk.get('evidence_grade'),
                'contributing_factors': risk.get('contributing_factors', [])
            }
            top_outcomes.append(outcome_data)

        return top_outcomes

    def _organize_medication_plan(self, medication_plan: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Organize medication plan by buckets"""
        if not medication_plan:
            return {}

        organized = {
            'draw_now': [],
            'standard': [],
            'consider': [],
            'contraindicated': []
        }

        # Extract medications from each bucket
        for bucket in organized.keys():
            meds = medication_plan.get(bucket, [])
            if isinstance(meds, list):
                organized[bucket] = meds

        return organized

    def _extract_citations(self, guidelines: List[Dict[str, Any]]) -> List[Citation]:
        """Extract citations from guidelines"""
        citations = []

        for guideline in guidelines:
            citation = Citation(
                pmid=guideline.get('pmid'),
                guideline=guideline.get('society'),
                title=guideline.get('title', ''),
                relevance_weight=guideline.get('relevance_weight', 1.0)
            )
            citations.append(citation)

        return citations

    def get_case_topics(self, context: PatientContext) -> List[str]:
        """
        Generate ranked list of case topics for item generation gating

        Returns list of topics present in this case that can be used for questions
        """
        topics = []

        # Add demographics-based topics
        if context.age is not None:
            if context.age < 18:
                topics.append('pediatric_considerations')
            elif context.age > 65:
                topics.append('geriatric_considerations')

        # Add extracted factor topics
        for factor in context.extracted_factors:
            token = factor.get('token', '')
            if token:
                topics.append(token.lower())

        # Add surgery domain topics
        if context.surgery_domain:
            topics.append(f"{context.surgery_domain}_anesthesia")

        # Add urgency-based topics
        if context.urgency != 'elective':
            topics.append(f"{context.urgency}_surgery")

        # Add top outcome topics
        for outcome in context.top_outcomes[:3]:
            if outcome.get('outcome'):
                topics.append(outcome['outcome'].lower())

        # Add medication-related topics
        for bucket_name, meds in context.medication_plan.items():
            if meds and bucket_name in ['draw_now', 'contraindicated']:
                topics.append(f"medication_{bucket_name}")

        return list(set(topics))  # Remove duplicates

    def validate_patient_anchoring(self, item_stem: str, context: PatientContext) -> bool:
        """
        Validate that an item stem is properly anchored to patient context

        Returns True if item references patient-specific information
        """
        case_topics = self.get_case_topics(context)
        stem_lower = item_stem.lower()

        # Check for patient-specific demographics
        if context.age and str(context.age) in item_stem:
            return True

        if context.weight_kg and str(context.weight_kg) in item_stem:
            return True

        # Check for case-specific factors
        for factor in context.extracted_factors:
            factor_label = factor.get('plain_label', '').lower()
            if factor_label and factor_label in stem_lower:
                return True

        # Check for surgery domain
        if context.surgery_domain and context.surgery_domain in stem_lower:
            return True

        # Check for top outcomes
        for outcome in context.top_outcomes[:3]:
            outcome_label = outcome.get('outcome_label', '').lower()
            if outcome_label and outcome_label in stem_lower:
                return True

        return False