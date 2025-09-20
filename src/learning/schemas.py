"""
Data schemas for the Learning module
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from enum import Enum
import hashlib

class LearningMode(Enum):
    BASICS = "basics"  # Junior residents
    BOARD = "board"    # Senior residents/fellows

class DifficultyLevel(Enum):
    EASY = "easy"
    MODERATE = "moderate"
    ADVANCED = "advanced"
    STRETCH = "stretch"

class ItemType(Enum):
    SINGLE_BEST = "single_best"
    MULTI_SELECT = "multi_select"
    ORDERING = "ordering"
    SHORT_JUSTIFICATION = "short_justification"

class BlueprintDomain(Enum):
    AIRWAY_ANATOMY = "airway_anatomy"
    HEMODYNAMICS = "hemodynamics"
    PHARMACOLOGY = "pharmacology"
    REGIONAL = "regional"
    PEDIATRIC = "pediatric"
    OBSTETRIC = "obstetric"
    NEURO = "neuro"
    PAIN = "pain"
    ICU_VENT = "icu_vent"

@dataclass
class Citation:
    pmid: Optional[str] = None
    guideline: Optional[str] = None
    title: str = ""
    relevance_weight: float = 1.0

@dataclass
class LearningItem:
    item_id: str
    stem: str  # Markdown formatted
    options: List[str]
    correct_keys: List[int]  # Indices of correct answers
    rationale: str  # Markdown with explanations
    citations: List[Citation]
    mode: LearningMode
    difficulty: DifficultyLevel
    item_type: ItemType
    domain_tags: List[BlueprintDomain]
    patient_anchors: List[str]  # What patient features this item tests
    seed: int
    version: str
    created_at: datetime
    case_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'item_id': self.item_id,
            'stem': self.stem,
            'options': self.options,
            'correct_keys': self.correct_keys,
            'rationale': self.rationale,
            'citations': [{'pmid': c.pmid, 'guideline': c.guideline, 'title': c.title} for c in self.citations],
            'mode': self.mode.value,
            'difficulty': self.difficulty.value,
            'item_type': self.item_type.value,
            'domain_tags': [d.value for d in self.domain_tags],
            'patient_anchors': self.patient_anchors,
            'seed': self.seed,
            'version': self.version,
            'case_hash': self.case_hash
        }

@dataclass
class UserResponse:
    item_id: str
    selected_answers: List[int]
    time_ms: int
    correct: bool

@dataclass
class LearningSession:
    session_id: str
    mode: LearningMode
    n_items: int
    items: List[LearningItem]
    blueprint_distribution: Dict[BlueprintDomain, int]
    seed: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    score: Optional[float] = None
    responses: List[UserResponse] = field(default_factory=list)
    case_hash: str = ""

    def calculate_score(self) -> float:
        if not self.responses:
            return 0.0
        correct_count = sum(1 for r in self.responses if r.correct)
        return correct_count / len(self.responses)

@dataclass
class PatientContext:
    # Demographics & numerics
    age: Optional[int] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    bmi: Optional[float] = None

    # Surgery & timing
    surgery_domain: Optional[str] = None
    procedure_keywords: List[str] = field(default_factory=list)
    urgency: str = "elective"  # elective/urgent/emergency

    # Parsed features (Meridian codes + labels)
    extracted_factors: List[Dict[str, Any]] = field(default_factory=list)

    # Risk outcomes (sorted by absolute risk and delta)
    top_outcomes: List[Dict[str, Any]] = field(default_factory=list)

    # Medication plan
    medication_plan: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    # Evidence & guidelines attached to this case
    case_guidelines: List[Dict[str, Any]] = field(default_factory=list)
    evidence_citations: List[Citation] = field(default_factory=list)

    # User profile (optional)
    user_role: Optional[str] = None  # CA-1/2/3, Fellow, Attending

    def generate_case_hash(self) -> str:
        """Generate deterministic hash for this patient context"""
        key_data = {
            'age': self.age,
            'weight_kg': self.weight_kg,
            'surgery_domain': self.surgery_domain,
            'extracted_factors': [f.get('token') for f in self.extracted_factors],
            'top_outcomes': [o.get('outcome') for o in self.top_outcomes[:3]]
        }
        hash_string = str(sorted(key_data.items()))
        return hashlib.md5(hash_string.encode()).hexdigest()[:8]

@dataclass
class LearningFeedback:
    session_id: str
    score: float
    total_time_sec: int
    avg_time_per_item: float
    strengths: List[str]  # Domain areas performed well
    weaknesses: List[str]  # Domain areas needing improvement
    recommended_reading: List[Dict[str, str]]  # Links to case studies/guidelines
    item_feedback: List[Dict[str, Any]]  # Per-item breakdown

@dataclass
class CMERecord:
    certificate_id: str
    session_id: str
    user_id: Optional[str]
    hours: float
    passed: bool
    score: float
    objectives_covered: List[str]
    issued_at: datetime
    expires_at: Optional[datetime] = None