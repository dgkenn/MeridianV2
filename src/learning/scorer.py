"""
Learning session scoring and feedback generation
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from .schemas import (
    LearningSession, UserResponse, LearningFeedback,
    BlueprintDomain, DifficultyLevel
)

logger = logging.getLogger(__name__)

class LearningScorer:
    """Scores learning sessions and generates educational feedback"""

    def __init__(self):
        self.passing_threshold = 0.7  # 70% to pass

    def score_session(self, session: LearningSession,
                     responses: List[UserResponse]) -> LearningFeedback:
        """
        Score a completed learning session and generate feedback

        Args:
            session: The learning session
            responses: User's responses to each item

        Returns:
            LearningFeedback with score and educational guidance
        """
        # Validate responses match session items
        if len(responses) != len(session.items):
            logger.warning(f"Response count ({len(responses)}) doesn't match item count ({len(session.items)})")

        # Calculate basic metrics
        total_time_sec = sum(r.time_ms for r in responses) / 1000
        score = self._calculate_score(responses)
        avg_time_per_item = total_time_sec / len(responses) if responses else 0

        # Analyze performance by domain
        domain_performance = self._analyze_domain_performance(session, responses)

        # Generate strengths and weaknesses
        strengths, weaknesses = self._identify_strengths_weaknesses(domain_performance)

        # Generate item-level feedback
        item_feedback = self._generate_item_feedback(session, responses)

        # Generate recommended reading based on case
        recommended_reading = self._generate_recommended_reading(session, weaknesses)

        # Update session with results
        session.responses = responses
        session.score = score
        session.completed_at = datetime.utcnow()

        return LearningFeedback(
            session_id=session.session_id,
            score=score,
            total_time_sec=int(total_time_sec),
            avg_time_per_item=avg_time_per_item,
            strengths=strengths,
            weaknesses=weaknesses,
            recommended_reading=recommended_reading,
            item_feedback=item_feedback
        )

    def _calculate_score(self, responses: List[UserResponse]) -> float:
        """Calculate overall score percentage"""
        if not responses:
            return 0.0

        correct_count = sum(1 for r in responses if r.correct)
        return correct_count / len(responses)

    def _analyze_domain_performance(self, session: LearningSession,
                                  responses: List[UserResponse]) -> Dict[BlueprintDomain, Dict[str, Any]]:
        """Analyze performance by blueprint domain"""
        domain_stats = {}

        for i, response in enumerate(responses):
            if i >= len(session.items):
                continue

            item = session.items[i]

            for domain in item.domain_tags:
                if domain not in domain_stats:
                    domain_stats[domain] = {
                        'total': 0,
                        'correct': 0,
                        'times': [],
                        'difficulties': []
                    }

                domain_stats[domain]['total'] += 1
                if response.correct:
                    domain_stats[domain]['correct'] += 1

                domain_stats[domain]['times'].append(response.time_ms)
                domain_stats[domain]['difficulties'].append(item.difficulty)

        # Calculate performance percentages
        for domain, stats in domain_stats.items():
            stats['percentage'] = stats['correct'] / stats['total'] if stats['total'] > 0 else 0
            stats['avg_time'] = sum(stats['times']) / len(stats['times']) if stats['times'] else 0

        return domain_stats

    def _identify_strengths_weaknesses(self, domain_performance: Dict[BlueprintDomain, Dict[str, Any]]) -> tuple:
        """Identify strength and weakness domains"""
        strengths = []
        weaknesses = []

        for domain, stats in domain_performance.items():
            percentage = stats['percentage']

            if percentage >= 0.8:  # 80%+ is strength
                strengths.append(self._domain_to_readable(domain))
            elif percentage < 0.6:  # <60% is weakness
                weaknesses.append(self._domain_to_readable(domain))

        return strengths, weaknesses

    def _domain_to_readable(self, domain: BlueprintDomain) -> str:
        """Convert domain enum to readable string"""
        domain_names = {
            BlueprintDomain.AIRWAY_ANATOMY: "Airway Management & Anatomy",
            BlueprintDomain.HEMODYNAMICS: "Hemodynamics & Physiology",
            BlueprintDomain.PHARMACOLOGY: "Pharmacology & Drug Dosing",
            BlueprintDomain.REGIONAL: "Regional Anesthesia",
            BlueprintDomain.PEDIATRIC: "Pediatric Anesthesia",
            BlueprintDomain.OBSTETRIC: "Obstetric Anesthesia",
            BlueprintDomain.NEURO: "Neuroanesthesia",
            BlueprintDomain.PAIN: "Pain Management",
            BlueprintDomain.ICU_VENT: "Critical Care & Ventilation"
        }
        return domain_names.get(domain, domain.value)

    def _generate_item_feedback(self, session: LearningSession,
                               responses: List[UserResponse]) -> List[Dict[str, Any]]:
        """Generate detailed feedback for each item"""
        feedback = []

        for i, response in enumerate(responses):
            if i >= len(session.items):
                continue

            item = session.items[i]

            item_feedback = {
                'item_id': item.item_id,
                'correct': response.correct,
                'time_ms': response.time_ms,
                'difficulty': item.difficulty.value,
                'domains': [d.value for d in item.domain_tags],
                'patient_anchors': item.patient_anchors,
                'rationale': item.rationale,
                'selected_answer': response.selected_answers,
                'correct_answers': item.correct_keys
            }

            # Add performance context
            if response.time_ms > 120000:  # >2 minutes
                item_feedback['time_flag'] = 'slow'
            elif response.time_ms < 15000:  # <15 seconds
                item_feedback['time_flag'] = 'fast'

            feedback.append(item_feedback)

        return feedback

    def _generate_recommended_reading(self, session: LearningSession,
                                    weaknesses: List[str]) -> List[Dict[str, str]]:
        """Generate case-specific recommended reading"""
        recommendations = []

        # Get case-specific topics from items
        case_topics = set()
        for item in session.items:
            case_topics.update(item.patient_anchors)

        # Generate recommendations based on weaknesses and case topics
        if "Pharmacology & Drug Dosing" in weaknesses:
            recommendations.append({
                'title': 'Case-Based Pharmacology Review',
                'description': f'Review medication dosing for this patient profile',
                'link': f'/learning/case-review?topic=pharmacology&case={session.case_hash}'
            })

        if "Airway Management & Anatomy" in weaknesses:
            recommendations.append({
                'title': 'Airway Management Guidelines',
                'description': 'Review airway management for high-risk patients',
                'link': f'/learning/case-review?topic=airway&case={session.case_hash}'
            })

        # Add general case review
        recommendations.append({
            'title': 'Complete Case Analysis',
            'description': 'Review all aspects of this patient case',
            'link': f'/learning/case-analysis?session={session.session_id}'
        })

        return recommendations

    def validate_responses(self, session: LearningSession,
                          responses: List[UserResponse]) -> bool:
        """Validate that responses are properly formatted"""
        if len(responses) != len(session.items):
            logger.error(f"Response count mismatch: {len(responses)} vs {len(session.items)}")
            return False

        for i, response in enumerate(responses):
            item = session.items[i]

            # Validate response format
            if not isinstance(response.selected_answers, list):
                logger.error(f"Invalid response format for item {i}")
                return False

            # Validate answer indices are within range
            max_option_index = len(item.options) - 1
            for answer_idx in response.selected_answers:
                if answer_idx < 0 or answer_idx > max_option_index:
                    logger.error(f"Answer index {answer_idx} out of range for item {i}")
                    return False

            # Validate timing
            if response.time_ms < 0 or response.time_ms > 600000:  # 0-10 minutes
                logger.error(f"Invalid time {response.time_ms}ms for item {i}")
                return False

        return True

    def calculate_cme_hours(self, session: LearningSession) -> float:
        """Calculate CME hours for session"""
        # Base calculation: 1 hour per 10 items, minimum 0.25 hours
        base_hours = max(0.25, len(session.items) / 10)

        # Adjust for mode
        if session.mode.value == 'board':
            return base_hours * 1.5  # Board-style questions worth more

        return base_hours

    def passes_cme_threshold(self, feedback: LearningFeedback) -> bool:
        """Check if session meets CME passing threshold"""
        return feedback.score >= self.passing_threshold