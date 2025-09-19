"""
Learning Item Data Model
Represents individual MCQ questions with metadata
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import hashlib


class ItemType(Enum):
    """Types of learning items"""
    SINGLE_BEST = "single_best"
    MULTI_SELECT = "multi_select"  # ≤2 correct
    ORDERING = "ordering"
    SHORT_JUSTIFICATION = "short_justification"


class DifficultyTier(Enum):
    """Difficulty levels for items"""
    EASY = "easy"
    MODERATE = "moderate"
    ADVANCED = "advanced"
    STRETCH = "stretch"


class LearningMode(Enum):
    """Learning modes"""
    BASICS = "basics"  # Junior residents
    BOARD = "board"    # Senior/fellow level


class BlueprintDomain(Enum):
    """Blueprint domains for categorization"""
    ANATOMY_AIRWAY = "anatomy_airway"
    HEMODYNAMICS = "hemodynamics"
    PHARMACOLOGY = "pharmacology"
    REGIONAL = "regional"
    PEDIATRIC = "pediatric"
    OBSTETRIC = "obstetric"
    NEURO = "neuro"
    PAIN = "pain"
    ICU_VENT = "icu_vent"


@dataclass
class MCQOption:
    """Individual MCQ option"""
    text: str
    is_correct: bool
    explanation: Optional[str] = None


@dataclass
class Citation:
    """Citation reference"""
    type: str  # "pubmed", "guideline", "textbook"
    identifier: str  # PMID, guideline name, etc.
    title: str
    url: Optional[str] = None


@dataclass
class LearningItem:
    """
    Core learning item model for MCQ generation
    """
    item_id: str
    stem_md: str  # Markdown formatted question stem
    options: List[MCQOption]
    item_type: ItemType
    mode: LearningMode
    difficulty: DifficultyTier
    domain_tags: List[BlueprintDomain]

    # Rationale and evidence
    rationale_md: str  # Markdown explanation
    citations: List[Citation]

    # Generation metadata
    seed: int  # For reproducible generation
    version: str
    case_context: Optional[Dict[str, Any]] = None  # Patient context used

    # Psychometrics (placeholders for future calibration)
    discrimination: Optional[float] = None  # Point-biserial correlation
    difficulty_pct: Optional[float] = None  # % correct globally
    irt_params: Optional[Dict[str, float]] = field(default_factory=dict)

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def correct_options(self) -> List[int]:
        """Return indices of correct options"""
        return [i for i, opt in enumerate(self.options) if opt.is_correct]

    @property
    def num_correct(self) -> int:
        """Number of correct options"""
        return len(self.correct_options)

    def validate(self) -> List[str]:
        """Validate item for safety and quality"""
        issues = []

        # Basic validation
        if not self.stem_md.strip():
            issues.append("Empty stem")

        if len(self.options) < 2:
            issues.append("Need at least 2 options")

        if len(self.options) > 5:
            issues.append("Too many options (max 5)")

        if self.num_correct == 0:
            issues.append("No correct options")

        if self.item_type == ItemType.SINGLE_BEST and self.num_correct != 1:
            issues.append("Single best answer must have exactly 1 correct option")

        if self.item_type == ItemType.MULTI_SELECT and self.num_correct > 2:
            issues.append("Multi-select must have ≤2 correct options")

        # Citation validation
        if not self.citations:
            issues.append("No citations provided")

        # Safety checks
        if any(self._check_unsafe_dose(opt.text) for opt in self.options):
            issues.append("Potentially unsafe dose detected")

        return issues

    def _check_unsafe_dose(self, text: str) -> bool:
        """Basic check for obviously unsafe doses"""
        # Simple regex patterns for common unsafe doses
        import re

        # Epinephrine > 1 mg IV
        epi_pattern = r'epinephrine.*?(\d+(?:\.\d+)?)\s*mg.*?iv'
        epi_match = re.search(epi_pattern, text.lower())
        if epi_match and float(epi_match.group(1)) > 1.0:
            return True

        # Add more safety checks as needed
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'item_id': self.item_id,
            'stem_md': self.stem_md,
            'options': [
                {
                    'text': opt.text,
                    'is_correct': opt.is_correct,
                    'explanation': opt.explanation
                }
                for opt in self.options
            ],
            'item_type': self.item_type.value,
            'mode': self.mode.value,
            'difficulty': self.difficulty.value,
            'domain_tags': [tag.value for tag in self.domain_tags],
            'rationale_md': self.rationale_md,
            'citations': [
                {
                    'type': cit.type,
                    'identifier': cit.identifier,
                    'title': cit.title,
                    'url': cit.url
                }
                for cit in self.citations
            ],
            'seed': self.seed,
            'version': self.version,
            'case_context': self.case_context,
            'discrimination': self.discrimination,
            'difficulty_pct': self.difficulty_pct,
            'irt_params': self.irt_params,
            'created_at': self.created_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LearningItem':
        """Create from dictionary"""
        options = [
            MCQOption(
                text=opt['text'],
                is_correct=opt['is_correct'],
                explanation=opt.get('explanation')
            )
            for opt in data['options']
        ]

        citations = [
            Citation(
                type=cit['type'],
                identifier=cit['identifier'],
                title=cit['title'],
                url=cit.get('url')
            )
            for cit in data['citations']
        ]

        return cls(
            item_id=data['item_id'],
            stem_md=data['stem_md'],
            options=options,
            item_type=ItemType(data['item_type']),
            mode=LearningMode(data['mode']),
            difficulty=DifficultyTier(data['difficulty']),
            domain_tags=[BlueprintDomain(tag) for tag in data['domain_tags']],
            rationale_md=data['rationale_md'],
            citations=citations,
            seed=data['seed'],
            version=data['version'],
            case_context=data.get('case_context'),
            discrimination=data.get('discrimination'),
            difficulty_pct=data.get('difficulty_pct'),
            irt_params=data.get('irt_params', {}),
            created_at=datetime.fromisoformat(data['created_at'])
        )

    @staticmethod
    def generate_id(seed: int, version: str, case_id: Optional[str] = None) -> str:
        """Generate deterministic item ID"""
        content = f"{seed}-{version}-{case_id or 'generic'}"
        return hashlib.md5(content.encode()).hexdigest()[:12]