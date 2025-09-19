#!/usr/bin/env python3
"""
Recursive Learning System for Meridian with Safety Constraints
Inspired by DiagnoseME's constrained learning protocols
"""

import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, asdict
from pathlib import Path
import statistics

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class LearningFailure:
    """Represents a learning failure that needs improvement"""
    case_id: str
    failure_type: str  # 'parsing', 'medication', 'risk', 'safety'
    expected: List[str]
    actual: List[str]
    severity: str  # 'low', 'medium', 'high', 'critical'
    safety_impact: bool
    improvement_suggestions: List[str]

@dataclass
class SafetyConstraint:
    """Safety constraint that must never be violated"""
    constraint_id: str
    description: str
    validation_function: str
    severity: str  # 'warning', 'error', 'critical'
    examples: List[str]

class SafetyConstraintEngine:
    """Enforces safety constraints during learning"""

    CRITICAL_CONSTRAINTS = [
        SafetyConstraint(
            constraint_id="SC001",
            description="No contraindicated medications in standard recommendations",
            validation_function="validate_no_contraindicated_in_standard",
            severity="critical",
            examples=["Morphine in COPD patients", "Succinylcholine in hyperkalemia"]
        ),
        SafetyConstraint(
            constraint_id="SC002",
            description="Pediatric medications must include weight-based dosing",
            validation_function="validate_pediatric_dosing",
            severity="critical",
            examples=["Missing weight for propofol dosing in 5-year-old"]
        ),
        SafetyConstraint(
            constraint_id="SC003",
            description="High-risk drug interactions must be flagged",
            validation_function="validate_drug_interactions",
            severity="critical",
            examples=["MAOI + meperidine", "Warfarin + aspirin without warnings"]
        ),
        SafetyConstraint(
            constraint_id="SC004",
            description="Emergency situations must include appropriate protocols",
            validation_function="validate_emergency_protocols",
            severity="error",
            examples=["Trauma without RSI protocol", "Anaphylaxis without epinephrine"]
        ),
        SafetyConstraint(
            constraint_id="SC005",
            description="Risk assessments must include evidence grades",
            validation_function="validate_evidence_grades",
            severity="warning",
            examples=["Risk calculation without literature support"]
        )
    ]

    @staticmethod
    def validate_no_contraindicated_in_standard(result: Dict) -> Tuple[bool, List[str]]:
        """Ensure contraindicated meds aren't in standard recommendations"""
        violations = []

        meds = result.get('medications', {})
        contraindicated = {med.get('medication', '') for med in meds.get('contraindicated', [])}
        standard = {med.get('medication', '') for med in meds.get('standard', [])}

        overlap = contraindicated.intersection(standard)
        if overlap:
            violations.append(f"Contraindicated medications in standard list: {overlap}")

        return len(violations) == 0, violations

    @staticmethod
    def validate_pediatric_dosing(result: Dict, demographics: Dict) -> Tuple[bool, List[str]]:
        """Validate pediatric dosing includes weight considerations"""
        violations = []

        if demographics.get('age_years', 100) < 18:
            weight = demographics.get('weight_kg')
            if not weight:
                violations.append("Pediatric case missing weight for medication dosing")

            meds = result.get('medications', {})
            for category in ['standard', 'consider', 'draw_now']:
                for med in meds.get(category, []):
                    dose = med.get('dose', '')
                    if 'mg/kg' not in dose and 'weight' not in dose.lower():
                        if med.get('medication') in ['PROPOFOL', 'ROCURONIUM', 'CISATRACURIUM']:
                            violations.append(f"Pediatric medication {med.get('medication')} missing weight-based dosing")

        return len(violations) == 0, violations

    @staticmethod
    def validate_drug_interactions(result: Dict) -> Tuple[bool, List[str]]:
        """Validate high-risk drug interactions are flagged"""
        violations = []

        meds = result.get('medications', {})
        contraindicated = meds.get('contraindicated', [])

        # Check for specific high-risk combinations
        all_meds = []
        for category in ['standard', 'consider', 'draw_now']:
            all_meds.extend([med.get('medication', '') for med in meds.get(category, [])])

        # MAOI interactions
        if any('MAOI' in med for med in all_meds):
            if 'MEPERIDINE' in all_meds and not any('MAOI' in med.get('contraindication_reason', '') for med in contraindicated):
                violations.append("MAOI + Meperidine interaction not flagged")

        return len(violations) == 0, violations

    @staticmethod
    def validate_emergency_protocols(result: Dict, case_text: str) -> Tuple[bool, List[str]]:
        """Validate emergency cases include appropriate protocols"""
        violations = []

        # Check for trauma cases
        if any(keyword in case_text.lower() for keyword in ['trauma', 'emergency', 'unstable', 'crash']):
            recommendations = result.get('recommendations', {})
            intraop = recommendations.get('intraoperative', [])

            # Should include rapid sequence intubation for trauma
            if 'trauma' in case_text.lower():
                rsi_mentioned = any('rapid' in rec.get('action', '').lower() or 'rsi' in rec.get('action', '').lower()
                                  for rec in intraop)
                if not rsi_mentioned:
                    violations.append("Trauma case missing rapid sequence intubation protocol")

        return len(violations) == 0, violations

    @staticmethod
    def validate_evidence_grades(result: Dict) -> Tuple[bool, List[str]]:
        """Validate risk assessments include evidence grades"""
        violations = []

        risks = result.get('risks', {}).get('risks', [])
        for risk in risks:
            if not risk.get('evidence_grade'):
                violations.append(f"Risk {risk.get('outcome')} missing evidence grade")

        return len(violations) == 0, violations

    def validate_all_constraints(self, result: Dict, demographics: Dict = None, case_text: str = "") -> Tuple[bool, List[str]]:
        """Validate all safety constraints"""
        all_violations = []
        critical_violation = False

        for constraint in self.CRITICAL_CONSTRAINTS:
            try:
                if constraint.validation_function == "validate_no_contraindicated_in_standard":
                    is_valid, violations = self.validate_no_contraindicated_in_standard(result)
                elif constraint.validation_function == "validate_pediatric_dosing":
                    is_valid, violations = self.validate_pediatric_dosing(result, demographics or {})
                elif constraint.validation_function == "validate_drug_interactions":
                    is_valid, violations = self.validate_drug_interactions(result)
                elif constraint.validation_function == "validate_emergency_protocols":
                    is_valid, violations = self.validate_emergency_protocols(result, case_text)
                elif constraint.validation_function == "validate_evidence_grades":
                    is_valid, violations = self.validate_evidence_grades(result)
                else:
                    continue

                if not is_valid:
                    for violation in violations:
                        all_violations.append(f"{constraint.constraint_id}: {violation}")
                        if constraint.severity == "critical":
                            critical_violation = True

            except Exception as e:
                logger.error(f"Error validating constraint {constraint.constraint_id}: {e}")

        return not critical_violation, all_violations

class RecursiveLearningEngine:
    """Recursive learning engine with safety constraints"""

    def __init__(self):
        self.safety_engine = SafetyConstraintEngine()
        self.learning_history = []
        self.improvement_patterns = {}
        self.safety_violations_log = []

    def analyze_failures(self, evaluation_results: Dict) -> List[LearningFailure]:
        """Analyze evaluation results to identify learning opportunities"""
        failures = []

        for result in evaluation_results.get('detailed_results', []):
            if not result.get('success', False):
                continue

            case_id = result.get('case_id')
            detailed = result.get('detailed_results', {})

            # Parsing failures
            if result.get('parsing_accuracy', 0) < 0.8:
                failures.append(LearningFailure(
                    case_id=case_id,
                    failure_type='parsing',
                    expected=detailed.get('expected_conditions', []),
                    actual=detailed.get('extracted_conditions', []),
                    severity='high' if result.get('parsing_accuracy', 0) < 0.5 else 'medium',
                    safety_impact=False,
                    improvement_suggestions=self._generate_parsing_improvements(detailed)
                ))

            # Medication failures
            if result.get('medication_accuracy', 0) < 0.8:
                failures.append(LearningFailure(
                    case_id=case_id,
                    failure_type='medication',
                    expected=detailed.get('expected_medications', []),
                    actual=list(detailed.get('recommended_medications', {}).keys()),
                    severity='critical' if not result.get('safety_compliance', True) else 'high',
                    safety_impact=not result.get('safety_compliance', True),
                    improvement_suggestions=self._generate_medication_improvements(detailed)
                ))

            # Safety failures
            if not result.get('safety_compliance', True):
                failures.append(LearningFailure(
                    case_id=case_id,
                    failure_type='safety',
                    expected=[],
                    actual=detailed.get('safety_violations', []),
                    severity='critical',
                    safety_impact=True,
                    improvement_suggestions=self._generate_safety_improvements(detailed)
                ))

        return failures

    def _generate_parsing_improvements(self, detailed_results: Dict) -> List[str]:
        """Generate specific parsing improvement suggestions"""
        suggestions = []

        expected = set(detailed_results.get('expected_conditions', []))
        actual = set(detailed_results.get('extracted_conditions', []))

        missing = expected - actual
        extra = actual - expected

        if missing:
            suggestions.append(f"Add pattern matching for: {', '.join(missing)}")

        if extra:
            suggestions.append(f"Improve specificity to avoid false positives: {', '.join(extra)}")

        # Pattern-specific suggestions
        for condition in missing:
            if 'CORONARY' in condition:
                suggestions.append("Enhance cardiovascular condition patterns (CAD, MI, angina)")
            elif 'DIABETES' in condition:
                suggestions.append("Improve diabetes pattern matching (DM, T1DM, T2DM)")
            elif 'KIDNEY' in condition:
                suggestions.append("Add renal condition patterns (CKD, ESRD, dialysis)")

        return suggestions

    def _generate_medication_improvements(self, detailed_results: Dict) -> List[str]:
        """Generate medication recommendation improvements"""
        suggestions = []

        # Analyze medication patterns
        recommended = detailed_results.get('recommended_medications', {})

        # Check for missing drug classes
        if not recommended.get('contraindicated'):
            suggestions.append("Improve contraindication detection algorithms")

        if not recommended.get('consider'):
            suggestions.append("Enhance specialized medication recommendations")

        # Safety-focused improvements
        suggestions.append("Validate all medication recommendations against patient conditions")
        suggestions.append("Ensure drug interaction checking is comprehensive")

        return suggestions

    def _generate_safety_improvements(self, detailed_results: Dict) -> List[str]:
        """Generate safety-focused improvements"""
        suggestions = []

        violations = detailed_results.get('safety_violations', [])

        for violation in violations:
            if 'contraindicated' in violation.lower():
                suggestions.append("Strengthen contraindication validation logic")
            elif 'pediatric' in violation.lower():
                suggestions.append("Enhance pediatric safety protocols")
            elif 'interaction' in violation.lower():
                suggestions.append("Improve drug interaction detection")

        suggestions.append("Implement additional safety checkpoints")
        suggestions.append("Add more comprehensive safety validation rules")

        return suggestions

    def generate_improvement_plan(self, failures: List[LearningFailure]) -> Dict:
        """Generate a prioritized improvement plan"""

        # Group failures by type and severity
        by_type = {}
        by_severity = {'critical': [], 'high': [], 'medium': [], 'low': []}

        for failure in failures:
            if failure.failure_type not in by_type:
                by_type[failure.failure_type] = []
            by_type[failure.failure_type].append(failure)
            by_severity[failure.severity].append(failure)

        # Priority rules (safety first)
        improvement_plan = {
            "timestamp": datetime.now().isoformat(),
            "total_failures": len(failures),
            "safety_critical_count": len([f for f in failures if f.safety_impact]),
            "priority_order": [],
            "detailed_improvements": {}
        }

        # 1. Critical safety issues first
        if by_severity['critical']:
            improvement_plan["priority_order"].append("critical_safety")
            improvement_plan["detailed_improvements"]["critical_safety"] = {
                "description": "Address critical safety violations immediately",
                "failures": [asdict(f) for f in by_severity['critical'] if f.safety_impact],
                "actions": self._get_safety_actions(),
                "estimated_effort": "High",
                "timeline": "Immediate"
            }

        # 2. High-severity parsing issues
        high_parsing = [f for f in by_severity['high'] if f.failure_type == 'parsing']
        if high_parsing:
            improvement_plan["priority_order"].append("parsing_accuracy")
            improvement_plan["detailed_improvements"]["parsing_accuracy"] = {
                "description": "Improve medical condition parsing accuracy",
                "failures": [asdict(f) for f in high_parsing],
                "actions": self._get_parsing_actions(high_parsing),
                "estimated_effort": "Medium",
                "timeline": "1-2 weeks"
            }

        # 3. Medication recommendation improvements
        med_failures = by_type.get('medication', [])
        if med_failures:
            improvement_plan["priority_order"].append("medication_accuracy")
            improvement_plan["detailed_improvements"]["medication_accuracy"] = {
                "description": "Enhance medication recommendation engine",
                "failures": [asdict(f) for f in med_failures],
                "actions": self._get_medication_actions(med_failures),
                "estimated_effort": "Medium",
                "timeline": "2-3 weeks"
            }

        return improvement_plan

    def _get_safety_actions(self) -> List[str]:
        """Get specific safety improvement actions"""
        return [
            "Implement additional validation checkpoints",
            "Add more contraindication rules",
            "Enhance drug interaction database",
            "Improve pediatric safety protocols",
            "Add emergency protocol validation",
            "Implement safety constraint testing"
        ]

    def _get_parsing_actions(self, failures: List[LearningFailure]) -> List[str]:
        """Get specific parsing improvement actions"""
        actions = []

        # Analyze common missing conditions
        all_missing = []
        for failure in failures:
            all_missing.extend(failure.expected)

        condition_counts = {}
        for condition in all_missing:
            condition_counts[condition] = condition_counts.get(condition, 0) + 1

        # Most common missed conditions
        common_missed = sorted(condition_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        for condition, count in common_missed:
            actions.append(f"Add pattern matching for {condition} (missed in {count} cases)")

        actions.extend([
            "Expand medical terminology database",
            "Improve synonym recognition",
            "Add context-aware parsing",
            "Enhance negation detection"
        ])

        return actions

    def _get_medication_actions(self, failures: List[LearningFailure]) -> List[str]:
        """Get specific medication improvement actions"""
        return [
            "Expand medication knowledge base",
            "Improve drug interaction detection",
            "Add more contraindication rules",
            "Enhance dose calculation algorithms",
            "Improve specialty-specific recommendations",
            "Add evidence-based medication protocols"
        ]

    def validate_proposed_changes(self, improvement_plan: Dict) -> Tuple[bool, List[str]]:
        """Validate that proposed changes don't violate safety constraints"""

        # Safety validation rules for improvements
        safety_concerns = []

        # Check if any improvements might compromise safety
        for improvement_type, details in improvement_plan.get("detailed_improvements", {}).items():
            actions = details.get("actions", [])

            # Flag potentially risky changes
            for action in actions:
                if any(risky_word in action.lower() for risky_word in ['remove', 'disable', 'bypass']):
                    safety_concerns.append(f"Action '{action}' may compromise safety")

        # Ensure safety improvements are prioritized
        priority_order = improvement_plan.get("priority_order", [])
        if "critical_safety" not in priority_order and improvement_plan.get("safety_critical_count", 0) > 0:
            safety_concerns.append("Critical safety issues must be prioritized first")

        return len(safety_concerns) == 0, safety_concerns

    def execute_learning_cycle(self, evaluation_results: Dict) -> Dict:
        """Execute a complete learning cycle with safety validation"""

        logger.info("Starting recursive learning cycle...")

        # 1. Analyze failures
        failures = self.analyze_failures(evaluation_results)
        logger.info(f"Identified {len(failures)} learning opportunities")

        # 2. Generate improvement plan
        improvement_plan = self.generate_improvement_plan(failures)
        logger.info(f"Generated improvement plan with {len(improvement_plan['priority_order'])} priorities")

        # 3. Safety validation
        is_safe, safety_concerns = self.validate_proposed_changes(improvement_plan)
        if not is_safe:
            logger.warning(f"Safety concerns identified: {safety_concerns}")
            improvement_plan["safety_validation"] = {
                "approved": False,
                "concerns": safety_concerns,
                "requires_review": True
            }
        else:
            improvement_plan["safety_validation"] = {
                "approved": True,
                "concerns": [],
                "requires_review": False
            }

        # 4. Record learning history
        learning_record = {
            "timestamp": datetime.now().isoformat(),
            "failures_analyzed": len(failures),
            "improvement_plan": improvement_plan,
            "safety_approved": is_safe
        }

        self.learning_history.append(learning_record)

        # 5. Save learning results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        learning_filename = f"learning_cycle_results_{timestamp}.json"

        with open(learning_filename, 'w') as f:
            json.dump(learning_record, f, indent=2)

        logger.info(f"Learning cycle complete. Results saved to {learning_filename}")

        return learning_record

def run_recursive_learning_evaluation():
    """Run the complete recursive learning evaluation"""

    # Import the comprehensive testing framework
    from comprehensive_test_100_cases import run_comprehensive_evaluation

    logger.info("=== MERIDIAN RECURSIVE LEARNING SYSTEM ===")

    # 1. Run comprehensive evaluation
    logger.info("Phase 1: Running comprehensive evaluation...")
    evaluation_results = run_comprehensive_evaluation()

    # 2. Initialize learning engine
    learning_engine = RecursiveLearningEngine()

    # 3. Execute learning cycle
    logger.info("Phase 2: Executing recursive learning cycle...")
    learning_results = learning_engine.execute_learning_cycle(evaluation_results)

    # 4. Print summary
    print("\n" + "="*70)
    print("RECURSIVE LEARNING ANALYSIS COMPLETE")
    print("="*70)

    eval_summary = evaluation_results["summary"]
    learning_summary = learning_results["improvement_plan"]

    print(f"Evaluation Success Rate: {eval_summary['success_rate']:.1%}")
    print(f"Safety Compliance Rate: {eval_summary['safety_compliance_rate']:.1%}")
    print(f"Learning Opportunities Identified: {learning_summary['total_failures']}")
    print(f"Safety-Critical Issues: {learning_summary['safety_critical_count']}")
    print(f"Improvement Plan Approved: {'Yes' if learning_results['safety_approved'] else 'No'}")

    if learning_summary["priority_order"]:
        print(f"\nTop Priorities:")
        for i, priority in enumerate(learning_summary["priority_order"][:3], 1):
            details = learning_summary["detailed_improvements"][priority]
            print(f"  {i}. {details['description']} ({details['timeline']})")

    print("="*70)

    return {
        "evaluation_results": evaluation_results,
        "learning_results": learning_results
    }

if __name__ == "__main__":
    results = run_recursive_learning_evaluation()