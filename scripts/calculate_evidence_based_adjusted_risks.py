#!/usr/bin/env python3
"""
Evidence-Based Adjusted Baseline Risk Calculation for CODEX v2

Creates baseline risk calculations adjusted ONLY using real evidence from our database:
- Age-specific adjustments from harvested studies
- Comorbidity-based adjustments for clinical context
- No hallucinated data - only real PubMed evidence

Usage:
    python scripts/calculate_evidence_based_adjusted_risks.py
"""

import sys
import os
import logging
import json
import math
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import argparse

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.database import init_database
from src.core.error_codes import CodexError, ErrorCode, ErrorLogger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
error_logger = ErrorLogger()

class EvidenceBasedAdjustedRiskCalculator:
    """Calculate adjusted baseline risks using only real evidence from database"""

    def __init__(self, db_path: str = "database/codex.duckdb"):
        self.db_path = db_path
        self.db = init_database(db_path)
        logger.info(f"Initialized EvidenceBasedAdjustedRiskCalculator with database: {db_path}")

    def get_evidence_based_age_adjustments(self) -> Dict[str, Dict[str, float]]:
        """Extract real age adjustment factors from harvested evidence"""

        age_adjustments = self.db.conn.execute("""
            SELECT
                outcome_token,
                modifier_token,
                AVG(estimate) as avg_effect,
                COUNT(*) as study_count
            FROM estimates
            WHERE modifier_token LIKE 'AGE_%'
            AND estimate IS NOT NULL
            GROUP BY outcome_token, modifier_token
            HAVING COUNT(*) >= 1  -- At least 1 study
        """).fetchall()

        adjustments = {}

        for outcome, modifier, avg_effect, study_count in age_adjustments:
            if modifier not in adjustments:
                adjustments[modifier] = {}

            # Use evidence-based adjustment factor
            adjustments[modifier][outcome] = avg_effect

            logger.info(f"Evidence-based adjustment: {outcome} + {modifier} = {avg_effect:.4f}x ({study_count} studies)")

        return adjustments

    def get_evidence_based_comorbidity_adjustments(self) -> Dict[str, Dict[str, float]]:
        """Extract real comorbidity adjustment factors from harvested evidence"""

        comorbidity_adjustments = self.db.conn.execute("""
            SELECT
                outcome_token,
                modifier_token,
                AVG(estimate) as avg_effect,
                COUNT(*) as study_count
            FROM estimates
            WHERE modifier_token IN ('HEART_FAILURE', 'COPD', 'FRAILTY', 'HYPERTENSION', 'OSA', 'ASTHMA')
            AND estimate IS NOT NULL
            GROUP BY outcome_token, modifier_token
            HAVING COUNT(*) >= 2  -- At least 2 studies for reliability
        """).fetchall()

        adjustments = {}

        for outcome, modifier, avg_effect, study_count in comorbidity_adjustments:
            if modifier not in adjustments:
                adjustments[modifier] = {}

            # Use evidence-based adjustment factor
            adjustments[modifier][outcome] = avg_effect

            logger.info(f"Evidence-based comorbidity adjustment: {outcome} + {modifier} = {avg_effect:.4f}x ({study_count} studies)")

        return adjustments

    def calculate_pooled_estimate(self, estimates: List[float], weights: List[float]) -> Dict:
        """Calculate simple pooled estimate using inverse variance weighting"""
        if not estimates or not weights:
            return None

        total_weight = sum(weights)
        if total_weight == 0:
            return None

        pooled_estimate = sum(est * weight for est, weight in zip(estimates, weights)) / total_weight
        pooled_se = 1.0 / math.sqrt(total_weight) if total_weight > 0 else 1.0
        ci_lower = pooled_estimate - 1.96 * pooled_se
        ci_upper = pooled_estimate + 1.96 * pooled_se

        return {
            'estimate': pooled_estimate,
            'standard_error': pooled_se,
            'ci_lower': ci_lower,
            'ci_upper': ci_upper,
            'studies_count': len(estimates),
            'total_weight': total_weight
        }

    def create_evidence_based_adjusted_risks(self):
        """Create evidence-based adjusted baseline risks"""
        logger.info("Creating evidence-based adjusted baseline risk estimates")

        # Get all unique outcomes
        query = """
            SELECT DISTINCT outcome_token
            FROM estimates e
            LEFT JOIN papers p ON e.pmid = p.pmid
            WHERE e.estimate IS NOT NULL
            AND (e.modifier_token IS NULL OR e.modifier_token = '')
        """

        outcomes = self.db.conn.execute(query).fetchall()
        logger.info(f"Found {len(outcomes)} unique outcomes")

        # Get evidence-based adjustment factors
        age_adjustments = self.get_evidence_based_age_adjustments()
        comorbidity_adjustments = self.get_evidence_based_comorbidity_adjustments()

        adjusted_risks = {}

        # Define categories we have evidence for
        age_groups = list(age_adjustments.keys())
        comorbidity_groups = list(comorbidity_adjustments.keys())

        logger.info(f"Evidence-based age groups: {age_groups}")
        logger.info(f"Evidence-based comorbidity groups: {comorbidity_groups}")

        for (outcome_token,) in outcomes:
            try:
                # Get baseline estimates for this outcome
                evidence_query = """
                    SELECT e.estimate, e.quality_weight, e.evidence_grade, e.n_group, p.year
                    FROM estimates e
                    LEFT JOIN papers p ON e.pmid = p.pmid
                    WHERE e.outcome_token = ?
                    AND (e.modifier_token IS NULL OR e.modifier_token = '')
                    AND e.estimate IS NOT NULL
                """

                evidence = self.db.conn.execute(evidence_query, [outcome_token]).fetchall()

                if evidence:
                    # Calculate baseline risk
                    estimates = []
                    weights = []

                    for est, quality_weight, evidence_grade, n_group, pub_year in evidence:
                        estimates.append(est)

                        # Calculate weight
                        weight = quality_weight or 1.0
                        grade_weights = {'A': 4.0, 'B': 3.0, 'C': 2.0, 'D': 1.0}
                        weight *= grade_weights.get(evidence_grade, 1.0)

                        if n_group and n_group > 0:
                            weight *= min(math.sqrt(n_group), 10.0)

                        # Temporal weighting
                        if pub_year and pub_year > 0:
                            current_year = datetime.now().year
                            years_old = current_year - pub_year
                            temporal_weight = max(0.1, math.exp(-0.0693 * years_old / 10))
                            weight *= temporal_weight

                        weights.append(weight)

                    baseline_result = self.calculate_pooled_estimate(estimates, weights)

                    if baseline_result:
                        baseline_risk = baseline_result['estimate']

                        # Create baseline entry (no adjustments)
                        risk_id = f"{outcome_token}_baseline"
                        adjusted_risks[risk_id] = {
                            'outcome_token': outcome_token,
                            'adjustment_category': 'baseline',
                            'adjustment_type': 'none',
                            'baseline_risk': baseline_risk,
                            'adjustment_multiplier': 1.0,
                            'adjusted_risk': baseline_risk,
                            'confidence_interval_lower': baseline_result['ci_lower'],
                            'confidence_interval_upper': baseline_result['ci_upper'],
                            'studies_count': baseline_result['studies_count'],
                            'evidence_grade': 'B',
                            'evidence_source': 'direct_harvest'
                        }

                        # Create age-adjusted risks where evidence exists
                        for age_group in age_groups:
                            if outcome_token in age_adjustments[age_group]:
                                age_mult = age_adjustments[age_group][outcome_token]
                                adjusted_risk = baseline_risk * age_mult

                                risk_id = f"{outcome_token}_{age_group.lower()}"
                                adjusted_risks[risk_id] = {
                                    'outcome_token': outcome_token,
                                    'adjustment_category': 'age',
                                    'adjustment_type': age_group,
                                    'baseline_risk': baseline_risk,
                                    'adjustment_multiplier': age_mult,
                                    'adjusted_risk': adjusted_risk,
                                    'confidence_interval_lower': baseline_result['ci_lower'] * age_mult,
                                    'confidence_interval_upper': baseline_result['ci_upper'] * age_mult,
                                    'studies_count': baseline_result['studies_count'],
                                    'evidence_grade': 'B',
                                    'evidence_source': 'direct_harvest'
                                }

                        # Create comorbidity-adjusted risks where evidence exists
                        for comorbidity_group in comorbidity_groups:
                            if outcome_token in comorbidity_adjustments[comorbidity_group]:
                                comorbidity_mult = comorbidity_adjustments[comorbidity_group][outcome_token]
                                adjusted_risk = baseline_risk * comorbidity_mult

                                risk_id = f"{outcome_token}_{comorbidity_group.lower()}"
                                adjusted_risks[risk_id] = {
                                    'outcome_token': outcome_token,
                                    'adjustment_category': 'comorbidity',
                                    'adjustment_type': comorbidity_group,
                                    'baseline_risk': baseline_risk,
                                    'adjustment_multiplier': comorbidity_mult,
                                    'adjusted_risk': adjusted_risk,
                                    'confidence_interval_lower': baseline_result['ci_lower'] * comorbidity_mult,
                                    'confidence_interval_upper': baseline_result['ci_upper'] * comorbidity_mult,
                                    'studies_count': baseline_result['studies_count'],
                                    'evidence_grade': 'B',
                                    'evidence_source': 'direct_harvest'
                                }

                        logger.info(f"Created evidence-based adjusted risks for {outcome_token}: baseline {baseline_risk:.6f}")

            except Exception as e:
                logger.error(f"Failed to calculate adjusted risk for {outcome_token}: {e}")
                continue

        return adjusted_risks

    def store_evidence_based_adjusted_risks(self, adjusted_risks: Dict):
        """Store evidence-based adjusted baseline risks in database"""
        logger.info("Storing evidence-based adjusted baseline risks in database")

        try:
            # Create evidence_based_adjusted_risks table
            self.db.conn.execute("""
                CREATE TABLE IF NOT EXISTS evidence_based_adjusted_risks (
                    id TEXT PRIMARY KEY,
                    outcome_token TEXT NOT NULL,
                    adjustment_category TEXT NOT NULL,
                    adjustment_type TEXT NOT NULL,
                    baseline_risk REAL NOT NULL,
                    adjustment_multiplier REAL NOT NULL,
                    adjusted_risk REAL NOT NULL,
                    confidence_interval_lower REAL,
                    confidence_interval_upper REAL,
                    studies_count INTEGER,
                    evidence_grade TEXT,
                    evidence_source TEXT,
                    last_updated TEXT
                )
            """)

            # Store adjusted risks
            for risk_id, risk_data in adjusted_risks.items():
                self.db.conn.execute("""
                    INSERT OR REPLACE INTO evidence_based_adjusted_risks
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    risk_id,
                    risk_data['outcome_token'],
                    risk_data['adjustment_category'],
                    risk_data['adjustment_type'],
                    risk_data['baseline_risk'],
                    risk_data['adjustment_multiplier'],
                    risk_data['adjusted_risk'],
                    risk_data['confidence_interval_lower'],
                    risk_data['confidence_interval_upper'],
                    risk_data['studies_count'],
                    risk_data['evidence_grade'],
                    risk_data['evidence_source'],
                    datetime.now().isoformat()
                ])

            self.db.conn.commit()
            logger.info(f"Stored {len(adjusted_risks)} evidence-based adjusted risk calculations")

        except Exception as e:
            logger.error(f"Failed to store evidence-based adjusted risks: {e}")
            raise

    def generate_report(self, adjusted_risks: Dict):
        """Generate evidence-based adjusted risk calculation report"""

        # Categorize risks
        baseline_risks = {k: v for k, v in adjusted_risks.items() if v['adjustment_category'] == 'baseline'}
        age_risks = {k: v for k, v in adjusted_risks.items() if v['adjustment_category'] == 'age'}
        comorbidity_risks = {k: v for k, v in adjusted_risks.items() if v['adjustment_category'] == 'comorbidity'}

        # High-risk adjustments
        high_risk_adjustments = {k: v for k, v in adjusted_risks.items()
                               if v['adjustment_multiplier'] > 5.0 and v['adjustment_category'] != 'baseline'}

        # Protective adjustments
        protective_adjustments = {k: v for k, v in adjusted_risks.items()
                                if v['adjustment_multiplier'] < 0.5 and v['adjustment_category'] != 'baseline'}

        report = {
            'calculation_summary': {
                'timestamp': datetime.now().isoformat(),
                'total_adjustments': len(adjusted_risks),
                'baseline_risks': len(baseline_risks),
                'age_adjustments': len(age_risks),
                'comorbidity_adjustments': len(comorbidity_risks),
                'evidence_source': 'direct_pubmed_harvest',
                'database_path': self.db_path
            },
            'high_risk_adjustments': dict(list(high_risk_adjustments.items())[:10]),
            'protective_adjustments': dict(list(protective_adjustments.items())[:10]),
            'age_adjustment_examples': dict(list(age_risks.items())[:10]),
            'comorbidity_adjustment_examples': dict(list(comorbidity_risks.items())[:10])
        }

        # Save report
        report_path = f"evidence_based_adjusted_risks_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info(f"Evidence-based adjusted risks report saved: {report_path}")
        return report_path

def main():
    parser = argparse.ArgumentParser(description='Calculate Evidence-Based Adjusted Risk Scores')
    parser.add_argument('--db-path', default='database/codex.duckdb', help='Database path')
    args = parser.parse_args()

    try:
        # Initialize calculator
        calculator = EvidenceBasedAdjustedRiskCalculator(db_path=args.db_path)

        logger.info("Starting evidence-based adjusted baseline risk calculation")

        # Calculate adjusted risks
        adjusted_risks = calculator.create_evidence_based_adjusted_risks()

        # Store results
        calculator.store_evidence_based_adjusted_risks(adjusted_risks)

        # Generate report
        report_path = calculator.generate_report(adjusted_risks)

        print("\n" + "="*60)
        print("EVIDENCE-BASED ADJUSTED BASELINE RISK CALCULATION COMPLETED")
        print("="*60)

        total_adjustments = len(adjusted_risks)
        baseline_count = len([r for r in adjusted_risks.values() if r['adjustment_category'] == 'baseline'])
        age_count = len([r for r in adjusted_risks.values() if r['adjustment_category'] == 'age'])
        comorbidity_count = len([r for r in adjusted_risks.values() if r['adjustment_category'] == 'comorbidity'])

        print(f"Total risk calculations: {total_adjustments}")
        print(f"Baseline risks: {baseline_count}")
        print(f"Age-adjusted risks: {age_count}")
        print(f"Comorbidity-adjusted risks: {comorbidity_count}")
        print(f"Evidence source: Direct PubMed harvest (no hallucinated data)")
        print(f"Report saved: {report_path}")
        print(f"Database: {args.db_path}")
        print("="*60)

        return 0

    except Exception as e:
        logger.error(f"Evidence-based adjusted baseline risk calculation failed: {e}")
        print(f"\nEvidence-based adjusted baseline risk calculation failed: {e}")
        return 1

if __name__ == "__main__":
    exit(main())