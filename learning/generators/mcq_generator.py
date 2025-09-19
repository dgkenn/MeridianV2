"""
MCQ Generation Engine for Medical Learning
Uses existing case data and evidence base to generate board-style questions
"""

import random
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

from ..models.learning_item import (
    LearningItem, MCQOption, Citation, ItemType,
    DifficultyTier, LearningMode, BlueprintDomain
)
from ..models.learning_session import BlueprintWeights

logger = logging.getLogger(__name__)


@dataclass
class CaseContext:
    """Patient case context for question generation"""
    age: int
    sex: str
    bmi: Optional[float] = None
    comorbidities: List[str] = None
    procedure: Optional[str] = None
    asa_class: Optional[str] = None
    medications: List[str] = None
    allergies: List[str] = None

    def __post_init__(self):
        if self.comorbidities is None:
            self.comorbidities = []
        if self.medications is None:
            self.medications = []
        if self.allergies is None:
            self.allergies = []


class MCQGenerator:
    """
    Core MCQ generation engine that creates case-anchored questions
    from existing evidence base and risk assessment data
    """

    def __init__(self, evidence_db_path: str = "database/production.duckdb"):
        self.evidence_db = evidence_db_path
        self.domain_templates = self._load_domain_templates()
        self.citation_library = self._load_citation_library()

    def generate_session_items(
        self,
        num_items: int,
        mode: LearningMode,
        blueprint_weights: BlueprintWeights,
        seed: int,
        case_context: Optional[CaseContext] = None
    ) -> List[LearningItem]:
        """Generate a complete set of MCQs for a learning session"""

        random.seed(seed)
        items = []

        # Calculate how many questions per domain based on weights
        domain_allocation = self._calculate_domain_allocation(num_items, blueprint_weights)

        for domain, count in domain_allocation.items():
            for i in range(count):
                try:
                    item = self._generate_single_item(
                        domain=BlueprintDomain(domain),
                        mode=mode,
                        seed=seed + len(items),
                        case_context=case_context
                    )
                    if item:
                        items.append(item)
                except Exception as e:
                    logger.error(f"Failed to generate item for {domain}: {e}")

        # Fill remaining slots if we're short
        while len(items) < num_items:
            fallback_domain = random.choice(list(BlueprintDomain))
            try:
                item = self._generate_single_item(
                    domain=fallback_domain,
                    mode=mode,
                    seed=seed + len(items),
                    case_context=case_context
                )
                if item:
                    items.append(item)
            except Exception as e:
                logger.error(f"Failed to generate fallback item: {e}")
                break

        return items[:num_items]

    def _calculate_domain_allocation(self, num_items: int, weights: BlueprintWeights) -> Dict[str, int]:
        """Calculate how many questions per domain based on blueprint weights"""
        weights_dict = weights.to_dict()
        allocation = {}

        for domain, weight in weights_dict.items():
            allocation[domain] = max(1, round(num_items * weight))

        # Adjust to ensure total equals num_items
        total_allocated = sum(allocation.values())
        if total_allocated != num_items:
            # Adjust largest allocation
            max_domain = max(allocation.keys(), key=lambda k: allocation[k])
            allocation[max_domain] += (num_items - total_allocated)

        return allocation

    def _generate_single_item(
        self,
        domain: BlueprintDomain,
        mode: LearningMode,
        seed: int,
        case_context: Optional[CaseContext] = None
    ) -> Optional[LearningItem]:
        """Generate a single MCQ for a specific domain"""

        random.seed(seed)

        # Select template for this domain
        templates = self.domain_templates.get(domain.value, [])
        if not templates:
            logger.warning(f"No templates available for domain {domain.value}")
            return None

        template = random.choice(templates)

        # Generate case context if not provided
        if case_context is None:
            case_context = self._generate_case_context(domain, mode)

        # Create question stem from template
        stem_md = self._create_question_stem(template, case_context, mode)

        # Generate options
        options = self._generate_options(template, case_context, mode)

        # Select difficulty based on mode
        difficulty = self._select_difficulty(mode, template.get('difficulty_range', ['moderate']))

        # Get citations
        citations = self._get_relevant_citations(domain, template)

        # Create rationale
        rationale_md = self._create_rationale(template, options, citations)

        # Generate item ID
        item_id = LearningItem.generate_id(seed, "v1.0", case_context.__dict__ if case_context else None)

        return LearningItem(
            item_id=item_id,
            stem_md=stem_md,
            options=options,
            item_type=template.get('item_type', ItemType.SINGLE_BEST),
            mode=mode,
            difficulty=difficulty,
            domain_tags=[domain],
            rationale_md=rationale_md,
            citations=citations,
            seed=seed,
            version="v1.0",
            case_context=case_context.__dict__ if case_context else None
        )

    def _generate_case_context(self, domain: BlueprintDomain, mode: LearningMode) -> CaseContext:
        """Generate realistic patient context for question"""

        # Age ranges based on domain and mode
        age_ranges = {
            BlueprintDomain.PEDIATRIC: (2, 17),
            BlueprintDomain.OBSTETRIC: (18, 45),
            BlueprintDomain.ANATOMY_AIRWAY: (25, 75),
            BlueprintDomain.HEMODYNAMICS: (40, 80),
        }

        age_range = age_ranges.get(domain, (25, 75))
        age = random.randint(*age_range)

        sex = random.choice(['M', 'F'])
        if domain == BlueprintDomain.OBSTETRIC:
            sex = 'F'

        # Common comorbidities by domain
        domain_comorbidities = {
            BlueprintDomain.ANATOMY_AIRWAY: ['OSA', 'obesity', 'GERD', 'difficult_airway_history'],
            BlueprintDomain.HEMODYNAMICS: ['hypertension', 'CAD', 'CHF', 'diabetes'],
            BlueprintDomain.REGIONAL: ['coagulopathy', 'spinal_stenosis', 'neuropathy'],
            BlueprintDomain.PEDIATRIC: ['asthma', 'congenital_heart_disease', 'prematurity'],
            BlueprintDomain.OBSTETRIC: ['gestational_diabetes', 'preeclampsia', 'placenta_previa'],
        }

        possible_comorbidities = domain_comorbidities.get(domain, ['hypertension', 'diabetes'])
        comorbidities = random.sample(possible_comorbidities, k=min(2, len(possible_comorbidities)))

        return CaseContext(
            age=age,
            sex=sex,
            bmi=round(random.uniform(18.5, 35.0), 1),
            comorbidities=comorbidities,
            procedure=self._select_procedure(domain),
            asa_class=random.choice(['II', 'III', 'IV']),
            medications=self._select_medications(comorbidities),
            allergies=random.choice([[], ['NKDA'], ['penicillin'], ['latex']])
        )

    def _select_procedure(self, domain: BlueprintDomain) -> str:
        """Select appropriate procedure for domain"""
        procedures = {
            BlueprintDomain.ANATOMY_AIRWAY: [
                'elective intubation', 'emergency intubation', 'fiberoptic intubation',
                'awake intubation', 'RSI'
            ],
            BlueprintDomain.HEMODYNAMICS: [
                'cardiac surgery', 'vascular surgery', 'major abdominal surgery',
                'orthopedic surgery', 'neurosurgery'
            ],
            BlueprintDomain.REGIONAL: [
                'epidural', 'spinal anesthesia', 'peripheral nerve block',
                'TAP block', 'interscalene block'
            ],
            BlueprintDomain.PEDIATRIC: [
                'pediatric surgery', 'tonsillectomy', 'appendectomy',
                'dental surgery', 'ENT surgery'
            ],
            BlueprintDomain.OBSTETRIC: [
                'cesarean section', 'labor epidural', 'vaginal delivery',
                'postpartum hemorrhage', 'emergency C-section'
            ]
        }

        domain_procedures = procedures.get(domain, ['general surgery'])
        return random.choice(domain_procedures)

    def _select_medications(self, comorbidities: List[str]) -> List[str]:
        """Select medications based on comorbidities"""
        med_map = {
            'hypertension': ['lisinopril', 'metoprolol', 'amlodipine'],
            'diabetes': ['metformin', 'insulin', 'glipizide'],
            'CAD': ['aspirin', 'atorvastatin', 'metoprolol'],
            'OSA': ['CPAP'],
            'asthma': ['albuterol', 'fluticasone']
        }

        medications = []
        for condition in comorbidities:
            if condition in med_map:
                medications.extend(random.sample(med_map[condition], k=1))

        return list(set(medications))  # Remove duplicates

    def _create_question_stem(
        self,
        template: Dict[str, Any],
        case_context: CaseContext,
        mode: LearningMode
    ) -> str:
        """Create question stem using template and case context"""

        stem_template = template.get('stem_template', '')

        # Replace placeholders with case context
        replacements = {
            '{age}': str(case_context.age),
            '{sex}': case_context.sex,
            '{bmi}': str(case_context.bmi) if case_context.bmi else 'unknown',
            '{procedure}': case_context.procedure or 'surgery',
            '{asa_class}': case_context.asa_class or 'II',
            '{comorbidities}': ', '.join(case_context.comorbidities) if case_context.comorbidities else 'none',
            '{medications}': ', '.join(case_context.medications) if case_context.medications else 'none'
        }

        stem = stem_template
        for placeholder, value in replacements.items():
            stem = stem.replace(placeholder, value)

        return stem

    def _generate_options(
        self,
        template: Dict[str, Any],
        case_context: CaseContext,
        mode: LearningMode
    ) -> List[MCQOption]:
        """Generate MCQ options based on template"""

        option_templates = template.get('options', [])
        options = []

        for opt_template in option_templates:
            text = opt_template.get('text', '')
            is_correct = opt_template.get('is_correct', False)
            explanation = opt_template.get('explanation', '')

            # Apply case-specific modifications
            if case_context and 'OSA' in case_context.comorbidities:
                if 'airway' in text.lower() and is_correct:
                    explanation += " This patient's OSA increases airway management risk significantly."

            options.append(MCQOption(
                text=text,
                is_correct=is_correct,
                explanation=explanation if explanation else None
            ))

        return options

    def _select_difficulty(self, mode: LearningMode, difficulty_range: List[str]) -> DifficultyTier:
        """Select appropriate difficulty based on mode"""

        if mode == LearningMode.BASICS:
            # Junior residents - easier questions
            weights = {'easy': 0.4, 'moderate': 0.5, 'advanced': 0.1, 'stretch': 0.0}
        else:  # BOARD mode
            # Senior/fellows - harder questions
            weights = {'easy': 0.1, 'moderate': 0.3, 'advanced': 0.5, 'stretch': 0.1}

        # Filter by available range
        available_difficulties = [d for d in difficulty_range if d in weights]
        if not available_difficulties:
            return DifficultyTier.MODERATE

        # Weighted random selection
        choices = []
        for diff in available_difficulties:
            choices.extend([diff] * int(weights[diff] * 100))

        selected = random.choice(choices) if choices else 'moderate'
        return DifficultyTier(selected)

    def _get_relevant_citations(self, domain: BlueprintDomain, template: Dict[str, Any]) -> List[Citation]:
        """Get evidence-based citations for the question"""

        # Use template citations if available
        template_citations = template.get('citations', [])
        citations = []

        for cit_data in template_citations:
            citation = Citation(
                type=cit_data.get('type', 'guideline'),
                identifier=cit_data.get('identifier', ''),
                title=cit_data.get('title', ''),
                url=cit_data.get('url')
            )
            citations.append(citation)

        # Add domain-specific citations if none provided
        if not citations:
            citations = self._get_default_citations(domain)

        return citations

    def _get_default_citations(self, domain: BlueprintDomain) -> List[Citation]:
        """Get default citations for each domain"""

        default_citations = {
            BlueprintDomain.ANATOMY_AIRWAY: [
                Citation(
                    type="guideline",
                    identifier="ASA-2022",
                    title="ASA Practice Guidelines for Management of the Difficult Airway",
                    url="https://pubs.asahq.org/anesthesiology/article/136/1/31/116949"
                )
            ],
            BlueprintDomain.HEMODYNAMICS: [
                Citation(
                    type="guideline",
                    identifier="AHA-2020",
                    title="AHA/ACC Guideline for the Management of Patients with Valvular Heart Disease",
                    url="https://www.ahajournals.org/doi/10.1161/CIR.0000000000000923"
                )
            ],
            BlueprintDomain.REGIONAL: [
                Citation(
                    type="guideline",
                    identifier="ASRA-2018",
                    title="ASRA Practice Advisory on Neurologic Complications Associated with Regional Anesthesia",
                    url="https://rapm.bmj.com/content/43/5/519"
                )
            ]
        }

        return default_citations.get(domain, [
            Citation(
                type="textbook",
                identifier="Miller-2020",
                title="Miller's Anesthesia, 9th Edition",
                url=None
            )
        ])

    def _create_rationale(
        self,
        template: Dict[str, Any],
        options: List[MCQOption],
        citations: List[Citation]
    ) -> str:
        """Create educational rationale explaining the correct answer"""

        rationale_template = template.get('rationale_template', '')

        if rationale_template:
            rationale = rationale_template
        else:
            # Generate basic rationale
            correct_options = [i for i, opt in enumerate(options) if opt.is_correct]
            correct_letters = [chr(65 + i) for i in correct_options]  # A, B, C, D...

            rationale = f"The correct answer is {', '.join(correct_letters)}. "

            # Add explanations from correct options
            for i, opt in enumerate(options):
                if opt.is_correct and opt.explanation:
                    rationale += opt.explanation + " "

        # Add citations
        if citations:
            rationale += "\n\n**References:**\n"
            for cit in citations:
                rationale += f"- {cit.title} ({cit.identifier})\n"

        return rationale.strip()

    def _load_domain_templates(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load question templates for each domain"""

        # In production, this would load from a database or JSON files
        # For now, return some example templates

        return {
            'anatomy_airway': [
                {
                    'stem_template': 'A {age}-year-old {sex} patient with {comorbidities} is scheduled for {procedure}. What is the most appropriate airway management approach?',
                    'options': [
                        {'text': 'Standard laryngoscopy and intubation', 'is_correct': False, 'explanation': 'May be difficult with OSA'},
                        {'text': 'Awake fiberoptic intubation', 'is_correct': True, 'explanation': 'Safest approach for predicted difficult airway'},
                        {'text': 'Rapid sequence induction', 'is_correct': False, 'explanation': 'Inappropriate for known difficult airway'},
                        {'text': 'LMA insertion only', 'is_correct': False, 'explanation': 'Inadequate for secure airway'}
                    ],
                    'difficulty_range': ['moderate', 'advanced'],
                    'item_type': ItemType.SINGLE_BEST,
                    'rationale_template': 'Patients with OSA have increased risk of difficult mask ventilation and intubation. Awake fiberoptic intubation maintains spontaneous ventilation and provides the safest approach.',
                    'citations': [
                        {
                            'type': 'guideline',
                            'identifier': 'ASA-2022',
                            'title': 'ASA Practice Guidelines for Management of the Difficult Airway',
                            'url': 'https://pubs.asahq.org/anesthesiology/article/136/1/31/116949'
                        }
                    ]
                }
            ],
            'hemodynamics': [
                {
                    'stem_template': 'During {procedure} in a {age}-year-old patient with {comorbidities}, blood pressure drops to 70/40 mmHg. What is the most appropriate initial intervention?',
                    'options': [
                        {'text': 'IV fluid bolus', 'is_correct': True, 'explanation': 'First-line treatment for hypotension'},
                        {'text': 'Epinephrine bolus', 'is_correct': False, 'explanation': 'Too aggressive for initial management'},
                        {'text': 'Decrease anesthetic depth', 'is_correct': False, 'explanation': 'May cause awareness'},
                        {'text': 'Trendelenburg position', 'is_correct': False, 'explanation': 'Minimal hemodynamic benefit'}
                    ],
                    'difficulty_range': ['easy', 'moderate'],
                    'item_type': ItemType.SINGLE_BEST
                }
            ],
            'pharmacology': [
                {
                    'stem_template': 'A {age}-year-old patient is taking {medications}. Which anesthetic consideration is most important?',
                    'options': [
                        {'text': 'Drug interactions with volatile agents', 'is_correct': True, 'explanation': 'Many medications interact with anesthetics'},
                        {'text': 'Increased MAC requirements', 'is_correct': False, 'explanation': 'Not universally true'},
                        {'text': 'Delayed emergence', 'is_correct': False, 'explanation': 'Variable effect'},
                        {'text': 'Increased PONV risk', 'is_correct': False, 'explanation': 'Not medication-related'}
                    ],
                    'difficulty_range': ['moderate', 'advanced'],
                    'item_type': ItemType.SINGLE_BEST
                }
            ]
        }

    def _load_citation_library(self) -> Dict[str, List[Citation]]:
        """Load comprehensive citation library"""

        # In production, this would be a comprehensive database
        return {
            'airway': [
                Citation(
                    type="guideline",
                    identifier="ASA-2022",
                    title="ASA Practice Guidelines for Management of the Difficult Airway",
                    url="https://pubs.asahq.org/anesthesiology/article/136/1/31/116949"
                )
            ],
            'hemodynamics': [
                Citation(
                    type="pubmed",
                    identifier="PMID:31613773",
                    title="Perioperative Hemodynamic Management in Cardiac Surgery",
                    url="https://pubmed.ncbi.nlm.nih.gov/31613773/"
                )
            ]
        }


def validate_generated_items(items: List[LearningItem]) -> Dict[str, Any]:
    """Validate a set of generated learning items"""

    validation_results = {
        'total_items': len(items),
        'valid_items': 0,
        'invalid_items': 0,
        'issues': [],
        'domain_distribution': {},
        'difficulty_distribution': {}
    }

    for item in items:
        issues = item.validate()
        if issues:
            validation_results['invalid_items'] += 1
            validation_results['issues'].extend([f"Item {item.item_id}: {issue}" for issue in issues])
        else:
            validation_results['valid_items'] += 1

        # Track distributions
        for domain in item.domain_tags:
            domain_name = domain.value
            validation_results['domain_distribution'][domain_name] = validation_results['domain_distribution'].get(domain_name, 0) + 1

        diff_name = item.difficulty.value
        validation_results['difficulty_distribution'][diff_name] = validation_results['difficulty_distribution'].get(diff_name, 0) + 1

    return validation_results