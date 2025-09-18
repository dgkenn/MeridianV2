#!/usr/bin/env python3
"""
Create Comprehensive Production Database for CODEX v2

Consolidates all risk calculation types into a lightweight production database:
- Basic baseline risks and modifiers
- Temporal-specific risks (intraoperative vs perioperative)
- Evidence-based adjusted risks for age and comorbidities
- Essential supporting tables for the web application

Usage:
    python scripts/create_comprehensive_production_db.py
"""

import sys
import os
import logging
from pathlib import Path
from datetime import datetime
import argparse

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.database import init_database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ComprehensiveProductionDatabaseCreator:
    """Create comprehensive production database with all risk calculation types"""

    def __init__(self, source_db_path: str = "database/codex.duckdb",
                 production_db_path: str = "database/production_comprehensive.duckdb"):
        self.source_db_path = source_db_path
        self.production_db_path = production_db_path
        logger.info(f"Initializing comprehensive production database creator")
        logger.info(f"Source: {source_db_path}")
        logger.info(f"Production: {production_db_path}")

    def create_comprehensive_production_database(self):
        """Create comprehensive production database with all risk types"""
        logger.info("Creating comprehensive production database")

        # Initialize source database
        source_db = init_database(self.source_db_path)

        # Remove existing production database
        if os.path.exists(self.production_db_path):
            os.remove(self.production_db_path)
            logger.info(f"Removed existing production database: {self.production_db_path}")

        # Initialize production database
        prod_db = init_database(self.production_db_path)

        try:
            # Create essential tables in production database
            self.create_production_tables(prod_db)

            # Copy risk calculation data
            self.copy_baseline_risks(source_db, prod_db)
            self.copy_risk_modifiers(source_db, prod_db)
            self.copy_temporal_risks(source_db, prod_db)
            self.copy_evidence_based_adjusted_risks(source_db, prod_db)

            # Copy essential supporting data
            self.copy_supporting_tables(source_db, prod_db)

            # Generate production summary
            summary = self.generate_production_summary(prod_db)

            # Optimize database
            self.optimize_production_database(prod_db)

            logger.info("Comprehensive production database created successfully")
            return summary

        except Exception as e:
            logger.error(f"Failed to create comprehensive production database: {e}")
            raise
        finally:
            source_db.close()
            prod_db.close()

    def create_production_tables(self, prod_db):
        """Create essential tables in production database"""
        logger.info("Creating production tables")

        # Baseline risks table
        prod_db.conn.execute("""
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

        # Risk modifiers table
        prod_db.conn.execute("""
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

        # Temporal baseline risks table
        prod_db.conn.execute("""
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
                conversion_factor REAL,
                last_updated TEXT
            )
        """)

        # Evidence-based adjusted risks table
        prod_db.conn.execute("""
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

        # Essential supporting tables
        prod_db.conn.execute("""
            CREATE TABLE IF NOT EXISTS medications (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT,
                anesthesia_category TEXT,
                half_life_hours REAL,
                onset_minutes REAL,
                duration_minutes REAL,
                contraindications TEXT,
                risk_factors TEXT
            )
        """)

        prod_db.conn.execute("""
            CREATE TABLE IF NOT EXISTS ontology (
                token TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                category TEXT,
                description TEXT,
                severity_score INTEGER,
                temporal_category TEXT
            )
        """)

    def copy_baseline_risks(self, source_db, prod_db):
        """Copy baseline risks data"""
        logger.info("Copying baseline risks")

        baseline_data = source_db.conn.execute("""
            SELECT outcome_token, baseline_risk, confidence_interval_lower,
                   confidence_interval_upper, evidence_grade, studies_count,
                   last_updated, population
            FROM baseline_risks
        """).fetchall()

        for row in baseline_data:
            prod_db.conn.execute("""
                INSERT OR REPLACE INTO baseline_risks
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, row)

        logger.info(f"Copied {len(baseline_data)} baseline risk records")

    def copy_risk_modifiers(self, source_db, prod_db):
        """Copy risk modifiers data"""
        logger.info("Copying risk modifiers")

        modifier_data = source_db.conn.execute("""
            SELECT id, outcome_token, modifier_token, effect_estimate,
                   confidence_interval_lower, confidence_interval_upper,
                   evidence_grade, studies_count, last_updated
            FROM risk_modifiers
        """).fetchall()

        for row in modifier_data:
            prod_db.conn.execute("""
                INSERT OR REPLACE INTO risk_modifiers
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, row)

        logger.info(f"Copied {len(modifier_data)} risk modifier records")

    def copy_temporal_risks(self, source_db, prod_db):
        """Copy temporal baseline risks data"""
        logger.info("Copying temporal baseline risks")

        try:
            temporal_data = source_db.conn.execute("""
                SELECT id, outcome_token, temporal_horizon, display_name,
                       baseline_risk, confidence_interval_lower, confidence_interval_upper,
                       evidence_grade, studies_count, conversion_factor, last_updated
                FROM temporal_baseline_risks
            """).fetchall()

            for row in temporal_data:
                prod_db.conn.execute("""
                    INSERT OR REPLACE INTO temporal_baseline_risks
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, row)

            logger.info(f"Copied {len(temporal_data)} temporal baseline risk records")

        except Exception as e:
            logger.warning(f"Could not copy temporal baseline risks: {e}")

    def copy_evidence_based_adjusted_risks(self, source_db, prod_db):
        """Copy evidence-based adjusted risks data"""
        logger.info("Copying evidence-based adjusted risks")

        adjusted_data = source_db.conn.execute("""
            SELECT id, outcome_token, adjustment_category, adjustment_type,
                   baseline_risk, adjustment_multiplier, adjusted_risk,
                   confidence_interval_lower, confidence_interval_upper,
                   studies_count, evidence_grade, evidence_source, last_updated
            FROM evidence_based_adjusted_risks
        """).fetchall()

        for row in adjusted_data:
            prod_db.conn.execute("""
                INSERT OR REPLACE INTO evidence_based_adjusted_risks
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, row)

        logger.info(f"Copied {len(adjusted_data)} evidence-based adjusted risk records")

    def copy_supporting_tables(self, source_db, prod_db):
        """Copy essential supporting tables"""
        logger.info("Copying supporting tables")

        # Copy medications
        try:
            med_data = source_db.conn.execute("""
                SELECT id, name, category, anesthesia_category, half_life_hours,
                       onset_minutes, duration_minutes, contraindications, risk_factors
                FROM medications
            """).fetchall()

            for row in med_data:
                prod_db.conn.execute("""
                    INSERT OR REPLACE INTO medications
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, row)

            logger.info(f"Copied {len(med_data)} medication records")

        except Exception as e:
            logger.warning(f"Could not copy medications: {e}")

        # Copy ontology
        try:
            ont_data = source_db.conn.execute("""
                SELECT token, display_name, category, description,
                       severity_score, temporal_category
                FROM ontology
            """).fetchall()

            for row in ont_data:
                prod_db.conn.execute("""
                    INSERT OR REPLACE INTO ontology
                    VALUES (?, ?, ?, ?, ?, ?)
                """, row)

            logger.info(f"Copied {len(ont_data)} ontology records")

        except Exception as e:
            logger.warning(f"Could not copy ontology: {e}")

    def optimize_production_database(self, prod_db):
        """Optimize production database for performance"""
        logger.info("Optimizing production database")

        # Create indexes for performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_baseline_outcome ON baseline_risks(outcome_token)",
            "CREATE INDEX IF NOT EXISTS idx_modifier_outcome ON risk_modifiers(outcome_token)",
            "CREATE INDEX IF NOT EXISTS idx_modifier_token ON risk_modifiers(modifier_token)",
            "CREATE INDEX IF NOT EXISTS idx_temporal_outcome ON temporal_baseline_risks(outcome_token)",
            "CREATE INDEX IF NOT EXISTS idx_temporal_horizon ON temporal_baseline_risks(temporal_horizon)",
            "CREATE INDEX IF NOT EXISTS idx_adjusted_outcome ON evidence_based_adjusted_risks(outcome_token)",
            "CREATE INDEX IF NOT EXISTS idx_adjusted_category ON evidence_based_adjusted_risks(adjustment_category)",
            "CREATE INDEX IF NOT EXISTS idx_ontology_token ON ontology(token)",
            "CREATE INDEX IF NOT EXISTS idx_medication_name ON medications(name)"
        ]

        for index_sql in indexes:
            try:
                prod_db.conn.execute(index_sql)
            except Exception as e:
                logger.warning(f"Could not create index: {e}")

        # Vacuum and analyze
        prod_db.conn.execute("VACUUM")
        prod_db.conn.execute("ANALYZE")
        prod_db.conn.commit()

    def generate_production_summary(self, prod_db):
        """Generate summary of production database"""
        logger.info("Generating production database summary")

        # Count records in each table
        baseline_count = prod_db.conn.execute("SELECT COUNT(*) FROM baseline_risks").fetchone()[0]
        modifier_count = prod_db.conn.execute("SELECT COUNT(*) FROM risk_modifiers").fetchone()[0]

        temporal_count = 0
        try:
            temporal_count = prod_db.conn.execute("SELECT COUNT(*) FROM temporal_baseline_risks").fetchone()[0]
        except:
            pass

        adjusted_count = prod_db.conn.execute("SELECT COUNT(*) FROM evidence_based_adjusted_risks").fetchone()[0]

        med_count = 0
        ont_count = 0
        try:
            med_count = prod_db.conn.execute("SELECT COUNT(*) FROM medications").fetchone()[0]
        except:
            pass
        try:
            ont_count = prod_db.conn.execute("SELECT COUNT(*) FROM ontology").fetchone()[0]
        except:
            pass

        # Get database size
        if os.path.exists(self.production_db_path):
            db_size_mb = os.path.getsize(self.production_db_path) / (1024 * 1024)
        else:
            db_size_mb = 0

        summary = {
            'timestamp': datetime.now().isoformat(),
            'database_path': self.production_db_path,
            'database_size_mb': round(db_size_mb, 2),
            'tables': {
                'baseline_risks': baseline_count,
                'risk_modifiers': modifier_count,
                'temporal_baseline_risks': temporal_count,
                'evidence_based_adjusted_risks': adjusted_count,
                'medications': med_count,
                'ontology': ont_count
            },
            'total_risk_calculations': baseline_count + modifier_count + temporal_count + adjusted_count
        }

        return summary

def main():
    parser = argparse.ArgumentParser(description='Create Comprehensive Production Database')
    parser.add_argument('--source-db', default='database/codex.duckdb', help='Source database path')
    parser.add_argument('--production-db', default='database/production_comprehensive.duckdb', help='Production database path')
    args = parser.parse_args()

    try:
        # Create comprehensive production database
        creator = ComprehensiveProductionDatabaseCreator(
            source_db_path=args.source_db,
            production_db_path=args.production_db
        )

        summary = creator.create_comprehensive_production_database()

        print("\n" + "="*80)
        print("COMPREHENSIVE PRODUCTION DATABASE CREATED")
        print("="*80)
        print(f"Database file: {args.production_db}")
        print(f"Database size: {summary['database_size_mb']} MB")
        print(f"Total risk calculations: {summary['total_risk_calculations']}")
        print()
        print("Risk calculation tables:")
        print(f"  - Baseline risks: {summary['tables']['baseline_risks']}")
        print(f"  - Risk modifiers: {summary['tables']['risk_modifiers']}")
        print(f"  - Temporal risks: {summary['tables']['temporal_baseline_risks']}")
        print(f"  - Evidence-based adjusted: {summary['tables']['evidence_based_adjusted_risks']}")
        print()
        print("Supporting tables:")
        print(f"  - Medications: {summary['tables']['medications']}")
        print(f"  - Ontology: {summary['tables']['ontology']}")
        print("="*80)
        print("Ready for production deployment!")
        print("="*80)

        return 0

    except Exception as e:
        logger.error(f"Comprehensive production database creation failed: {e}")
        print(f"\nComprehensive production database creation failed: {e}")
        return 1

if __name__ == "__main__":
    exit(main())