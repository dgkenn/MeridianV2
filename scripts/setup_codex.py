#!/usr/bin/env python3
"""
Comprehensive setup script for Codex v2.
Initializes database, loads ontology, and prepares system for operation.
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from core.database import init_database, get_database
from ontology.core_ontology import AnesthesiaOntology
from evidence.pubmed_harvester import PubMedHarvester
from evidence.pooling_engine import MetaAnalysisEngine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_database():
    """Initialize database with complete schema."""
    logger.info("Initializing database...")

    db = init_database()
    logger.info("Database schema created successfully")

    # Create initial evidence version
    version = db.create_evidence_version("Initial Codex v2 deployment")
    logger.info(f"Created evidence version: {version}")

    return db

def load_ontology(db):
    """Load comprehensive ontology into database."""
    logger.info("Loading ontology...")

    ontology = AnesthesiaOntology()
    records = ontology.to_database_records()

    # Insert ontology records
    for record in records:
        db.conn.execute("""
            INSERT OR REPLACE INTO ontology
            (token, type, plain_label, synonyms, category, severity_weight,
             notes, icd10_codes, mesh_codes, parent_token, children_tokens)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            record['token'], record['type'], record['plain_label'],
            record['synonyms'], record['category'], record['severity_weight'],
            record['notes'], record['icd10_codes'], record['mesh_codes'],
            record['parent_token'], record['children_tokens']
        ])

    logger.info(f"Loaded {len(records)} ontology terms")

    # Log the action
    db.log_action("ontology", "bulk_load", "INSERT", {
        "terms_loaded": len(records),
        "types": list(set(r['type'] for r in records))
    })

def load_sample_evidence(db):
    """Load sample evidence data for demonstration."""
    logger.info("Loading sample evidence...")

    # Sample papers (would normally come from PubMed)
    sample_papers = [
        {
            "pmid": "12345678",
            "title": "Risk factors for laryngospasm in pediatric anesthesia: a retrospective analysis",
            "abstract": "Background: Laryngospasm is a significant complication in pediatric anesthesia. We analyzed risk factors in a large cohort. Methods: Retrospective review of 5,234 pediatric cases. Results: Recent URI increased laryngospasm risk (OR 2.8, 95% CI 1.6-4.9, p<0.001). OSA was also associated with increased risk (OR 1.9, CI 1.2-3.1). Conclusions: Recent URI and OSA are significant risk factors.",
            "journal": "Anesthesiology",
            "year": 2023,
            "design": "retrospective cohort",
            "n_total": 5234,
            "population": "pediatric",
            "procedure": "mixed",
            "time_horizon": "intraoperative",
            "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
            "raw_path": "database/raw_xml/sample_12345678.xml",
            "ingest_query_id": "sample_load",
            "evidence_grade": "B",
            "study_quality_score": 3.2
        },
        {
            "pmid": "23456789",
            "title": "Bronchospasm risk in asthmatic children undergoing general anesthesia",
            "abstract": "Objective: To assess bronchospasm risk in asthmatic children. Design: Prospective cohort study of 1,892 asthmatic children. Results: Bronchospasm occurred in 5.6% of cases. Asthma increased risk significantly (OR 2.8, 95% CI 2.1-3.7). Desflurane was associated with higher risk than sevoflurane. Conclusion: Asthmatic children have increased bronchospasm risk.",
            "journal": "Pediatric Anesthesia",
            "year": 2023,
            "design": "prospective cohort",
            "n_total": 1892,
            "population": "pediatric",
            "procedure": "mixed",
            "time_horizon": "perioperative",
            "url": "https://pubmed.ncbi.nlm.nih.gov/23456789/",
            "raw_path": "database/raw_xml/sample_23456789.xml",
            "ingest_query_id": "sample_load",
            "evidence_grade": "A",
            "study_quality_score": 4.1
        }
    ]

    # Insert sample papers
    for paper in sample_papers:
        db.conn.execute("""
            INSERT OR REPLACE INTO papers
            (pmid, title, abstract, journal, year, design, n_total, population,
             procedure, time_horizon, url, raw_path, ingest_query_id,
             evidence_grade, study_quality_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            paper["pmid"], paper["title"], paper["abstract"], paper["journal"],
            paper["year"], paper["design"], paper["n_total"], paper["population"],
            paper["procedure"], paper["time_horizon"], paper["url"], paper["raw_path"],
            paper["ingest_query_id"], paper["evidence_grade"], paper["study_quality_score"]
        ])

    # Sample effect estimates
    sample_estimates = [
        {
            "id": "est_12345678_laryngospasm_recent_uri",
            "pmid": "12345678",
            "outcome_token": "LARYNGOSPASM",
            "modifier_token": "RECENT_URI_2W",
            "measure": "OR",
            "estimate": 2.8,
            "ci_low": 1.6,
            "ci_high": 4.9,
            "adjusted": True,
            "n_group": 856,
            "n_events": 24,
            "definition_note": "Laryngospasm with recent URI (≤2 weeks)",
            "time_horizon": "intraoperative",
            "quality_weight": 3.2,
            "evidence_grade": "B",
            "population_match": 1.0,
            "extraction_confidence": 0.9
        },
        {
            "id": "est_12345678_laryngospasm_osa",
            "pmid": "12345678",
            "outcome_token": "LARYNGOSPASM",
            "modifier_token": "OSA",
            "measure": "OR",
            "estimate": 1.9,
            "ci_low": 1.2,
            "ci_high": 3.1,
            "adjusted": True,
            "n_group": 412,
            "n_events": 16,
            "definition_note": "Laryngospasm with OSA",
            "time_horizon": "intraoperative",
            "quality_weight": 3.2,
            "evidence_grade": "B",
            "population_match": 1.0,
            "extraction_confidence": 0.85
        },
        {
            "id": "est_23456789_bronchospasm_asthma",
            "pmid": "23456789",
            "outcome_token": "BRONCHOSPASM",
            "modifier_token": "ASTHMA",
            "measure": "OR",
            "estimate": 2.8,
            "ci_low": 2.1,
            "ci_high": 3.7,
            "adjusted": True,
            "n_group": 1892,
            "n_events": 106,
            "definition_note": "Bronchospasm in asthmatic children",
            "time_horizon": "perioperative",
            "quality_weight": 4.1,
            "evidence_grade": "A",
            "population_match": 1.0,
            "extraction_confidence": 0.95
        }
    ]

    # Insert sample estimates
    for estimate in sample_estimates:
        db.conn.execute("""
            INSERT OR REPLACE INTO estimates
            (id, pmid, outcome_token, modifier_token, measure, estimate,
             ci_low, ci_high, adjusted, n_group, n_events, definition_note,
             time_horizon, quality_weight, evidence_grade, population_match,
             extraction_confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            estimate["id"], estimate["pmid"], estimate["outcome_token"],
            estimate["modifier_token"], estimate["measure"], estimate["estimate"],
            estimate["ci_low"], estimate["ci_high"], estimate["adjusted"],
            estimate["n_group"], estimate["n_events"], estimate["definition_note"],
            estimate["time_horizon"], estimate["quality_weight"], estimate["evidence_grade"],
            estimate["population_match"], estimate["extraction_confidence"]
        ])

    # Sample baseline risks
    sample_baselines = [
        {
            "outcome_token": "LARYNGOSPASM",
            "context": "pediatric_ent",
            "risk": 0.015,
            "n_total": 2500,
            "studies": ["12345678"]
        },
        {
            "outcome_token": "BRONCHOSPASM",
            "context": "pediatric_general",
            "risk": 0.020,
            "n_total": 3000,
            "studies": ["23456789"]
        }
    ]

    logger.info(f"Loaded {len(sample_papers)} sample papers and {len(sample_estimates)} estimates")

def create_sample_pooled_evidence(db):
    """Create sample pooled evidence for demonstration."""
    logger.info("Creating sample pooled evidence...")

    evidence_version = db.get_current_evidence_version()

    # Sample pooled baseline
    db.conn.execute("""
        INSERT OR REPLACE INTO baselines_pooled
        (id, outcome_token, context_label, k, p0_mean, p0_ci_low, p0_ci_high,
         N_total, time_horizon, pmids, method, i_squared, evidence_version,
         quality_summary)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        "baseline_laryngospasm_pediatric_ent",
        "LARYNGOSPASM",
        "pediatric_ent",
        3,
        0.015,
        0.008,
        0.028,
        2500,
        "intraoperative",
        json.dumps(["12345678", "sample2", "sample3"]),
        "random_effects",
        35.2,
        evidence_version,
        json.dumps({"grade_distribution": {"A": 1, "B": 2}, "mean_quality_weight": 3.5})
    ])

    # Sample pooled effect
    db.conn.execute("""
        INSERT OR REPLACE INTO effects_pooled
        (id, outcome_token, modifier_token, context_label, k, or_mean,
         or_ci_low, or_ci_high, log_or_var, method, inputs, pmids,
         i_squared, tau_squared, evidence_version, quality_summary)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        "effect_laryngospasm_recent_uri_pediatric",
        "LARYNGOSPASM",
        "RECENT_URI_2W",
        "pediatric",
        2,
        2.8,
        1.6,
        4.9,
        0.25,
        "random_effects",
        json.dumps(["est_12345678_laryngospasm_recent_uri"]),
        json.dumps(["12345678"]),
        15.8,
        0.12,
        evidence_version,
        json.dumps({"grade_distribution": {"B": 2}, "mean_quality_weight": 3.2})
    ])

    logger.info("Created sample pooled evidence")

def load_medications(db):
    """Load medication database."""
    logger.info("Loading medication database...")

    # This would be much more comprehensive in practice
    sample_medications = [
        {
            "token": "PROPOFOL",
            "generic_name": "Propofol",
            "brand_names": json.dumps(["Diprivan"]),
            "drug_class": "induction_agent",
            "indications": json.dumps(["smooth_induction", "airway_reactivity"]),
            "contraindications": json.dumps(["egg_allergy", "soy_allergy"]),
            "adult_dose": "1-2.5 mg/kg IV",
            "peds_dose": "2-3 mg/kg IV",
            "evidence_grade": "A",
            "cost_tier": 2,
            "availability": "standard"
        },
        {
            "token": "SEVOFLURANE",
            "generic_name": "Sevoflurane",
            "brand_names": json.dumps(["Ultane"]),
            "drug_class": "volatile_anesthetic",
            "indications": json.dumps(["smooth_emergence", "airway_tolerance"]),
            "contraindications": json.dumps(["malignant_hyperthermia"]),
            "adult_dose": "2-3% inspired",
            "peds_dose": "2-3% inspired",
            "evidence_grade": "A",
            "cost_tier": 3,
            "availability": "standard"
        }
    ]

    for med in sample_medications:
        db.conn.execute("""
            INSERT OR REPLACE INTO medications
            (token, generic_name, brand_names, drug_class, indications,
             contraindications, adult_dose, peds_dose, evidence_grade,
             cost_tier, availability)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            med["token"], med["generic_name"], med["brand_names"],
            med["drug_class"], med["indications"], med["contraindications"],
            med["adult_dose"], med["peds_dose"], med["evidence_grade"],
            med["cost_tier"], med["availability"]
        ])

    logger.info(f"Loaded {len(sample_medications)} medications")

def create_sample_queries(db):
    """Create sample PubMed queries for future evidence updates."""
    logger.info("Creating sample queries...")

    sample_queries = [
        {
            "id": "laryngospasm_pediatric",
            "name": "Laryngospasm in pediatric anesthesia",
            "query_string": "(pediatric OR child OR infant) AND (laryngospasm OR laryngeal spasm) AND (anesthesia OR anaesthesia) AND (2015:3000[dp])",
            "population": "pediatric",
            "context": "general",
            "outcome_token": "LARYNGOSPASM",
            "total_results": 0
        },
        {
            "id": "bronchospasm_asthma",
            "name": "Bronchospasm in asthmatic patients",
            "query_string": "(asthma OR asthmatic) AND (bronchospasm OR wheeze) AND (anesthesia OR anaesthesia) AND (2015:3000[dp])",
            "population": "both",
            "context": "asthma",
            "outcome_token": "BRONCHOSPASM",
            "total_results": 0
        }
    ]

    for query in sample_queries:
        db.conn.execute("""
            INSERT OR REPLACE INTO queries
            (id, name, query_string, population, context, outcome_token, total_results)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            query["id"], query["name"], query["query_string"],
            query["population"], query["context"], query["outcome_token"],
            query["total_results"]
        ])

    logger.info(f"Created {len(sample_queries)} sample queries")

def validate_setup(db):
    """Validate the setup by running basic queries."""
    logger.info("Validating setup...")

    # Check ontology
    ontology_count = db.conn.execute("SELECT COUNT(*) FROM ontology").fetchone()[0]
    logger.info(f"Ontology terms: {ontology_count}")

    # Check papers
    papers_count = db.conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    logger.info(f"Papers: {papers_count}")

    # Check estimates
    estimates_count = db.conn.execute("SELECT COUNT(*) FROM estimates").fetchone()[0]
    logger.info(f"Estimates: {estimates_count}")

    # Check pooled evidence
    baselines_count = db.conn.execute("SELECT COUNT(*) FROM baselines_pooled").fetchone()[0]
    effects_count = db.conn.execute("SELECT COUNT(*) FROM effects_pooled").fetchone()[0]
    logger.info(f"Pooled baselines: {baselines_count}, effects: {effects_count}")

    # Check medications
    meds_count = db.conn.execute("SELECT COUNT(*) FROM medications").fetchone()[0]
    logger.info(f"Medications: {meds_count}")

    # Check evidence version
    current_version = db.get_current_evidence_version()
    logger.info(f"Current evidence version: {current_version}")

    logger.info("Setup validation completed successfully!")

def main():
    parser = argparse.ArgumentParser(description="Setup Codex v2 system")
    parser.add_argument("--skip-evidence", action="store_true",
                       help="Skip loading sample evidence (faster setup)")
    parser.add_argument("--db-path", default="database/codex.duckdb",
                       help="Database file path")
    parser.add_argument("--force", action="store_true",
                       help="Force recreation of existing database")

    args = parser.parse_args()

    # Check if database exists
    db_path = Path(args.db_path)
    if db_path.exists() and not args.force:
        logger.error(f"Database {db_path} already exists. Use --force to recreate.")
        sys.exit(1)

    try:
        # Setup database
        db = setup_database()

        # Load core data
        load_ontology(db)
        load_medications(db)
        create_sample_queries(db)

        # Load evidence if requested
        if not args.skip_evidence:
            load_sample_evidence(db)
            create_sample_pooled_evidence(db)

        # Validate setup
        validate_setup(db)

        logger.info("Codex v2 setup completed successfully!")
        logger.info(f"Database created at: {db_path.absolute()}")
        logger.info("You can now start the application with: python src/frontend/app.py")

    except Exception as e:
        logger.error(f"Setup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()