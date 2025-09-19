"""
Risk scoring engine with baseline + modifier calculations.
Implements evidence-based risk assessment with confidence intervals and audit trails.
"""

import numpy as np
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import math

from ..core.database import get_database
from ..evidence.pooling_engine import MetaAnalysisEngine
from ..ontology.core_ontology import AnesthesiaOntology
from ..api.evidence_referencing import EvidenceReferencingEngine
from .hpi_parser import ExtractedFactor, ParsedHPI

logger = logging.getLogger(__name__)

@dataclass
class RiskAssessment:
    outcome: str
    outcome_label: str
    category: str
    baseline_risk: float
    baseline_context: str
    adjusted_risk: float
    confidence_interval: Tuple[float, float]
    risk_ratio: float
    risk_difference: float
    evidence_grade: str
    k_studies: int
    contributing_factors: List[Dict[str, Any]]
    citations: List[str]
    last_updated: datetime
    no_evidence: bool = False

@dataclass
class RiskSummary:
    session_id: str
    evidence_version: str
    mode: str
    risks: List[RiskAssessment]
    summary: Dict[str, Any]
    calculated_at: datetime

class RiskEngine:
    """
    Comprehensive risk assessment engine that combines baseline risks
    with effect modifiers using evidence-based calculations.
    """

    def __init__(self):
        self.db = get_database()
        self.pooling_engine = MetaAnalysisEngine()
        self.ontology = AnesthesiaOntology()
        self.evidence_engine = EvidenceReferencingEngine()

        # Risk calculation parameters
        self.min_baseline_risk = 0.0001  # 0.01%
        self.max_baseline_risk = 0.5     # 50%
        self.min_or = 0.1               # Minimum OR/RR
        self.max_or = 50.0              # Maximum OR/RR

        # Context matching weights
        self.context_weights = {
            "exact_match": 1.0,
            "population_match": 0.8,
            "procedure_match": 0.7,
            "general": 0.5
        }

        # Evidence quality thresholds
        self.min_studies_for_pooled = 2
        self.min_quality_score = 2.0

    def calculate_risks(self, factors: List[ExtractedFactor], demographics: Dict[str, Any],
                       mode: str = "model_based", context_label: str = None,
                       session_id: str = None) -> RiskSummary:
        """
        Calculate comprehensive risk assessment for a patient case.

        Args:
            factors: Extracted risk factors from HPI
            demographics: Patient demographics
            mode: "model_based" (pooled evidence) or "literature_live" (real-time)
            context_label: Specific clinical context
            session_id: Session identifier for audit

        Returns:
            Complete risk summary with all assessed outcomes
        """

        if not session_id:
            session_id = f"risk_{datetime.now().isoformat()}"

        # Determine clinical context
        if not context_label:
            context_label = self._determine_context(demographics, factors)

        # Get all assessable outcomes
        outcome_tokens = self._get_assessable_outcomes()

        # Calculate risks for each outcome
        risk_assessments = []
        for outcome_token in outcome_tokens:
            assessment = self._calculate_outcome_risk(
                outcome_token, factors, demographics, context_label, mode
            )
            if assessment:
                risk_assessments.append(assessment)

        # Sort by absolute risk (highest first)
        risk_assessments.sort(key=lambda x: x.adjusted_risk, reverse=True)

        # Generate summary statistics
        summary = self._generate_risk_summary(risk_assessments, factors)

        # Create final summary object
        risk_summary = RiskSummary(
            session_id=session_id,
            evidence_version=self.db.get_current_evidence_version() or "v1.0.0",
            mode=mode,
            risks=risk_assessments,
            summary=summary,
            calculated_at=datetime.now()
        )

        # Store for audit
        self._store_risk_assessment(risk_summary)

        # Log calculation
        self.db.log_action("risk_calculations", session_id, "CALCULATE", {
            "num_factors": len(factors),
            "num_outcomes": len(risk_assessments),
            "mode": mode,
            "context": context_label
        })

        return risk_summary

    def _determine_context(self, demographics: Dict[str, Any], factors: List[ExtractedFactor]) -> str:
        """Determine clinical context for baseline risk selection."""

        # Extract key context elements
        age_category = demographics.get('age_category', 'AGE_ADULT_YOUNG')
        procedure = demographics.get('procedure', 'unknown')
        urgency = demographics.get('urgency', 'ELECTIVE')

        # Map age categories
        if age_category in ['AGE_NEONATE', 'AGE_INFANT', 'AGE_1_5', 'AGE_6_12', 'AGE_13_17']:
            population = "pediatric"
        else:
            population = "adult"

        # Map procedures to contexts
        procedure_contexts = {
            'TONSILLECTOMY': 'ent',
            'ADENOIDECTOMY': 'ent',
            'MYRINGOTOMY': 'ent',
            'DENTAL': 'dental',
            'HERNIA_REPAIR': 'general'
        }

        procedure_context = procedure_contexts.get(procedure, 'general')

        # Combine context elements
        if urgency == 'EMERGENCY':
            return f"{population}_emergency"
        else:
            return f"{population}_{procedure_context}"

    def _get_assessable_outcomes(self) -> List[str]:
        """Get list of outcomes that can be assessed."""
        outcome_terms = self.ontology.get_terms_by_type("outcome")
        return [term.token for term in outcome_terms]

    def _calculate_outcome_risk(self, outcome_token: str, factors: List[ExtractedFactor],
                              demographics: Dict[str, Any], context_label: str,
                              mode: str) -> Optional[RiskAssessment]:
        """Calculate risk for a specific outcome."""

        try:
            # Get baseline risk
            baseline_result = self._get_baseline_risk(outcome_token, context_label)
            if not baseline_result:
                return None

            baseline_risk, baseline_context, baseline_citations = baseline_result

            # Calculate effect modifiers
            modifier_results = self._calculate_modifiers(outcome_token, factors, context_label, mode)

            if not modifier_results:
                # No modifiers found - return baseline only
                outcome_term = self.ontology.get_term(outcome_token)
                return RiskAssessment(
                    outcome=outcome_token,
                    outcome_label=outcome_term.plain_label if outcome_term else outcome_token,
                    category=outcome_term.category if outcome_term else "unknown",
                    baseline_risk=baseline_risk,
                    baseline_context=baseline_context,
                    adjusted_risk=baseline_risk,
                    confidence_interval=(baseline_risk * 0.8, baseline_risk * 1.2),
                    risk_ratio=1.0,
                    risk_difference=0.0,
                    evidence_grade="C",
                    k_studies=1,
                    contributing_factors=[],
                    citations=baseline_citations,
                    last_updated=datetime.now(),
                    no_evidence=True
                )

            # Apply modifiers to baseline risk
            adjusted_risk, confidence_interval, contributing_factors, all_citations = self._apply_modifiers(
                baseline_risk, modifier_results
            )

            # Combine citations
            all_citations.extend(baseline_citations)

            # Calculate summary statistics
            risk_ratio = adjusted_risk / baseline_risk if baseline_risk > 0 else 1.0
            risk_difference = adjusted_risk - baseline_risk

            # Determine overall evidence grade
            evidence_grade = self._determine_evidence_grade([baseline_result] + modifier_results)

            # Count total studies
            k_studies = 1 + sum(len(mod.get('studies', [])) for mod in modifier_results)

            outcome_term = self.ontology.get_term(outcome_token)

            return RiskAssessment(
                outcome=outcome_token,
                outcome_label=outcome_term.plain_label if outcome_term else outcome_token,
                category=outcome_term.category if outcome_term else "unknown",
                baseline_risk=baseline_risk,
                baseline_context=baseline_context,
                adjusted_risk=adjusted_risk,
                confidence_interval=confidence_interval,
                risk_ratio=risk_ratio,
                risk_difference=risk_difference,
                evidence_grade=evidence_grade,
                k_studies=k_studies,
                contributing_factors=contributing_factors,
                citations=list(set(all_citations)),  # Deduplicate
                last_updated=datetime.now()
            )

        except Exception as e:
            logger.error(f"Error calculating risk for {outcome_token}: {e}")
            return None

    def _get_baseline_risk(self, outcome_token: str, context_label: str) -> Optional[Tuple[float, str, List[str]]]:
        """Get baseline risk for outcome in given context using comprehensive evidence database."""

        # Determine population from context
        population = "mixed"
        if "pediatric" in context_label.lower():
            population = "pediatric"
        elif "adult" in context_label.lower():
            population = "adult"
        elif "obstetric" in context_label.lower():
            population = "obstetric"

        # First try to get baseline from evidence_based_adjusted_risks table (most specific)
        evidence_based_query = """
            SELECT adjusted_risk, confidence_interval_lower, confidence_interval_upper,
                   studies_count, evidence_grade, adjustment_category
            FROM evidence_based_adjusted_risks
            WHERE outcome_token = ?
            AND adjustment_category = 'baseline'
            LIMIT 1
        """

        evidence_result = self.db.conn.execute(evidence_based_query, [outcome_token]).fetchone()

        if evidence_result:
            baseline_risk = evidence_result[0]
            context = f"{population}_evidence_based"

            # Validate baseline risk is reasonable
            if self.min_baseline_risk <= baseline_risk <= self.max_baseline_risk:
                return (baseline_risk, context, [])

        # Fallback: Try to get baseline from baseline_risks table
        baseline_query = """
            SELECT baseline_risk, confidence_interval_lower, confidence_interval_upper,
                   studies_count, evidence_grade, population
            FROM baseline_risks
            WHERE outcome_token = ?
            AND (population = ? OR population = 'mixed')
            ORDER BY
                CASE WHEN population = ? THEN 1 ELSE 2 END,
                CASE WHEN evidence_grade = 'A' THEN 1
                     WHEN evidence_grade = 'B' THEN 2
                     WHEN evidence_grade = 'C' THEN 3
                     ELSE 4 END,
                studies_count DESC
            LIMIT 1
        """

        baseline_result = self.db.conn.execute(baseline_query, [
            outcome_token, population, population
        ]).fetchone()

        if baseline_result:
            baseline_risk = baseline_result[0]
            context = f"{baseline_result[5] or 'mixed'}_baseline"

            # Validate baseline risk is reasonable
            if self.min_baseline_risk <= baseline_risk <= self.max_baseline_risk:
                return (baseline_risk, context, [])

        # Fallback: try less specific population
        if population != "mixed":
            fallback_result = self.db.conn.execute(baseline_query, [
                outcome_token, "mixed", "mixed"
            ]).fetchone()

            if fallback_result:
                baseline_risk = fallback_result[0]
                context = "mixed_baseline"

                if self.min_baseline_risk <= baseline_risk <= self.max_baseline_risk:
                    return (baseline_risk, context, [])

        # Final fallback: use individual estimates to calculate baseline
        individual_baseline = self._calculate_baseline_from_estimates(outcome_token, population)
        if individual_baseline:
            return individual_baseline

        # No baseline available
        logger.warning(f"No baseline risk available for {outcome_token} in context {context_label}")
        return None

    def _calculate_baseline_from_estimates(self, outcome_token: str, population: str) -> Optional[Tuple[float, str, List[str]]]:
        """Calculate baseline from individual estimates when no pooled baseline exists."""

        estimates_query = """
            SELECT estimate, pmid, n_group, n_events, quality_weight, evidence_grade
            FROM estimates
            WHERE outcome_token = ?
            AND modifier_token IS NULL
            AND measure = 'INCIDENCE'
            AND extraction_confidence >= 0.7
            ORDER BY quality_weight DESC, evidence_grade
            LIMIT 10
        """

        estimates = self.db.conn.execute(estimates_query, [outcome_token]).fetchall()

        if not estimates:
            return None

        # Simple weighted average of incidence rates
        total_weight = 0
        weighted_sum = 0
        pmids = []

        for est in estimates:
            estimate = est[0]
            pmid = est[1]
            quality_weight = est[4] or 1.0

            # Convert percentage to proportion if needed
            if estimate > 1:
                estimate = estimate / 100.0

            if self.min_baseline_risk <= estimate <= self.max_baseline_risk:
                weighted_sum += estimate * quality_weight
                total_weight += quality_weight
                pmids.append(pmid)

        if total_weight > 0:
            baseline_risk = weighted_sum / total_weight
            context = f"{population}_calculated_baseline"
            return (baseline_risk, context, pmids)

        return None

    def _generate_context_variations(self, context_label: str) -> List[str]:
        """Generate context variations for broader matching."""
        variations = []

        # Split context by underscore
        parts = context_label.split('_')

        if len(parts) >= 2:
            # Try population only
            variations.append(parts[0])

            # Try procedure only if available
            if len(parts) >= 3:
                variations.append(f"{parts[0]}_{parts[1]}")

        variations.append("general")
        return variations

    def _calculate_modifiers(self, outcome_token: str, factors: List[ExtractedFactor],
                           context_label: str, mode: str) -> List[Dict[str, Any]]:
        """Calculate effect modifiers for an outcome using comprehensive evidence database."""

        modifier_results = []

        # Determine population from context
        population = "mixed"
        if "pediatric" in context_label.lower():
            population = "pediatric"
        elif "adult" in context_label.lower():
            population = "adult"
        elif "obstetric" in context_label.lower():
            population = "obstetric"

        for factor in factors:
            if mode == "model_based":
                # Use comprehensive pooled evidence from new database
                effect_result = self._get_pooled_effect_estimate(outcome_token, factor.token, population)

                if effect_result:
                    modifier_results.append(effect_result)

            elif mode == "literature_live":
                # Real-time evidence search using evidence referencing engine
                live_result = self._get_live_evidence_comprehensive(outcome_token, factor.token)
                if live_result:
                    modifier_results.append(live_result)

        return modifier_results

    def _get_pooled_effect_estimate(self, outcome_token: str, modifier_token: str, population: str) -> Optional[Dict[str, Any]]:
        """Get pooled effect estimate from comprehensive evidence database."""

        # First try to get from evidence_based_adjusted_risks table (most specific)
        evidence_based_query = """
            SELECT adjustment_multiplier, confidence_interval_lower, confidence_interval_upper,
                   studies_count, evidence_grade, adjustment_type
            FROM evidence_based_adjusted_risks
            WHERE outcome_token = ?
            AND adjustment_type = ?
            AND adjustment_category != 'baseline'
            LIMIT 1
        """

        evidence_result = self.db.conn.execute(evidence_based_query, [outcome_token, modifier_token]).fetchone()

        if evidence_result:
            or_value = evidence_result[0]
            ci_low = evidence_result[1] if evidence_result[1] is not None else or_value * 0.8
            ci_high = evidence_result[2] if evidence_result[2] is not None else or_value * 1.2
            n_studies = evidence_result[3] or 1
            evidence_grade = evidence_result[4] or 'C'

            # Validate OR is reasonable
            if self.min_or <= or_value <= self.max_or:
                return {
                    'or_value': or_value,
                    'ci_low': ci_low,
                    'ci_high': ci_high,
                    'n_studies': n_studies,
                    'evidence_grade': evidence_grade,
                    'pmids': [],
                    'heterogeneity_i2': 0.0,
                    'factor': modifier_token,
                    'factor_label': modifier_token,
                    'factor_type': 'evidence_based_adjustment'
                }

        # Fallback: Query risk modifiers table for this outcome-modifier combination
        effect_query = """
            SELECT effect_estimate, confidence_interval_lower, confidence_interval_upper,
                   studies_count, evidence_grade
            FROM risk_modifiers
            WHERE outcome_token = ?
            AND modifier_token = ?
            ORDER BY
                CASE WHEN evidence_grade = 'A' THEN 1
                     WHEN evidence_grade = 'B' THEN 2
                     WHEN evidence_grade = 'C' THEN 3
                     ELSE 4 END,
                studies_count DESC
            LIMIT 1
        """

        effect_result = self.db.conn.execute(effect_query, [outcome_token, modifier_token]).fetchone()

        if effect_result:
            or_value = effect_result[0]
            ci_low = effect_result[1] if effect_result[1] is not None else or_value * 0.8
            ci_high = effect_result[2] if effect_result[2] is not None else or_value * 1.2
            n_studies = effect_result[3] or 1
            evidence_grade = effect_result[4] or 'C'

            # Validate OR is reasonable
            if self.min_or <= or_value <= self.max_or:
                # Get factor label from ontology
                factor_term = self.ontology.get_term(modifier_token)
                factor_label = factor_term.plain_label if factor_term else modifier_token

                return {
                    'or_value': or_value,
                    'ci_low': ci_low,
                    'ci_high': ci_high,
                    'n_studies': n_studies,
                    'evidence_grade': evidence_grade,
                    'pmids': [],
                    'heterogeneity_i2': 0.0,
                    'factor': modifier_token,
                    'factor_label': factor_label,
                    'factor_type': 'risk_modifier'
                }

        # Fallback: try to get individual estimates and calculate on-the-fly
        individual_result = self._calculate_effect_from_estimates(outcome_token, modifier_token, population)
        if individual_result:
            return individual_result

        return None

    def _calculate_effect_from_estimates(self, outcome_token: str, modifier_token: str, population: str) -> Optional[Dict[str, Any]]:
        """Calculate effect estimate from individual studies when no pooled estimate exists."""

        estimates_query = """
            SELECT estimate, ci_low, ci_high, pmid, quality_weight, evidence_grade,
                   adjusted, n_group, extraction_confidence
            FROM estimates
            WHERE outcome_token = ?
            AND modifier_token = ?
            AND measure IN ('OR', 'RR', 'HR')
            AND extraction_confidence >= 0.6
            ORDER BY quality_weight DESC, evidence_grade, extraction_confidence DESC
            LIMIT 10
        """

        estimates = self.db.conn.execute(estimates_query, [outcome_token, modifier_token]).fetchall()

        if not estimates:
            return None

        if len(estimates) == 1:
            # Single estimate
            est = estimates[0]
            or_value = est[0]
            ci_low = est[1]
            ci_high = est[2]
            pmid = est[3]
            evidence_grade = est[5]

            if self.min_or <= or_value <= self.max_or:
                factor_term = self.ontology.terms.get(modifier_token)
                factor_label = factor_term.plain_label if factor_term else modifier_token

                return {
                    'factor': modifier_token,
                    'factor_label': factor_label,
                    'or': or_value,
                    'ci': (ci_low, ci_high) if ci_low and ci_high else None,
                    'evidence_grade': evidence_grade,
                    'k_studies': 1,
                    'total_n': est[7],
                    'pmids': [pmid],
                    'heterogeneity_i2': None,
                    'population': population,
                    'method': 'single_estimate'
                }

        else:
            # Multiple estimates - simple meta-analysis
            valid_estimates = []
            pmids = []
            evidence_grades = []

            for est in estimates:
                or_value = est[0]
                pmid = est[3]
                quality_weight = est[4] or 1.0
                evidence_grade = est[5]

                if self.min_or <= or_value <= self.max_or:
                    log_or = math.log(or_value)
                    valid_estimates.append((log_or, quality_weight))
                    pmids.append(pmid)
                    evidence_grades.append(evidence_grade)

            if len(valid_estimates) >= 2:
                # Weighted average in log space
                total_weight = sum(w for _, w in valid_estimates)
                weighted_log_or = sum(log_or * w for log_or, w in valid_estimates) / total_weight
                pooled_or = math.exp(weighted_log_or)

                # Simple CI estimation
                se_log_or = math.sqrt(1 / total_weight)  # Simplified SE
                ci_low = math.exp(weighted_log_or - 1.96 * se_log_or)
                ci_high = math.exp(weighted_log_or + 1.96 * se_log_or)

                # Best evidence grade with fallback
                grade_order = {"A": 4, "B": 3, "C": 2, "D": 1}
                if evidence_grades:
                    best_grade = max(evidence_grades, key=lambda g: grade_order.get(g, 1))
                else:
                    best_grade = "D"  # Default to lowest grade if no evidence

                factor_term = self.ontology.terms.get(modifier_token)
                factor_label = factor_term.plain_label if factor_term else modifier_token

                return {
                    'factor': modifier_token,
                    'factor_label': factor_label,
                    'or': pooled_or,
                    'ci': (ci_low, ci_high),
                    'evidence_grade': best_grade,
                    'k_studies': len(valid_estimates),
                    'total_n': None,
                    'pmids': pmids,
                    'heterogeneity_i2': None,  # Would need proper calculation
                    'population': population,
                    'method': 'calculated_meta'
                }

        return None

    def _get_live_evidence_comprehensive(self, outcome_token: str, modifier_token: str) -> Optional[Dict[str, Any]]:
        """Get live evidence using comprehensive evidence referencing system."""

        # Get evidence summary from referencing engine
        evidence_summary = self.evidence_engine.get_outcome_evidence_summary(
            outcome_token, modifier_token
        )

        if evidence_summary and evidence_summary.pooled_estimate:
            factor_term = self.ontology.terms.get(modifier_token)
            factor_label = factor_term.plain_label if factor_term else modifier_token

            return {
                'factor': modifier_token,
                'factor_label': factor_label,
                'or': evidence_summary.pooled_estimate,
                'ci': (evidence_summary.ci_low, evidence_summary.ci_high),
                'evidence_grade': evidence_summary.evidence_grade,
                'k_studies': evidence_summary.n_studies,
                'total_n': evidence_summary.total_n,
                'pmids': [c.pmid for c in evidence_summary.contributing_citations],
                'heterogeneity_i2': evidence_summary.heterogeneity_i2,
                'population': 'mixed',
                'method': 'live_comprehensive'
            }

        return None

    def _apply_modifiers(self, baseline_risk: float, modifier_results: List[Dict[str, Any]]) -> Tuple[float, Tuple[float, float], List[Dict[str, Any]], List[str]]:
        """Apply effect modifiers to baseline risk using odds multiplication."""

        # Convert baseline risk to odds
        baseline_odds = baseline_risk / (1 - baseline_risk) if baseline_risk < 1 else baseline_risk / 0.01

        # Apply each modifier
        combined_or = 1.0
        log_or_variance = 0.0
        contributing_factors = []
        all_citations = []

        for modifier in modifier_results:
            # Handle both field name formats for compatibility
            or_value = modifier.get('or') or modifier.get('or_value')
            or_ci = modifier.get('ci') or (modifier.get('ci_low'), modifier.get('ci_high'))

            # Validate we have a numeric OR value
            if or_value is None or not isinstance(or_value, (int, float)):
                logger.warning(f"Invalid OR value for modifier {modifier}: {or_value}")
                continue

            # Validate OR
            if self.min_or <= or_value <= self.max_or:
                combined_or *= or_value

                # Estimate log OR variance from CI
                if or_ci and len(or_ci) == 2 and or_ci[0] > 0 and or_ci[1] > 0:
                    log_or_low = math.log(or_ci[0])
                    log_or_high = math.log(or_ci[1])
                    se_log_or = (log_or_high - log_or_low) / (2 * 1.96)
                    log_or_variance += se_log_or ** 2

                # Add to contributing factors
                contributing_factors.append({
                    'factor': modifier['factor'],
                    'factor_label': modifier.get('factor_label', modifier['factor']),
                    'or': or_value,
                    'ci': or_ci,
                    'evidence_grade': modifier.get('evidence_grade', 'C')
                })

                # Collect citations
                if 'pmids' in modifier:
                    all_citations.extend(modifier['pmids'])

        # Calculate adjusted risk
        adjusted_odds = baseline_odds * combined_or
        adjusted_risk = adjusted_odds / (1 + adjusted_odds)

        # Ensure reasonable bounds
        adjusted_risk = max(self.min_baseline_risk, min(adjusted_risk, self.max_baseline_risk))

        # Calculate confidence interval for adjusted risk
        if log_or_variance > 0:
            # Propagate uncertainty
            log_combined_or = math.log(combined_or)
            se_combined = math.sqrt(log_or_variance)

            # CI for combined OR
            ci_or_low = math.exp(log_combined_or - 1.96 * se_combined)
            ci_or_high = math.exp(log_combined_or + 1.96 * se_combined)

            # Apply to baseline odds
            ci_odds_low = baseline_odds * ci_or_low
            ci_odds_high = baseline_odds * ci_or_high

            # Convert back to risk
            ci_risk_low = ci_odds_low / (1 + ci_odds_low)
            ci_risk_high = ci_odds_high / (1 + ci_odds_high)

            confidence_interval = (
                max(self.min_baseline_risk, ci_risk_low),
                min(self.max_baseline_risk, ci_risk_high)
            )
        else:
            # Default uncertainty
            confidence_interval = (
                max(self.min_baseline_risk, adjusted_risk * 0.7),
                min(self.max_baseline_risk, adjusted_risk * 1.3)
            )

        return adjusted_risk, confidence_interval, contributing_factors, all_citations

    def _get_live_evidence(self, outcome_token: str, modifier_token: str) -> Optional[Dict[str, Any]]:
        """Get real-time evidence from literature (placeholder for demo)."""
        # This would integrate with the PubMed harvester for real-time searches
        # For now, return None to indicate no live evidence available
        return None

    def _extract_evidence_grade(self, quality_summary: Dict[str, Any]) -> str:
        """Extract overall evidence grade from quality summary."""
        if not quality_summary:
            return "D"

        grade_counts = quality_summary.get('grade_distribution', {})
        if not grade_counts:
            return "D"

        # Return highest grade with significant representation
        for grade in ['A', 'B', 'C', 'D']:
            if grade_counts.get(grade, 0) >= 2:  # At least 2 studies
                return grade

        # Return most common grade with fallback
        if grade_counts:
            return max(grade_counts.items(), key=lambda x: x[1])[0]
        else:
            return "D"  # Default to lowest grade if no evidence

    def _determine_evidence_grade(self, all_results: List[Any]) -> str:
        """Determine overall evidence grade for an assessment."""
        grades = []

        for result in all_results:
            if isinstance(result, tuple):  # Baseline result
                grades.append("C")  # Default for baselines
            elif isinstance(result, dict):  # Modifier result
                grades.append(result.get('evidence_grade', 'D'))

        if not grades:
            return "D"

        # Return best grade if multiple A/B grades
        grade_counts = {}
        for grade in grades:
            grade_counts[grade] = grade_counts.get(grade, 0) + 1

        for grade in ['A', 'B', 'C', 'D']:
            if grade_counts.get(grade, 0) > 0:
                return grade

        return "D"

    def _generate_risk_summary(self, risk_assessments: List[RiskAssessment],
                             factors: List[ExtractedFactor]) -> Dict[str, Any]:
        """Generate summary statistics for risk assessment."""

        if not risk_assessments:
            return {
                "highest_absolute_risks": [],
                "biggest_risk_increases": [],
                "total_outcomes_assessed": 0,
                "outcomes_with_evidence": 0,
                "overall_risk_score": "unknown"
            }

        # Top absolute risks
        highest_absolute = sorted(risk_assessments, key=lambda x: x.adjusted_risk, reverse=True)[:5]
        highest_absolute_risks = [
            {
                "outcome": r.outcome,
                "outcome_label": r.outcome_label,
                "risk": r.adjusted_risk,
                "label": f"{r.adjusted_risk:.1%} risk of {r.outcome_label.lower()}"
            }
            for r in highest_absolute
        ]

        # Biggest increases from baseline
        biggest_increases = sorted(
            [r for r in risk_assessments if r.risk_ratio > 1.1],
            key=lambda x: x.risk_ratio, reverse=True
        )[:5]

        biggest_risk_increases = [
            {
                "outcome": r.outcome,
                "outcome_label": r.outcome_label,
                "increase": f"{r.risk_ratio:.1f}x above baseline",
                "absolute_increase": r.risk_difference
            }
            for r in biggest_increases
        ]

        # Evidence quality metrics
        outcomes_with_evidence = len([r for r in risk_assessments if not r.no_evidence])

        # Overall risk score
        max_risk = max(r.adjusted_risk for r in risk_assessments) if risk_assessments else 0
        if max_risk > 0.10:
            overall_risk_score = "high"
        elif max_risk > 0.05:
            overall_risk_score = "moderate"
        elif max_risk > 0.01:
            overall_risk_score = "low"
        else:
            overall_risk_score = "minimal"

        return {
            "highest_absolute_risks": highest_absolute_risks,
            "biggest_risk_increases": biggest_risk_increases,
            "total_outcomes_assessed": len(risk_assessments),
            "outcomes_with_evidence": outcomes_with_evidence,
            "overall_risk_score": overall_risk_score,
            "max_absolute_risk": max_risk,
            "total_risk_factors": len(factors)
        }

    def _store_risk_assessment(self, risk_summary: RiskSummary):
        """Store risk assessment for audit trail."""
        try:
            # Convert risks to dict format with datetime serialization
            risks_data = []
            for risk in risk_summary.risks:
                risk_dict = asdict(risk)
                # Convert datetime field to string
                if 'last_updated' in risk_dict and risk_dict['last_updated'] is not None:
                    risk_dict['last_updated'] = risk_dict['last_updated'].isoformat()
                risks_data.append(risk_dict)

            # Update case session with risk scores
            risk_data = {
                "risks": risks_data,
                "summary": risk_summary.summary,
                "mode": risk_summary.mode,
                "evidence_version": risk_summary.evidence_version,
                "calculated_at": risk_summary.calculated_at.isoformat()
            }

            self.db.conn.execute("""
                UPDATE case_sessions
                SET risk_scores = ?
                WHERE session_id = ?
            """, [json.dumps(risk_data), risk_summary.session_id])

        except Exception as e:
            logger.error(f"Error storing risk assessment {risk_summary.session_id}: {e}")

    def get_outcome_evidence(self, outcome_token: str, modifier_tokens: List[str] = None,
                           context_label: str = None) -> Dict[str, Any]:
        """Get detailed evidence for a specific outcome."""

        evidence = {
            "outcome": outcome_token,
            "baseline_evidence": None,
            "modifier_evidence": {},
            "guidelines": [],
            "last_updated": datetime.now().isoformat()
        }

        # Get baseline evidence
        baseline = self.pooling_engine.get_pooled_baseline(outcome_token, context_label or "general")
        if baseline:
            evidence["baseline_evidence"] = {
                "k_studies": baseline.k,
                "pooled_risk": baseline.p0_mean,
                "confidence_interval": [baseline.p0_ci_low, baseline.p0_ci_high],
                "i_squared": baseline.i_squared,
                "method": baseline.method,
                "pmids": baseline.pmids
            }

        # Get modifier evidence
        if modifier_tokens:
            for modifier_token in modifier_tokens:
                effect = self.pooling_engine.get_pooled_effect(
                    outcome_token, modifier_token, context_label or "general"
                )
                if effect:
                    evidence["modifier_evidence"][modifier_token] = {
                        "k_studies": effect.k,
                        "pooled_or": effect.or_mean,
                        "confidence_interval": [effect.or_ci_low, effect.or_ci_high],
                        "i_squared": effect.i_squared,
                        "method": effect.method,
                        "pmids": effect.pmids
                    }

        # Get guidelines (placeholder - would query guidelines table)
        # evidence["guidelines"] = self._get_guidelines(outcome_token)

        return evidence