#!/usr/bin/env python3
"""
Risk Score Calculation with Temporal Weighting for CODEX v2

Implements the temporal weighting approach requested:
- Recency weighting: prioritize more recent studies (exponential decay, τ=7 years)
- Cohort alignment: additional weight for modern perioperative practices (2015+)
- Guidelines cutoff: emphasize society guidelines after 2015
- Both raw and temporally adjusted scores

Features:
- Calculates baseline risks for all outcomes
- Generates modifier effects for risk factors
- Implements temporal weighting with configurable parameters
- Stores both raw and adjusted effect sizes
- Provides audit trail for transparency

Usage:
    python scripts/calculate_risk_scores_temporal.py
    python scripts/calculate_risk_scores_temporal.py --tau 10  # Custom temporal decay
    python scripts/calculate_risk_scores_temporal.py --modern-cutoff 2010  # Custom modern cutoff
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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('risk_calculation_temporal.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
error_logger = ErrorLogger()

class TemporalRiskCalculator:
    """Risk calculator with temporal weighting implementation"""

    def __init__(self, db_path: str = "database/codex.duckdb", tau: float = 7.0, modern_cutoff: int = 2015):
        self.db_path = db_path
        self.tau = tau  # Temporal decay half-life in years
        self.modern_cutoff = modern_cutoff  # Modern practice cutoff year
        self.current_year = datetime.now().year

        # Initialize database
        self.db = init_database(db_path)

        # Temporal weighting parameters
        self.guideline_weight_multiplier = 1.5  # Extra weight for recent guidelines
        self.modern_practice_multiplier = 1.3   # Extra weight for modern cohorts

        logger.info(f"Initialized TemporalRiskCalculator with tau={tau} years, modern cutoff={modern_cutoff}")

    def calculate_temporal_weight(self, publication_year: int, study_type: str = "study") -> float:
        """
        Calculate temporal weight for a study based on publication year

        Uses exponential decay: weight = exp(-(current_year - pub_year)/τ)
        Additional multipliers for guidelines and modern practices
        """
        if publication_year is None or publication_year < 1950 or publication_year > self.current_year:
            return 0.1  # Minimal weight for invalid years

        # Base temporal weight with exponential decay
        years_ago = self.current_year - publication_year
        temporal_weight = math.exp(-years_ago / self.tau)

        # Additional weight for recent guidelines
        if study_type.lower() in ["guideline", "consensus", "recommendation"] and publication_year >= self.modern_cutoff:
            temporal_weight *= self.guideline_weight_multiplier

        # Additional weight for modern practice era
        if publication_year >= self.modern_cutoff:
            temporal_weight *= self.modern_practice_multiplier

        return temporal_weight

    def get_evidence_for_outcome(self, outcome_token: str, population: str = "mixed") -> List[Dict]:
        """Get all evidence estimates for a specific outcome"""
        query = """
            SELECT
                e.estimate,
                e.standard_error,
                e.confidence_interval_lower,
                e.confidence_interval_upper,
                e.evidence_grade,
                e.sample_size,
                e.modifier_token,
                p.publication_year,
                p.study_type,
                p.title,
                p.journal
            FROM estimates e
            LEFT JOIN papers p ON e.paper_id = p.paper_id
            WHERE e.outcome_token = ?
            AND (e.population = ? OR e.population IS NULL OR e.population = 'mixed')
            AND e.estimate IS NOT NULL
            ORDER BY p.publication_year DESC
        """

        results = self.db.conn.execute(query, [outcome_token, population]).fetchall()

        evidence_list = []
        for row in results:
            evidence_list.append({
                'estimate': row[0],
                'standard_error': row[1],
                'ci_lower': row[2],
                'ci_upper': row[3],
                'evidence_grade': row[4],
                'sample_size': row[5],
                'modifier_token': row[6],
                'publication_year': row[7],
                'study_type': row[8] or 'study',
                'title': row[9],
                'journal': row[10]
            })

        return evidence_list

    def calculate_inverse_variance_weight(self, evidence: Dict) -> float:
        """Calculate inverse variance weight for meta-analysis"""
        if evidence['standard_error'] is None or evidence['standard_error'] <= 0:
            # Fallback based on sample size if available
            if evidence['sample_size'] and evidence['sample_size'] > 0:
                # Approximate SE from sample size: SE ≈ 1/√n
                approx_se = 1.0 / math.sqrt(evidence['sample_size'])
                return 1.0 / (approx_se ** 2)
            else:
                return 1.0  # Minimal weight

        return 1.0 / (evidence['standard_error'] ** 2)

    def calculate_evidence_grade_weight(self, grade: str) -> float:
        """Convert evidence grade to numeric weight"""
        grade_weights = {
            'A': 4.0,  # High quality RCTs, meta-analyses
            'B': 3.0,  # Good quality cohort studies
            'C': 2.0,  # Case-control, lower quality studies
            'D': 1.0   # Expert opinion, case reports
        }
        return grade_weights.get(grade, 1.0)

    def pool_evidence_temporal(self, evidence_list: List[Dict]) -> Dict:
        """
        Pool evidence using temporal weighting and inverse variance meta-analysis

        Returns both raw pooled estimate and temporally adjusted estimate
        """
        if not evidence_list:
            return None

        # Calculate weights for each study
        raw_weights = []
        temporal_weights = []
        estimates = []

        for evidence in evidence_list:
            # Base inverse variance weight
            iv_weight = self.calculate_inverse_variance_weight(evidence)

            # Evidence grade weight
            grade_weight = self.calculate_evidence_grade_weight(evidence['evidence_grade'])

            # Temporal weight
            temporal_weight = self.calculate_temporal_weight(
                evidence['publication_year'],
                evidence['study_type']
            )

            # Combined weights
            raw_weight = iv_weight * grade_weight
            temporal_adjusted_weight = raw_weight * temporal_weight

            raw_weights.append(raw_weight)
            temporal_weights.append(temporal_adjusted_weight)
            estimates.append(evidence['estimate'])

        # Calculate raw pooled estimate
        if sum(raw_weights) > 0:
            raw_pooled = sum(est * weight for est, weight in zip(estimates, raw_weights)) / sum(raw_weights)
            raw_se = 1.0 / math.sqrt(sum(raw_weights))
        else:
            raw_pooled = estimates[0] if estimates else 0.0
            raw_se = 1.0

        # Calculate temporally adjusted pooled estimate
        if sum(temporal_weights) > 0:
            temporal_pooled = sum(est * weight for est, weight in zip(estimates, temporal_weights)) / sum(temporal_weights)
            temporal_se = 1.0 / math.sqrt(sum(temporal_weights))
        else:
            temporal_pooled = raw_pooled
            temporal_se = raw_se

        # Calculate confidence intervals
        raw_ci_lower = raw_pooled - 1.96 * raw_se
        raw_ci_upper = raw_pooled + 1.96 * raw_se
        temporal_ci_lower = temporal_pooled - 1.96 * temporal_se
        temporal_ci_upper = temporal_pooled + 1.96 * temporal_se

        # Check if temporal adjustment made significant difference
        temporal_adjustment_applied = abs(temporal_pooled - raw_pooled) > 0.01

        # Calculate average publication year for data age assessment
        years = [e['publication_year'] for e in evidence_list if e['publication_year']]
        avg_year = sum(years) / len(years) if years else None
        data_age_warning = avg_year and (self.current_year - avg_year) > 15

        return {
            'raw_estimate': raw_pooled,
            'raw_standard_error': raw_se,
            'raw_ci_lower': raw_ci_lower,
            'raw_ci_upper': raw_ci_upper,
            'temporal_estimate': temporal_pooled,
            'temporal_standard_error': temporal_se,
            'temporal_ci_lower': temporal_ci_lower,
            'temporal_ci_upper': temporal_ci_upper,
            'studies_count': len(evidence_list),
            'temporal_adjustment_applied': temporal_adjustment_applied,
            'average_publication_year': avg_year,
            'data_age_warning': data_age_warning,
            'oldest_study': min(years) if years else None,
            'newest_study': max(years) if years else None
        }

    def calculate_baseline_risks(self) -> Dict:
        """Calculate baseline risks for all outcomes with temporal weighting"""
        logger.info("Calculating baseline risks with temporal weighting")

        # Get all unique outcomes
        query = """
            SELECT DISTINCT outcome_token,
                   COALESCE(population, 'mixed') as pop
            FROM estimates
            WHERE estimate IS NOT NULL
            AND modifier_token IS NULL  -- Only baseline risks
        """

        outcome_populations = self.db.conn.execute(query).fetchall()

        baseline_risks = {}

        for outcome_token, population in outcome_populations:
            try:
                evidence_list = self.get_evidence_for_outcome(outcome_token, population)

                # Filter for baseline evidence (no modifiers)
                baseline_evidence = [e for e in evidence_list if not e['modifier_token']]

                if baseline_evidence:
                    pooled_result = self.pool_evidence_temporal(baseline_evidence)

                    if pooled_result:
                        baseline_risks[f"{outcome_token}_{population}"] = {
                            'outcome_token': outcome_token,
                            'population': population,
                            'type': 'baseline_risk',
                            **pooled_result
                        }

                        logger.info(f"Calculated baseline risk for {outcome_token} ({population}): "
                                  f"raw={pooled_result['raw_estimate']:.4f}, "
                                  f"temporal={pooled_result['temporal_estimate']:.4f}")

            except Exception as e:
                logger.error(f"Failed to calculate baseline risk for {outcome_token} ({population}): {e}")
                continue

        logger.info(f"Calculated {len(baseline_risks)} baseline risks")
        return baseline_risks

    def calculate_modifier_effects(self) -> Dict:
        """Calculate modifier effects for all risk factors with temporal weighting"""
        logger.info("Calculating modifier effects with temporal weighting")

        # Get all unique outcome-modifier combinations
        query = """
            SELECT DISTINCT outcome_token, modifier_token,
                   COALESCE(population, 'mixed') as pop
            FROM estimates
            WHERE estimate IS NOT NULL
            AND modifier_token IS NOT NULL
        """

        combinations = self.db.conn.execute(query).fetchall()

        modifier_effects = {}

        for outcome_token, modifier_token, population in combinations:
            try:
                evidence_list = self.get_evidence_for_outcome(outcome_token, population)

                # Filter for this specific modifier
                modifier_evidence = [e for e in evidence_list if e['modifier_token'] == modifier_token]

                if modifier_evidence:
                    pooled_result = self.pool_evidence_temporal(modifier_evidence)

                    if pooled_result:
                        key = f"{outcome_token}_{modifier_token}_{population}"
                        modifier_effects[key] = {
                            'outcome_token': outcome_token,
                            'modifier_token': modifier_token,
                            'population': population,
                            'type': 'modifier_effect',
                            **pooled_result
                        }

                        logger.info(f"Calculated modifier effect for {outcome_token}+{modifier_token} ({population}): "
                                  f"raw={pooled_result['raw_estimate']:.4f}, "
                                  f"temporal={pooled_result['temporal_estimate']:.4f}")

            except Exception as e:
                logger.error(f"Failed to calculate modifier effect for {outcome_token}+{modifier_token} ({population}): {e}")
                continue

        logger.info(f"Calculated {len(modifier_effects)} modifier effects")
        return modifier_effects

    def store_risk_calculations(self, baseline_risks: Dict, modifier_effects: Dict):
        """Store calculated risks in database with audit trail"""
        logger.info("Storing risk calculations in database")

        try:
            # Create risk_calculations table if not exists
            self.db.conn.execute("""
                CREATE TABLE IF NOT EXISTS risk_calculations (
                    calculation_id TEXT PRIMARY KEY,
                    outcome_token TEXT NOT NULL,
                    modifier_token TEXT,
                    population TEXT NOT NULL,
                    calculation_type TEXT NOT NULL,
                    raw_estimate REAL,
                    raw_standard_error REAL,
                    raw_ci_lower REAL,
                    raw_ci_upper REAL,
                    temporal_estimate REAL,
                    temporal_standard_error REAL,
                    temporal_ci_lower REAL,
                    temporal_ci_upper REAL,
                    studies_count INTEGER,
                    temporal_adjustment_applied BOOLEAN,
                    average_publication_year REAL,
                    data_age_warning BOOLEAN,
                    oldest_study INTEGER,
                    newest_study INTEGER,
                    calculation_timestamp TEXT,
                    temporal_parameters TEXT
                )
            """)

            # Store metadata about calculation parameters
            temporal_params = {
                'tau': self.tau,
                'modern_cutoff': self.modern_cutoff,
                'guideline_weight_multiplier': self.guideline_weight_multiplier,
                'modern_practice_multiplier': self.modern_practice_multiplier,
                'calculation_date': datetime.now().isoformat()
            }

            # Store baseline risks
            for key, risk_data in baseline_risks.items():
                calculation_id = f"baseline_{key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

                self.db.conn.execute("""
                    INSERT OR REPLACE INTO risk_calculations
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    calculation_id,
                    risk_data['outcome_token'],
                    None,  # No modifier for baseline
                    risk_data['population'],
                    'baseline_risk',
                    risk_data['raw_estimate'],
                    risk_data['raw_standard_error'],
                    risk_data['raw_ci_lower'],
                    risk_data['raw_ci_upper'],
                    risk_data['temporal_estimate'],
                    risk_data['temporal_standard_error'],
                    risk_data['temporal_ci_lower'],
                    risk_data['temporal_ci_upper'],
                    risk_data['studies_count'],
                    risk_data['temporal_adjustment_applied'],
                    risk_data['average_publication_year'],
                    risk_data['data_age_warning'],
                    risk_data['oldest_study'],
                    risk_data['newest_study'],
                    datetime.now().isoformat(),
                    json.dumps(temporal_params)
                ])

            # Store modifier effects
            for key, effect_data in modifier_effects.items():
                calculation_id = f"modifier_{key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

                self.db.conn.execute("""
                    INSERT OR REPLACE INTO risk_calculations
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    calculation_id,
                    effect_data['outcome_token'],
                    effect_data['modifier_token'],
                    effect_data['population'],
                    'modifier_effect',
                    effect_data['raw_estimate'],
                    effect_data['raw_standard_error'],
                    effect_data['raw_ci_lower'],
                    effect_data['raw_ci_upper'],
                    effect_data['temporal_estimate'],
                    effect_data['temporal_standard_error'],
                    effect_data['temporal_ci_lower'],
                    effect_data['temporal_ci_upper'],
                    effect_data['studies_count'],
                    effect_data['temporal_adjustment_applied'],
                    effect_data['average_publication_year'],
                    effect_data['data_age_warning'],
                    effect_data['oldest_study'],
                    effect_data['newest_study'],
                    datetime.now().isoformat(),
                    json.dumps(temporal_params)
                ])

            self.db.conn.commit()
            logger.info(f"Stored {len(baseline_risks)} baseline risks and {len(modifier_effects)} modifier effects")

        except Exception as e:
            error = CodexError(
                error_code=ErrorCode.DB_WRITE_FAILED,
                message="Failed to store risk calculations",
                details={'baseline_count': len(baseline_risks), 'modifier_count': len(modifier_effects)},
                original_exception=e
            )
            error_logger.log_error(error)
            raise error

    def generate_calculation_report(self, baseline_risks: Dict, modifier_effects: Dict) -> str:
        """Generate comprehensive calculation report"""

        # Calculate summary statistics
        total_calculations = len(baseline_risks) + len(modifier_effects)

        temporal_adjustments = sum(1 for r in baseline_risks.values() if r['temporal_adjustment_applied'])
        temporal_adjustments += sum(1 for r in modifier_effects.values() if r['temporal_adjustment_applied'])

        data_age_warnings = sum(1 for r in baseline_risks.values() if r['data_age_warning'])
        data_age_warnings += sum(1 for r in modifier_effects.values() if r['data_age_warning'])

        # Create report
        report = {
            'calculation_summary': {
                'timestamp': datetime.now().isoformat(),
                'total_calculations': total_calculations,
                'baseline_risks': len(baseline_risks),
                'modifier_effects': len(modifier_effects),
                'temporal_adjustments_applied': temporal_adjustments,
                'data_age_warnings': data_age_warnings,
                'temporal_parameters': {
                    'tau_years': self.tau,
                    'modern_cutoff': self.modern_cutoff,
                    'guideline_weight_multiplier': self.guideline_weight_multiplier,
                    'modern_practice_multiplier': self.modern_practice_multiplier
                }
            },
            'examples': {
                'baseline_risks': dict(list(baseline_risks.items())[:3]),
                'modifier_effects': dict(list(modifier_effects.items())[:3])
            },
            'data_quality_assessment': {
                'outcomes_with_modern_evidence': len([r for r in baseline_risks.values()
                                                   if r['newest_study'] and r['newest_study'] >= self.modern_cutoff]),
                'outcomes_needing_updates': len([r for r in baseline_risks.values()
                                               if r['data_age_warning']]),
                'average_study_age': {
                    'baseline': sum(self.current_year - r['average_publication_year']
                                  for r in baseline_risks.values()
                                  if r['average_publication_year']) / len(baseline_risks) if baseline_risks else 0,
                    'modifiers': sum(self.current_year - r['average_publication_year']
                                   for r in modifier_effects.values()
                                   if r['average_publication_year']) / len(modifier_effects) if modifier_effects else 0
                }
            }
        }

        # Save report
        report_path = f"risk_calculation_temporal_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info(f"Calculation report saved: {report_path}")
        return report_path

def main():
    parser = argparse.ArgumentParser(description='Calculate Risk Scores with Temporal Weighting')
    parser.add_argument('--db-path', default='database/codex.duckdb', help='Database path')
    parser.add_argument('--tau', type=float, default=7.0, help='Temporal decay parameter (years)')
    parser.add_argument('--modern-cutoff', type=int, default=2015, help='Modern practice cutoff year')

    args = parser.parse_args()

    try:
        # Initialize calculator
        calculator = TemporalRiskCalculator(
            db_path=args.db_path,
            tau=args.tau,
            modern_cutoff=args.modern_cutoff
        )

        logger.info("Starting temporal risk score calculation")

        # Calculate baseline risks
        baseline_risks = calculator.calculate_baseline_risks()

        # Calculate modifier effects
        modifier_effects = calculator.calculate_modifier_effects()

        # Store results
        calculator.store_risk_calculations(baseline_risks, modifier_effects)

        # Generate report
        report_path = calculator.generate_calculation_report(baseline_risks, modifier_effects)

        print("\n" + "="*60)
        print("TEMPORAL RISK CALCULATION COMPLETED")
        print("="*60)
        print(f"Baseline risks calculated: {len(baseline_risks)}")
        print(f"Modifier effects calculated: {len(modifier_effects)}")
        print(f"Total calculations: {len(baseline_risks) + len(modifier_effects)}")
        print(f"Temporal parameters: τ={args.tau} years, modern cutoff={args.modern_cutoff}")
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