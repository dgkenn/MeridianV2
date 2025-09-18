#!/usr/bin/env python3
"""
Temporal-Specific Risk Calculation for CODEX v2

Creates individualized risk calculations based on clinical temporal horizons:
- Intraoperative risks (during surgery)
- Perioperative risks (30-day recovery period)

Usage:
    python scripts/calculate_temporal_risks.py
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

class TemporalRiskCalculator:
    """Temporal-specific risk calculator with multiple clinical horizons"""

    def __init__(self, db_path: str = "database/codex.duckdb"):
        self.db_path = db_path
        self.db = init_database(db_path)
        logger.info(f"Initialized TemporalRiskCalculator with database: {db_path}")

    def get_temporal_mapping(self) -> Dict[str, List[str]]:
        """Define temporal horizons for each outcome based on clinical evidence"""

        return {
            # Immediate/Intraoperative events (during surgery)
            'FAILED_INTUBATION': ['intraoperative'],
            'ASPIRATION': ['intraoperative', 'perioperative'],  # Can occur during induction or recovery
            'LARYNGOSPASM': ['intraoperative'],
            'BRONCHOSPASM': ['intraoperative', 'perioperative'],  # Can be immediate or delayed
            'AWARENESS_UNDER_ANESTHESIA': ['intraoperative'],
            'AMNIOTIC_FLUID_EMBOLISM': ['intraoperative'],

            # Cardiac events (can be immediate or early postop)
            'CARDIAC_ARREST': ['intraoperative', 'perioperative'],
            'CARDIOGENIC_SHOCK': ['intraoperative', 'perioperative'],
            'VENTRICULAR_ARRHYTHMIA': ['intraoperative', 'perioperative'],

            # Postoperative complications
            'STROKE': ['perioperative'],
            'PULMONARY_EMBOLISM': ['perioperative'],
            'ARDS': ['perioperative'],
            'SEPSIS': ['perioperative'],
            'ACUTE_KIDNEY_INJURY': ['perioperative'],
            'MULTIPLE_ORGAN_DYSFUNCTION': ['perioperative'],

            # Mortality (by temporal definition)
            'MORTALITY_24H': ['perioperative'],
            'MORTALITY_30D': ['perioperative'],
            'MORTALITY_INHOSPITAL': ['perioperative'],
        }

    def get_conversion_factors(self) -> Dict[str, Dict[str, float]]:
        """Get evidence-based conversion factors for temporal horizons"""

        return {
            'intraoperative': {
                # For intraoperative risks, adjust based on clinical evidence
                'ASPIRATION': 0.8,  # ~80% of aspiration is intraoperative
                'BRONCHOSPASM': 0.7,  # ~70% is intraoperative
                'CARDIAC_ARREST': 0.6,  # ~60% of cardiac arrests are intraoperative
                'CARDIOGENIC_SHOCK': 0.4,  # ~40% are intraoperative
                'VENTRICULAR_ARRHYTHMIA': 0.7,  # ~70% are intraoperative
                'DEFAULT': 1.0
            },
            'perioperative': {
                # For perioperative (30-day) risks - full clinical horizon
                'ASPIRATION': 1.0,  # Total risk includes intra + postop
                'BRONCHOSPASM': 1.0,  # Total risk
                'CARDIAC_ARREST': 1.0,  # Total risk
                'CARDIOGENIC_SHOCK': 1.0,  # Total risk
                'VENTRICULAR_ARRHYTHMIA': 1.0,  # Total risk
                'MORTALITY_24H': 1.5,  # Convert 24h to 30-day equivalent
                'DEFAULT': 1.0
            }
        }

    def calculate_pooled_estimate(self, estimates: List[float], weights: List[float]) -> Dict:
        """Calculate pooled estimate using inverse variance weighting"""
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

    def calculate_temporal_risks(self):
        """Calculate risks for all outcomes across temporal horizons"""
        logger.info("Starting temporal-specific risk calculation")

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

        temporal_mapping = self.get_temporal_mapping()
        conversion_factors = self.get_conversion_factors()
        temporal_risks = {}

        for (outcome_token,) in outcomes:
            try:
                # Get evidence for this outcome
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
                    # Get temporal horizons for this outcome
                    horizons = temporal_mapping.get(outcome_token, ['perioperative'])

                    for horizon in horizons:
                        estimates = []
                        weights = []

                        for est, quality_weight, evidence_grade, n_group, pub_year in evidence:
                            # Apply temporal conversion factor
                            horizon_factors = conversion_factors.get(horizon, conversion_factors['perioperative'])
                            conversion_factor = horizon_factors.get(outcome_token, horizon_factors['DEFAULT'])
                            adjusted_estimate = est * conversion_factor
                            estimates.append(adjusted_estimate)

                            # Calculate weights (quality + evidence grade + sample size + temporal)
                            weight = quality_weight or 1.0

                            # Evidence grade weighting
                            grade_weights = {'A': 4.0, 'B': 3.0, 'C': 2.0, 'D': 1.0}
                            weight *= grade_weights.get(evidence_grade, 1.0)

                            # Sample size weighting
                            if n_group and n_group > 0:
                                weight *= min(math.sqrt(n_group), 10.0)

                            # Temporal weighting (favor recent publications)
                            if pub_year and pub_year > 0:
                                current_year = datetime.now().year
                                years_old = current_year - pub_year
                                temporal_weight = max(0.1, math.exp(-0.0693 * years_old / 10))
                                weight *= temporal_weight

                            weights.append(weight)

                        # Calculate pooled estimate
                        pooled_result = self.calculate_pooled_estimate(estimates, weights)

                        if pooled_result:
                            # Create unique key for outcome-horizon combination
                            risk_key = f"{outcome_token}_{horizon}"

                            temporal_risks[risk_key] = {
                                'outcome_token': outcome_token,
                                'temporal_horizon': horizon,
                                'display_name': f"{outcome_token} ({horizon})",
                                **pooled_result
                            }

                            logger.info(f"Calculated {horizon} risk for {outcome_token}: "
                                      f"{pooled_result['estimate']:.6f} ({pooled_result['studies_count']} studies)")

            except Exception as e:
                logger.error(f"Failed to calculate temporal risks for {outcome_token}: {e}")
                continue

        return temporal_risks

    def store_temporal_risks(self, temporal_risks: Dict):
        """Store temporal-specific risks in database"""
        logger.info("Storing temporal-specific risks in database")

        try:
            # Create temporal baseline_risks table
            self.db.conn.execute("""
                CREATE TABLE IF NOT EXISTS temporal_baseline_risks (
                    id TEXT PRIMARY KEY,
                    outcome_token TEXT NOT NULL,
                    temporal_horizon TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    baseline_risk REAL NOT NULL,
                    confidence_interval_lower REAL,
                    confidence_interval_upper REAL,
                    evidence_grade TEXT,
                    studies_count INTEGER,
                    last_updated TEXT,
                    population TEXT DEFAULT 'mixed'
                )
            """)

            # Store temporal risks
            for risk_key, risk_data in temporal_risks.items():
                self.db.conn.execute("""
                    INSERT OR REPLACE INTO temporal_baseline_risks
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'B', ?, ?, 'mixed')
                """, [
                    risk_key,
                    risk_data['outcome_token'],
                    risk_data['temporal_horizon'],
                    risk_data['display_name'],
                    risk_data['estimate'],
                    risk_data['ci_lower'],
                    risk_data['ci_upper'],
                    risk_data['studies_count'],
                    datetime.now().isoformat()
                ])

            self.db.conn.commit()
            logger.info(f"Stored {len(temporal_risks)} temporal-specific risk calculations")

        except Exception as e:
            logger.error(f"Failed to store temporal risks: {e}")
            raise

    def generate_report(self, temporal_risks: Dict):
        """Generate temporal risk calculation report"""

        intraop_risks = {k: v for k, v in temporal_risks.items() if 'intraoperative' in k}
        periop_risks = {k: v for k, v in temporal_risks.items() if 'perioperative' in k}

        report = {
            'calculation_summary': {
                'timestamp': datetime.now().isoformat(),
                'total_calculations': len(temporal_risks),
                'intraoperative_risks': len(intraop_risks),
                'perioperative_risks': len(periop_risks),
                'database_path': self.db_path
            },
            'intraoperative_examples': dict(list(intraop_risks.items())[:5]),
            'perioperative_examples': dict(list(periop_risks.items())[:5])
        }

        # Save report
        report_path = f"temporal_risk_calculation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info(f"Temporal risk report saved: {report_path}")
        return report_path

def main():
    parser = argparse.ArgumentParser(description='Calculate Temporal-Specific Risk Scores')
    parser.add_argument('--db-path', default='database/codex.duckdb', help='Database path')
    args = parser.parse_args()

    try:
        # Initialize calculator
        calculator = TemporalRiskCalculator(db_path=args.db_path)

        logger.info("Starting temporal-specific risk score calculation")

        # Calculate temporal risks
        temporal_risks = calculator.calculate_temporal_risks()

        # Store results
        calculator.store_temporal_risks(temporal_risks)

        # Generate report
        report_path = calculator.generate_report(temporal_risks)

        print("\n" + "="*60)
        print("TEMPORAL RISK CALCULATION COMPLETED")
        print("="*60)

        intraop_count = len([k for k in temporal_risks.keys() if 'intraoperative' in k])
        periop_count = len([k for k in temporal_risks.keys() if 'perioperative' in k])

        print(f"Intraoperative risks calculated: {intraop_count}")
        print(f"Perioperative risks calculated: {periop_count}")
        print(f"Total temporal calculations: {len(temporal_risks)}")
        print(f"Report saved: {report_path}")
        print(f"Database: {args.db_path}")
        print("="*60)

        return 0

    except Exception as e:
        logger.error(f"Temporal risk calculation failed: {e}")
        print(f"\nTemporal risk calculation failed: {e}")
        return 1

if __name__ == "__main__":
    exit(main())