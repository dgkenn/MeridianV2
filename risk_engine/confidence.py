"""
Confidence scoring system (A-D grades) based on evidence quality
"""

import numpy as np
from typing import List, Dict, Optional, Any
from datetime import datetime
import logging

from .schema import (Study, PooledEffect, ConfidenceBreakdown, ConfidenceLevel,
                    StudyDesign, RiskOfBias, RiskConfig)

logger = logging.getLogger(__name__)

class ConfidenceScorer:
    """Calculates confidence scores and letter grades for pooled effects"""

    def __init__(self, config: RiskConfig):
        self.config = config
        self.current_year = 2025

    def calculate_confidence(self, pooled_effect: PooledEffect) -> ConfidenceBreakdown:
        """
        Calculate overall confidence score with detailed breakdown
        Returns score 0-100 and letter grade A-D
        """

        weights = self.config.confidence_weights

        # Component scores (0-1)
        k_score = self._score_study_count(pooled_effect.k_studies)
        design_score = self._score_design_mix(pooled_effect.studies)
        bias_score = self._score_bias_quality(pooled_effect.studies)
        temporal_score = self._score_temporal_freshness(pooled_effect.studies)
        window_score = self._score_window_match(pooled_effect.studies, pooled_effect.window)
        heterogeneity_score = self._score_heterogeneity(pooled_effect.i_squared)
        egger_penalty = self._score_publication_bias(pooled_effect.egger_p, pooled_effect.trim_fill_added)
        loo_score = self._score_loo_stability(pooled_effect.loo_max_delta_pp)

        # Weighted total (0-100)
        total_score = (
            weights["k_studies"] * k_score +
            weights["design_mix"] * design_score +
            weights["bias"] * bias_score +
            weights["temporal"] * temporal_score +
            weights["window_match"] * window_score +
            weights["heterogeneity"] * heterogeneity_score +
            weights["publication_bias"] * egger_penalty +
            weights["loo_stability"] * loo_score
        ) * 100

        # Convert to letter grade
        letter_grade = self._score_to_letter(total_score)

        return ConfidenceBreakdown(
            k_studies_score=k_score,
            design_mix_score=design_score,
            bias_score=bias_score,
            temporal_freshness_score=temporal_score,
            window_match_score=window_score,
            heterogeneity_score=heterogeneity_score,
            egger_penalty=egger_penalty,
            loo_stability_score=loo_score,
            total_score=total_score,
            letter_grade=letter_grade
        )

    def _score_study_count(self, k_studies: int) -> float:
        """
        Score based on number of studies
        More studies = higher confidence
        """
        if k_studies >= 20:
            return 1.0
        elif k_studies >= 10:
            return 0.9
        elif k_studies >= 5:
            return 0.7
        elif k_studies >= 3:
            return 0.5
        elif k_studies >= 2:
            return 0.3
        else:
            return 0.1

    def _score_design_mix(self, studies: List[Study]) -> float:
        """
        Score based on study design quality mix
        RCTs > Prospective > Retrospective
        """
        if not studies:
            return 0.0

        design_counts = {
            StudyDesign.RCT: 0,
            StudyDesign.PROSPECTIVE: 0,
            StudyDesign.RETROSPECTIVE: 0
        }

        for study in studies:
            design_counts[study.design] += 1

        total = len(studies)
        rct_prop = design_counts[StudyDesign.RCT] / total
        prospective_prop = design_counts[StudyDesign.PROSPECTIVE] / total
        retrospective_prop = design_counts[StudyDesign.RETROSPECTIVE] / total

        # Weighted score
        score = (rct_prop * 1.0 +
                prospective_prop * 0.7 +
                retrospective_prop * 0.3)

        return score

    def _score_bias_quality(self, studies: List[Study]) -> float:
        """
        Score based on risk of bias distribution
        """
        if not studies:
            return 0.0

        bias_counts = {
            RiskOfBias.LOW: 0,
            RiskOfBias.SOME: 0,
            RiskOfBias.HIGH: 0
        }

        for study in studies:
            bias_counts[study.risk_of_bias] += 1

        total = len(studies)
        low_prop = bias_counts[RiskOfBias.LOW] / total
        some_prop = bias_counts[RiskOfBias.SOME] / total
        high_prop = bias_counts[RiskOfBias.HIGH] / total

        # Weighted score
        score = (low_prop * 1.0 +
                some_prop * 0.6 +
                high_prop * 0.2)

        return score

    def _score_temporal_freshness(self, studies: List[Study]) -> float:
        """
        Score based on how recent the evidence is
        """
        if not studies:
            return 0.0

        # Calculate weighted average age of evidence
        total_weight = 0
        weighted_age_sum = 0

        for study in studies:
            age = self.current_year - study.pub_year
            weight = np.exp(-age / self.config.temporal_tau)

            total_weight += weight
            weighted_age_sum += weight * age

        if total_weight == 0:
            return 0.0

        avg_age = weighted_age_sum / total_weight

        # Score based on average age
        if avg_age <= 3:
            return 1.0
        elif avg_age <= 5:
            return 0.9
        elif avg_age <= 7:
            return 0.8
        elif avg_age <= 10:
            return 0.6
        elif avg_age <= 15:
            return 0.4
        else:
            return 0.2

    def _score_window_match(self, studies: List[Study], target_window) -> float:
        """
        Score based on outcome window alignment
        """
        if not studies:
            return 0.0

        exact_matches = sum(1 for s in studies if s.window == target_window)
        total = len(studies)

        exact_prop = exact_matches / total

        # High score for exact matches, moderate penalty for mismatches
        if exact_prop >= 0.8:
            return 1.0
        elif exact_prop >= 0.6:
            return 0.8
        elif exact_prop >= 0.4:
            return 0.6
        elif exact_prop >= 0.2:
            return 0.4
        else:
            return 0.2

    def _score_heterogeneity(self, i_squared: float) -> float:
        """
        Score based on between-study heterogeneity (I²)
        Lower heterogeneity = higher confidence
        """
        if i_squared <= 25:
            return 1.0  # Low heterogeneity
        elif i_squared <= 50:
            return 0.8  # Moderate heterogeneity
        elif i_squared <= 75:
            return 0.5  # Substantial heterogeneity
        else:
            return 0.2  # Considerable heterogeneity

    def _score_publication_bias(self, egger_p: Optional[float],
                               trim_fill_added: int) -> float:
        """
        Score publication bias indicators
        Lower scores indicate more bias concerns
        """
        base_score = 1.0

        # Egger test penalty
        if egger_p is not None:
            if egger_p < 0.01:
                base_score *= 0.3  # Strong evidence of bias
            elif egger_p < 0.05:
                base_score *= 0.6  # Some evidence of bias
            elif egger_p < 0.10:
                base_score *= 0.8  # Weak evidence of bias

        # Trim-and-fill penalty
        if trim_fill_added > 0:
            penalty = min(0.5, trim_fill_added * 0.1)
            base_score *= (1 - penalty)

        return base_score

    def _score_loo_stability(self, loo_max_delta_pp: Optional[float]) -> float:
        """
        Score leave-one-out stability
        Lower changes = higher confidence
        """
        if loo_max_delta_pp is None:
            return 0.8  # Unknown stability

        if loo_max_delta_pp <= 1.0:
            return 1.0  # Very stable
        elif loo_max_delta_pp <= 2.0:
            return 0.9  # Stable
        elif loo_max_delta_pp <= 5.0:
            return 0.7  # Moderately stable
        elif loo_max_delta_pp <= 10.0:
            return 0.4  # Unstable
        else:
            return 0.1  # Very unstable

    def _score_to_letter(self, score: float) -> ConfidenceLevel:
        """Convert numeric score to letter grade"""
        thresholds = self.config.confidence_thresholds

        if score >= thresholds["A"]:
            return ConfidenceLevel.A
        elif score >= thresholds["B"]:
            return ConfidenceLevel.B
        elif score >= thresholds["C"]:
            return ConfidenceLevel.C
        else:
            return ConfidenceLevel.D

    def get_confidence_explanation(self, breakdown: ConfidenceBreakdown) -> Dict[str, str]:
        """
        Generate human-readable explanations for confidence components
        """
        explanations = {}

        # K studies
        if breakdown.k_studies_score >= 0.9:
            explanations["studies"] = "Strong evidence base with many studies"
        elif breakdown.k_studies_score >= 0.7:
            explanations["studies"] = "Good evidence base with adequate studies"
        elif breakdown.k_studies_score >= 0.5:
            explanations["studies"] = "Moderate evidence base with few studies"
        else:
            explanations["studies"] = "Limited evidence base with very few studies"

        # Design quality
        if breakdown.design_mix_score >= 0.8:
            explanations["design"] = "High-quality study designs (RCTs/prospective)"
        elif breakdown.design_mix_score >= 0.6:
            explanations["design"] = "Mixed study designs with some high-quality evidence"
        else:
            explanations["design"] = "Predominantly observational/retrospective evidence"

        # Risk of bias
        if breakdown.bias_score >= 0.8:
            explanations["bias"] = "Low risk of bias across studies"
        elif breakdown.bias_score >= 0.6:
            explanations["bias"] = "Moderate risk of bias in some studies"
        else:
            explanations["bias"] = "High risk of bias concerns"

        # Temporal freshness
        if breakdown.temporal_freshness_score >= 0.8:
            explanations["freshness"] = "Recent, up-to-date evidence"
        elif breakdown.temporal_freshness_score >= 0.6:
            explanations["freshness"] = "Moderately recent evidence"
        else:
            explanations["freshness"] = "Older evidence may not reflect current practice"

        # Heterogeneity
        if breakdown.heterogeneity_score >= 0.8:
            explanations["consistency"] = "Consistent results across studies"
        elif breakdown.heterogeneity_score >= 0.5:
            explanations["consistency"] = "Some variation in results between studies"
        else:
            explanations["consistency"] = "Substantial variation in results between studies"

        # Publication bias
        if breakdown.egger_penalty >= 0.8:
            explanations["bias_test"] = "No evidence of publication bias"
        elif breakdown.egger_penalty >= 0.6:
            explanations["bias_test"] = "Some concerns about publication bias"
        else:
            explanations["bias_test"] = "Significant concerns about publication bias"

        # Stability
        if breakdown.loo_stability_score >= 0.9:
            explanations["stability"] = "Results stable when individual studies removed"
        elif breakdown.loo_stability_score >= 0.7:
            explanations["stability"] = "Generally stable results"
        else:
            explanations["stability"] = "Results sensitive to individual studies"

        return explanations

    def get_recommendation_flags(self, breakdown: ConfidenceBreakdown) -> List[str]:
        """
        Generate recommendation flags based on confidence breakdown
        """
        flags = []

        if breakdown.letter_grade == ConfidenceLevel.A:
            flags.append("HIGH_CONFIDENCE")
        elif breakdown.letter_grade == ConfidenceLevel.D:
            flags.append("LOW_CONFIDENCE")

        if breakdown.k_studies_score < 0.5:
            flags.append("LIMITED_STUDIES")

        if breakdown.heterogeneity_score < 0.5:
            flags.append("HIGH_HETEROGENEITY")

        if breakdown.egger_penalty < 0.6:
            flags.append("PUBLICATION_BIAS_CONCERN")

        if breakdown.temporal_freshness_score < 0.5:
            flags.append("OUTDATED_EVIDENCE")

        if breakdown.loo_stability_score < 0.5:
            flags.append("UNSTABLE_ESTIMATE")

        return flags