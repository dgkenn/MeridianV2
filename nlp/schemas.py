"""
Pydantic schemas for clinical NLP pipeline outputs
"""

from pydantic import BaseModel
from typing import List, Optional, Literal

class Modifier(BaseModel):
    """Modifiers for clinical entities (negation, temporality, etc.)"""
    negated: bool = False
    uncertain: bool = False
    temporality: Optional[Literal["recent", "current", "historical"]] = None
    recency_days: Optional[int] = None
    experiencer: Optional[Literal["patient", "family"]] = "patient"
    severity: Optional[str] = None

class ParsedFeature(BaseModel):
    """A clinical risk factor extracted from text"""
    code: str              # Meridian key e.g., "RECENT_URI_2W"
    label: str             # plain language e.g., "Recent upper respiratory infection (<=2 weeks)"
    text: str              # raw span from original text
    source: Literal["rule", "quickumls", "bert"]
    confidence: float
    modifiers: Modifier

class ParsedHPI(BaseModel):
    """Complete structured output from HPI parsing"""
    age_years: Optional[int] = None
    sex: Optional[str] = None
    urgency: Optional[Literal["elective", "urgent", "emergency"]] = "elective"
    case_type: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    bmi: Optional[float] = None
    features: List[ParsedFeature] = []

    def get_feature_codes(self, include_negated: bool = False) -> List[str]:
        """Get list of feature codes, optionally excluding negated ones"""
        if include_negated:
            return [f.code for f in self.features]
        else:
            return [f.code for f in self.features if not f.modifiers.negated]

    def get_features_by_source(self, source: str) -> List[ParsedFeature]:
        """Get features from a specific extraction source"""
        return [f for f in self.features if f.source == source]

    def has_feature(self, code: str, include_negated: bool = False) -> bool:
        """Check if a specific feature code is present"""
        return code in self.get_feature_codes(include_negated=include_negated)