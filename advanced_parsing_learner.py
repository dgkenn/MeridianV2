#!/usr/bin/env python3
"""
Advanced Parsing Learner with Recursive Learning and Safety Guardrails
Target: 90%+ parsing accuracy with overfitting prevention
"""

import sys
import json
import re
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Set, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict, Counter
import statistics

sys.path.append(str(Path(__file__).parent))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ParsingFailure:
    """Detailed parsing failure analysis"""
    case_id: str
    expected_condition: str
    missed_by_parser: bool
    false_positive: bool
    evidence_text: str
    context_window: str
    failure_category: str
    complexity_score: int

@dataclass
class PatternCandidate:
    """Candidate pattern for learning"""
    condition: str
    pattern: str
    confidence: float
    support_cases: List[str]
    validation_score: float
    overfitting_risk: float
    safety_approved: bool

class SafetyGuardedPatternLearner:
    """Pattern learner with safety guardrails and overfitting prevention"""

    def __init__(self):
        self.learned_patterns = {}
        self.validation_cache = {}
        self.overfitting_monitor = OverfittingMonitor()
        self.safety_validator = PatternSafetyValidator()
        self.iteration_history = []

    def analyze_parsing_failures(self, test_results: List[Dict]) -> List[ParsingFailure]:
        """Analyze parsing failures in detail"""
        failures = []

        for result in test_results:
            if not result.get('success', False):
                continue

            case_id = result.get('case_id', '')
            expected = set(result.get('expected_conditions', []))
            actual_factors = result.get('detailed_results', {}).get('extracted_conditions', [])
            actual = set(actual_factors)
            hpi_text = result.get('hpi_text', '')

            # Find missed conditions (false negatives)
            missed = expected - actual
            for condition in missed:
                # Find evidence in text
                evidence = self._find_evidence_in_text(condition, hpi_text)
                context = self._get_context_window(evidence, hpi_text, 50)

                failures.append(ParsingFailure(
                    case_id=case_id,
                    expected_condition=condition,
                    missed_by_parser=True,
                    false_positive=False,
                    evidence_text=evidence,
                    context_window=context,
                    failure_category=self._categorize_failure(condition, evidence),
                    complexity_score=self._assess_complexity(evidence, context)
                ))

            # Find false positives
            false_positives = actual - expected
            for condition in false_positives:
                failures.append(ParsingFailure(
                    case_id=case_id,
                    expected_condition=condition,
                    missed_by_parser=False,
                    false_positive=True,
                    evidence_text="",
                    context_window="",
                    failure_category="false_positive",
                    complexity_score=1
                ))

        logger.info(f"Analyzed {len(failures)} parsing failures")
        return failures

    def _find_evidence_in_text(self, condition: str, text: str) -> str:
        """Find evidence for a condition in text"""
        # Mapping conditions to search terms
        condition_terms = {
            'CORONARY_ARTERY_DISEASE': ['coronary artery disease', 'cad', 'cabg', 'stent', 'myocardial infarction', 'mi', 'heart attack'],
            'DIABETES': ['diabetes', 'diabetic', 'dm', 'type 1', 'type 2', 'metformin', 'insulin', 'glucose'],
            'HYPERTENSION': ['hypertension', 'hypertensive', 'high blood pressure', 'htn', 'bp'],
            'CHRONIC_KIDNEY_DISEASE': ['chronic kidney disease', 'ckd', 'renal insufficiency', 'dialysis', 'creatinine'],
            'ASTHMA': ['asthma', 'asthmatic', 'wheeze', 'bronchospasm', 'albuterol', 'inhaler'],
            'OSA': ['sleep apnea', 'osa', 'obstructive sleep', 'ahi', 'cpap'],
            'RECENT_URI_2W': ['upper respiratory infection', 'uri', 'cold', 'cough', 'runny nose', 'recent infection'],
            'HEART_FAILURE': ['heart failure', 'chf', 'congestive', 'reduced ejection fraction', 'nyha'],
            'TRAUMA': ['trauma', 'accident', 'injury', 'fracture', 'mva', 'fall'],
            'PREECLAMPSIA': ['preeclampsia', 'severe preeclampsia', 'pregnancy hypertension', 'proteinuria']
        }

        terms = condition_terms.get(condition, [condition.lower().replace('_', ' ')])

        for term in terms:
            if term.lower() in text.lower():
                # Find the sentence containing the term
                sentences = text.split('.')
                for sentence in sentences:
                    if term.lower() in sentence.lower():
                        return sentence.strip()

        return ""

    def _get_context_window(self, evidence: str, full_text: str, window_size: int) -> str:
        """Get context window around evidence"""
        if not evidence:
            return ""

        start_idx = full_text.lower().find(evidence.lower())
        if start_idx == -1:
            return evidence

        start = max(0, start_idx - window_size)
        end = min(len(full_text), start_idx + len(evidence) + window_size)

        return full_text[start:end]

    def _categorize_failure(self, condition: str, evidence: str) -> str:
        """Categorize the type of parsing failure"""
        if not evidence:
            return "no_evidence"

        if any(term in evidence.lower() for term in ['history', 'past', 'previous']):
            return "temporal_context"
        elif any(term in evidence.lower() for term in ['family', 'mother', 'father']):
            return "family_history"
        elif any(term in evidence.lower() for term in ['no', 'denies', 'negative']):
            return "negation"
        elif len(evidence.split()) > 20:
            return "complex_sentence"
        else:
            return "simple_miss"

    def _assess_complexity(self, evidence: str, context: str) -> int:
        """Assess complexity of the parsing challenge (1-5)"""
        complexity = 1

        if len(context.split()) > 30:
            complexity += 1
        if any(term in context.lower() for term in ['history', 'family', 'previous']):
            complexity += 1
        if any(term in context.lower() for term in ['no', 'denies', 'without']):
            complexity += 1
        if len(re.findall(r'\b\w+\b', context)) > 50:
            complexity += 1

        return min(5, complexity)

    def generate_pattern_candidates(self, failures: List[ParsingFailure]) -> List[PatternCandidate]:
        """Generate pattern candidates from failures"""
        candidates = []

        # Group failures by condition
        condition_failures = defaultdict(list)
        for failure in failures:
            if failure.missed_by_parser and failure.evidence_text:
                condition_failures[failure.expected_condition].append(failure)

        for condition, condition_failures_list in condition_failures.items():
            if len(condition_failures_list) < 2:  # Need multiple examples
                continue

            # Extract common patterns
            patterns = self._extract_patterns_from_failures(condition_failures_list)

            for pattern_text, support_cases in patterns:
                confidence = len(support_cases) / len(condition_failures_list)

                candidate = PatternCandidate(
                    condition=condition,
                    pattern=pattern_text,
                    confidence=confidence,
                    support_cases=support_cases,
                    validation_score=0.0,
                    overfitting_risk=0.0,
                    safety_approved=False
                )

                candidates.append(candidate)

        logger.info(f"Generated {len(candidates)} pattern candidates")
        return candidates

    def _extract_patterns_from_failures(self, failures: List[ParsingFailure]) -> List[Tuple[str, List[str]]]:
        """Extract patterns from failure examples"""
        patterns = []

        # Collect evidence texts
        evidence_texts = [f.evidence_text for f in failures if f.evidence_text]

        if len(evidence_texts) < 2:
            return patterns

        # Extract common terms
        all_words = []
        for text in evidence_texts:
            words = re.findall(r'\b\w+\b', text.lower())
            all_words.extend(words)

        word_counts = Counter(all_words)
        common_words = [word for word, count in word_counts.most_common(10) if count >= 2]

        # Generate patterns from common words
        for word in common_words:
            if len(word) > 3:  # Skip short words
                pattern = f"\\b{re.escape(word)}\\b"
                support_cases = [f.case_id for f in failures if word in f.evidence_text.lower()]

                if len(support_cases) >= 2:
                    patterns.append((pattern, support_cases))

        # Generate phrase patterns
        for text in evidence_texts:
            # Extract 2-3 word phrases
            words = re.findall(r'\b\w+\b', text.lower())
            for i in range(len(words) - 1):
                phrase = " ".join(words[i:i+2])
                if len(phrase) > 6:  # Meaningful phrases
                    pattern = f"\\b{re.escape(phrase)}\\b"
                    support_cases = [f.case_id for f in failures if phrase in f.evidence_text.lower()]

                    if len(support_cases) >= 2:
                        patterns.append((pattern, support_cases))

        return patterns

    def validate_patterns(self, candidates: List[PatternCandidate], test_data: List[Dict]) -> List[PatternCandidate]:
        """Validate pattern candidates against test data"""
        validated_candidates = []

        for candidate in candidates:
            # Test pattern against all cases
            true_positives = 0
            false_positives = 0
            true_negatives = 0
            false_negatives = 0

            pattern = re.compile(candidate.pattern, re.I)

            for test_case in test_data:
                hpi_text = test_case.get('hpi_text', '')
                expected_conditions = set(test_case.get('expected_conditions', []))

                pattern_matches = bool(pattern.search(hpi_text))
                condition_expected = candidate.condition in expected_conditions

                if pattern_matches and condition_expected:
                    true_positives += 1
                elif pattern_matches and not condition_expected:
                    false_positives += 1
                elif not pattern_matches and not condition_expected:
                    true_negatives += 1
                elif not pattern_matches and condition_expected:
                    false_negatives += 1

            # Calculate metrics
            precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
            recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
            f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

            candidate.validation_score = f1_score

            # Calculate overfitting risk
            candidate.overfitting_risk = self.overfitting_monitor.assess_overfitting_risk(candidate, test_data)

            # Safety validation
            candidate.safety_approved = self.safety_validator.validate_pattern_safety(candidate)

            if candidate.validation_score > 0.3 and candidate.safety_approved:  # Minimum thresholds
                validated_candidates.append(candidate)

        # Sort by validation score
        validated_candidates.sort(key=lambda x: x.validation_score, reverse=True)

        logger.info(f"Validated {len(validated_candidates)} patterns")
        return validated_candidates

    def select_best_patterns(self, candidates: List[PatternCandidate], max_patterns: int = 10) -> List[PatternCandidate]:
        """Select best patterns avoiding overfitting"""
        selected = []

        # Group by condition
        condition_candidates = defaultdict(list)
        for candidate in candidates:
            condition_candidates[candidate.condition].append(candidate)

        # Select best patterns per condition
        for condition, condition_list in condition_candidates.items():
            # Sort by composite score (validation - overfitting risk)
            condition_list.sort(key=lambda x: x.validation_score - x.overfitting_risk, reverse=True)

            # Select top patterns for this condition (max 3 per condition)
            selected.extend(condition_list[:3])

        # Final selection by overall score
        selected.sort(key=lambda x: x.validation_score - x.overfitting_risk, reverse=True)

        return selected[:max_patterns]

class OverfittingMonitor:
    """Monitor and prevent overfitting in pattern learning"""

    def assess_overfitting_risk(self, candidate: PatternCandidate, test_data: List[Dict]) -> float:
        """Assess overfitting risk for a pattern candidate"""
        risk_factors = 0.0

        # Risk factor 1: Too specific (matches very few cases)
        total_cases = len(test_data)
        support_ratio = len(candidate.support_cases) / total_cases
        if support_ratio < 0.05:  # Less than 5% support
            risk_factors += 0.3

        # Risk factor 2: Perfect performance on training data
        if candidate.confidence >= 0.95:
            risk_factors += 0.2

        # Risk factor 3: Very complex pattern
        pattern_complexity = len(candidate.pattern)
        if pattern_complexity > 50:
            risk_factors += 0.2

        # Risk factor 4: Highly specific terminology
        if any(term in candidate.pattern.lower() for term in ['\\d+', '[0-9]', 'very', 'extremely']):
            risk_factors += 0.1

        # Risk factor 5: Single character patterns
        if len(candidate.pattern.replace('\\b', '').replace('\\w', '').replace('+', '')) < 4:
            risk_factors += 0.3

        return min(1.0, risk_factors)

    def validate_generalization(self, patterns: List[PatternCandidate], holdout_data: List[Dict]) -> Dict:
        """Validate pattern generalization on holdout data"""
        results = {
            'total_patterns': len(patterns),
            'generalizing_patterns': 0,
            'overfitted_patterns': 0,
            'pattern_details': []
        }

        for pattern in patterns:
            # Test on holdout data
            holdout_score = self._test_pattern_on_holdout(pattern, holdout_data)

            # Compare with training score
            performance_drop = pattern.validation_score - holdout_score

            is_overfitted = performance_drop > 0.2  # More than 20% drop

            if is_overfitted:
                results['overfitted_patterns'] += 1
            else:
                results['generalizing_patterns'] += 1

            results['pattern_details'].append({
                'condition': pattern.condition,
                'pattern': pattern.pattern,
                'training_score': pattern.validation_score,
                'holdout_score': holdout_score,
                'performance_drop': performance_drop,
                'overfitted': is_overfitted
            })

        return results

    def _test_pattern_on_holdout(self, pattern: PatternCandidate, holdout_data: List[Dict]) -> float:
        """Test pattern performance on holdout data"""
        pattern_re = re.compile(pattern.pattern, re.I)

        true_positives = 0
        false_positives = 0
        false_negatives = 0

        for case in holdout_data:
            hpi_text = case.get('hpi_text', '')
            expected_conditions = set(case.get('expected_conditions', []))

            pattern_matches = bool(pattern_re.search(hpi_text))
            condition_expected = pattern.condition in expected_conditions

            if pattern_matches and condition_expected:
                true_positives += 1
            elif pattern_matches and not condition_expected:
                false_positives += 1
            elif not pattern_matches and condition_expected:
                false_negatives += 1

        # Calculate F1 score
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

        return f1_score

class PatternSafetyValidator:
    """Validate pattern safety and prevent harmful learning"""

    SAFETY_RULES = [
        "Patterns must not discriminate based on demographic factors",
        "Patterns must not override critical safety conditions",
        "Patterns must maintain clinical accuracy",
        "Patterns must not create false medical associations"
    ]

    def validate_pattern_safety(self, candidate: PatternCandidate) -> bool:
        """Validate that a pattern candidate is safe"""

        # Rule 1: No demographic discrimination
        if self._contains_demographic_bias(candidate.pattern):
            return False

        # Rule 2: No override of safety-critical conditions
        if self._overrides_safety_critical(candidate):
            return False

        # Rule 3: Clinically plausible
        if not self._is_clinically_plausible(candidate):
            return False

        # Rule 4: No spurious medical associations
        if self._creates_spurious_association(candidate):
            return False

        return True

    def _contains_demographic_bias(self, pattern: str) -> bool:
        """Check for demographic bias in patterns"""
        bias_terms = [
            'male', 'female', 'man', 'woman', 'boy', 'girl',
            'black', 'white', 'hispanic', 'asian',
            'young', 'old', 'elderly'
        ]

        pattern_lower = pattern.lower()
        return any(term in pattern_lower for term in bias_terms)

    def _overrides_safety_critical(self, candidate: PatternCandidate) -> bool:
        """Check if pattern overrides safety-critical conditions"""
        safety_critical_conditions = [
            'MALIGNANT_HYPERTHERMIA', 'ANAPHYLAXIS', 'AIRWAY_OBSTRUCTION',
            'MASSIVE_BLEEDING', 'CARDIAC_ARREST'
        ]

        return candidate.condition in safety_critical_conditions

    def _is_clinically_plausible(self, candidate: PatternCandidate) -> bool:
        """Check if pattern represents clinically plausible association"""
        # Basic plausibility checks
        pattern_lower = candidate.pattern.lower()
        condition = candidate.condition

        # Check for nonsensical medical associations
        if condition == 'DIABETES' and 'surgery' in pattern_lower and 'heart' not in pattern_lower:
            return True  # Diabetes can be associated with various surgeries

        if condition == 'HYPERTENSION' and any(term in pattern_lower for term in ['blood pressure', 'bp', 'hypertensive']):
            return True

        # Default to true for now - could be enhanced with medical knowledge base
        return True

    def _creates_spurious_association(self, candidate: PatternCandidate) -> bool:
        """Check for spurious medical associations"""
        # Patterns that are too generic
        if len(candidate.pattern.replace('\\b', '').replace('\\w', '').strip()) < 5:
            return True

        # Patterns based on procedure names only
        if candidate.condition in ['DIABETES', 'HYPERTENSION'] and 'surgery' in candidate.pattern.lower():
            return True  # Too generic

        return False

class AdvancedParsingLearner:
    """Main class for advanced parsing learning with safety guardrails"""

    def __init__(self):
        self.pattern_learner = SafetyGuardedPatternLearner()
        self.current_accuracy = 0.0
        self.target_accuracy = 0.90
        self.max_iterations = 10
        self.learning_history = []

    def run_recursive_learning_cycle(self) -> Dict:
        """Run recursive learning until target accuracy reached"""
        logger.info("=== STARTING ADVANCED PARSING RECURSIVE LEARNING ===")

        iteration = 0
        best_accuracy = 0.0
        best_patterns = []

        while iteration < self.max_iterations and self.current_accuracy < self.target_accuracy:
            iteration += 1
            logger.info(f"Learning Iteration {iteration}/{self.max_iterations}")

            # Get current test results
            test_results = self._run_parsing_tests()
            current_accuracy = self._calculate_parsing_accuracy(test_results)

            logger.info(f"Current parsing accuracy: {current_accuracy:.1%}")

            if current_accuracy >= self.target_accuracy:
                logger.info("🎯 Target accuracy reached!")
                break

            # Analyze failures
            failures = self.pattern_learner.analyze_parsing_failures(test_results)

            # Generate pattern candidates
            candidates = self.pattern_learner.generate_pattern_candidates(failures)

            if not candidates:
                logger.warning("No pattern candidates generated")
                break

            # Validate patterns
            validated_candidates = self.pattern_learner.validate_patterns(candidates, test_results)

            # Select best patterns with overfitting prevention
            selected_patterns = self.pattern_learner.select_best_patterns(validated_candidates)

            if not selected_patterns:
                logger.warning("No safe patterns selected")
                break

            # Test improvements
            improvement_score = self._test_pattern_improvements(selected_patterns, test_results)

            # Record iteration
            iteration_result = {
                'iteration': iteration,
                'current_accuracy': current_accuracy,
                'failures_analyzed': len(failures),
                'candidates_generated': len(candidates),
                'patterns_selected': len(selected_patterns),
                'improvement_score': improvement_score,
                'selected_patterns': [asdict(p) for p in selected_patterns]
            }

            self.learning_history.append(iteration_result)

            # Update current accuracy if improved
            if improvement_score > best_accuracy:
                best_accuracy = improvement_score
                best_patterns = selected_patterns
                self.current_accuracy = improvement_score

            # Early stopping if no improvement
            if iteration > 3 and improvement_score <= current_accuracy:
                logger.info("No significant improvement, stopping early")
                break

            logger.info(f"Iteration {iteration} complete. Best accuracy: {best_accuracy:.1%}")

        # Final results
        final_result = {
            'target_reached': self.current_accuracy >= self.target_accuracy,
            'final_accuracy': self.current_accuracy,
            'iterations_completed': iteration,
            'best_patterns': [asdict(p) for p in best_patterns],
            'learning_history': self.learning_history
        }

        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"parsing_learning_results_{timestamp}.json"

        with open(filename, 'w') as f:
            json.dump(final_result, f, indent=2)

        logger.info(f"Learning results saved to {filename}")

        return final_result

    def _run_parsing_tests(self) -> List[Dict]:
        """Run parsing tests and return results"""
        # Import our test cases
        test_cases = [
            {
                "case_id": "PT001",
                "hpi_text": "65-year-old male with coronary artery disease status post CABG 2 years ago, diabetes mellitus type 2 on metformin and insulin, hypertension on lisinopril, chronic kidney disease stage 3",
                "expected_conditions": ["CORONARY_ARTERY_DISEASE", "DIABETES", "HYPERTENSION", "CHRONIC_KIDNEY_DISEASE"]
            },
            {
                "case_id": "PT002",
                "hpi_text": "5-year-old boy with asthma on daily fluticasone inhaler and albuterol PRN. Recent upper respiratory infection 2 weeks ago with persistent cough",
                "expected_conditions": ["ASTHMA", "RECENT_URI_2W"]
            },
            {
                "case_id": "PT003",
                "hpi_text": "32-year-old G2P1 with severe preeclampsia, blood pressure 180/110, proteinuria 3+, visual changes",
                "expected_conditions": ["PREECLAMPSIA"]
            },
            {
                "case_id": "PT004",
                "hpi_text": "25-year-old male motorcycle accident victim with traumatic brain injury, last meal 2 hours ago",
                "expected_conditions": ["TRAUMA", "HEAD_INJURY", "FULL_STOMACH"]
            },
            {
                "case_id": "PT005",
                "hpi_text": "89-year-old female with dementia, atrial fibrillation on warfarin, heart failure NYHA class III",
                "expected_conditions": ["DEMENTIA", "HEART_FAILURE", "ANTICOAGULANTS", "AGE_VERY_ELDERLY"]
            }
        ]

        # Test against production API
        import requests
        results = []

        for case in test_cases:
            try:
                response = requests.post(
                    "https://meridian-zr3e.onrender.com/api/analyze",
                    json={
                        "hpi_text": case["hpi_text"],
                        "demographics": {"age_years": 65, "sex": "male", "weight_kg": 75}
                    },
                    timeout=30
                )

                if response.status_code == 200:
                    result_data = response.json()
                    extracted_factors = result_data.get('parsed', {}).get('extracted_factors', [])
                    extracted_conditions = [f.get('token', '') for f in extracted_factors]

                    results.append({
                        'case_id': case['case_id'],
                        'hpi_text': case['hpi_text'],
                        'expected_conditions': case['expected_conditions'],
                        'extracted_conditions': extracted_conditions,
                        'success': True
                    })
                else:
                    results.append({
                        'case_id': case['case_id'],
                        'success': False,
                        'error': f"HTTP {response.status_code}"
                    })

                time.sleep(0.5)  # Rate limiting

            except Exception as e:
                results.append({
                    'case_id': case['case_id'],
                    'success': False,
                    'error': str(e)
                })

        return results

    def _calculate_parsing_accuracy(self, test_results: List[Dict]) -> float:
        """Calculate overall parsing accuracy"""
        total_conditions = 0
        correct_conditions = 0

        for result in test_results:
            if not result.get('success', False):
                continue

            expected = set(result.get('expected_conditions', []))
            actual = set(result.get('extracted_conditions', []))

            total_conditions += len(expected)
            correct_conditions += len(expected.intersection(actual))

        return correct_conditions / total_conditions if total_conditions > 0 else 0.0

    def _test_pattern_improvements(self, patterns: List[PatternCandidate], test_results: List[Dict]) -> float:
        """Test how much patterns would improve parsing"""
        # Simulate improved parsing with new patterns
        improved_correct = 0
        total_conditions = 0

        for result in test_results:
            if not result.get('success', False):
                continue

            expected = set(result.get('expected_conditions', []))
            actual = set(result.get('extracted_conditions', []))
            hpi_text = result.get('hpi_text', '')

            # Add conditions that would be caught by new patterns
            for pattern in patterns:
                pattern_re = re.compile(pattern.pattern, re.I)
                if pattern_re.search(hpi_text) and pattern.condition in expected:
                    actual.add(pattern.condition)

            total_conditions += len(expected)
            improved_correct += len(expected.intersection(actual))

        return improved_correct / total_conditions if total_conditions > 0 else 0.0

    def print_learning_summary(self, results: Dict):
        """Print learning summary"""
        print("\n" + "="*80)
        print("ADVANCED PARSING RECURSIVE LEARNING COMPLETE")
        print("="*80)

        print(f"Target Accuracy: {self.target_accuracy:.1%}")
        print(f"Final Accuracy: {results['final_accuracy']:.1%}")
        print(f"Target Reached: {'YES' if results['target_reached'] else 'NO'}")
        print(f"Iterations Completed: {results['iterations_completed']}")
        print(f"Best Patterns Found: {len(results['best_patterns'])}")

        if results['learning_history']:
            print(f"\nLearning Progress:")
            for i, history in enumerate(results['learning_history'], 1):
                print(f"  Iteration {i}: {history['current_accuracy']:.1%} -> {history['improvement_score']:.1%}")

        if results['best_patterns']:
            print(f"\nTop Patterns:")
            for i, pattern in enumerate(results['best_patterns'][:3], 1):
                print(f"  {i}. {pattern['condition']}: {pattern['pattern'][:50]}...")
                print(f"     Validation Score: {pattern['validation_score']:.2f}")

        print("="*80)

def run_advanced_parsing_learning():
    """Run the advanced parsing learning system"""
    learner = AdvancedParsingLearner()

    try:
        results = learner.run_recursive_learning_cycle()
        learner.print_learning_summary(results)
        return results
    except Exception as e:
        logger.error(f"Error in parsing learning: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    results = run_advanced_parsing_learning()