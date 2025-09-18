#!/usr/bin/env python3
"""
Harvest Evidence-Based Adjustment Factors for Age, Surgery Type, and Urgency

Systematically harvests real evidence from PubMed for:
- Age-specific risk adjustments (neonate, infant, pediatric, adult, elderly)
- Surgery type-specific adjustments (cardiac, thoracic, neuro, obstetric, orthopedic)
- Urgency-specific adjustments (elective, urgent, emergency)

Usage:
    python scripts/harvest_adjustment_factors.py
"""

import sys
import os
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import argparse

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.database import init_database
from src.evidence.pubmed_harvester import PubMedHarvester
from src.evidence.nlp_extractor import NLPExtractor
from src.core.error_codes import CodexError, ErrorCode, ErrorLogger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
error_logger = ErrorLogger()

class AdjustmentFactorHarvester:
    """Harvest evidence-based adjustment factors from PubMed"""

    def __init__(self, db_path: str = "database/codex.duckdb", api_key: str = None):
        self.db_path = db_path
        self.db = init_database(db_path)
        self.harvester = PubMedHarvester(api_key=api_key)
        self.extractor = NLPExtractor()
        logger.info(f"Initialized AdjustmentFactorHarvester with database: {db_path}")

    def get_age_specific_queries(self) -> Dict[str, List[str]]:
        """Age-specific search queries for each outcome"""

        age_queries = {
            'neonate': [
                "neonatal anesthesia complications",
                "newborn perioperative mortality",
                "neonatal cardiac arrest anesthesia",
                "neonate surgical risk factors"
            ],
            'infant': [
                "infant anesthesia complications",
                "infant perioperative mortality",
                "pediatric anesthesia age risk",
                "infant surgical outcomes"
            ],
            'pediatric': [
                "pediatric anesthesia complications",
                "children surgical mortality",
                "pediatric perioperative outcomes",
                "child anesthesia risk factors"
            ],
            'elderly': [
                "elderly anesthesia complications",
                "geriatric surgical mortality",
                "aging perioperative outcomes",
                "elderly anesthesia risk factors"
            ]
        }

        return age_queries

    def get_surgery_type_queries(self) -> Dict[str, List[str]]:
        """Surgery type-specific search queries"""

        surgery_queries = {
            'cardiac': [
                "cardiac surgery anesthesia complications",
                "cardiac anesthesia mortality",
                "cardiac surgery perioperative outcomes",
                "cardiothoracic anesthesia risk"
            ],
            'thoracic': [
                "thoracic surgery anesthesia complications",
                "lung surgery anesthesia mortality",
                "thoracic anesthesia perioperative outcomes",
                "pulmonary surgery anesthesia risk"
            ],
            'neurosurgery': [
                "neurosurgery anesthesia complications",
                "neuroanesthesia mortality",
                "brain surgery anesthesia outcomes",
                "neurosurgical anesthesia risk"
            ],
            'obstetric': [
                "obstetric anesthesia complications",
                "cesarean anesthesia mortality",
                "obstetric perioperative outcomes",
                "pregnancy anesthesia risk"
            ],
            'orthopedic': [
                "orthopedic surgery anesthesia complications",
                "orthopedic anesthesia mortality",
                "bone surgery anesthesia outcomes",
                "orthopedic perioperative risk"
            ]
        }

        return surgery_queries

    def get_urgency_queries(self) -> Dict[str, List[str]]:
        """Urgency-specific search queries"""

        urgency_queries = {
            'emergency': [
                "emergency surgery anesthesia complications",
                "emergency anesthesia mortality",
                "urgent surgery perioperative outcomes",
                "emergency surgical risk factors"
            ],
            'elective': [
                "elective surgery anesthesia complications",
                "planned surgery anesthesia outcomes",
                "elective perioperative mortality",
                "scheduled surgery anesthesia risk"
            ]
        }

        return urgency_queries

    async def harvest_age_adjustments(self):
        """Harvest age-specific adjustment evidence"""
        logger.info("Harvesting age-specific adjustment factors")

        age_queries = self.get_age_specific_queries()

        for age_group, queries in age_queries.items():
            logger.info(f"Harvesting evidence for age group: {age_group}")

            for query in queries:
                try:
                    # Search for papers
                    pmids = await self.harvester.search_pubmed(query, max_results=50)
                    logger.info(f"Found {len(pmids)} papers for query: {query}")

                    if pmids:
                        # Fetch and process papers
                        papers = await self.harvester.fetch_papers(pmids)

                        for paper in papers:
                            # Extract adjustment factors
                            effects = self.extractor.extract_numerical_data(paper)

                            for effect in effects:
                                # Store with age modifier
                                effect['modifier_token'] = f"AGE_{age_group.upper()}"
                                effect['modifier_type'] = 'age_adjustment'
                                effect['search_query'] = query

                                # Store in database
                                self.store_adjustment_effect(effect, paper)

                except Exception as e:
                    logger.error(f"Error harvesting age adjustment for {age_group}, query '{query}': {e}")
                    continue

    async def harvest_surgery_adjustments(self):
        """Harvest surgery type-specific adjustment evidence"""
        logger.info("Harvesting surgery type-specific adjustment factors")

        surgery_queries = self.get_surgery_type_queries()

        for surgery_type, queries in surgery_queries.items():
            logger.info(f"Harvesting evidence for surgery type: {surgery_type}")

            for query in queries:
                try:
                    # Search for papers
                    pmids = await self.harvester.search_pubmed(query, max_results=50)
                    logger.info(f"Found {len(pmids)} papers for query: {query}")

                    if pmids:
                        # Fetch and process papers
                        papers = await self.harvester.fetch_papers(pmids)

                        for paper in papers:
                            # Extract adjustment factors
                            effects = self.extractor.extract_numerical_data(paper)

                            for effect in effects:
                                # Store with surgery modifier
                                effect['modifier_token'] = f"SURGERY_{surgery_type.upper()}"
                                effect['modifier_type'] = 'surgery_adjustment'
                                effect['search_query'] = query

                                # Store in database
                                self.store_adjustment_effect(effect, paper)

                except Exception as e:
                    logger.error(f"Error harvesting surgery adjustment for {surgery_type}, query '{query}': {e}")
                    continue

    async def harvest_urgency_adjustments(self):
        """Harvest urgency-specific adjustment evidence"""
        logger.info("Harvesting urgency-specific adjustment factors")

        urgency_queries = self.get_urgency_queries()

        for urgency_level, queries in urgency_queries.items():
            logger.info(f"Harvesting evidence for urgency level: {urgency_level}")

            for query in queries:
                try:
                    # Search for papers
                    pmids = await self.harvester.search_pubmed(query, max_results=50)
                    logger.info(f"Found {len(pmids)} papers for query: {query}")

                    if pmids:
                        # Fetch and process papers
                        papers = await self.harvester.fetch_papers(pmids)

                        for paper in papers:
                            # Extract adjustment factors
                            effects = self.extractor.extract_numerical_data(paper)

                            for effect in effects:
                                # Store with urgency modifier
                                effect['modifier_token'] = f"URGENCY_{urgency_level.upper()}"
                                effect['modifier_type'] = 'urgency_adjustment'
                                effect['search_query'] = query

                                # Store in database
                                self.store_adjustment_effect(effect, paper)

                except Exception as e:
                    logger.error(f"Error harvesting urgency adjustment for {urgency_level}, query '{query}': {e}")
                    continue

    def store_adjustment_effect(self, effect: Dict, paper: Dict):
        """Store adjustment effect in database"""
        try:
            # Insert paper if not exists
            self.db.conn.execute("""
                INSERT OR IGNORE INTO papers (pmid, title, authors, journal, year, abstract)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [
                paper.get('pmid'),
                paper.get('title', ''),
                paper.get('authors', ''),
                paper.get('journal', ''),
                paper.get('year'),
                paper.get('abstract', '')
            ])

            # Insert estimate
            self.db.conn.execute("""
                INSERT INTO estimates (
                    pmid, outcome_token, modifier_token, estimate,
                    estimate_type, quality_weight, evidence_grade,
                    n_group, harvest_batch_id, extracted_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                paper.get('pmid'),
                effect.get('outcome_token', 'UNKNOWN'),
                effect.get('modifier_token'),
                effect.get('estimate'),
                effect.get('estimate_type', 'adjustment_factor'),
                effect.get('quality_weight', 2.0),
                effect.get('evidence_grade', 'C'),
                effect.get('n_group'),
                f"adjustment_harvest_{datetime.now().strftime('%Y%m%d')}",
                effect.get('extracted_text', '')
            ])

            self.db.conn.commit()

        except Exception as e:
            logger.error(f"Error storing adjustment effect: {e}")

    async def run_comprehensive_harvest(self):
        """Run comprehensive adjustment factor harvest"""
        logger.info("Starting comprehensive adjustment factor harvest")

        try:
            # Harvest age adjustments
            await self.harvest_age_adjustments()

            # Harvest surgery type adjustments
            await self.harvest_surgery_adjustments()

            # Harvest urgency adjustments
            await self.harvest_urgency_adjustments()

            # Generate summary report
            self.generate_harvest_report()

            logger.info("Comprehensive adjustment factor harvest completed")

        except Exception as e:
            logger.error(f"Error in comprehensive harvest: {e}")
            raise

    def generate_harvest_report(self):
        """Generate harvest summary report"""

        # Count adjustment factors by type
        age_count = self.db.conn.execute("""
            SELECT COUNT(*) FROM estimates
            WHERE modifier_token LIKE 'AGE_%'
        """).fetchone()[0]

        surgery_count = self.db.conn.execute("""
            SELECT COUNT(*) FROM estimates
            WHERE modifier_token LIKE 'SURGERY_%'
        """).fetchone()[0]

        urgency_count = self.db.conn.execute("""
            SELECT COUNT(*) FROM estimates
            WHERE modifier_token LIKE 'URGENCY_%'
        """).fetchone()[0]

        report = {
            'harvest_summary': {
                'timestamp': datetime.now().isoformat(),
                'age_adjustments': age_count,
                'surgery_adjustments': surgery_count,
                'urgency_adjustments': urgency_count,
                'total_adjustments': age_count + surgery_count + urgency_count
            }
        }

        # Save report
        report_path = f"adjustment_factor_harvest_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info(f"Adjustment factor harvest report saved: {report_path}")

        print("\n" + "="*60)
        print("ADJUSTMENT FACTOR HARVEST COMPLETED")
        print("="*60)
        print(f"Age adjustments harvested: {age_count}")
        print(f"Surgery type adjustments harvested: {surgery_count}")
        print(f"Urgency adjustments harvested: {urgency_count}")
        print(f"Total adjustment factors: {age_count + surgery_count + urgency_count}")
        print(f"Report saved: {report_path}")
        print("="*60)

def main():
    parser = argparse.ArgumentParser(description='Harvest Evidence-Based Adjustment Factors')
    parser.add_argument('--db-path', default='database/codex.duckdb', help='Database path')
    parser.add_argument('--api-key', help='NCBI API key for faster access')
    args = parser.parse_args()

    # Get API key from environment if not provided
    api_key = args.api_key or os.getenv('NCBI_API_KEY')

    try:
        import asyncio

        # Initialize harvester
        harvester = AdjustmentFactorHarvester(db_path=args.db_path, api_key=api_key)

        # Run harvest
        asyncio.run(harvester.run_comprehensive_harvest())

        return 0

    except Exception as e:
        logger.error(f"Adjustment factor harvest failed: {e}")
        print(f"\nAdjustment factor harvest failed: {e}")
        return 1

if __name__ == "__main__":
    exit(main())