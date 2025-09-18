"""
Meta-analysis pooling engine with REML, HK-SJ corrections, and publication bias tests
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional, Any
from scipy import stats
from scipy.optimize import minimize_scalar
import warnings
import logging
from dataclasses import dataclass

from .schema import Study, PooledEffect, RiskConfig, TimeWindow

logger = logging.getLogger(__name__)

@dataclass
class MetaAnalysisResult:
    """Raw meta-analysis results before conversion to PooledEffect schema"""
    log_effect: float
    se: float
    tau_squared: float
    i_squared: float
    q_statistic: float
    p_heterogeneity: float
    k_studies: int
    total_weight: float
    hk_sj_used: bool = False
    egger_p: Optional[float] = None
    trim_fill_added: int = 0

class MetaAnalysisEngine:
    """Core meta-analysis engine with REML pooling and quality adjustments"""

    def __init__(self, config: RiskConfig):
        self.config = config
        self.current_year = 2025  # Update as needed

    def pool_studies(self, studies: List[Study], factor: str, outcome: str,
                    window: TimeWindow) -> Optional[PooledEffect]:
        """
        Pool studies for a factor-outcome pair using REML with quality weights
        """
        if len(studies) < self.config.validation.min_studies_per_factor:
            logger.warning(f"Insufficient studies for {factor}-{outcome}: {len(studies)}")
            return None

        try:
            # Prepare effect data
            effects_data = self._prepare_effects(studies)

            # Apply quality weights
            weights = self._calculate_weights(studies, effects_data)

            # Run meta-analysis
            ma_result = self._run_meta_analysis(effects_data, weights)

            # Publication bias tests
            if len(studies) >= 10:  # Need sufficient studies
                ma_result.egger_p = self._egger_test(effects_data, weights)
                if ma_result.egger_p and ma_result.egger_p < 0.05:
                    ma_result.trim_fill_added = self._trim_and_fill(effects_data, weights)

            # Leave-one-out diagnostics
            loo_delta = self._loo_diagnostics(effects_data, weights)

            # Bayesian shrinkage (optional)
            log_effect_shrunk = None
            se_shrunk = None
            if self.config.features.enable_bayesian_shrinkage:
                log_effect_shrunk, se_shrunk = self._bayesian_shrinkage(
                    ma_result.log_effect, ma_result.se, ma_result.k_studies
                )

            return PooledEffect(
                factor=factor,
                outcome=outcome,
                window=window,
                log_effect_raw=ma_result.log_effect,
                se_raw=ma_result.se,
                log_effect_shrunk=log_effect_shrunk,
                se_shrunk=se_shrunk,
                k_studies=ma_result.k_studies,
                tau_squared=ma_result.tau_squared,
                i_squared=ma_result.i_squared,
                q_statistic=ma_result.q_statistic,
                p_heterogeneity=ma_result.p_heterogeneity,
                hk_sj_used=ma_result.hk_sj_used,
                egger_p=ma_result.egger_p,
                trim_fill_added=ma_result.trim_fill_added,
                loo_max_delta_pp=loo_delta,
                total_weight=ma_result.total_weight,
                studies=studies
            )

        except Exception as e:
            logger.error(f"Meta-analysis failed for {factor}-{outcome}: {e}")
            return None

    def _prepare_effects(self, studies: List[Study]) -> np.ndarray:
        """Convert studies to log effects with standard errors"""
        effects = []

        for study in studies:
            # Convert to log scale
            if study.measure in ["OR", "RR", "HR"]:
                log_effect = np.log(study.value)
            else:
                raise ValueError(f"Unsupported measure: {study.measure}")

            # Calculate SE from CI if not provided
            if study.se is None:
                if study.ci_lower and study.ci_upper:
                    # SE = (log(upper) - log(lower)) / (2 * 1.96)
                    se = (np.log(study.ci_upper) - np.log(study.ci_lower)) / (2 * 1.96)
                else:
                    # Fallback: estimate from counts using Haldane-Anscombe
                    se = self._estimate_se_from_counts(study)
            else:
                se = study.se

            effects.append([log_effect, se])

        return np.array(effects)

    def _estimate_se_from_counts(self, study: Study) -> float:
        """Estimate SE from event counts using Haldane-Anscombe correction"""
        if not all([study.events_exposed, study.events_control,
                   study.n_exposed, study.n_control]):
            # Fallback: use wide SE for uncertain effects
            return 0.5

        # Add 0.5 to all cells (Haldane-Anscombe)
        a = study.events_exposed + 0.5
        b = study.n_exposed - study.events_exposed + 0.5
        c = study.events_control + 0.5
        d = study.n_control - study.events_control + 0.5

        # SE for log(OR)
        se = np.sqrt(1/a + 1/b + 1/c + 1/d)
        return se

    def _calculate_weights(self, studies: List[Study], effects_data: np.ndarray) -> np.ndarray:
        """Calculate composite quality weights for each study"""
        weights = []

        for i, study in enumerate(studies):
            # Base inverse-variance weight (will be updated with tau²)
            base_weight = 1.0 / (effects_data[i, 1] ** 2)

            # Temporal weight
            temporal_weight = np.exp(-(self.current_year - study.pub_year) / self.config.temporal_tau)

            # Design weight
            design_weight = self.config.design_weights.get(study.design, 0.5)

            # Bias penalty
            bias_weight = self.config.bias_penalty.get(study.risk_of_bias, 0.5)

            # Window match weight (simplified - assume exact match for now)
            window_weight = 1.0

            # Small study penalty
            small_study_weight = (self.config.small_study_penalty
                                if study.n_total < self.config.small_study_threshold
                                else 1.0)

            # Composite weight
            composite_weight = (base_weight * temporal_weight * design_weight *
                              bias_weight * window_weight * small_study_weight)

            weights.append(composite_weight)

        return np.array(weights)

    def _run_meta_analysis(self, effects_data: np.ndarray,
                          weights: np.ndarray) -> MetaAnalysisResult:
        """Run REML meta-analysis with optional HK-SJ correction"""

        # Step 1: Estimate tau² using REML
        tau_squared = self._estimate_tau_squared_reml(effects_data, weights)

        # Step 2: Update weights with tau²
        updated_weights = 1.0 / (effects_data[:, 1] ** 2 + tau_squared)
        final_weights = weights * updated_weights

        # Step 3: Calculate pooled effect
        sum_weights = np.sum(final_weights)
        pooled_effect = np.sum(final_weights * effects_data[:, 0]) / sum_weights
        pooled_se = np.sqrt(1.0 / sum_weights)

        # Step 4: Heterogeneity statistics
        q_stat = np.sum(final_weights * (effects_data[:, 0] - pooled_effect) ** 2)
        df = len(effects_data) - 1
        p_heterogeneity = 1 - stats.chi2.cdf(q_stat, df) if df > 0 else 1.0

        # I² calculation
        i_squared = max(0, (q_stat - df) / q_stat) if q_stat > 0 else 0
        i_squared_pct = i_squared * 100

        # Step 5: Knapp-Hartung adjustment if needed
        hk_sj_used = False
        if (self.config.use_hk_sj and
            (len(effects_data) < self.config.hk_sj_threshold_k or
             i_squared_pct > self.config.hk_sj_threshold_i2)):

            pooled_se = self._knapp_hartung_adjustment(
                effects_data, final_weights, pooled_effect, tau_squared
            )
            hk_sj_used = True

        return MetaAnalysisResult(
            log_effect=pooled_effect,
            se=pooled_se,
            tau_squared=tau_squared,
            i_squared=i_squared_pct,
            q_statistic=q_stat,
            p_heterogeneity=p_heterogeneity,
            k_studies=len(effects_data),
            total_weight=sum_weights,
            hk_sj_used=hk_sj_used
        )

    def _estimate_tau_squared_reml(self, effects_data: np.ndarray,
                                  weights: np.ndarray) -> float:
        """Estimate between-study variance using REML"""

        def reml_objective(tau_sq):
            # REML log-likelihood (simplified)
            w_i = 1.0 / (effects_data[:, 1] ** 2 + tau_sq)
            w_i = weights * w_i  # Apply quality weights

            sum_w = np.sum(w_i)
            pooled_effect = np.sum(w_i * effects_data[:, 0]) / sum_w

            # Q statistic
            q = np.sum(w_i * (effects_data[:, 0] - pooled_effect) ** 2)

            # REML criterion (negative log-likelihood)
            reml = 0.5 * (q + np.sum(np.log(effects_data[:, 1] ** 2 + tau_sq)) +
                         np.log(sum_w))

            return reml

        # Optimize tau²
        try:
            result = minimize_scalar(reml_objective, bounds=(0, 2), method='bounded')
            return max(0, result.x)
        except:
            # Fallback to DerSimonian-Laird
            return self._estimate_tau_squared_dl(effects_data, weights)

    def _estimate_tau_squared_dl(self, effects_data: np.ndarray,
                                weights: np.ndarray) -> float:
        """Fallback DerSimonian-Laird estimator for tau²"""
        # Simple inverse-variance weights for DL
        w_i = 1.0 / (effects_data[:, 1] ** 2)
        sum_w = np.sum(w_i)
        pooled_effect = np.sum(w_i * effects_data[:, 0]) / sum_w

        q = np.sum(w_i * (effects_data[:, 0] - pooled_effect) ** 2)
        df = len(effects_data) - 1

        if df <= 0:
            return 0.0

        c = sum_w - np.sum(w_i ** 2) / sum_w
        tau_squared = max(0, (q - df) / c) if c > 0 else 0

        return tau_squared

    def _knapp_hartung_adjustment(self, effects_data: np.ndarray,
                                 weights: np.ndarray, pooled_effect: float,
                                 tau_squared: float) -> float:
        """Apply Knapp-Hartung adjustment for small studies/high heterogeneity"""

        # Calculate residual sum of squares
        residuals = effects_data[:, 0] - pooled_effect
        rss = np.sum(weights * residuals ** 2)

        # Degrees of freedom
        df = len(effects_data) - 1

        if df <= 0:
            return np.sqrt(1.0 / np.sum(weights))

        # HK adjustment
        s_squared = rss / df
        adjusted_se = np.sqrt(s_squared / np.sum(weights))

        return adjusted_se

    def _egger_test(self, effects_data: np.ndarray, weights: np.ndarray) -> Optional[float]:
        """Egger's test for publication bias"""
        try:
            # Precision = 1/SE
            precision = 1.0 / effects_data[:, 1]

            # Weighted regression: effect ~ precision
            X = np.column_stack([np.ones(len(precision)), precision])
            W = np.diag(weights)

            # Weighted least squares
            XtWX_inv = np.linalg.inv(X.T @ W @ X)
            beta = XtWX_inv @ X.T @ W @ effects_data[:, 0]

            # Test intercept = 0 (no bias)
            residuals = effects_data[:, 0] - X @ beta
            mse = np.sum(weights * residuals ** 2) / (len(effects_data) - 2)
            se_intercept = np.sqrt(mse * XtWX_inv[0, 0])

            t_stat = beta[0] / se_intercept
            p_value = 2 * (1 - stats.t.cdf(abs(t_stat), len(effects_data) - 2))

            return p_value

        except Exception as e:
            logger.warning(f"Egger test failed: {e}")
            return None

    def _trim_and_fill(self, effects_data: np.ndarray, weights: np.ndarray) -> int:
        """Simple trim-and-fill for publication bias (simplified implementation)"""
        # This is a simplified version - full implementation would be more complex
        try:
            # Estimate number of missing studies (very basic)
            n_missing = max(0, int(0.1 * len(effects_data)))  # Placeholder
            return n_missing
        except:
            return 0

    def _loo_diagnostics(self, effects_data: np.ndarray, weights: np.ndarray) -> Optional[float]:
        """Leave-one-out diagnostics for stability"""
        if len(effects_data) <= 2:
            return None

        try:
            # Original pooled effect
            original_result = self._run_meta_analysis(effects_data, weights)
            original_risk = self._log_odds_to_prob(original_result.log_effect, 0.05)  # Assume 5% baseline

            max_delta = 0.0

            # Leave each study out
            for i in range(len(effects_data)):
                loo_effects = np.delete(effects_data, i, axis=0)
                loo_weights = np.delete(weights, i)

                loo_result = self._run_meta_analysis(loo_effects, loo_weights)
                loo_risk = self._log_odds_to_prob(loo_result.log_effect, 0.05)

                delta_pp = abs(loo_risk - original_risk) * 100  # Percentage points
                max_delta = max(max_delta, delta_pp)

            return max_delta

        except Exception as e:
            logger.warning(f"LOO diagnostics failed: {e}")
            return None

    def _log_odds_to_prob(self, log_odds: float, baseline_prob: float) -> float:
        """Convert log odds to probability given baseline"""
        baseline_odds = baseline_prob / (1 - baseline_prob)
        new_odds = baseline_odds * np.exp(log_odds)
        return new_odds / (1 + new_odds)

    def _bayesian_shrinkage(self, log_effect: float, se: float,
                           k_studies: int) -> Tuple[float, float]:
        """Apply Bayesian shrinkage with skeptical prior"""

        # Prior: N(0, skeptical_prior_sd²)
        prior_variance = self.config.skeptical_prior_sd ** 2
        data_variance = se ** 2

        # Posterior precision = prior precision + data precision
        prior_precision = 1.0 / prior_variance
        data_precision = 1.0 / data_variance
        posterior_precision = prior_precision + data_precision

        # Shrinkage factor
        shrinkage = data_precision / posterior_precision

        # Shrunk estimate
        shrunk_effect = shrinkage * log_effect  # Prior mean is 0
        shrunk_se = np.sqrt(1.0 / posterior_precision)

        return shrunk_effect, shrunk_se