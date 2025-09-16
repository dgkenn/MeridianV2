"""
DuckDB database schema and connection management for Codex evidence engine.
Audit-ready design with complete provenance tracking.
"""

import duckdb
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class CodexDatabase:
    def __init__(self, db_path: str = "database/codex.duckdb"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(str(self.db_path))
        self.init_schema()

    def init_schema(self):
        """Initialize complete database schema for evidence engine."""

        # Core papers table - stores normalized PubMed records
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS papers (
                pmid VARCHAR PRIMARY KEY,
                title TEXT NOT NULL,
                abstract TEXT,
                journal VARCHAR,
                year INTEGER,
                design VARCHAR,  -- RCT, cohort, case-control, etc.
                n_total INTEGER,
                population VARCHAR,  -- adult, peds, mixed
                procedure VARCHAR,
                time_horizon VARCHAR,  -- 24h, 30d, in-hospital, etc.
                url VARCHAR,
                raw_path VARCHAR,  -- path to stored XML
                ingest_query_id VARCHAR,
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                doi VARCHAR,
                authors TEXT,  -- JSON array
                keywords TEXT,  -- JSON array
                mesh_terms TEXT,  -- JSON array
                study_quality_score REAL DEFAULT 0.0,
                evidence_grade VARCHAR  -- A, B, C, D
            )
        """)

        # Estimates table - extracted effect sizes and incidences
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS estimates (
                id VARCHAR PRIMARY KEY,
                pmid VARCHAR NOT NULL,
                outcome_token VARCHAR NOT NULL,
                modifier_token VARCHAR,  -- NULL for baseline incidence
                measure VARCHAR NOT NULL,  -- OR, RR, HR, INCIDENCE
                estimate REAL NOT NULL,
                ci_low REAL,
                ci_high REAL,
                adjusted BOOLEAN DEFAULT FALSE,
                n_group INTEGER,
                n_events INTEGER,
                definition_note TEXT,
                time_horizon VARCHAR,
                quality_weight REAL DEFAULT 1.0,
                evidence_grade VARCHAR,
                population_match REAL DEFAULT 1.0,  -- 0-1 match score
                extraction_confidence REAL DEFAULT 1.0,
                covariates TEXT,  -- JSON array of adjusted variables
                subgroup VARCHAR,  -- pediatric age band, etc.
                extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                harvest_batch_id VARCHAR,  -- Links to evidence harvest batch
                FOREIGN KEY (pmid) REFERENCES papers(pmid)
            )
        """)

        # Pooled effects - outcome-modifier combinations
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS effects_pooled (
                id VARCHAR PRIMARY KEY,
                outcome_token VARCHAR NOT NULL,
                modifier_token VARCHAR NOT NULL,
                context_label VARCHAR,  -- age×urgency×case_type
                k INTEGER NOT NULL,  -- number of studies
                or_mean REAL NOT NULL,
                or_ci_low REAL NOT NULL,
                or_ci_high REAL NOT NULL,
                log_or_var REAL,
                method VARCHAR,  -- random-effects, fixed-effects, etc.
                inputs TEXT NOT NULL,  -- JSON array of estimate IDs
                pmids TEXT NOT NULL,  -- JSON array
                i_squared REAL,  -- heterogeneity statistic
                tau_squared REAL,  -- between-study variance
                evidence_version VARCHAR NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                quality_summary TEXT  -- JSON with grade distribution
            )
        """)

        # Pooled baselines - outcome baseline risks by context
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS baselines_pooled (
                id VARCHAR PRIMARY KEY,
                outcome_token VARCHAR NOT NULL,
                context_label VARCHAR NOT NULL,
                k INTEGER NOT NULL,
                p0_mean REAL NOT NULL,
                p0_ci_low REAL NOT NULL,
                p0_ci_high REAL NOT NULL,
                N_total INTEGER,
                time_horizon VARCHAR,
                pmids TEXT NOT NULL,  -- JSON array
                method VARCHAR,
                i_squared REAL,
                evidence_version VARCHAR NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                quality_summary TEXT
            )
        """)

        # Guidelines from professional societies
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS guidelines (
                id VARCHAR PRIMARY KEY,
                society VARCHAR NOT NULL,  -- ASA, ASRA, SPA, etc.
                year INTEGER NOT NULL,
                title TEXT NOT NULL,
                section VARCHAR,
                statement TEXT NOT NULL,
                class VARCHAR,  -- I, IIa, IIb, III
                strength VARCHAR,  -- A, B, C
                link VARCHAR,
                outcome_tokens TEXT,  -- JSON array
                med_tokens TEXT,  -- JSON array
                risk_factor_tokens TEXT,  -- JSON array
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                pdf_path VARCHAR,
                page_number INTEGER
            )
        """)

        # Ontology - canonical tokens and mappings
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS ontology (
                token VARCHAR PRIMARY KEY,
                type VARCHAR NOT NULL,  -- risk_factor, outcome, med, drug_class, context
                synonyms TEXT,  -- JSON array
                plain_label VARCHAR NOT NULL,
                notes TEXT,
                category VARCHAR,  -- organ system, drug class, etc.
                severity_weight REAL DEFAULT 1.0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                icd10_codes TEXT,  -- JSON array
                mesh_codes TEXT,  -- JSON array
                parent_token VARCHAR,
                children_tokens TEXT  -- JSON array
            )
        """)

        # PubMed search queries
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS queries (
                id VARCHAR PRIMARY KEY,
                name VARCHAR NOT NULL,
                query_string TEXT NOT NULL,
                population VARCHAR,  -- adult, peds, both
                context VARCHAR,
                outcome_token VARCHAR,
                last_run_at TIMESTAMP,
                pmids_added TEXT,  -- JSON array of new PMIDs from last run
                total_results INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Comprehensive audit log
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id VARCHAR PRIMARY KEY,
                entity VARCHAR NOT NULL,  -- table name
                entity_id VARCHAR NOT NULL,
                action VARCHAR NOT NULL,  -- INSERT, UPDATE, DELETE, POOL
                details_json TEXT,
                old_values TEXT,  -- JSON of previous values
                new_values TEXT,  -- JSON of new values
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                by_user VARCHAR DEFAULT 'system',
                evidence_version VARCHAR,
                session_id VARCHAR
            )
        """)

        # Medications knowledge base
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS medications (
                token VARCHAR PRIMARY KEY,
                generic_name VARCHAR NOT NULL,
                brand_names TEXT,  -- JSON array
                drug_class VARCHAR NOT NULL,
                indications TEXT,  -- JSON array
                contraindications TEXT,  -- JSON array
                adult_dose VARCHAR,
                peds_dose VARCHAR,
                onset_minutes REAL,
                duration_hours REAL,
                elimination_half_life_hours REAL,
                metabolism TEXT,
                side_effects TEXT,  -- JSON array
                monitoring TEXT,  -- JSON array
                interactions TEXT,  -- JSON array
                pregnancy_category VARCHAR,
                cost_tier INTEGER,  -- 1=cheap, 5=expensive
                availability VARCHAR,  -- standard, special_order, rare
                evidence_grade VARCHAR,
                guideline_support TEXT,  -- JSON of society recommendations
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Evidence versions and change tracking
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS evidence_versions (
                version VARCHAR PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                description TEXT,
                papers_added INTEGER DEFAULT 0,
                estimates_added INTEGER DEFAULT 0,
                pools_updated INTEGER DEFAULT 0,
                changelog TEXT,  -- JSON of detailed changes
                validation_results TEXT,  -- JSON of quality checks
                is_current BOOLEAN DEFAULT FALSE
            )
        """)

        # Patient case sessions (for debugging/audit)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS case_sessions (
                session_id VARCHAR PRIMARY KEY,
                hpi_text TEXT NOT NULL,
                parsed_factors TEXT,  -- JSON array
                risk_scores TEXT,  -- JSON of all computed risks
                medication_recommendations TEXT,  -- JSON
                evidence_version VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id VARCHAR,
                anonymized_hpi TEXT  -- PHI-scrubbed version
            )
        """)

        # Evidence harvest batches - track systematic evidence collection
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS harvest_batches (
                batch_id VARCHAR PRIMARY KEY,
                outcome_token VARCHAR NOT NULL,
                population VARCHAR NOT NULL,
                query_used TEXT NOT NULL,
                papers_found INTEGER DEFAULT 0,
                papers_processed INTEGER DEFAULT 0,
                effects_extracted INTEGER DEFAULT 0,
                quality_grade_distribution TEXT,  -- JSON
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                status VARCHAR DEFAULT 'running',  -- running, completed, failed
                error_message TEXT,
                priority INTEGER DEFAULT 3,
                harvest_type VARCHAR DEFAULT 'comprehensive'  -- comprehensive, update, targeted
            )
        """)

        # Pooled estimates - enhanced with comprehensive referencing
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS pooled_estimates (
                id VARCHAR PRIMARY KEY,
                outcome_token VARCHAR NOT NULL,
                modifier_token VARCHAR,
                population VARCHAR DEFAULT 'mixed',
                pooled_estimate REAL NOT NULL,
                pooled_ci_low REAL NOT NULL,
                pooled_ci_high REAL NOT NULL,
                heterogeneity_i2 REAL,
                n_studies INTEGER NOT NULL,
                total_n INTEGER,
                evidence_grade VARCHAR NOT NULL,
                method VARCHAR DEFAULT 'random_effects',
                contributing_pmids TEXT,  -- JSON array of PMIDs
                contributing_estimates TEXT,  -- JSON array of estimate IDs
                quality_summary TEXT,  -- JSON with grade distribution
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                harvest_batch_ids TEXT,  -- JSON array linking to harvest batches
                notes TEXT
            )
        """)

        # Evidence citations - comprehensive referencing system
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS evidence_citations (
                citation_id VARCHAR PRIMARY KEY,
                pmid VARCHAR NOT NULL,
                outcome_token VARCHAR,
                modifier_token VARCHAR,
                citation_type VARCHAR NOT NULL,  -- primary_evidence, supporting_evidence, guideline
                citation_text TEXT NOT NULL,
                page_reference VARCHAR,
                figure_table_reference VARCHAR,
                evidence_strength VARCHAR,  -- A, B, C, D
                clinical_relevance REAL DEFAULT 1.0,  -- 0-1 relevance score
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pmid) REFERENCES papers(pmid)
            )
        """)

        # Risk factor mappings - link parsed risk factors to evidence
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS risk_factor_evidence_mapping (
                mapping_id VARCHAR PRIMARY KEY,
                parsed_risk_factor VARCHAR NOT NULL,  -- What was extracted from HPI
                ontology_token VARCHAR NOT NULL,  -- Canonical ontology term
                confidence_score REAL DEFAULT 1.0,
                supporting_pmids TEXT,  -- JSON array of supporting literature
                pooled_estimate_id VARCHAR,  -- Link to pooled effect if available
                mapping_method VARCHAR DEFAULT 'rule_based',  -- rule_based, ml_based, manual
                validated BOOLEAN DEFAULT FALSE,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ontology_token) REFERENCES ontology(token)
            )
        """)

        # Create indexes for performance
        self._create_indexes()

        logger.info("Database schema initialized successfully")

    def _create_indexes(self):
        """Create performance indexes."""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_estimates_outcome ON estimates(outcome_token)",
            "CREATE INDEX IF NOT EXISTS idx_estimates_modifier ON estimates(modifier_token)",
            "CREATE INDEX IF NOT EXISTS idx_estimates_pmid ON estimates(pmid)",
            "CREATE INDEX IF NOT EXISTS idx_estimates_harvest_batch ON estimates(harvest_batch_id)",
            "CREATE INDEX IF NOT EXISTS idx_papers_year ON papers(year)",
            "CREATE INDEX IF NOT EXISTS idx_papers_population ON papers(population)",
            "CREATE INDEX IF NOT EXISTS idx_ontology_type ON ontology(type)",
            "CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity, entity_id)",
            "CREATE INDEX IF NOT EXISTS idx_baselines_context ON baselines_pooled(context_label)",
            "CREATE INDEX IF NOT EXISTS idx_effects_outcome_modifier ON effects_pooled(outcome_token, modifier_token)",
            "CREATE INDEX IF NOT EXISTS idx_harvest_batches_outcome ON harvest_batches(outcome_token)",
            "CREATE INDEX IF NOT EXISTS idx_harvest_batches_status ON harvest_batches(status)",
            "CREATE INDEX IF NOT EXISTS idx_pooled_estimates_outcome ON pooled_estimates(outcome_token)",
            "CREATE INDEX IF NOT EXISTS idx_pooled_estimates_modifier ON pooled_estimates(modifier_token)",
            "CREATE INDEX IF NOT EXISTS idx_citations_pmid ON evidence_citations(pmid)",
            "CREATE INDEX IF NOT EXISTS idx_citations_outcome ON evidence_citations(outcome_token)",
            "CREATE INDEX IF NOT EXISTS idx_risk_mapping_token ON risk_factor_evidence_mapping(ontology_token)",
            "CREATE INDEX IF NOT EXISTS idx_risk_mapping_parsed ON risk_factor_evidence_mapping(parsed_risk_factor)"
        ]

        for idx in indexes:
            self.conn.execute(idx)

    def log_action(self, entity: str, entity_id: str, action: str,
                   details: Dict[str, Any], evidence_version: str = None,
                   session_id: str = None):
        """Log audit trail entry."""
        audit_id = f"{entity}_{entity_id}_{action}_{datetime.now().isoformat()}"

        self.conn.execute("""
            INSERT INTO audit_log (id, entity, entity_id, action, details_json,
                                 evidence_version, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [audit_id, entity, entity_id, action, json.dumps(details),
              evidence_version, session_id])

    def get_current_evidence_version(self) -> Optional[str]:
        """Get the current evidence version."""
        result = self.conn.execute("""
            SELECT version FROM evidence_versions
            WHERE is_current = TRUE
            ORDER BY created_at DESC LIMIT 1
        """).fetchone()

        return result[0] if result else None

    def create_evidence_version(self, description: str) -> str:
        """Create new evidence version."""
        version = f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Mark all previous versions as not current
        self.conn.execute("UPDATE evidence_versions SET is_current = FALSE")

        # Create new version
        self.conn.execute("""
            INSERT INTO evidence_versions (version, description, is_current)
            VALUES (?, ?, TRUE)
        """, [version, description])

        return version

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# Global database instance
_db_instance = None

def get_database() -> CodexDatabase:
    """Get global database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = CodexDatabase()
    return _db_instance

def init_database(db_path: str = None) -> CodexDatabase:
    """Initialize database with custom path."""
    global _db_instance
    _db_instance = CodexDatabase(db_path) if db_path else CodexDatabase()
    return _db_instance