"""
Patient-anchored question templates for learning module
"""

import random
import re
from typing import Dict, List, Optional, Tuple, Any
from .schemas import PatientContext, LearningMode, DifficultyLevel, ItemType, BlueprintDomain, Citation

class QuestionTemplate:
    """Base class for patient-anchored question templates"""

    def __init__(self, template_id: str, domains: List[BlueprintDomain],
                 difficulty: DifficultyLevel, item_type: ItemType):
        self.template_id = template_id
        self.domains = domains
        self.difficulty = difficulty
        self.item_type = item_type

    def can_generate(self, context: PatientContext) -> bool:
        """Check if this template can generate a question for this patient"""
        raise NotImplementedError

    def generate(self, context: PatientContext, mode: LearningMode,
                seed: int) -> Optional[Dict[str, Any]]:
        """Generate question for this patient context"""
        raise NotImplementedError

class RiskActionTemplate(QuestionTemplate):
    """Risk-to-action questions based on patient's top outcomes"""

    def __init__(self):
        super().__init__(
            "risk_action",
            [BlueprintDomain.HEMODYNAMICS, BlueprintDomain.PHARMACOLOGY],
            DifficultyLevel.MODERATE,
            ItemType.SINGLE_BEST
        )

    def can_generate(self, context: PatientContext) -> bool:
        return len(context.top_outcomes) > 0 and len(context.extracted_factors) > 0

    def generate(self, context: PatientContext, mode: LearningMode,
                seed: int) -> Optional[Dict[str, Any]]:
        random.seed(seed)

        if not self.can_generate(context):
            return None

        # Select highest risk outcome
        top_outcome = context.top_outcomes[0]
        outcome_label = top_outcome.get('outcome_label', 'complication')

        # Get contributing factors
        factors = [f.get('plain_label', '') for f in context.extracted_factors[:2]]
        factor_text = ' and '.join(factors) if factors else 'multiple risk factors'

        # Build patient-specific stem
        age_text = f"{context.age}-year-old" if context.age else "patient"
        weight_text = f" ({context.weight_kg} kg)" if context.weight_kg else ""

        stem = f"A {age_text}{weight_text} with {factor_text} undergoing {context.surgery_domain or 'surgery'} has the largest increase in risk of {outcome_label.lower()}. The best pre-induction mitigation for this patient is:"

        # Generate options based on outcome and factors
        options = self._generate_risk_action_options(top_outcome, context, mode)

        # Determine correct answer based on evidence
        correct_key = self._determine_correct_action(top_outcome, context)

        rationale = self._generate_risk_action_rationale(top_outcome, context, correct_key)

        return {
            'stem': stem,
            'options': options,
            'correct_keys': [correct_key],
            'rationale': rationale,
            'patient_anchors': [f"age_{context.age}", factor_text, outcome_label],
            'citations': self._get_outcome_citations(top_outcome)
        }

    def _generate_risk_action_options(self, outcome: Dict[str, Any],
                                    context: PatientContext, mode: LearningMode) -> List[str]:
        """Generate evidence-based options for risk mitigation"""
        outcome_token = outcome.get('outcome', '').upper()

        # Common mitigation strategies by outcome
        strategies = {
            'LARYNGOSPASM': [
                'Albuterol pre-treatment and deep extubation',
                'Prophylactic lidocaine and gentle suctioning',
                'High-dose opioids and rapid sequence induction',
                'Ketamine induction and early extubation',
                'Sevoflurane induction with maintained spontaneous ventilation'
            ],
            'BRONCHOSPASM': [
                'Pre-operative bronchodilator therapy',
                'Propofol induction with ketamine',
                'High-dose steroid premedication',
                'Avoid desflurane, use sevoflurane',
                'Deep extubation under anesthesia'
            ],
            'PONV': [
                'Multimodal prophylaxis with ondansetron and dexamethasone',
                'Total intravenous anesthesia technique',
                'High-dose opioid-based technique',
                'Scopolamine patch and metoclopramide',
                'Regional anesthesia when appropriate'
            ]
        }

        if outcome_token in strategies:
            options = strategies[outcome_token].copy()
        else:
            # Generic options
            options = [
                'Risk-specific prophylactic medication',
                'Modified anesthetic technique',
                'Enhanced monitoring approach',
                'Alternative anesthetic plan',
                'Specialized equipment preparation'
            ]

        # Adjust complexity for mode
        if mode == LearningMode.BASICS:
            # Make options more distinct
            return options[:4]
        else:
            # Keep subtle differences for board-style
            return options

    def _determine_correct_action(self, outcome: Dict[str, Any],
                                context: PatientContext) -> int:
        """Determine correct answer index based on evidence"""
        # This would integrate with evidence base in production
        # For now, use outcome-specific logic
        outcome_token = outcome.get('outcome', '').upper()

        correct_indices = {
            'LARYNGOSPASM': 1,  # Prophylactic lidocaine
            'BRONCHOSPASM': 0,  # Pre-operative bronchodilator
            'PONV': 0          # Multimodal prophylaxis
        }

        return correct_indices.get(outcome_token, 0)

    def _generate_risk_action_rationale(self, outcome: Dict[str, Any],
                                      context: PatientContext, correct_key: int) -> str:
        """Generate evidence-based rationale"""
        outcome_label = outcome.get('outcome_label', 'complication')
        risk_ratio = outcome.get('risk_ratio', 1.0)

        rationale = f"This patient has a {risk_ratio:.1f}x increased risk of {outcome_label.lower()} based on their risk factors. "

        # Add outcome-specific rationale
        outcome_token = outcome.get('outcome', '').upper()
        if outcome_token == 'LARYNGOSPASM':
            rationale += "Prophylactic lidocaine (1-2 mg/kg IV) reduces laryngospasm incidence by 50-70% in high-risk patients."
        elif outcome_token == 'BRONCHOSPASM':
            rationale += "Pre-operative bronchodilator therapy significantly reduces bronchospasm risk in patients with reactive airway disease."
        elif outcome_token == 'PONV':
            rationale += "Multimodal prophylaxis with 5-HT3 antagonist and corticosteroid reduces PONV by 70-80% in high-risk patients."

        return rationale

    def _get_outcome_citations(self, outcome: Dict[str, Any]) -> List[Citation]:
        """Get citations for outcome-specific evidence"""
        # This would pull from actual evidence base
        return [Citation(pmid="placeholder", title="Evidence-based outcome management")]

class DoseCalculationTemplate(QuestionTemplate):
    """Patient-specific dose calculation questions"""

    def __init__(self):
        super().__init__(
            "dose_calculation",
            [BlueprintDomain.PHARMACOLOGY],
            DifficultyLevel.MODERATE,
            ItemType.SINGLE_BEST
        )

    def can_generate(self, context: PatientContext) -> bool:
        return (context.weight_kg is not None and
                len(context.medication_plan.get('draw_now', [])) > 0)

    def generate(self, context: PatientContext, mode: LearningMode,
                seed: int) -> Optional[Dict[str, Any]]:
        random.seed(seed)

        if not self.can_generate(context):
            return None

        # Select medication from draw_now bucket
        draw_now_meds = context.medication_plan.get('draw_now', [])
        if not draw_now_meds:
            return None

        med = random.choice(draw_now_meds)
        med_name = med.get('name', 'medication')

        # Get dose calculation info
        dose_calc = med.get('dose_calculation', {})
        mg_dose = dose_calc.get('mg')
        mcg_dose = dose_calc.get('mcg')
        concentration = dose_calc.get('concentration', '1 mg/mL')

        if not (mg_dose or mcg_dose):
            return None

        # Build patient-specific stem
        weight = context.weight_kg
        primary_dose = mg_dose if mg_dose else mcg_dose / 1000
        unit = 'mg' if mg_dose else 'mcg'
        dose_per_kg = primary_dose / weight if weight else 0

        stem = f"For a {weight} kg patient with high {self._get_indication_from_factors(context)} risk, the {med_name} IV push dose is {dose_per_kg:.1f} {unit}/kg. From {concentration}, draw:"

        # Calculate correct volume
        conc_value = self._parse_concentration(concentration)
        if mg_dose:
            correct_volume = mg_dose / conc_value
        else:
            correct_volume = (mcg_dose / 1000) / conc_value

        # Generate options
        options = self._generate_volume_options(correct_volume, mode)
        correct_key = self._find_correct_volume_index(options, correct_volume)

        rationale = f"Dose calculation: {weight} kg × {dose_per_kg:.1f} {unit}/kg = {primary_dose:.1f} {unit}. From {concentration}: {primary_dose:.1f} {unit} ÷ {conc_value} {unit}/mL = {correct_volume:.1f} mL."

        return {
            'stem': stem,
            'options': options,
            'correct_keys': [correct_key],
            'rationale': rationale,
            'patient_anchors': [f"weight_{weight}kg", med_name, "dose_calculation"],
            'citations': [Citation(title="Medication dosing guidelines")]
        }

    def _get_indication_from_factors(self, context: PatientContext) -> str:
        """Get indication based on patient factors"""
        factors = [f.get('token', '') for f in context.extracted_factors]

        if 'ASTHMA' in factors or 'BRONCHOSPASM' in factors:
            return 'bronchospasm'
        elif 'LARYNGOSPASM' in factors:
            return 'laryngospasm'
        else:
            return 'complication'

    def _parse_concentration(self, concentration: str) -> float:
        """Parse concentration string to numeric value"""
        # Extract number from strings like "1 mg/mL", "100 mcg/mL"
        match = re.search(r'(\d+(?:\.\d+)?)', concentration)
        if match:
            return float(match.group(1))
        return 1.0

    def _generate_volume_options(self, correct_volume: float, mode: LearningMode) -> List[str]:
        """Generate volume options with distractors"""
        options = []

        # Correct answer
        options.append(f"{correct_volume:.1f} mL")

        # Common calculation errors
        options.append(f"{correct_volume * 2:.1f} mL")  # Double dose
        options.append(f"{correct_volume / 2:.1f} mL")  # Half dose
        options.append(f"{correct_volume * 10:.1f} mL")  # Unit error

        if mode == LearningMode.BOARD:
            # Add more subtle distractors
            options.append(f"{correct_volume * 1.5:.1f} mL")

        random.shuffle(options)
        return options[:4]

    def _find_correct_volume_index(self, options: List[str], correct_volume: float) -> int:
        """Find index of correct volume in shuffled options"""
        correct_text = f"{correct_volume:.1f} mL"
        for i, option in enumerate(options):
            if option == correct_text:
                return i
        return 0

class ContraindicationTemplate(QuestionTemplate):
    """Contraindication questions based on patient factors"""

    def __init__(self):
        super().__init__(
            "contraindication",
            [BlueprintDomain.PHARMACOLOGY],
            DifficultyLevel.ADVANCED,
            ItemType.SINGLE_BEST
        )

    def can_generate(self, context: PatientContext) -> bool:
        return len(context.medication_plan.get('contraindicated', [])) > 0

    def generate(self, context: PatientContext, mode: LearningMode,
                seed: int) -> Optional[Dict[str, Any]]:
        random.seed(seed)

        if not self.can_generate(context):
            return None

        contraindicated_meds = context.medication_plan.get('contraindicated', [])
        med = random.choice(contraindicated_meds)

        med_name = med.get('name', 'medication')
        contraindication = med.get('contraindication_reason', 'patient factors')

        # Find the specific factor causing contraindication
        contraindication_factor = self._identify_contraindication_factor(med, context)

        stem = f"Given this patient's {contraindication_factor}, which anesthetic medication is contraindicated?"

        # Generate options with contraindicated med as correct answer
        options = self._generate_contraindication_options(med_name, mode)

        # Correct answer is the contraindicated medication
        correct_key = 0  # First option is always the contraindicated med

        rationale = f"{med_name} is contraindicated in patients with {contraindication_factor} due to {contraindication}."

        return {
            'stem': stem,
            'options': options,
            'correct_keys': [correct_key],
            'rationale': rationale,
            'patient_anchors': [contraindication_factor, med_name],
            'citations': [Citation(title="Contraindication guidelines")]
        }

    def _identify_contraindication_factor(self, med: Dict[str, Any],
                                        context: PatientContext) -> str:
        """Identify which patient factor causes the contraindication"""
        factors = [f.get('plain_label', '') for f in context.extracted_factors]

        # Common contraindication patterns
        if any('malignant hyperthermia' in f.lower() for f in factors):
            return 'malignant hyperthermia susceptibility'
        elif any('allergy' in f.lower() for f in factors):
            return 'documented drug allergy'
        elif any('renal' in f.lower() for f in factors):
            return 'renal dysfunction'
        else:
            return 'medical history'

    def _generate_contraindication_options(self, contraindicated_med: str,
                                         mode: LearningMode) -> List[str]:
        """Generate options with contraindicated med first"""
        options = [contraindicated_med]

        # Add alternative medications as distractors
        alternatives = [
            'Propofol',
            'Etomidate',
            'Ketamine',
            'Midazolam'
        ]

        # Remove the contraindicated med if it's in alternatives
        alternatives = [alt for alt in alternatives if alt.lower() != contraindicated_med.lower()]

        options.extend(alternatives[:3])
        return options

# Template registry
QUESTION_TEMPLATES = [
    RiskActionTemplate(),
    DoseCalculationTemplate(),
    ContraindicationTemplate()
]

def get_applicable_templates(context: PatientContext) -> List[QuestionTemplate]:
    """Get list of templates that can generate questions for this patient"""
    applicable = []
    for template in QUESTION_TEMPLATES:
        if template.can_generate(context):
            applicable.append(template)
    return applicable