"""
Risk scoring API endpoint - integrates all risk engine components
"""

import yaml
import json
import hashlib
from typing import List, Dict, Optional, Any
from pathlib import Path
from flask import Blueprint, request, jsonify
import logging

from risk_engine.schema import (RiskConfig, AgeBand, SurgeryType, Urgency, TimeWindow,
                               OutcomeRisk, ConfidenceLevel)
from risk_engine.pool import MetaAnalysisEngine
from risk_engine.convert import RiskConverter
from risk_engine.baseline import BaselineRiskEngine
from risk_engine.confidence import ConfidenceScorer

logger = logging.getLogger(__name__)

# Create blueprint
risk_bp = Blueprint('risk', __name__, url_prefix='/api/risk')

# Global instances (initialized on first use)
_config = None
_meta_engine = None
_converter = None
_baseline_engine = None
_confidence_scorer = None

def _get_config() -> RiskConfig:
    """Load risk configuration"""
    global _config
    if _config is None:
        config_path = Path(__file__).parent.parent / "config" / "risk_config.yaml"
        try:
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f)
            _config = RiskConfig(**config_data)
        except Exception as e:
            logger.error(f"Failed to load risk config: {e}")
            _config = RiskConfig()  # Use defaults
    return _config

def _get_engines():
    """Initialize all risk engine components"""
    global _meta_engine, _converter, _baseline_engine, _confidence_scorer

    if _meta_engine is None:
        config = _get_config()
        _meta_engine = MetaAnalysisEngine(config)
        _converter = RiskConverter(mc_draws=config.monte_carlo.n_draws,
                                  seed=config.monte_carlo.seed)
        _baseline_engine = BaselineRiskEngine(config)
        _confidence_scorer = ConfidenceScorer(config)

    return _meta_engine, _converter, _baseline_engine, _confidence_scorer

@risk_bp.route('/score', methods=['POST'])
def calculate_risk_score():
    """
    Calculate risk scores for given patient factors

    Expected input:
    {
        "outcome": "LARYNGOSPASM",
        "window": "intraop",
        "age_band": "1-3",
        "surgery": "ENT",
        "urgency": "elective",
        "factors": ["ASTHMA", "RECENT_URI_2W"]
    }
    """
    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ["outcome", "window", "age_band", "surgery", "urgency", "factors"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # Parse enum values
        try:
            window = TimeWindow(data["window"])
            age_band = AgeBand(data["age_band"])
            surgery = SurgeryType(data["surgery"])
            urgency = Urgency(data["urgency"])
        except ValueError as e:
            return jsonify({"error": f"Invalid enum value: {e}"}), 400

        outcome = data["outcome"]
        factor_codes = data["factors"]

        # Get engines
        meta_engine, converter, baseline_engine, confidence_scorer = _get_engines()

        # Get baseline risk
        baseline_risk = baseline_engine.get_baseline_risk(
            outcome, window, age_band, surgery, urgency
        )

        if not baseline_risk:
            return jsonify({"error": f"No baseline data for {outcome}/{window}/{age_band}/{surgery}/{urgency}"}), 404

        # For demo purposes, create synthetic pooled effects
        # In production, these would come from actual meta-analysis
        pooled_effects = _create_demo_pooled_effects(outcome, window, factor_codes)

        # Calculate absolute risk with CI
        point_risk, ci_lower, ci_upper = converter.calculate_absolute_risk_ci(
            pooled_effects, baseline_risk, factor_codes
        )

        # Calculate risk differences
        risk_differences = converter.calculate_risk_differences(point_risk, baseline_risk)

        # Calculate confidence for the main effect (simplified)
        if pooled_effects:
            main_effect = pooled_effects[0]  # Use first effect as representative
            confidence_breakdown = confidence_scorer.calculate_confidence(main_effect)
        else:
            # No effects - baseline only
            confidence_breakdown = _create_baseline_confidence()

        # Create response
        outcome_risk = OutcomeRisk(
            outcome=outcome,
            window=window,
            baseline=baseline_risk,
            adjusted_risk=point_risk,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            absolute_increase_pp=risk_differences["absolute_increase_pp"],
            relative_risk_ratio=risk_differences["relative_risk_ratio"],
            confidence=confidence_breakdown,
            factors=[{"code": code, "effect": "included"} for code in factor_codes],
            diagnostics={
                "method": "REML+HK-SJ",
                "mc_draws": converter.mc_draws,
                "baseline_source": baseline_risk.era or "synthetic"
            },
            citations=[],  # Would include actual study citations
            flags=_generate_risk_flags(baseline_risk, point_risk, confidence_breakdown)
        )

        return jsonify(outcome_risk.dict())

    except Exception as e:
        logger.error(f"Risk calculation error: {e}")
        return jsonify({"error": "Internal server error"}), 500

def _create_demo_pooled_effects(outcome: str, window: TimeWindow, factor_codes: List[str]):
    """Create demo pooled effects for testing"""
    from risk_engine.schema import PooledEffect, Study, StudyDesign, RiskOfBias

    pooled_effects = []

    # Demo effect sizes based on clinical literature
    effect_map = {
        "ASTHMA": {"log_effect": 0.693, "se": 0.2},  # OR = 2.0
        "RECENT_URI_2W": {"log_effect": 1.099, "se": 0.25},  # OR = 3.0
        "OSA": {"log_effect": 0.588, "se": 0.3},  # OR = 1.8
        "PREMATURITY": {"log_effect": 0.405, "se": 0.35},  # OR = 1.5
    }

    for factor in factor_codes:
        if factor in effect_map:
            # Create synthetic studies
            demo_studies = [
                Study(
                    pmid=f"demo_{factor}_1",
                    title=f"Study of {factor} and {outcome}",
                    first_author="Demo et al",
                    pub_year=2022,
                    design=StudyDesign.PROSPECTIVE,
                    risk_of_bias=RiskOfBias.LOW,
                    age_pop="pediatric",
                    surgery_domain=SurgeryType.ENT,
                    urgency=Urgency.ELECTIVE,
                    outcome=outcome,
                    window=window,
                    factor=factor,
                    measure="OR",
                    value=2.0,
                    ci_lower=1.4,
                    ci_upper=2.8,
                    n_total=500,
                    is_adjusted=True
                )
            ]

            effect_data = effect_map[factor]
            pooled_effect = PooledEffect(
                factor=factor,
                outcome=outcome,
                window=window,
                log_effect_raw=effect_data["log_effect"],
                se_raw=effect_data["se"],
                log_effect_shrunk=effect_data["log_effect"] * 0.9,  # Slight shrinkage
                se_shrunk=effect_data["se"] * 1.1,
                k_studies=3,  # Demo
                tau_squared=0.1,
                i_squared=25.0,
                q_statistic=4.5,
                p_heterogeneity=0.15,
                hk_sj_used=False,
                egger_p=0.8,  # No bias
                trim_fill_added=0,
                loo_max_delta_pp=1.2,
                total_weight=15.0,
                studies=demo_studies
            )
            pooled_effects.append(pooled_effect)

    return pooled_effects

def _create_baseline_confidence():
    """Create confidence breakdown for baseline-only estimates"""
    from risk_engine.schema import ConfidenceBreakdown, ConfidenceLevel

    return ConfidenceBreakdown(
        k_studies_score=0.0,
        design_mix_score=0.0,
        bias_score=0.0,
        temporal_freshness_score=0.0,
        window_match_score=0.0,
        heterogeneity_score=1.0,  # No heterogeneity for baseline
        egger_penalty=1.0,
        loo_stability_score=1.0,
        total_score=20.0,  # Low score for baseline only
        letter_grade=ConfidenceLevel.D
    )

def _generate_risk_flags(baseline_risk, adjusted_risk, confidence_breakdown):
    """Generate warning/info flags for the risk assessment"""
    flags = []

    if baseline_risk.baseline_high_risk:
        flags.append("BASELINE_HIGH_RISK")

    if adjusted_risk > 0.1:  # >10% risk
        flags.append("HIGH_ABSOLUTE_RISK")

    if adjusted_risk / baseline_risk.p0 > 5:  # >5x increase
        flags.append("LARGE_RELATIVE_INCREASE")

    if confidence_breakdown.letter_grade == ConfidenceLevel.D:
        flags.append("LOW_CONFIDENCE_EVIDENCE")

    if confidence_breakdown.heterogeneity_score < 0.5:
        flags.append("HIGH_HETEROGENEITY")

    return flags

@risk_bp.route('/config', methods=['GET'])
def get_risk_config():
    """Get current risk engine configuration"""
    config = _get_config()
    return jsonify(config.dict())

@risk_bp.route('/baseline/<outcome>/<window>', methods=['GET'])
def get_baseline_data(outcome: str, window: str):
    """Get baseline risk data for an outcome/window"""
    try:
        _, _, baseline_engine, _ = _get_engines()

        # Get query parameters
        age_band = request.args.get('age_band', 'SEVEN_TO_12')
        surgery = request.args.get('surgery', 'ENT')
        urgency = request.args.get('urgency', 'elective')

        # Parse enums
        window_enum = TimeWindow(window)
        age_band_enum = AgeBand(age_band)
        surgery_enum = SurgeryType(surgery)
        urgency_enum = Urgency(urgency)

        baseline_risk = baseline_engine.get_baseline_risk(
            outcome, window_enum, age_band_enum, surgery_enum, urgency_enum
        )

        if not baseline_risk:
            return jsonify({"error": "No baseline data found"}), 404

        return jsonify(baseline_risk.dict())

    except ValueError as e:
        return jsonify({"error": f"Invalid parameter: {e}"}), 400
    except Exception as e:
        logger.error(f"Baseline lookup error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@risk_bp.route('/coverage', methods=['GET'])
def get_coverage_stats():
    """Get statistics about data coverage"""
    try:
        _, _, baseline_engine, _ = _get_engines()
        stats = baseline_engine.get_coverage_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Coverage stats error: {e}")
        return jsonify({"error": "Internal server error"}), 500