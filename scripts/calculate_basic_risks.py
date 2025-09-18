#!/usr/bin/env python3
"""
Basic Risk Calculation for CODEX v2

Creates baseline risk calculations from harvested evidence data.
Works with the actual database schema and focuses on getting the system working.

Usage:
    python scripts/calculate_basic_risks.py
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

class BasicRiskCalculator:
    """Basic risk calculator to get the system working"""

    def __init__(self, db_path: str = "database/codex.duckdb"):
        self.db_path = db_path
        self.db = init_database(db_path)
        logger.info(f"Initialized BasicRiskCalculator with database: {db_path}")

    def normalize_outcome_temporal(self, outcome_token: str, estimate: float) -> float:
        """Normalize outcome estimates to 30-day standard timeframe"""

        # Temporal conversion factors based on clinical evidence
        # These convert shorter timeframes to approximate 30-day risk
        temporal_factors = {
            # Mortality timeframes
            'MORTALITY_24H': 1.5,    # 24h mortality is typically ~67% of 30-day
            'MORTALITY_7D': 1.2,     # 7-day mortality is typically ~83% of 30-day
            'MORTALITY_30D': 1.0,    # Already 30-day standard
            'MORTALITY_90D': 0.9,    # 90-day mortality higher, adjust down to 30-day

            # Cardiac events (typically occur early)
            'CARDIAC_ARREST': 1.1,   # Most occur within first few days
            'CARDIOGENIC_SHOCK': 1.2, # Often early complication

            # Other complications (vary by timing)
            'ASPIRATION': 1.0,       # Usually immediate/early
            'BRONCHOSPASM': 1.0,     # Usually immediate
            'FAILED_INTUBATION': 1.0, # Immediate event
            'AMNIOTIC_FLUID_EMBOLISM': 1.0, # Immediate event

            # Default for unspecified outcomes
            'DEFAULT': 1.0
        }

        # Apply temporal normalization
        factor = temporal_factors.get(outcome_token, temporal_factors['DEFAULT'])

        # For very small estimates, be more conservative with adjustment
        if estimate < 0.001:  # < 0.1%
            factor = min(factor, 1.1)  # Limit adjustment for rare events

        return estimate * factor

    def calculate_pooled_estimate(self, estimates: List[float], weights: List[float]) -> Dict:
        """Calculate simple pooled estimate using inverse variance weighting"""
        if not estimates or not weights:
            return None

        # Calculate weighted average
        total_weight = sum(weights)
        if total_weight == 0:
            return None

        pooled_estimate = sum(est * weight for est, weight in zip(estimates, weights)) / total_weight

        # Simple standard error approximation
        pooled_se = 1.0 / math.sqrt(total_weight) if total_weight > 0 else 1.0

        # Confidence interval
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

    def create_baseline_risks(self):
        """Create baseline risk estimates for all outcomes"""
        logger.info("Creating baseline risk estimates")

        # Get all unique outcomes with baseline evidence (no modifier)
        query = """
            SELECT DISTINCT outcome_token
            FROM estimates e
            LEFT JOIN papers p ON e.pmid = p.pmid
            WHERE e.estimate IS NOT NULL
            AND (e.modifier_token IS NULL OR e.modifier_token = '')
        """

        outcomes = self.db.conn.execute(query).fetchall()
        logger.info(f"Found {len(outcomes)} unique outcomes")

        baseline_risks = {}

        for (outcome_token,) in outcomes:
            try:
                # Get all baseline estimates for this outcome
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
                    estimates = []
                    weights = []

                    for est, quality_weight, evidence_grade, n_group, pub_year in evidence:
                        # Apply temporal outcome normalization
                        normalized_est = self.normalize_outcome_temporal(outcome_token, est)
                        estimates.append(normalized_est)

                        # Calculate weight based on quality and sample size
                        weight = quality_weight or 1.0

                        # Add evidence grade weight
                        grade_weights = {'A': 4.0, 'B': 3.0, 'C': 2.0, 'D': 1.0}
                        weight *= grade_weights.get(evidence_grade, 1.0)

                        # Add sample size weight if available
                        if n_group and n_group > 0:
                            weight *= min(math.sqrt(n_group), 10.0)  # Cap at 10x weight

                        # Add temporal weighting - favor recent publications
                        if pub_year and pub_year > 0:
                            current_year = datetime.now().year
                            years_old = current_year - pub_year

                            # Exponential decay: recent papers get higher weight
                            # Half-life of 10 years, minimum weight of 0.1
                            temporal_weight = max(0.1, math.exp(-0.0693 * years_old / 10))
                            weight *= temporal_weight

                        weights.append(weight)

                    # Calculate pooled estimate
                    pooled_result = self.calculate_pooled_estimate(estimates, weights)

                    if pooled_result:
                        baseline_risks[outcome_token] = {
                            'outcome_token': outcome_token,
                            'risk_type': 'baseline',
                            **pooled_result
                        }

                        logger.info(f"Calculated baseline risk for {outcome_token}: "
                                  f"{pooled_result['estimate']:.6f} ({pooled_result['studies_count']} studies)")

            except Exception as e:
                logger.error(f"Failed to calculate baseline risk for {outcome_token}: {e}")
                continue

        return baseline_risks

    def create_modifier_effects(self):
        """Create modifier effect estimates"""
        logger.info("Creating modifier effect estimates")

        # Get all unique outcome-modifier combinations
        query = """
            SELECT DISTINCT outcome_token, modifier_token
            FROM estimates e
            WHERE e.estimate IS NOT NULL
            AND e.modifier_token IS NOT NULL
            AND e.modifier_token != ''
        """

        combinations = self.db.conn.execute(query).fetchall()
        logger.info(f"Found {len(combinations)} outcome-modifier combinations")

        modifier_effects = {}

        for outcome_token, modifier_token in combinations:
            try:
                # Get all estimates for this combination
                evidence_query = """
                    SELECT e.estimate, e.quality_weight, e.evidence_grade, e.n_group, p.year
                    FROM estimates e
                    LEFT JOIN papers p ON e.pmid = p.pmid
                    WHERE e.outcome_token = ?
                    AND e.modifier_token = ?
                    AND e.estimate IS NOT NULL
                """

                evidence = self.db.conn.execute(evidence_query, [outcome_token, modifier_token]).fetchall()

                if evidence:
                    estimates = []
                    weights = []

                    for est, quality_weight, evidence_grade, n_group, pub_year in evidence:
                        # Apply temporal outcome normalization
                        normalized_est = self.normalize_outcome_temporal(outcome_token, est)
                        estimates.append(normalized_est)

                        # Calculate weight
                        weight = quality_weight or 1.0
                        grade_weights = {'A': 4.0, 'B': 3.0, 'C': 2.0, 'D': 1.0}
                        weight *= grade_weights.get(evidence_grade, 1.0)

                        if n_group and n_group > 0:
                            weight *= min(math.sqrt(n_group), 10.0)

                        # Add temporal weighting - favor recent publications
                        if pub_year and pub_year > 0:
                            current_year = datetime.now().year
                            years_old = current_year - pub_year

                            # Exponential decay: recent papers get higher weight
                            # Half-life of 10 years, minimum weight of 0.1
                            temporal_weight = max(0.1, math.exp(-0.0693 * years_old / 10))
                            weight *= temporal_weight

                        weights.append(weight)

                    # Calculate pooled estimate
                    pooled_result = self.calculate_pooled_estimate(estimates, weights)

                    if pooled_result:
                        key = f"{outcome_token}_{modifier_token}"
                        modifier_effects[key] = {
                            'outcome_token': outcome_token,
                            'modifier_token': modifier_token,
                            'effect_type': 'modifier',
                            **pooled_result
                        }

                        logger.info(f"Calculated modifier effect for {outcome_token}+{modifier_token}: "
                                  f"{pooled_result['estimate']:.6f} ({pooled_result['studies_count']} studies)")

            except Exception as e:
                logger.error(f"Failed to calculate modifier effect for {outcome_token}+{modifier_token}: {e}")
                continue

        return modifier_effects

    def store_risk_calculations(self, baseline_risks: Dict, modifier_effects: Dict):
        """Store calculated risks in simplified baseline_risks table"""
        logger.info("Storing risk calculations in database")

        try:
            # Create simplified baseline_risks table
            self.db.conn.execute("""
                CREATE TABLE IF NOT EXISTS baseline_risks (
                    outcome_token TEXT PRIMARY KEY,
                    baseline_risk REAL NOT NULL,
                    confidence_interval_lower REAL,
                    confidence_interval_upper REAL,
                    evidence_grade TEXT,
                    studies_count INTEGER,
                    last_updated TEXT,
                    population TEXT DEFAULT 'mixed'
                )
            """)

            # Create risk_modifiers table
            self.db.conn.execute("""
                CREATE TABLE IF NOT EXISTS risk_modifiers (
                    id TEXT PRIMARY KEY,
                    outcome_token TEXT NOT NULL,
                    modifier_token TEXT NOT NULL,
                    effect_estimate REAL NOT NULL,
                    confidence_interval_lower REAL,
                    confidence_interval_upper REAL,
                    evidence_grade TEXT,
                    studies_count INTEGER,
                    last_updated TEXT
                )
            """)

            # Store baseline risks
            for outcome_token, risk_data in baseline_risks.items():
                self.db.conn.execute("""
                    INSERT OR REPLACE INTO baseline_risks
                    VALUES (?, ?, ?, ?, 'B', ?, ?, 'mixed')
                """, [
                    outcome_token,
                    risk_data['estimate'],
                    risk_data['ci_lower'],
                    risk_data['ci_upper'],
                    risk_data['studies_count'],
                    datetime.now().isoformat()
                ])

            # Store modifier effects
            for key, effect_data in modifier_effects.items():
                modifier_id = f"{effect_data['outcome_token']}_{effect_data['modifier_token']}"
                self.db.conn.execute("""
                    INSERT OR REPLACE INTO risk_modifiers
                    VALUES (?, ?, ?, ?, ?, ?, 'B', ?, ?)
                """, [
                    modifier_id,
                    effect_data['outcome_token'],
                    effect_data['modifier_token'],
                    effect_data['estimate'],
                    effect_data['ci_lower'],
                    effect_data['ci_upper'],
                    effect_data['studies_count'],
                    datetime.now().isoformat()
                ])

            self.db.conn.commit()
            logger.info(f"Stored {len(baseline_risks)} baseline risks and {len(modifier_effects)} modifier effects")

        except Exception as e:
            logger.error(f"Failed to store risk calculations: {e}")
            raise

    def generate_summary_report(self, baseline_risks: Dict, modifier_effects: Dict):
        """Generate summary report"""

        total_calculations = len(baseline_risks) + len(modifier_effects)

        report = {
            'calculation_summary': {
                'timestamp': datetime.now().isoformat(),
                'total_calculations': total_calculations,
                'baseline_risks': len(baseline_risks),
                'modifier_effects': len(modifier_effects),
                'database_path': self.db_path
            },
            'baseline_risk_examples': dict(list(baseline_risks.items())[:5]),
            'modifier_effect_examples': dict(list(modifier_effects.items())[:5])
        }

        # Save report
        report_path = f"basic_risk_calculation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info(f"Report saved: {report_path}")
        return report_path

def main():
    parser = argparse.ArgumentParser(description='Calculate Basic Risk Scores')
    parser.add_argument('--db-path', default='database/codex.duckdb', help='Database path')
    args = parser.parse_args()

    try:
        # Initialize calculator
        calculator = BasicRiskCalculator(db_path=args.db_path)

        logger.info("Starting basic risk score calculation")

        # Calculate baseline risks
        baseline_risks = calculator.create_baseline_risks()

        # Calculate modifier effects
        modifier_effects = calculator.create_modifier_effects()

        # Store results
        calculator.store_risk_calculations(baseline_risks, modifier_effects)

        # Generate report
        report_path = calculator.generate_summary_report(baseline_risks, modifier_effects)

        print("\n" + "="*60)
        print("BASIC RISK CALCULATION COMPLETED")
        print("="*60)
        print(f"Baseline risks calculated: {len(baseline_risks)}")
        print(f"Modifier effects calculated: {len(modifier_effects)}")
        print(f"Total calculations: {len(baseline_risks) + len(modifier_effects)}")
        print(f"Report saved: {report_path}")
        print(f"Database: {args.db_path}")
        print("="*60)

        return 0

    except Exception as e:
        logger.error(f"Risk calculation failed: {e}")
        print(f"\nRisk calculation failed: {e}")
        return 1

if __name__ == "__main__":
    exit(main())