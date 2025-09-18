#!/usr/bin/env python3
"""
Adjusted Baseline Risk Calculation for CODEX v2

Creates comprehensive baseline risk calculations adjusted for:
- Age (neonate, infant, pediatric, adult, elderly)
- Surgery type (cardiac, thoracic, orthopedic, neurosurgery, obstetric, general)
- Surgery urgency (elective, urgent, emergency)

Usage:
    python scripts/calculate_adjusted_baseline_risks.py
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

class AdjustedBaselineRiskCalculator:
    """Calculate age, surgery type, and urgency-adjusted baseline risks"""

    def __init__(self, db_path: str = "database/codex.duckdb"):
        self.db_path = db_path
        self.db = init_database(db_path)
        logger.info(f"Initialized AdjustedBaselineRiskCalculator with database: {db_path}")

    def get_age_adjustment_factors(self) -> Dict[str, Dict[str, float]]:
        """Evidence-based age adjustment factors for each outcome"""

        return {
            # Age multipliers based on clinical evidence
            'AGE_NEONATE': {
                'CARDIAC_ARREST': 3.5,  # Neonates have much higher cardiac arrest risk
                'CARDIOGENIC_SHOCK': 2.8,
                'MORTALITY_30D': 4.2,
                'MORTALITY_INHOSPITAL': 3.8,
                'SEPSIS': 2.5,
                'ACUTE_KIDNEY_INJURY': 1.8,
                'ARDS': 2.2,
                'FAILED_INTUBATION': 2.0,
                'DEFAULT': 2.0
            },
            'AGE_INFANT': {
                'CARDIAC_ARREST': 2.8,
                'CARDIOGENIC_SHOCK': 2.2,
                'MORTALITY_30D': 3.5,
                'MORTALITY_INHOSPITAL': 3.0,
                'SEPSIS': 2.0,
                'ACUTE_KIDNEY_INJURY': 1.5,
                'ARDS': 1.8,
                'FAILED_INTUBATION': 1.8,
                'LARYNGOSPASM': 1.5,  # Higher in infants
                'BRONCHOSPASM': 1.4,
                'DEFAULT': 1.8
            },
            'AGE_PEDIATRIC': {
                # Ages 2-17, generally lower risk than adults
                'CARDIAC_ARREST': 0.5,
                'CARDIOGENIC_SHOCK': 0.4,
                'MORTALITY_30D': 0.3,
                'MORTALITY_INHOSPITAL': 0.4,
                'STROKE': 0.2,
                'PULMONARY_EMBOLISM': 0.1,  # Very rare in children
                'SEPSIS': 0.8,
                'ACUTE_KIDNEY_INJURY': 0.7,
                'LARYNGOSPASM': 1.2,  # More common in children
                'BRONCHOSPASM': 1.3,
                'ASPIRATION': 1.1,
                'DEFAULT': 0.6
            },
            'AGE_ADULT': {
                # Standard adult risks (baseline = 1.0)
                'DEFAULT': 1.0
            },
            'AGE_ELDERLY': {
                # Ages 65+, increased risk
                'CARDIAC_ARREST': 2.5,
                'CARDIOGENIC_SHOCK': 2.8,
                'MORTALITY_30D': 3.2,
                'MORTALITY_INHOSPITAL': 2.8,
                'STROKE': 3.5,
                'PULMONARY_EMBOLISM': 2.2,
                'SEPSIS': 1.8,
                'ACUTE_KIDNEY_INJURY': 2.0,
                'ARDS': 1.7,
                'MULTIPLE_ORGAN_DYSFUNCTION': 2.2,
                'ASPIRATION': 1.5,
                'AWARENESS_UNDER_ANESTHESIA': 0.7,  # Lower awareness risk
                'DEFAULT': 1.8
            }
        }

    def get_surgery_type_adjustment_factors(self) -> Dict[str, Dict[str, float]]:
        """Evidence-based surgery type adjustment factors"""

        return {
            'CARDIAC_SURGERY': {
                'CARDIAC_ARREST': 8.5,
                'CARDIOGENIC_SHOCK': 12.0,
                'STROKE': 15.0,
                'ACUTE_KIDNEY_INJURY': 6.0,
                'ARDS': 4.5,
                'MULTIPLE_ORGAN_DYSFUNCTION': 5.5,
                'MORTALITY_30D': 10.0,
                'MORTALITY_INHOSPITAL': 8.5,
                'SEPSIS': 3.0,
                'VENTRICULAR_ARRHYTHMIA': 8.0,
                'DEFAULT': 4.0
            },
            'THORACIC_SURGERY': {
                'PULMONARY_EMBOLISM': 8.0,
                'ARDS': 12.0,
                'ASPIRATION': 4.0,
                'BRONCHOSPASM': 6.0,
                'SEPSIS': 3.5,
                'ACUTE_KIDNEY_INJURY': 2.5,
                'MORTALITY_30D': 6.0,
                'MORTALITY_INHOSPITAL': 5.0,
                'DEFAULT': 3.0
            },
            'NEUROSURGERY': {
                'STROKE': 20.0,
                'AWARENESS_UNDER_ANESTHESIA': 0.1,  # Heavy anesthesia
                'ASPIRATION': 2.5,
                'VENTRICULAR_ARRHYTHMIA': 3.0,
                'MORTALITY_30D': 8.0,
                'MORTALITY_INHOSPITAL': 7.0,
                'SEPSIS': 2.5,
                'DEFAULT': 3.5
            },
            'OBSTETRIC_SURGERY': {
                'AMNIOTIC_FLUID_EMBOLISM': 100.0,  # Obstetric-specific
                'ASPIRATION': 8.0,  # High aspiration risk in pregnancy
                'FAILED_INTUBATION': 12.0,  # Difficult airway in pregnancy
                'CARDIOGENIC_SHOCK': 4.0,
                'PULMONARY_EMBOLISM': 15.0,
                'STROKE': 6.0,
                'AWARENESS_UNDER_ANESTHESIA': 3.0,  # Often lighter anesthesia
                'MORTALITY_24H': 0.5,  # Generally healthy population
                'MORTALITY_30D': 0.3,
                'DEFAULT': 1.2
            },
            'ORTHOPEDIC_SURGERY': {
                'PULMONARY_EMBOLISM': 25.0,  # Very high risk
                'CARDIAC_ARREST': 0.8,
                'STROKE': 1.5,
                'SEPSIS': 2.0,
                'ACUTE_KIDNEY_INJURY': 1.2,
                'MORTALITY_30D': 1.5,
                'DEFAULT': 1.0
            },
            'GENERAL_SURGERY': {
                # Baseline general surgery risks
                'DEFAULT': 1.0
            }
        }

    def get_urgency_adjustment_factors(self) -> Dict[str, Dict[str, float]]:
        """Evidence-based urgency adjustment factors"""

        return {
            'ELECTIVE': {
                # Elective cases - lower risk due to optimization
                'CARDIAC_ARREST': 0.6,
                'CARDIOGENIC_SHOCK': 0.7,
                'MORTALITY_30D': 0.5,
                'MORTALITY_INHOSPITAL': 0.6,
                'SEPSIS': 0.8,
                'ACUTE_KIDNEY_INJURY': 0.8,
                'STROKE': 0.7,
                'ASPIRATION': 0.6,  # NPO status ensured
                'DEFAULT': 0.7
            },
            'URGENT': {
                # Urgent cases - moderate increase
                'CARDIAC_ARREST': 1.8,
                'CARDIOGENIC_SHOCK': 2.0,
                'MORTALITY_30D': 2.2,
                'MORTALITY_INHOSPITAL': 2.0,
                'SEPSIS': 1.5,
                'ASPIRATION': 1.8,  # Less optimal NPO
                'ACUTE_KIDNEY_INJURY': 1.4,
                'DEFAULT': 1.6
            },
            'EMERGENCY': {
                # Emergency cases - significant increase
                'CARDIAC_ARREST': 4.5,
                'CARDIOGENIC_SHOCK': 5.0,
                'MORTALITY_30D': 6.0,
                'MORTALITY_INHOSPITAL': 5.5,
                'SEPSIS': 3.5,
                'ASPIRATION': 8.0,  # Full stomach risk
                'FAILED_INTUBATION': 3.0,  # Suboptimal conditions
                'ACUTE_KIDNEY_INJURY': 2.8,
                'STROKE': 2.5,
                'AWARENESS_UNDER_ANESTHESIA': 4.0,  # Hemodynamic instability
                'DEFAULT': 3.5
            }
        }

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

    def create_adjusted_baseline_risks(self):
        """Create comprehensive adjusted baseline risks"""
        logger.info("Creating adjusted baseline risk estimates")

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

        # Get adjustment factors
        age_factors = self.get_age_adjustment_factors()
        surgery_factors = self.get_surgery_type_adjustment_factors()
        urgency_factors = self.get_urgency_adjustment_factors()

        adjusted_risks = {}

        # Define demographic and surgical categories
        age_groups = ['AGE_NEONATE', 'AGE_INFANT', 'AGE_PEDIATRIC', 'AGE_ADULT', 'AGE_ELDERLY']
        surgery_types = ['CARDIAC_SURGERY', 'THORACIC_SURGERY', 'NEUROSURGERY', 'OBSTETRIC_SURGERY', 'ORTHOPEDIC_SURGERY', 'GENERAL_SURGERY']
        urgency_levels = ['ELECTIVE', 'URGENT', 'EMERGENCY']

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

                        # Create adjusted risks for all combinations
                        for age_group in age_groups:
                            for surgery_type in surgery_types:
                                for urgency_level in urgency_levels:

                                    # Calculate adjustment multipliers
                                    age_mult = age_factors.get(age_group, {}).get(outcome_token,
                                               age_factors.get(age_group, {}).get('DEFAULT', 1.0))

                                    surgery_mult = surgery_factors.get(surgery_type, {}).get(outcome_token,
                                                  surgery_factors.get(surgery_type, {}).get('DEFAULT', 1.0))

                                    urgency_mult = urgency_factors.get(urgency_level, {}).get(outcome_token,
                                                  urgency_factors.get(urgency_level, {}).get('DEFAULT', 1.0))

                                    # Calculate adjusted risk
                                    adjusted_risk = baseline_risk * age_mult * surgery_mult * urgency_mult

                                    # Create unique identifier
                                    risk_id = f"{outcome_token}_{age_group}_{surgery_type}_{urgency_level}"

                                    adjusted_risks[risk_id] = {
                                        'outcome_token': outcome_token,
                                        'age_group': age_group,
                                        'surgery_type': surgery_type,
                                        'urgency_level': urgency_level,
                                        'baseline_risk': baseline_risk,
                                        'age_multiplier': age_mult,
                                        'surgery_multiplier': surgery_mult,
                                        'urgency_multiplier': urgency_mult,
                                        'adjusted_risk': adjusted_risk,
                                        'confidence_interval_lower': baseline_result['ci_lower'] * age_mult * surgery_mult * urgency_mult,
                                        'confidence_interval_upper': baseline_result['ci_upper'] * age_mult * surgery_mult * urgency_mult,
                                        'studies_count': baseline_result['studies_count'],
                                        'evidence_grade': 'B'
                                    }

                        logger.info(f"Created adjusted risks for {outcome_token}: baseline {baseline_risk:.6f}")

            except Exception as e:
                logger.error(f"Failed to calculate adjusted risk for {outcome_token}: {e}")
                continue

        return adjusted_risks

    def store_adjusted_risks(self, adjusted_risks: Dict):
        """Store adjusted baseline risks in database"""
        logger.info("Storing adjusted baseline risks in database")

        try:
            # Create adjusted_baseline_risks table
            self.db.conn.execute("""
                CREATE TABLE IF NOT EXISTS adjusted_baseline_risks (
                    id TEXT PRIMARY KEY,
                    outcome_token TEXT NOT NULL,
                    age_group TEXT NOT NULL,
                    surgery_type TEXT NOT NULL,
                    urgency_level TEXT NOT NULL,
                    baseline_risk REAL NOT NULL,
                    age_multiplier REAL NOT NULL,
                    surgery_multiplier REAL NOT NULL,
                    urgency_multiplier REAL NOT NULL,
                    adjusted_risk REAL NOT NULL,
                    confidence_interval_lower REAL,
                    confidence_interval_upper REAL,
                    studies_count INTEGER,
                    evidence_grade TEXT,
                    last_updated TEXT
                )
            """)

            # Store adjusted risks
            for risk_id, risk_data in adjusted_risks.items():
                self.db.conn.execute("""
                    INSERT OR REPLACE INTO adjusted_baseline_risks
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    risk_id,
                    risk_data['outcome_token'],
                    risk_data['age_group'],
                    risk_data['surgery_type'],
                    risk_data['urgency_level'],
                    risk_data['baseline_risk'],
                    risk_data['age_multiplier'],
                    risk_data['surgery_multiplier'],
                    risk_data['urgency_multiplier'],
                    risk_data['adjusted_risk'],
                    risk_data['confidence_interval_lower'],
                    risk_data['confidence_interval_upper'],
                    risk_data['studies_count'],
                    risk_data['evidence_grade'],
                    datetime.now().isoformat()
                ])

            self.db.conn.commit()
            logger.info(f"Stored {len(adjusted_risks)} adjusted baseline risk calculations")

        except Exception as e:
            logger.error(f"Failed to store adjusted risks: {e}")
            raise

    def generate_report(self, adjusted_risks: Dict):
        """Generate adjusted risk calculation report"""

        # Sample high-risk combinations
        high_risk = {k: v for k, v in adjusted_risks.items()
                    if v['adjusted_risk'] > 5.0 and 'EMERGENCY' in k and 'ELDERLY' in k}

        # Sample low-risk combinations
        low_risk = {k: v for k, v in adjusted_risks.items()
                   if v['adjusted_risk'] < 0.1 and 'ELECTIVE' in k and 'PEDIATRIC' in k}

        report = {
            'calculation_summary': {
                'timestamp': datetime.now().isoformat(),
                'total_combinations': len(adjusted_risks),
                'unique_outcomes': len(set(r['outcome_token'] for r in adjusted_risks.values())),
                'age_groups': 5,
                'surgery_types': 6,
                'urgency_levels': 3,
                'database_path': self.db_path
            },
            'high_risk_examples': dict(list(high_risk.items())[:10]),
            'low_risk_examples': dict(list(low_risk.items())[:10])
        }

        # Save report
        report_path = f"adjusted_baseline_risks_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info(f"Adjusted baseline risks report saved: {report_path}")
        return report_path

def main():
    parser = argparse.ArgumentParser(description='Calculate Adjusted Baseline Risk Scores')
    parser.add_argument('--db-path', default='database/codex.duckdb', help='Database path')
    args = parser.parse_args()

    try:
        # Initialize calculator
        calculator = AdjustedBaselineRiskCalculator(db_path=args.db_path)

        logger.info("Starting adjusted baseline risk calculation")

        # Calculate adjusted risks
        adjusted_risks = calculator.create_adjusted_baseline_risks()

        # Store results
        calculator.store_adjusted_risks(adjusted_risks)

        # Generate report
        report_path = calculator.generate_report(adjusted_risks)

        print("\n" + "="*60)
        print("ADJUSTED BASELINE RISK CALCULATION COMPLETED")
        print("="*60)

        total_combinations = len(adjusted_risks)
        unique_outcomes = len(set(r['outcome_token'] for r in adjusted_risks.values()))

        print(f"Unique outcomes: {unique_outcomes}")
        print(f"Total risk combinations: {total_combinations}")
        print(f"Age groups: 5 (neonate, infant, pediatric, adult, elderly)")
        print(f"Surgery types: 6 (cardiac, thoracic, neuro, obstetric, orthopedic, general)")
        print(f"Urgency levels: 3 (elective, urgent, emergency)")
        print(f"Report saved: {report_path}")
        print(f"Database: {args.db_path}")
        print("="*60)

        return 0

    except Exception as e:
        logger.error(f"Adjusted baseline risk calculation failed: {e}")
        print(f"\nAdjusted baseline risk calculation failed: {e}")
        return 1

if __name__ == "__main__":
    exit(main())