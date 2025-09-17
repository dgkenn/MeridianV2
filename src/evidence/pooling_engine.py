"""
Statistical pooling engine for baseline risks and effect modifiers.
Implements random-effects meta-analysis with quality weighting and audit trails.
"""

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize_scalar
import json
import logging
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import warnings

from ..core.database import get_database

logger = logging.getLogger(__name__)

@dataclass
class PooledBaseline:
    id: str
    outcome_token: str
    context_label: str
    k: int  # number of studies
    p0_mean: float
    p0_ci_low: float
    p0_ci_high: float
    N_total: int
    time_horizon: str
    pmids: List[str]
    method: str
    i_squared: float
    evidence_version: str
    quality_summary: Dict[str, Any]

@dataclass
class PooledEffect:
    id: str
    outcome_token: str
    modifier_token: str
    context_label: str
    k: int
    or_mean: float
    or_ci_low: float
    or_ci_high: float
    log_or_var: float
    method: str
    inputs: List[str]  # estimate IDs
    pmids: List[str]
    i_squared: float
    tau_squared: float
    evidence_version: str
    quality_summary: Dict[str, Any]

class MetaAnalysisEngine:
    """
    Comprehensive meta-analysis engine with multiple pooling methods
    and robust heterogeneity assessment.
    """

    def __init__(self):
        self.db = get_database()

        # Minimum study requirements
        self.min_studies_baseline = 2
        self.min_studies_effect = 2

        # Quality weight thresholds
        self.min_quality_weight = 0.5

    def pool_baseline_risks(self, outcome_token: str, context_label: str = None,
                           evidence_version: str = None) -> Optional[PooledBaseline]:
        """
        Pool baseline risk estimates for an outcome using logit transformation.
        """

        # Fetch baseline incidence estimates
        estimates = self._get_baseline_estimates(outcome_token, context_label)

        if len(estimates) < self.min_studies_baseline:
            logger.warning(f"Insufficient studies for baseline pooling: {outcome_token}")
            return None

        # Prepare data for meta-analysis
        study_data = []
        for est in estimates:
            if est['measure'] == 'INCIDENCE' and est['estimate'] > 0 and est['estimate'] < 1:
                # Convert percentage to proportion if needed
                prop = est['estimate'] / 100 if est['estimate'] > 1 else est['estimate']

                # Skip extreme values
                if prop <= 0.001 or prop >= 0.999:
                    continue

                study_data.append({
                    'pmid': est['pmid'],
                    'estimate_id': est['id'],
                    'proportion': prop,
                    'n_total': est['n_group'] or 100,  # Default if missing
                    'n_events': est['n_events'] or int(prop * (est['n_group'] or 100)),
                    'quality_weight': est['quality_weight'] or 1.0,
                    'evidence_grade': est['evidence_grade'] or 'D'
                })

        if len(study_data) < self.min_studies_baseline:
            logger.warning(f"Insufficient valid studies after filtering: {outcome_token}")
            return None

        # Perform logit-transformed random effects meta-analysis
        pooled_result = self._pool_proportions(study_data)

        if not pooled_result:
            return None

        # Create pooled baseline object
        baseline_id = f"baseline_{outcome_token}_{context_label or 'general'}_{datetime.now().isoformat()}"

        baseline = PooledBaseline(
            id=baseline_id,
            outcome_token=outcome_token,
            context_label=context_label or "general",
            k=len(study_data),
            p0_mean=pooled_result['pooled_proportion'],
            p0_ci_low=pooled_result['ci_lower'],
            p0_ci_high=pooled_result['ci_upper'],
            N_total=sum(s['n_total'] for s in study_data),
            time_horizon=self._determine_time_horizon(estimates),
            pmids=[s['pmid'] for s in study_data],
            method=pooled_result['method'],
            i_squared=pooled_result['i_squared'],
            evidence_version=evidence_version or self._get_current_version(),
            quality_summary=self._summarize_quality(study_data)
        )

        # Store in database
        self._store_pooled_baseline(baseline)

        return baseline

    def pool_effect_modifiers(self, outcome_token: str, modifier_token: str,
                             context_label: str = None, evidence_version: str = None) -> Optional[PooledEffect]:
        """
        Pool effect modifier estimates using log-OR random effects meta-analysis.
        """

        # Fetch effect estimates
        estimates = self._get_effect_estimates(outcome_token, modifier_token, context_label)

        if len(estimates) < self.min_studies_effect:
            logger.warning(f"Insufficient studies for effect pooling: {modifier_token} -> {outcome_token}")
            return None

        # Prepare data for meta-analysis
        study_data = []
        for est in estimates:
            if est['measure'] in ['OR', 'RR', 'HR'] and est['estimate'] > 0:

                # Calculate log effect and variance
                log_effect = np.log(est['estimate'])

                # Estimate variance from CI if available
                if est['ci_low'] and est['ci_high'] and est['ci_low'] > 0:
                    log_ci_low = np.log(est['ci_low'])
                    log_ci_high = np.log(est['ci_high'])
                    se_log = (log_ci_high - log_ci_low) / (2 * 1.96)
                    variance = se_log ** 2
                else:
                    # Use default variance based on quality
                    variance = self._estimate_variance_from_quality(est)

                # Skip studies with unreasonable variance
                if variance <= 0 or variance > 10:
                    continue

                study_data.append({
                    'pmid': est['pmid'],
                    'estimate_id': est['id'],
                    'log_effect': log_effect,
                    'variance': variance,
                    'weight': 1.0 / variance,
                    'quality_weight': est['quality_weight'] or 1.0,
                    'evidence_grade': est['evidence_grade'] or 'D',
                    'adjusted': est['adjusted'] or False
                })

        if len(study_data) < self.min_studies_effect:
            logger.warning(f"Insufficient valid studies after filtering: {modifier_token} -> {outcome_token}")
            return None

        # Perform random effects meta-analysis
        pooled_result = self._pool_log_effects(study_data)

        if not pooled_result:
            return None

        # Create pooled effect object
        effect_id = f"effect_{outcome_token}_{modifier_token}_{context_label or 'general'}_{datetime.now().isoformat()}"

        effect = PooledEffect(
            id=effect_id,
            outcome_token=outcome_token,
            modifier_token=modifier_token,
            context_label=context_label or "general",
            k=len(study_data),
            or_mean=pooled_result['pooled_or'],
            or_ci_low=pooled_result['ci_lower'],
            or_ci_high=pooled_result['ci_upper'],
            log_or_var=pooled_result['pooled_variance'],
            method=pooled_result['method'],
            inputs=[s['estimate_id'] for s in study_data],
            pmids=[s['pmid'] for s in study_data],
            i_squared=pooled_result['i_squared'],
            tau_squared=pooled_result['tau_squared'],
            evidence_version=evidence_version or self._get_current_version(),
            quality_summary=self._summarize_quality(study_data)
        )

        # Store in database
        self._store_pooled_effect(effect)

        return effect

    def _pool_proportions(self, study_data: List[Dict]) -> Optional[Dict]:
        """
        Pool proportions using logit transformation and random effects.
        """
        try:
            # Convert to arrays
            proportions = np.array([s['proportion'] for s in study_data])
            n_totals = np.array([s['n_total'] for s in study_data])
            quality_weights = np.array([s['quality_weight'] for s in study_data])

            # Logit transform
            logits = np.log(proportions / (1 - proportions))

            # Calculate variances using delta method
            variances = 1 / (n_totals * proportions * (1 - proportions))

            # Apply quality weighting
            weights = quality_weights / variances
            weights = weights / np.sum(weights)  # Normalize

            # Fixed effects estimate
            fixed_logit = np.sum(weights * logits)
            fixed_var = 1 / np.sum(1 / variances)

            # Test for heterogeneity
            Q = np.sum((logits - fixed_logit) ** 2 / variances)
            df = len(study_data) - 1
            p_het = 1 - stats.chi2.cdf(Q, df) if df > 0 else 1.0

            # Calculate I²
            i_squared = max(0, (Q - df) / Q) if Q > 0 else 0

            # Random effects if significant heterogeneity
            if p_het < 0.10 and len(study_data) >= 3:
                # DerSimonian-Laird tau² estimation
                tau_squared = max(0, (Q - df) / (np.sum(1/variances) - np.sum(1/variances**2) / np.sum(1/variances)))

                # Random effects weights
                re_weights = 1 / (variances + tau_squared)
                re_weights = re_weights / np.sum(re_weights)

                pooled_logit = np.sum(re_weights * logits)
                pooled_var = 1 / np.sum(re_weights)
                method = "random_effects"
            else:
                pooled_logit = fixed_logit
                pooled_var = fixed_var
                method = "fixed_effects"

            # Transform back to proportion scale
            pooled_proportion = 1 / (1 + np.exp(-pooled_logit))

            # Confidence interval on logit scale, then transform
            logit_se = np.sqrt(pooled_var)
            logit_ci_low = pooled_logit - 1.96 * logit_se
            logit_ci_high = pooled_logit + 1.96 * logit_se

            ci_lower = 1 / (1 + np.exp(-logit_ci_low))
            ci_upper = 1 / (1 + np.exp(-logit_ci_high))

            return {
                'pooled_proportion': pooled_proportion,
                'ci_lower': ci_lower,
                'ci_upper': ci_upper,
                'method': method,
                'i_squared': i_squared,
                'q_statistic': Q,
                'p_heterogeneity': p_het
            }

        except Exception as e:
            logger.error(f"Error in proportion pooling: {e}")
            return None

    def _pool_log_effects(self, study_data: List[Dict]) -> Optional[Dict]:
        """
        Pool log effects using random effects meta-analysis with Hartung-Knapp adjustment.
        """
        try:
            # Convert to arrays
            log_effects = np.array([s['log_effect'] for s in study_data])
            variances = np.array([s['variance'] for s in study_data])
            quality_weights = np.array([s['quality_weight'] for s in study_data])

            # Inverse variance weights
            iv_weights = 1 / variances

            # Apply quality weighting
            weights = quality_weights * iv_weights
            weights = weights / np.sum(weights)

            # Fixed effects estimate
            fixed_effect = np.sum(weights * log_effects)
            fixed_var = 1 / np.sum(iv_weights)

            # Test for heterogeneity
            Q = np.sum(iv_weights * (log_effects - fixed_effect) ** 2)
            df = len(study_data) - 1
            p_het = 1 - stats.chi2.cdf(Q, df) if df > 0 else 1.0

            # Calculate I²
            i_squared = max(0, (Q - df) / Q) if Q > 0 else 0

            # Random effects if significant heterogeneity or >= 3 studies
            if (p_het < 0.10 or len(study_data) >= 3) and df > 0:
                # Paule-Mandel tau² estimation (more robust than DL)
                tau_squared = self._estimate_tau_squared_pm(log_effects, variances)

                # Random effects weights
                re_weights = 1 / (variances + tau_squared)

                pooled_effect = np.sum(re_weights * log_effects) / np.sum(re_weights)
                pooled_var = 1 / np.sum(re_weights)

                # Hartung-Knapp adjustment for small studies
                if len(study_data) <= 10:
                    hk_factor = self._hartung_knapp_adjustment(log_effects, variances, tau_squared)
                    pooled_var *= hk_factor

                method = "random_effects_pm"
            else:
                pooled_effect = fixed_effect
                pooled_var = fixed_var
                tau_squared = 0.0
                method = "fixed_effects"

            # Transform to OR scale
            pooled_or = np.exp(pooled_effect)

            # Confidence interval
            se = np.sqrt(pooled_var)
            ci_log_lower = pooled_effect - 1.96 * se
            ci_log_upper = pooled_effect + 1.96 * se

            ci_lower = np.exp(ci_log_lower)
            ci_upper = np.exp(ci_log_upper)

            return {
                'pooled_or': pooled_or,
                'ci_lower': ci_lower,
                'ci_upper': ci_upper,
                'pooled_variance': pooled_var,
                'method': method,
                'i_squared': i_squared,
                'tau_squared': tau_squared,
                'q_statistic': Q,
                'p_heterogeneity': p_het
            }

        except Exception as e:
            logger.error(f"Error in effect pooling: {e}")
            return None

    def _estimate_tau_squared_pm(self, effects: np.ndarray, variances: np.ndarray) -> float:
        """
        Paule-Mandel estimator for between-study variance.
        More robust than DerSimonian-Laird for small studies.
        """
        def pm_equation(tau_sq):
            weights = 1 / (variances + tau_sq)
            weighted_mean = np.sum(weights * effects) / np.sum(weights)
            Q = np.sum(weights * (effects - weighted_mean) ** 2)
            return Q - (len(effects) - 1)

        try:
            # Solve for tau² that makes Q = k-1
            result = minimize_scalar(lambda x: pm_equation(x) ** 2, bounds=(0, 10), method='bounded')
            return max(0, result.x)
        except:
            # Fall back to DerSimonian-Laird if PM fails
            weights = 1 / variances
            weighted_mean = np.sum(weights * effects) / np.sum(weights)
            Q = np.sum(weights * (effects - weighted_mean) ** 2)
            df = len(effects) - 1
            return max(0, (Q - df) / (np.sum(weights) - np.sum(weights**2) / np.sum(weights)))

    def _hartung_knapp_adjustment(self, effects: np.ndarray, variances: np.ndarray, tau_squared: float) -> float:
        """
        Hartung-Knapp adjustment factor for small studies.
        """
        try:
            weights = 1 / (variances + tau_squared)
            weighted_mean = np.sum(weights * effects) / np.sum(weights)

            # Calculate adjusted variance
            residuals = effects - weighted_mean
            adj_variance = np.sum(weights * residuals ** 2) / ((len(effects) - 1) * np.sum(weights))

            return adj_variance / (1 / np.sum(weights))
        except:
            return 1.0

    def _estimate_variance_from_quality(self, estimate: Dict) -> float:
        """
        Estimate variance when CI is not available, based on study quality.
        """
        # Base variance depends on effect size (larger effects often less precise)
        base_var = min(1.0, 0.1 + 0.1 * abs(np.log(estimate['estimate'])))

        # Adjust by quality grade
        quality_multipliers = {'A': 0.5, 'B': 0.7, 'C': 1.0, 'D': 1.5}
        grade = estimate.get('evidence_grade', 'D')

        # Adjust by adjustment status
        adjustment_factor = 0.8 if estimate.get('adjusted', False) else 1.2

        return base_var * quality_multipliers.get(grade, 1.5) * adjustment_factor

    def _get_baseline_estimates(self, outcome_token: str, context_label: str = None) -> List[Dict]:
        """Fetch baseline estimates from database."""

        query = """
            SELECT outcome_token, context_label, baseline_risk, baseline_source
            FROM estimates
            WHERE outcome_token = ? AND modifier_token IS NULL AND measure = 'INCIDENCE'
        """
        params = [outcome_token]

        if context_label:
            query += " AND (definition_note LIKE ? OR pmid IN (SELECT pmid FROM papers WHERE procedure = ?))"
            params.extend([f"%{context_label}%", context_label])

        query += " ORDER BY quality_weight DESC, year DESC"

        results = self.db.conn.execute(query, params).fetchall()
        return [dict(row) for row in results]

    def _get_effect_estimates(self, outcome_token: str, modifier_token: str, context_label: str = None) -> List[Dict]:
        """Fetch effect modifier estimates from database."""

        query = """
            SELECT outcome_token, context_label, baseline_risk, baseline_source
            FROM estimates
            WHERE outcome_token = ? AND modifier_token = ? AND measure IN ('OR', 'RR', 'HR')
        """
        params = [outcome_token, modifier_token]

        if context_label:
            query += " AND (definition_note LIKE ? OR pmid IN (SELECT pmid FROM papers WHERE procedure = ?))"
            params.extend([f"%{context_label}%", context_label])

        query += " ORDER BY quality_weight DESC, adjusted DESC, year DESC"

        results = self.db.conn.execute(query, params).fetchall()
        return [dict(row) for row in results]

    def _determine_time_horizon(self, estimates: List[Dict]) -> str:
        """Determine most common time horizon from estimates."""
        horizons = [est.get('time_horizon', 'unspecified') for est in estimates]
        horizon_counts = {}
        for h in horizons:
            horizon_counts[h] = horizon_counts.get(h, 0) + 1

        return max(horizon_counts.items(), key=lambda x: x[1])[0] if horizon_counts else "unspecified"

    def _summarize_quality(self, study_data: List[Dict]) -> Dict[str, Any]:
        """Summarize quality distribution of included studies."""
        grades = [s.get('evidence_grade', 'D') for s in study_data]
        grade_counts = {}
        for g in grades:
            grade_counts[g] = grade_counts.get(g, 0) + 1

        return {
            'grade_distribution': grade_counts,
            'mean_quality_weight': np.mean([s.get('quality_weight', 1.0) for s in study_data]),
            'adjusted_studies': sum(1 for s in study_data if s.get('adjusted', False)),
            'total_studies': len(study_data)
        }

    def _get_current_version(self) -> str:
        """Get current evidence version."""
        return self.db.get_current_evidence_version() or "v1.0.0"

    def _store_pooled_baseline(self, baseline: PooledBaseline):
        """Store pooled baseline in database."""
        try:
            self.db.conn.execute("""
                INSERT OR REPLACE INTO baselines_pooled
                (id, outcome_token, context_label, k, p0_mean, p0_ci_low, p0_ci_high,
                 N_total, time_horizon, pmids, method, i_squared, evidence_version,
                 quality_summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                baseline.id, baseline.outcome_token, baseline.context_label, baseline.k,
                baseline.p0_mean, baseline.p0_ci_low, baseline.p0_ci_high,
                baseline.N_total, baseline.time_horizon, json.dumps(baseline.pmids),
                baseline.method, baseline.i_squared, baseline.evidence_version,
                json.dumps(baseline.quality_summary)
            ])

            # Log the action
            self.db.log_action("baselines_pooled", baseline.id, "INSERT", asdict(baseline))

            logger.info(f"Stored pooled baseline: {baseline.id}")

        except Exception as e:
            logger.error(f"Error storing pooled baseline {baseline.id}: {e}")

    def _store_pooled_effect(self, effect: PooledEffect):
        """Store pooled effect in database."""
        try:
            self.db.conn.execute("""
                INSERT OR REPLACE INTO effects_pooled
                (id, outcome_token, modifier_token, context_label, k, or_mean,
                 or_ci_low, or_ci_high, log_or_var, method, inputs, pmids,
                 i_squared, tau_squared, evidence_version, quality_summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                effect.id, effect.outcome_token, effect.modifier_token, effect.context_label,
                effect.k, effect.or_mean, effect.or_ci_low, effect.or_ci_high,
                effect.log_or_var, effect.method, json.dumps(effect.inputs),
                json.dumps(effect.pmids), effect.i_squared, effect.tau_squared,
                effect.evidence_version, json.dumps(effect.quality_summary)
            ])

            # Log the action
            self.db.log_action("effects_pooled", effect.id, "INSERT", asdict(effect))

            logger.info(f"Stored pooled effect: {effect.id}")

        except Exception as e:
            logger.error(f"Error storing pooled effect {effect.id}: {e}")

    def get_pooled_baseline(self, outcome_token: str, context_label: str = None) -> Optional[PooledBaseline]:
        """Retrieve pooled baseline from database."""

        query = """
            SELECT * FROM baselines_pooled
            WHERE outcome_token = ? AND context_label = ?
            ORDER BY updated_at DESC LIMIT 1
        """

        result = self.db.conn.execute(query, [outcome_token, context_label or "general"]).fetchone()

        if result:
            row_dict = dict(result)
            row_dict['pmids'] = json.loads(row_dict['pmids'])
            row_dict['quality_summary'] = json.loads(row_dict['quality_summary'])
            return PooledBaseline(**row_dict)

        return None

    def get_pooled_effect(self, outcome_token: str, modifier_token: str,
                         context_label: str = None) -> Optional[PooledEffect]:
        """Retrieve pooled effect from database."""

        query = """
            SELECT * FROM effects_pooled
            WHERE outcome_token = ? AND modifier_token = ? AND context_label = ?
            ORDER BY updated_at DESC LIMIT 1
        """

        result = self.db.conn.execute(query, [outcome_token, modifier_token,
                                            context_label or "general"]).fetchone()

        if result:
            row_dict = dict(result)
            row_dict['inputs'] = json.loads(row_dict['inputs'])
            row_dict['pmids'] = json.loads(row_dict['pmids'])
            row_dict['quality_summary'] = json.loads(row_dict['quality_summary'])
            return PooledEffect(**row_dict)

        return None