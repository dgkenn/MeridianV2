"""
Risk conversion utilities - OR/RR/HR conversions and absolute risk calculation
"""

import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from scipy import stats
import logging

from .schema import Study, PooledEffect, BaselineRisk, EffectMeasure

logger = logging.getLogger(__name__)

class RiskConverter:
    """Converts between effect measures and calculates absolute risks"""

    def __init__(self, mc_draws: int = 5000, seed: Optional[int] = None):
        self.mc_draws = mc_draws
        self.rng = np.random.RandomState(seed)

    def rr_to_or(self, rr: float, baseline_prob: float) -> float:
        """
        Convert RR to OR using local baseline probability
        OR = RR(1-p0) / (1 - RR*p0)
        """
        if baseline_prob <= 0 or baseline_prob >= 1:
            raise ValueError(f"Invalid baseline probability: {baseline_prob}")

        if rr <= 0:
            raise ValueError(f"Invalid RR: {rr}")

        denominator = 1 - rr * baseline_prob
        if denominator <= 0:
            # RR too large for this baseline - return large OR
            return 999.0

        or_value = rr * (1 - baseline_prob) / denominator
        return or_value

    def or_to_rr(self, or_value: float, baseline_prob: float) -> float:
        """
        Convert OR to RR using local baseline probability
        RR = OR / (1 - p0 + OR*p0)
        """
        if baseline_prob <= 0 or baseline_prob >= 1:
            raise ValueError(f"Invalid baseline probability: {baseline_prob}")

        if or_value <= 0:
            raise ValueError(f"Invalid OR: {or_value}")

        denominator = 1 - baseline_prob + or_value * baseline_prob
        rr = or_value / denominator
        return rr

    def log_or_to_prob(self, log_or: float, baseline_prob: float) -> float:
        """
        Convert log odds ratio to absolute probability
        """
        # Baseline odds
        baseline_odds = baseline_prob / (1 - baseline_prob)

        # New odds
        new_odds = baseline_odds * np.exp(log_or)

        # Convert back to probability
        new_prob = new_odds / (1 + new_odds)

        return new_prob

    def combine_log_effects(self, log_effects: List[float]) -> float:
        """
        Combine multiple log effects additively
        """
        return sum(log_effects)

    def calculate_absolute_risk_ci(self,
                                  pooled_effects: List[PooledEffect],
                                  baseline_risk: BaselineRisk,
                                  factor_codes: List[str]) -> Tuple[float, float, float]:
        """
        Calculate absolute risk with 95% CI using Monte Carlo simulation

        Returns:
            (point_estimate, ci_lower, ci_upper)
        """

        # Find relevant effects
        relevant_effects = []
        effect_variances = []

        for effect in pooled_effects:
            if effect.factor in factor_codes:
                # Use shrunk effect if available, otherwise raw
                log_effect = effect.log_effect_shrunk or effect.log_effect_raw
                se = effect.se_shrunk or effect.se_raw

                relevant_effects.append(log_effect)
                effect_variances.append(se ** 2)

        if not relevant_effects:
            # No effects - return baseline
            return baseline_risk.p0, baseline_risk.p0, baseline_risk.p0

        # Point estimate
        combined_log_effect = self.combine_log_effects(relevant_effects)
        point_risk = self.log_or_to_prob(combined_log_effect, baseline_risk.p0)

        # Monte Carlo for CI
        # Sample combined effect from multivariate normal
        # (Simplified: assume independence for now)
        combined_variance = sum(effect_variances)

        sampled_effects = self.rng.normal(
            combined_log_effect,
            np.sqrt(combined_variance),
            self.mc_draws
        )

        # Sample baseline if uncertainty available
        if baseline_risk.p0_ci_lower and baseline_risk.p0_ci_upper:
            # Approximate beta distribution from CI
            baseline_samples = self._sample_baseline_from_ci(
                baseline_risk.p0,
                baseline_risk.p0_ci_lower,
                baseline_risk.p0_ci_upper
            )
        else:
            baseline_samples = np.full(self.mc_draws, baseline_risk.p0)

        # Calculate risk for each draw
        risk_samples = []
        for i in range(self.mc_draws):
            try:
                risk = self.log_or_to_prob(sampled_effects[i], baseline_samples[i])
                # Clip to reasonable range
                risk = np.clip(risk, 0.0001, 0.9999)
                risk_samples.append(risk)
            except:
                # Skip invalid samples
                continue

        if not risk_samples:
            return point_risk, point_risk, point_risk

        risk_samples = np.array(risk_samples)

        # Calculate percentiles
        ci_lower = np.percentile(risk_samples, 2.5)
        ci_upper = np.percentile(risk_samples, 97.5)

        return point_risk, ci_lower, ci_upper

    def _sample_baseline_from_ci(self, p0: float, ci_lower: float, ci_upper: float) -> np.ndarray:
        """
        Sample baseline probability from beta distribution fitted to CI
        """
        try:
            # Method of moments to fit beta from mean and CI
            # This is approximate - more sophisticated methods exist

            # Assume normal approximation on logit scale
            logit_p0 = np.log(p0 / (1 - p0))
            logit_lower = np.log(ci_lower / (1 - ci_lower))
            logit_upper = np.log(ci_upper / (1 - ci_upper))

            logit_se = (logit_upper - logit_lower) / (2 * 1.96)

            # Sample on logit scale
            logit_samples = self.rng.normal(logit_p0, logit_se, self.mc_draws)

            # Transform back to probability
            prob_samples = 1 / (1 + np.exp(-logit_samples))

            # Clip to valid range
            prob_samples = np.clip(prob_samples, 0.0001, 0.9999)

            return prob_samples

        except:
            # Fallback to fixed baseline
            return np.full(self.mc_draws, p0)

    def calculate_risk_differences(self, adjusted_risk: float, baseline_risk: BaselineRisk) -> Dict[str, float]:
        """
        Calculate various risk difference measures
        """
        p0 = baseline_risk.p0
        p1 = adjusted_risk
        p_ref = baseline_risk.p_ref

        return {
            "absolute_increase_pp": (p1 - p0) * 100,  # Percentage points
            "relative_risk_ratio": p1 / p0 if p0 > 0 else float('inf'),
            "number_needed_to_harm": 1 / (p1 - p0) if p1 > p0 else float('inf'),
            "delta_vs_reference_pp": (p1 - p_ref) * 100,
            "fold_vs_reference": p1 / p_ref if p_ref > 0 else float('inf')
        }

    def check_baseline_high_risk(self, baseline_risk: BaselineRisk,
                                thresholds: Dict[str, float]) -> bool:
        """
        Check if baseline risk meets high-risk criteria
        """
        p0 = baseline_risk.p0
        p_ref = baseline_risk.p_ref

        # Absolute threshold
        if p0 >= thresholds["T_abs"]:
            return True

        # Absolute difference threshold
        if abs(p0 - p_ref) >= thresholds["T_delta"]:
            return True

        # Relative threshold
        if p_ref > 0 and p0 / p_ref >= thresholds["T_rel"]:
            return True

        return False

    def validate_conversion(self, or_value: float, baseline_prob: float) -> bool:
        """
        Validate that conversion produces reasonable results
        """
        try:
            # Check inputs
            if not (0 < baseline_prob < 1):
                return False
            if or_value <= 0:
                return False

            # Check conversion
            risk = self.log_or_to_prob(np.log(or_value), baseline_prob)
            if not (0 <= risk <= 1):
                return False

            # Check that OR > 1 increases risk
            if or_value > 1 and risk <= baseline_prob:
                return False
            if or_value < 1 and risk >= baseline_prob:
                return False

            return True

        except:
            return False

    def estimate_se_from_ci(self, ci_lower: float, ci_upper: float,
                           on_log_scale: bool = True) -> float:
        """
        Estimate standard error from confidence interval
        """
        if on_log_scale:
            se = (np.log(ci_upper) - np.log(ci_lower)) / (2 * 1.96)
        else:
            se = (ci_upper - ci_lower) / (2 * 1.96)

        return se

    def haldane_anscombe_correction(self, a: int, b: int, c: int, d: int) -> Tuple[float, float]:
        """
        Apply Haldane-Anscombe 0.5 continuity correction for zero cells
        Returns (log_or, se)
        """
        # Add 0.5 to all cells
        a_adj = a + 0.5
        b_adj = b + 0.5
        c_adj = c + 0.5
        d_adj = d + 0.5

        # Calculate OR
        or_value = (a_adj * d_adj) / (b_adj * c_adj)
        log_or = np.log(or_value)

        # Calculate SE
        se = np.sqrt(1/a_adj + 1/b_adj + 1/c_adj + 1/d_adj)

        return log_or, se