"""
Learning Session and Response Models
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
from .learning_item import LearningMode, BlueprintDomain


@dataclass
class LearningResponse:
    """Individual question response within a session"""
    item_id: str
    answer: List[int]  # Selected option indices
    correct: bool
    time_ms: int  # Time taken to answer
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'item_id': self.item_id,
            'answer': self.answer,
            'correct': self.correct,
            'time_ms': self.time_ms,
            'timestamp': self.timestamp.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LearningResponse':
        return cls(
            item_id=data['item_id'],
            answer=data['answer'],
            correct=data['correct'],
            time_ms=data['time_ms'],
            timestamp=datetime.fromisoformat(data['timestamp'])
        )


@dataclass
class BlueprintWeights:
    """Blueprint domain weights for session generation"""
    anatomy_airway: float = 0.15
    hemodynamics: float = 0.15
    pharmacology: float = 0.20
    regional: float = 0.10
    pediatric: float = 0.10
    obstetric: float = 0.05
    neuro: float = 0.10
    pain: float = 0.10
    icu_vent: float = 0.05

    def to_dict(self) -> Dict[str, float]:
        return {
            'anatomy_airway': self.anatomy_airway,
            'hemodynamics': self.hemodynamics,
            'pharmacology': self.pharmacology,
            'regional': self.regional,
            'pediatric': self.pediatric,
            'obstetric': self.obstetric,
            'neuro': self.neuro,
            'pain': self.pain,
            'icu_vent': self.icu_vent
        }

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> 'BlueprintWeights':
        return cls(
            anatomy_airway=data.get('anatomy_airway', 0.15),
            hemodynamics=data.get('hemodynamics', 0.15),
            pharmacology=data.get('pharmacology', 0.20),
            regional=data.get('regional', 0.10),
            pediatric=data.get('pediatric', 0.10),
            obstetric=data.get('obstetric', 0.05),
            neuro=data.get('neuro', 0.10),
            pain=data.get('pain', 0.10),
            icu_vent=data.get('icu_vent', 0.05)
        )

    def validate(self) -> bool:
        """Check if weights sum to approximately 1.0"""
        total = sum(self.to_dict().values())
        return 0.95 <= total <= 1.05


@dataclass
class SessionFeedback:
    """Post-session feedback and recommendations"""
    score: float  # 0.0 to 1.0
    total_time_sec: int
    avg_time_per_item: float
    strengths: List[str]  # Blueprint domains performed well
    weaknesses: List[str]  # Blueprint domains needing improvement
    recommendations: List[str]  # Suggested next steps
    domain_scores: Dict[str, float]  # Per-domain performance

    def to_dict(self) -> Dict[str, Any]:
        return {
            'score': self.score,
            'total_time_sec': self.total_time_sec,
            'avg_time_per_item': self.avg_time_per_item,
            'strengths': self.strengths,
            'weaknesses': self.weaknesses,
            'recommendations': self.recommendations,
            'domain_scores': self.domain_scores
        }


@dataclass
class LearningSession:
    """
    Learning session containing multiple items and responses
    """
    session_id: str
    mode: LearningMode
    blueprint_weights: BlueprintWeights
    seed: int

    # Items and responses
    item_ids: List[str]
    responses: List[LearningResponse] = field(default_factory=list)

    # User context
    user_id: Optional[str] = None
    case_context: Optional[Dict[str, Any]] = None

    # Session metadata
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    # Feedback (populated after completion)
    feedback: Optional[SessionFeedback] = None

    @property
    def is_completed(self) -> bool:
        """Check if session is completed"""
        return len(self.responses) == len(self.item_ids) and self.completed_at is not None

    @property
    def current_score(self) -> float:
        """Current score based on responses so far"""
        if not self.responses:
            return 0.0
        correct = sum(1 for r in self.responses if r.correct)
        return correct / len(self.responses)

    def add_response(self, response: LearningResponse) -> None:
        """Add a response to the session"""
        self.responses.append(response)

        # Auto-complete if all items answered
        if len(self.responses) == len(self.item_ids) and not self.completed_at:
            self.completed_at = datetime.now()

    def calculate_feedback(self, items: List['LearningItem']) -> SessionFeedback:
        """Calculate session feedback based on responses and items"""
        if not self.is_completed:
            raise ValueError("Cannot calculate feedback for incomplete session")

        # Basic statistics
        score = self.current_score
        total_time = sum(r.time_ms for r in self.responses) / 1000
        avg_time = total_time / len(self.responses) if self.responses else 0

        # Domain-specific performance
        domain_scores = {}
        domain_counts = {}

        for item, response in zip(items, self.responses):
            for domain in item.domain_tags:
                domain_name = domain.value
                if domain_name not in domain_scores:
                    domain_scores[domain_name] = 0
                    domain_counts[domain_name] = 0

                domain_scores[domain_name] += 1 if response.correct else 0
                domain_counts[domain_name] += 1

        # Calculate percentages
        for domain in domain_scores:
            if domain_counts[domain] > 0:
                domain_scores[domain] = domain_scores[domain] / domain_counts[domain]

        # Identify strengths and weaknesses
        strengths = [domain for domain, score in domain_scores.items() if score >= 0.8]
        weaknesses = [domain for domain, score in domain_scores.items() if score < 0.6]

        # Generate recommendations
        recommendations = []
        if weaknesses:
            recommendations.append(f"Review concepts in: {', '.join(weaknesses)}")
        if avg_time > 120:  # > 2 minutes per question
            recommendations.append("Practice to improve response time")
        if score < 0.7:
            recommendations.append("Consider reviewing foundational concepts")

        feedback = SessionFeedback(
            score=score,
            total_time_sec=int(total_time),
            avg_time_per_item=avg_time,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations,
            domain_scores=domain_scores
        )

        self.feedback = feedback
        return feedback

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'session_id': self.session_id,
            'mode': self.mode.value,
            'blueprint_weights': self.blueprint_weights.to_dict(),
            'seed': self.seed,
            'item_ids': self.item_ids,
            'responses': [r.to_dict() for r in self.responses],
            'user_id': self.user_id,
            'case_context': self.case_context,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'feedback': self.feedback.to_dict() if self.feedback else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LearningSession':
        """Create from dictionary"""
        responses = [LearningResponse.from_dict(r) for r in data['responses']]

        feedback = None
        if data.get('feedback'):
            feedback = SessionFeedback(
                score=data['feedback']['score'],
                total_time_sec=data['feedback']['total_time_sec'],
                avg_time_per_item=data['feedback']['avg_time_per_item'],
                strengths=data['feedback']['strengths'],
                weaknesses=data['feedback']['weaknesses'],
                recommendations=data['feedback']['recommendations'],
                domain_scores=data['feedback']['domain_scores']
            )

        return cls(
            session_id=data['session_id'],
            mode=LearningMode(data['mode']),
            blueprint_weights=BlueprintWeights.from_dict(data['blueprint_weights']),
            seed=data['seed'],
            item_ids=data['item_ids'],
            responses=responses,
            user_id=data.get('user_id'),
            case_context=data.get('case_context'),
            started_at=datetime.fromisoformat(data['started_at']),
            completed_at=datetime.fromisoformat(data['completed_at']) if data.get('completed_at') else None,
            feedback=feedback
        )

    @staticmethod
    def generate_id() -> str:
        """Generate unique session ID"""
        return str(uuid.uuid4())