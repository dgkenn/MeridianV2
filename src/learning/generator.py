"""
Learning item generator - Creates patient-anchored questions from case context
"""

import random
import logging
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime

from .schemas import (
    LearningItem, LearningSession, LearningMode, DifficultyLevel,
    ItemType, BlueprintDomain, PatientContext, Citation
)
from .templates import get_applicable_templates
from .patient_context import PatientContextExtractor

logger = logging.getLogger(__name__)

class LearningItemGenerator:
    """Generates patient-anchored learning items from case context"""

    def __init__(self):
        self.context_extractor = PatientContextExtractor()
        self.version = "1.0"

    def generate_session(self,
                        parsed_hpi: Dict[str, Any],
                        risk_assessments: List[Dict[str, Any]],
                        medication_plan: Dict[str, Any],
                        mode: LearningMode,
                        n_items: int = 8,
                        seed: Optional[int] = None,
                        guidelines: List[Dict[str, Any]] = None) -> LearningSession:
        """
        Generate a learning session from current case data

        Args:
            parsed_hpi: HPI parser output
            risk_assessments: Risk engine output
            medication_plan: Medication recommendations
            mode: BASICS or BOARD difficulty level
            n_items: Number of questions to generate
            seed: Random seed for reproducibility
            guidelines: Attached guidelines/citations

        Returns:
            LearningSession with patient-anchored questions
        """
        if seed is None:
            seed = random.randint(1000, 9999)

        logger.info(f"Generating {mode.value} learning session with {n_items} items, seed={seed}")

        # Extract patient context
        context = self.context_extractor.extract_from_app_state(
            parsed_hpi, risk_assessments, medication_plan, guidelines
        )

        # Validate sufficient case data
        if not self._validate_case_sufficiency(context):
            logger.warning("Insufficient case data for learning item generation")
            return self._create_empty_session(mode, n_items, seed, context)

        # Generate items
        items = self._generate_items(context, mode, n_items, seed)

        # Create session
        session_id = str(uuid.uuid4())
        session = LearningSession(
            session_id=session_id,
            mode=mode,
            n_items=len(items),
            items=items,
            blueprint_distribution=self._calculate_blueprint_distribution(items),
            seed=seed,
            started_at=datetime.utcnow(),
            case_hash=context.generate_case_hash()
        )

        logger.info(f"Generated session {session_id} with {len(items)} patient-anchored items")
        return session

    def _validate_case_sufficiency(self, context: PatientContext) -> bool:
        """Validate that case has sufficient data for learning items"""
        # Must have at least some extracted factors
        if len(context.extracted_factors) < 1:
            return False

        # Must have either risk data or medication plan
        has_risks = len(context.top_outcomes) > 0
        has_meds = any(len(bucket) > 0 for bucket in context.medication_plan.values())

        return has_risks or has_meds

    def _generate_items(self, context: PatientContext, mode: LearningMode,
                       n_items: int, seed: int) -> List[LearningItem]:
        """Generate patient-anchored learning items"""
        items = []
        random.seed(seed)

        # Get applicable templates for this patient
        applicable_templates = get_applicable_templates(context)

        if not applicable_templates:
            logger.warning("No applicable templates for this patient context")
            return []

        # Distribution strategy: prioritize outcome-based and medication questions
        target_distribution = self._calculate_target_distribution(context, n_items)

        # Generate items by category
        for template_type, count in target_distribution.items():
            template_items = self._generate_items_by_type(
                context, mode, template_type, count, seed
            )
            items.extend(template_items)

        # Fill remaining slots with any applicable template
        while len(items) < n_items and applicable_templates:
            template = random.choice(applicable_templates)
            item_seed = random.randint(1000, 9999)

            try:
                item_data = template.generate(context, mode, item_seed)
                if item_data and self._validate_patient_anchoring(item_data, context):
                    item = self._create_learning_item(
                        item_data, template, context, mode, item_seed
                    )
                    items.append(item)
            except Exception as e:
                logger.warning(f"Failed to generate item with {template.template_id}: {e}")

        return items[:n_items]

    def _calculate_target_distribution(self, context: PatientContext,
                                     n_items: int) -> Dict[str, int]:
        """Calculate target distribution of item types based on case"""
        distribution = {}

        # Prioritize outcome-based questions if we have risk data
        if len(context.top_outcomes) >= 2:
            distribution['risk_action'] = max(1, n_items // 3)

        # Prioritize medication questions if we have med plan
        draw_now_count = len(context.medication_plan.get('draw_now', []))
        contraindicated_count = len(context.medication_plan.get('contraindicated', []))

        if draw_now_count > 0:
            distribution['dose_calculation'] = max(1, min(2, draw_now_count))

        if contraindicated_count > 0:
            distribution['contraindication'] = max(1, min(2, contraindicated_count))

        return distribution

    def _generate_items_by_type(self, context: PatientContext, mode: LearningMode,
                               template_type: str, count: int, seed: int) -> List[LearningItem]:
        """Generate items of specific type"""
        items = []
        applicable_templates = get_applicable_templates(context)

        # Filter templates by type
        matching_templates = [
            t for t in applicable_templates
            if t.template_id == template_type
        ]

        if not matching_templates:
            return []

        template = matching_templates[0]

        for i in range(count):
            item_seed = random.randint(1000, 9999)

            try:
                item_data = template.generate(context, mode, item_seed)
                if item_data and self._validate_patient_anchoring(item_data, context):
                    item = self._create_learning_item(
                        item_data, template, context, mode, item_seed
                    )
                    items.append(item)
            except Exception as e:
                logger.warning(f"Failed to generate {template_type} item: {e}")

        return items

    def _create_learning_item(self, item_data: Dict[str, Any],
                             template: Any, context: PatientContext,
                             mode: LearningMode, seed: int) -> LearningItem:
        """Create LearningItem from template output"""
        item_id = str(uuid.uuid4())

        return LearningItem(
            item_id=item_id,
            stem=item_data['stem'],
            options=item_data['options'],
            correct_keys=item_data['correct_keys'],
            rationale=item_data['rationale'],
            citations=item_data.get('citations', []),
            mode=mode,
            difficulty=template.difficulty,
            item_type=template.item_type,
            domain_tags=template.domains,
            patient_anchors=item_data.get('patient_anchors', []),
            seed=seed,
            version=self.version,
            created_at=datetime.utcnow(),
            case_hash=context.generate_case_hash()
        )

    def _validate_patient_anchoring(self, item_data: Dict[str, Any],
                                  context: PatientContext) -> bool:
        """Validate that item is properly anchored to patient context"""
        stem = item_data.get('stem', '')

        # Use context extractor validation
        return self.context_extractor.validate_patient_anchoring(stem, context)

    def _calculate_blueprint_distribution(self, items: List[LearningItem]) -> Dict[BlueprintDomain, int]:
        """Calculate distribution of blueprint domains"""
        distribution = {}

        for item in items:
            for domain in item.domain_tags:
                distribution[domain] = distribution.get(domain, 0) + 1

        return distribution

    def _create_empty_session(self, mode: LearningMode, n_items: int,
                             seed: int, context: PatientContext) -> LearningSession:
        """Create empty session when insufficient case data"""
        session_id = str(uuid.uuid4())

        return LearningSession(
            session_id=session_id,
            mode=mode,
            n_items=0,
            items=[],
            blueprint_distribution={},
            seed=seed,
            started_at=datetime.utcnow(),
            case_hash=context.generate_case_hash()
        )

    def validate_item_safety(self, item: LearningItem, context: PatientContext) -> bool:
        """Validate item safety - no PHI, safe doses, valid citations"""
        # Check for PHI patterns
        phi_patterns = [
            r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
            r'\b\d{2}/\d{2}/\d{4}\b',  # Dates
            r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b'  # Names
        ]

        full_text = f"{item.stem} {' '.join(item.options)} {item.rationale}"
        for pattern in phi_patterns:
            if re.search(pattern, full_text):
                logger.warning(f"Potential PHI detected in item {item.item_id}")
                return False

        # Validate dose safety if it's a dose calculation
        if 'dose' in item.stem.lower() and context.weight_kg:
            if not self._validate_dose_safety(item, context):
                return False

        # Ensure citations exist for keyed answers
        if not item.citations:
            logger.warning(f"No citations for item {item.item_id}")
            return False

        return True

    def _validate_dose_safety(self, item: LearningItem, context: PatientContext) -> bool:
        """Validate medication doses are within safe ranges"""
        # Extract dose from correct answer
        correct_option = item.options[item.correct_keys[0]]

        # Check for unrealistic volumes
        volume_match = re.search(r'(\d+(?:\.\d+)?)\s*mL', correct_option)
        if volume_match:
            volume = float(volume_match.group(1))
            # Flag volumes > 20 mL for IV push
            if volume > 20:
                logger.warning(f"Unsafe volume {volume} mL in item {item.item_id}")
                return False

        return True

    def generate_case_based_items(self, app_state: Dict[str, Any],
                                 mode: LearningMode = LearningMode.BASICS,
                                 n_items: int = 6) -> LearningSession:
        """
        Convenience method to generate items from complete app state

        Args:
            app_state: Complete app state with parsed_hpi, risks, medications
            mode: Learning mode
            n_items: Number of items

        Returns:
            LearningSession
        """
        return self.generate_session(
            parsed_hpi=app_state.get('parsed_hpi', {}),
            risk_assessments=app_state.get('risk_assessments', []),
            medication_plan=app_state.get('medication_plan', {}),
            mode=mode,
            n_items=n_items,
            guidelines=app_state.get('guidelines', [])
        )