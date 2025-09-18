#!/usr/bin/env python3
"""
Optimized Evidence Harvest for CODEX v2
- API key optimization
- High-quality studies prioritization
- Adaptive batch sizing
- Local database first
- Risk calculation integration
"""

import os
import sys
import logging
import time
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import argparse
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.database import CodexDatabase, init_database
from src.evidence.pubmed_harvester import PubMedHarvester
from src.evidence.pooling_engine import EvidencePoolingEngine
from src.core.risk_engine import RiskEngine
from src.core.error_codes import CodexError, ErrorCode, ErrorLogger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('evidence_harvest_optimized.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
error_logger = ErrorLogger()

class OptimizedEvidenceHarvester:
    """Optimized evidence harvester with API key integration and smart batching"""

    def __init__(self, api_key: str, local_db_path: str = "database/codex_local.duckdb"):
        self.api_key = api_key
        self.local_db_path = local_db_path

        # Set API key environment variable
        os.environ['NCBI_API_KEY'] = api_key

        # Initialize local database
        self.db = init_database(local_db_path)
        self.harvester = PubMedHarvester()
        self.pooling_engine = EvidencePoolingEngine(self.db)
        self.risk_engine = RiskEngine(self.db)

        # Optimized parameters
        self.high_quality_only = True  # Prioritize A/B studies
        self.initial_batch_size = 50   # Start conservative with API key
        self.max_batch_size = 200      # Max batch size
        self.rate_limit_delay = 1.0    # Base delay between requests
        self.adaptive_delay = True     # Adjust delay based on response times

        # Priority outcomes for initial harvest
        self.priority_outcomes = [
            'MORTALITY_24H', 'MORTALITY_30D', 'MORTALITY_INHOSPITAL',
            'CARDIAC_ARREST', 'FAILED_INTUBATION', 'ASPIRATION',
            'ANAPHYLAXIS', 'MALIGNANT_HYPERTHERMIA', 'PONV',
            'DIFFICULT_INTUBATION', 'AIRWAY_TRAUMA', 'HYPOXEMIA',
            'POSTOP_RESP_FAILURE', 'PNEUMONIA', 'ACUTE_KIDNEY_INJURY'
        ]

        logger.info(f"Initialized OptimizedEvidenceHarvester with API key: {api_key[:8]}...")
        logger.info(f"Local database: {local_db_path}")
        logger.info(f"High quality only: {self.high_quality_only}")

    def adaptive_batch_sizing(self, success_rate: float, avg_response_time: float) -> int:
        """Dynamically adjust batch size based on API performance"""
        if success_rate > 0.95 and avg_response_time < 2.0:
            # High success, fast response - increase batch size
            return min(self.max_batch_size, self.initial_batch_size + 25)
        elif success_rate > 0.85 and avg_response_time < 5.0:
            # Good performance - maintain batch size
            return self.initial_batch_size
        else:
            # Poor performance - reduce batch size
            return max(10, self.initial_batch_size - 25)

    def harvest_outcome_optimized(self, outcome: str, population: str = "mixed") -> Dict:
        """Harvest evidence for a specific outcome with optimizations"""
        logger.info(f"Starting optimized harvest for {outcome} ({population})")

        start_time = time.time()
        total_papers = 0
        total_effects = 0
        success_count = 0
        attempt_count = 0
        response_times = []

        try:
            # Create harvest batch record
            batch_id = f"opt_{outcome}_{population}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # Quality filters for high-quality studies
            quality_filters = []
            if self.high_quality_only:
                quality_filters = [
                    '"randomized controlled trial"',
                    '"systematic review"',
                    '"meta-analysis"'
                ]

            # Adaptive harvesting with multiple query strategies
            for query_strategy in ['comprehensive', 'focused', 'recent']:
                request_start = time.time()
                attempt_count += 1

                try:
                    current_batch_size = self.adaptive_batch_sizing(
                        success_count / max(attempt_count, 1),
                        sum(response_times) / max(len(response_times), 1)
                    )

                    # Harvest with current strategy
                    papers, effects = self.harvester.harvest_outcome_evidence(
                        outcome_token=outcome,
                        population=population,
                        max_papers=current_batch_size,
                        quality_filter=query_strategy,
                        batch_id=batch_id
                    )

                    response_time = time.time() - request_start
                    response_times.append(response_time)

                    total_papers += len(papers)
                    total_effects += len(effects)
                    success_count += 1

                    logger.info(f"Strategy {query_strategy}: {len(papers)} papers, {len(effects)} effects")

                    # Adaptive delay
                    if self.adaptive_delay:
                        delay = self.rate_limit_delay * (1 + response_time / 5.0)
                        time.sleep(min(delay, 10.0))
                    else:
                        time.sleep(self.rate_limit_delay)

                except Exception as e:
                    logger.warning(f"Strategy {query_strategy} failed: {e}")
                    # Increase delay on failures
                    time.sleep(self.rate_limit_delay * 2)
                    continue

            # Pool evidence if sufficient data collected
            if total_effects > 5:
                try:
                    pooled_results = self.pooling_engine.pool_outcome_evidence(outcome, population)
                    logger.info(f"Pooled {len(pooled_results)} effect estimates for {outcome}")
                except Exception as e:
                    logger.warning(f"Pooling failed for {outcome}: {e}")

            duration = time.time() - start_time
            success_rate = success_count / max(attempt_count, 1)

            return {
                'outcome': outcome,
                'population': population,
                'papers_harvested': total_papers,
                'effects_extracted': total_effects,
                'success_rate': success_rate,
                'duration_seconds': duration,
                'batch_id': batch_id
            }

        except Exception as e:
            error = CodexError(
                error_code=ErrorCode.EVID_EXTRACTION_FAILED,
                message=f"Optimized harvest failed for {outcome}",
                details={
                    'outcome': outcome,
                    'population': population,
                    'total_papers': total_papers,
                    'total_effects': total_effects
                },
                original_exception=e
            )
            error_logger.log_error(error)
            raise error

    def run_priority_harvest(self) -> Dict:
        """Run harvest for priority outcomes first"""
        logger.info("Starting priority outcomes harvest")

        results = []
        total_start = time.time()

        for outcome in self.priority_outcomes:
            try:
                # Harvest for both adult and pediatric populations
                for population in ['adult', 'pediatric']:
                    result = self.harvest_outcome_optimized(outcome, population)
                    results.append(result)

                    logger.info(f"Completed {outcome} ({population}): "
                              f"{result['papers_harvested']} papers, "
                              f"{result['effects_extracted']} effects")

            except Exception as e:
                logger.error(f"Failed to harvest {outcome}: {e}")
                continue

        total_duration = time.time() - total_start

        summary = {
            'phase': 'priority_outcomes',
            'outcomes_processed': len(self.priority_outcomes),
            'total_papers': sum(r['papers_harvested'] for r in results),
            'total_effects': sum(r['effects_extracted'] for r in results),
            'total_duration_minutes': total_duration / 60,
            'results': results
        }

        logger.info(f"Priority harvest completed: {summary['total_papers']} papers, "
                   f"{summary['total_effects']} effects in {summary['total_duration_minutes']:.1f} minutes")

        return summary

    def calculate_all_risk_scores(self) -> Dict:
        """Calculate risk scores for all available evidence"""
        logger.info("Starting comprehensive risk score calculation")

        try:
            # Get all unique outcome-population combinations from database
            query = """
                SELECT DISTINCT outcome_token,
                       COALESCE(population, 'mixed') as population
                FROM estimates
                WHERE estimate IS NOT NULL
            """
            combinations = self.db.conn.execute(query).fetchall()

            calculated_scores = 0
            calculation_results = []

            for outcome_token, population in combinations:
                try:
                    # Calculate baseline and modifier risks
                    baseline_risk = self.risk_engine.calculate_baseline_risk(outcome_token, population)

                    if baseline_risk:
                        # Get all risk factors that have evidence for this outcome
                        modifier_query = """
                            SELECT DISTINCT modifier_token
                            FROM estimates
                            WHERE outcome_token = ?
                            AND modifier_token IS NOT NULL
                        """
                        modifiers = self.db.conn.execute(modifier_query, [outcome_token]).fetchall()

                        for (modifier_token,) in modifiers:
                            try:
                                effect = self.risk_engine.calculate_modifier_effect(
                                    outcome_token, modifier_token, population
                                )
                                if effect:
                                    calculated_scores += 1
                                    calculation_results.append({
                                        'outcome': outcome_token,
                                        'modifier': modifier_token,
                                        'population': population,
                                        'baseline_risk': baseline_risk,
                                        'effect': effect
                                    })
                            except Exception as e:
                                logger.debug(f"Failed to calculate effect for {outcome_token}+{modifier_token}: {e}")
                                continue

                except Exception as e:
                    logger.debug(f"Failed to calculate baseline for {outcome_token}: {e}")
                    continue

            logger.info(f"Calculated {calculated_scores} risk scores across {len(combinations)} outcome-population combinations")

            return {
                'total_combinations': len(combinations),
                'calculated_scores': calculated_scores,
                'calculation_results': calculation_results[:10],  # Sample of results
                'success_rate': calculated_scores / max(len(combinations), 1)
            }

        except Exception as e:
            error = CodexError(
                error_code=ErrorCode.RISK_CALCULATION_OVERFLOW,
                message="Failed to calculate comprehensive risk scores",
                details={'combinations_attempted': len(combinations) if 'combinations' in locals() else 0},
                original_exception=e
            )
            error_logger.log_error(error)
            raise error

    def generate_comprehensive_report(self, harvest_results: Dict, risk_results: Dict) -> str:
        """Generate comprehensive harvest and calculation report"""

        report = {
            'timestamp': datetime.now().isoformat(),
            'api_key_used': self.api_key[:8] + "...",
            'local_database': self.local_db_path,
            'harvest_summary': harvest_results,
            'risk_calculation_summary': risk_results,
            'database_stats': self.get_database_stats(),
            'optimization_settings': {
                'high_quality_only': self.high_quality_only,
                'batch_size_range': f"{self.initial_batch_size}-{self.max_batch_size}",
                'rate_limit_delay': self.rate_limit_delay,
                'adaptive_delay': self.adaptive_delay
            }
        }

        # Save detailed report
        report_path = f"evidence_harvest_comprehensive_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info(f"Comprehensive report saved: {report_path}")
        return report_path

    def get_database_stats(self) -> Dict:
        """Get current database statistics"""
        stats = {}

        try:
            # Papers count
            papers_count = self.db.conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
            stats['total_papers'] = papers_count

            # Effects count
            effects_count = self.db.conn.execute("SELECT COUNT(*) FROM estimates").fetchone()[0]
            stats['total_effects'] = effects_count

            # Quality distribution
            quality_dist = self.db.conn.execute("""
                SELECT evidence_grade, COUNT(*)
                FROM estimates
                WHERE evidence_grade IS NOT NULL
                GROUP BY evidence_grade
            """).fetchall()
            stats['quality_distribution'] = dict(quality_dist)

            # Unique outcomes
            outcomes = self.db.conn.execute("SELECT COUNT(DISTINCT outcome_token) FROM estimates").fetchone()[0]
            stats['unique_outcomes'] = outcomes

            # Population coverage
            populations = self.db.conn.execute("""
                SELECT population, COUNT(DISTINCT outcome_token)
                FROM estimates
                WHERE population IS NOT NULL
                GROUP BY population
            """).fetchall()
            stats['population_coverage'] = dict(populations)

        except Exception as e:
            logger.warning(f"Failed to get database stats: {e}")
            stats['error'] = str(e)

        return stats

def main():
    parser = argparse.ArgumentParser(description='Optimized Evidence Harvest for CODEX v2')
    parser.add_argument('--api-key', required=True, help='NCBI API key')
    parser.add_argument('--db-path', default='database/codex_local.duckdb', help='Local database path')
    parser.add_argument('--priority-only', action='store_true', help='Run priority outcomes only')
    parser.add_argument('--skip-risk-calc', action='store_true', help='Skip risk score calculation')
    parser.add_argument('--high-quality-only', action='store_true', default=True, help='Prioritize high-quality studies')

    args = parser.parse_args()

    try:
        # Initialize harvester
        harvester = OptimizedEvidenceHarvester(
            api_key=args.api_key,
            local_db_path=args.db_path
        )
        harvester.high_quality_only = args.high_quality_only

        logger.info("Starting optimized evidence harvest with API key integration")

        # Run priority harvest
        harvest_results = harvester.run_priority_harvest()

        # Calculate risk scores if requested
        risk_results = {}
        if not args.skip_risk_calc:
            risk_results = harvester.calculate_all_risk_scores()

        # Generate comprehensive report
        report_path = harvester.generate_comprehensive_report(harvest_results, risk_results)

        print("\n" + "="*60)
        print("OPTIMIZED EVIDENCE HARVEST COMPLETED")
        print("="*60)
        print(f"Total papers harvested: {harvest_results['total_papers']}")
        print(f"Total effects extracted: {harvest_results['total_effects']}")
        print(f"Duration: {harvest_results['total_duration_minutes']:.1f} minutes")

        if risk_results:
            print(f"Risk scores calculated: {risk_results['calculated_scores']}")
            print(f"Success rate: {risk_results['success_rate']:.2%}")

        print(f"Report saved: {report_path}")
        print(f"Local database: {args.db_path}")
        print("="*60)

    except KeyboardInterrupt:
        logger.info("Harvest interrupted by user")
        print("\nHarvest interrupted. Partial results may be available in local database.")

    except Exception as e:
        logger.error(f"Harvest failed: {e}")
        print(f"\nHarvest failed: {e}")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())