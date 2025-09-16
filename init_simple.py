#!/usr/bin/env python3
"""
Simple initialization script for Codex v2.
"""

import duckdb
import json
import os
from pathlib import Path

# Create database directory
os.makedirs("database", exist_ok=True)

# Connect to database
conn = duckdb.connect("database/codex.duckdb")

print("Creating database schema...")

# Create core tables
conn.execute("""
    CREATE TABLE IF NOT EXISTS papers (
        pmid VARCHAR PRIMARY KEY,
        title TEXT NOT NULL,
        abstract TEXT,
        journal VARCHAR,
        year INTEGER,
        design VARCHAR,
        n_total INTEGER,
        population VARCHAR,
        procedure VARCHAR,
        time_horizon VARCHAR,
        url VARCHAR,
        raw_path VARCHAR,
        ingest_query_id VARCHAR,
        ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        evidence_grade VARCHAR,
        study_quality_score REAL DEFAULT 0.0
    )
""")

conn.execute("""
    CREATE TABLE IF NOT EXISTS estimates (
        id VARCHAR PRIMARY KEY,
        pmid VARCHAR NOT NULL,
        outcome_token VARCHAR NOT NULL,
        modifier_token VARCHAR,
        measure VARCHAR NOT NULL,
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
        population_match REAL DEFAULT 1.0,
        extraction_confidence REAL DEFAULT 1.0,
        extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

conn.execute("""
    CREATE TABLE IF NOT EXISTS ontology (
        token VARCHAR PRIMARY KEY,
        type VARCHAR NOT NULL,
        plain_label VARCHAR NOT NULL,
        synonyms TEXT,
        category VARCHAR,
        severity_weight REAL DEFAULT 1.0,
        notes TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

conn.execute("""
    CREATE TABLE IF NOT EXISTS case_sessions (
        session_id VARCHAR PRIMARY KEY,
        hpi_text TEXT NOT NULL,
        parsed_factors TEXT,
        risk_scores TEXT,
        medication_recommendations TEXT,
        evidence_version VARCHAR,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        anonymized_hpi TEXT
    )
""")

conn.execute("""
    CREATE TABLE IF NOT EXISTS evidence_versions (
        version VARCHAR PRIMARY KEY,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        description TEXT,
        is_current BOOLEAN DEFAULT FALSE
    )
""")

print("Loading sample ontology...")

# Sample ontology terms
sample_ontology = [
    ("ASTHMA", "risk_factor", "Asthma", '["asthma", "bronchial asthma"]', "pulmonary", 2.0),
    ("RECENT_URI_2W", "risk_factor", "Recent upper respiratory infection (≤2 weeks)", '["recent URI", "recent cold"]', "pulmonary", 2.5),
    ("OSA", "risk_factor", "Obstructive sleep apnea", '["sleep apnea", "OSA"]', "airway", 2.5),
    ("AGE_1_5", "risk_factor", "Age 1-5 years", '["preschool age"]', "demographics", 1.0),
    ("SEX_MALE", "risk_factor", "Male sex", '["male"]', "demographics", 1.0),
    ("LARYNGOSPASM", "outcome", "Laryngospasm", '["laryngeal spasm"]', "airway", 3.0),
    ("BRONCHOSPASM", "outcome", "Bronchospasm", '["wheeze", "bronchial spasm"]', "respiratory", 2.5),
    ("PONV", "outcome", "Postoperative nausea and vomiting", '["nausea", "vomiting"]', "gastrointestinal", 2.0),
]

for term in sample_ontology:
    conn.execute("""
        INSERT OR REPLACE INTO ontology (token, type, plain_label, synonyms, category, severity_weight)
        VALUES (?, ?, ?, ?, ?, ?)
    """, term)

print("Creating initial evidence version...")
conn.execute("""
    INSERT OR REPLACE INTO evidence_versions (version, description, is_current)
    VALUES ('v1.0.0', 'Initial Codex v2 deployment', TRUE)
""")

print("Loading sample evidence...")

# Sample papers
sample_papers = [
    ("12345678", "Risk factors for laryngospasm in pediatric anesthesia",
     "Recent URI increased laryngospasm risk (OR 2.8, 95% CI 1.6-4.9).",
     "Anesthesiology", 2023, "retrospective cohort", 5234, "pediatric", "mixed",
     "intraoperative", "https://pubmed.ncbi.nlm.nih.gov/12345678/", "", "sample_load", "B", 3.2),
    ("23456789", "Bronchospasm risk in asthmatic children",
     "Asthma increased bronchospasm risk (OR 2.8, 95% CI 2.1-3.7).",
     "Pediatric Anesthesia", 2023, "prospective cohort", 1892, "pediatric", "mixed",
     "perioperative", "https://pubmed.ncbi.nlm.nih.gov/23456789/", "", "sample_load", "A", 4.1)
]

for paper in sample_papers:
    conn.execute("""
        INSERT OR REPLACE INTO papers
        (pmid, title, abstract, journal, year, design, n_total, population, procedure,
         time_horizon, url, raw_path, ingest_query_id, evidence_grade, study_quality_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, paper)

# Sample estimates
sample_estimates = [
    ("est_1", "12345678", "LARYNGOSPASM", "RECENT_URI_2W", "OR", 2.8, 1.6, 4.9, True, 856, 24,
     "Laryngospasm with recent URI", "intraoperative", 3.2, "B", 1.0, 0.9),
    ("est_2", "23456789", "BRONCHOSPASM", "ASTHMA", "OR", 2.8, 2.1, 3.7, True, 1892, 106,
     "Bronchospasm in asthmatic children", "perioperative", 4.1, "A", 1.0, 0.95)
]

for estimate in sample_estimates:
    conn.execute("""
        INSERT OR REPLACE INTO estimates
        (id, pmid, outcome_token, modifier_token, measure, estimate, ci_low, ci_high,
         adjusted, n_group, n_events, definition_note, time_horizon, quality_weight,
         evidence_grade, population_match, extraction_confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, estimate)

print("Database initialized successfully!")

# Check counts
papers_count = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
ontology_count = conn.execute("SELECT COUNT(*) FROM ontology").fetchone()[0]
estimates_count = conn.execute("SELECT COUNT(*) FROM estimates").fetchone()[0]

print(f"Database contains:")
print(f"- {papers_count} papers")
print(f"- {ontology_count} ontology terms")
print(f"- {estimates_count} effect estimates")

conn.close()
print("Setup complete! You can now run: python src/frontend/app.py")