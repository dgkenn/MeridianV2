# Codex v2 - Evidence-Based Anesthesia Risk Assessment Platform

**"OpenEvidence for Anesthesiology"** - A comprehensive clinical decision support system that parses free-text HPI, computes perioperative risks using pooled evidence, and generates evidence-based medication recommendations.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Installation](#installation)
4. [Database Schema](#database-schema)
5. [Core Components](#core-components)
6. [Usage](#usage)
7. [Evidence Collection](#evidence-collection)
8. [API Documentation](#api-documentation)
9. [Development](#development)
10. [Deployment](#deployment)
11. [Maintenance](#maintenance)
12. [Troubleshooting](#troubleshooting)

## Overview

Codex v2 is a next-generation clinical decision support platform designed specifically for anesthesiology. It implements a rigorous evidence-based approach to risk assessment, medication selection, and clinical planning.

### Key Features

- **Comprehensive Ontology**: 40+ outcomes, 120+ risk factors, 100+ medications
- **Evidence Harvest**: Automated PubMed integration with effect extraction
- **Statistical Pooling**: Random-effects meta-analysis with quality weighting
- **HPI Processing**: Advanced NLP with PHI detection and anonymization
- **Real-time Risk Scoring**: Baseline + modifier calculations with confidence intervals
- **Medication Draw-up Lists**: Evidence-based recommendations with contraindications
- **Audit Trails**: Complete provenance tracking for regulatory compliance
- **Versioned Evidence**: Monthly updates with change tracking

### Design Principles

1. **No Hallucination**: Every quantitative value must have PMID(s) or guideline citations
2. **Audit-Ready**: Complete provenance from raw data to final recommendations
3. **Evidence Grading**: A-D quality grades with numeric weights
4. **Outcome-First**: All queries and pooling organized by clinical outcomes
5. **Clinician-First UX**: Optimized for real-world clinical workflows

## Architecture

```
codex-v2/
├── src/
│   ├── core/                    # Core system components
│   │   ├── database.py          # DuckDB schema and connection management
│   │   ├── hpi_parser.py        # NLP processing and risk factor extraction
│   │   └── risk_engine.py       # Risk scoring and calculation logic
│   ├── evidence/                # Evidence collection and pooling
│   │   ├── pubmed_harvester.py  # PubMed API integration
│   │   ├── pooling_engine.py    # Meta-analysis algorithms
│   │   └── guideline_parser.py  # Professional guideline integration
│   ├── ontology/                # Medical knowledge representation
│   │   ├── core_ontology.py     # Comprehensive anesthesia ontology
│   │   └── medication_db.py     # Drug database and interactions
│   ├── frontend/                # Web interface
│   │   ├── static/              # CSS, JS, images
│   │   ├── templates/           # Jinja2 templates
│   │   └── app.py              # Flask application
│   └── api/                     # REST API endpoints
│       ├── risk_api.py          # Risk assessment endpoints
│       ├── evidence_api.py      # Evidence retrieval endpoints
│       └── medication_api.py    # Medication recommendation endpoints
├── database/                    # Database files and raw data
│   ├── codex.duckdb            # Main DuckDB database
│   ├── raw_xml/                # Raw PubMed XML files
│   └── guidelines/             # PDF guidelines and extracts
├── docs/                       # Documentation
├── tests/                      # Test suite
└── config/                     # Configuration files
```

### Technology Stack

- **Database**: DuckDB (audit-friendly, embedded analytics)
- **Backend**: Python 3.9+ with Flask
- **NLP**: spaCy, NLTK, custom medical processing
- **Statistics**: NumPy, SciPy, pandas (meta-analysis)
- **Frontend**: HTML5, JavaScript, modern CSS
- **APIs**: PubMed E-utilities, potential FHIR integration
- **Deployment**: Docker, cloud-ready architecture

## Installation

### Prerequisites

- Python 3.9 or higher
- Git
- 4GB+ RAM
- 10GB+ disk space for evidence database

### Quick Start

```bash
# Clone repository
git clone <repository-url>
cd codex-v2

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm

# Initialize database
python -c "from src.core.database import init_database; init_database()"

# Load ontology
python -c "from src.ontology.core_ontology import AnesthesiaOntology; from src.core.database import get_database; ont = AnesthesiaOntology(); db = get_database(); [db.conn.execute('INSERT OR REPLACE INTO ontology VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', list(r.values())) for r in ont.to_database_records()]"

# Run application
python src/frontend/app.py
```

### Environment Variables

Create a `.env` file:

```bash
# PubMed API (optional but recommended)
NCBI_API_KEY=your_api_key_here
CONTACT_EMAIL=your_email@domain.com

# Database
DATABASE_PATH=database/codex.duckdb

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/codex.log

# Security
SECRET_KEY=your_secret_key_here
```

## Database Schema

### Core Tables

#### papers
Stores normalized PubMed records with quality scoring.

```sql
CREATE TABLE papers (
    pmid VARCHAR PRIMARY KEY,
    title TEXT NOT NULL,
    abstract TEXT,
    journal VARCHAR,
    year INTEGER,
    design VARCHAR,           -- RCT, cohort, etc.
    n_total INTEGER,
    population VARCHAR,       -- adult, peds, mixed
    procedure VARCHAR,
    time_horizon VARCHAR,     -- 24h, 30d, in-hospital
    url VARCHAR,
    raw_path VARCHAR,         -- Path to stored XML
    evidence_grade VARCHAR,   -- A, B, C, D
    study_quality_score REAL,
    -- Additional metadata fields...
);
```

#### estimates
Extracted effect sizes and incidences with extraction confidence.

```sql
CREATE TABLE estimates (
    id VARCHAR PRIMARY KEY,
    pmid VARCHAR NOT NULL,
    outcome_token VARCHAR NOT NULL,
    modifier_token VARCHAR,    -- NULL for baseline incidence
    measure VARCHAR NOT NULL,  -- OR, RR, HR, INCIDENCE
    estimate REAL NOT NULL,
    ci_low REAL,
    ci_high REAL,
    adjusted BOOLEAN DEFAULT FALSE,
    quality_weight REAL DEFAULT 1.0,
    evidence_grade VARCHAR,
    population_match REAL DEFAULT 1.0,
    extraction_confidence REAL DEFAULT 1.0,
    -- Additional fields...
);
```

#### effects_pooled
Meta-analysis results for outcome-modifier combinations.

```sql
CREATE TABLE effects_pooled (
    id VARCHAR PRIMARY KEY,
    outcome_token VARCHAR NOT NULL,
    modifier_token VARCHAR NOT NULL,
    context_label VARCHAR,     -- age×urgency×case_type
    k INTEGER NOT NULL,        -- Number of studies
    or_mean REAL NOT NULL,
    or_ci_low REAL NOT NULL,
    or_ci_high REAL NOT NULL,
    method VARCHAR,            -- random_effects, fixed_effects
    inputs TEXT NOT NULL,      -- JSON array of estimate IDs
    pmids TEXT NOT NULL,       -- JSON array of PMIDs
    i_squared REAL,           -- Heterogeneity statistic
    evidence_version VARCHAR NOT NULL,
    -- Additional fields...
);
```

#### baselines_pooled
Pooled baseline risks by context.

```sql
CREATE TABLE baselines_pooled (
    id VARCHAR PRIMARY KEY,
    outcome_token VARCHAR NOT NULL,
    context_label VARCHAR NOT NULL,
    k INTEGER NOT NULL,
    p0_mean REAL NOT NULL,
    p0_ci_low REAL NOT NULL,
    p0_ci_high REAL NOT NULL,
    method VARCHAR,
    evidence_version VARCHAR NOT NULL,
    -- Additional fields...
);
```

### Supporting Tables

- **ontology**: Canonical terms, synonyms, and mappings
- **guidelines**: Professional society recommendations
- **medications**: Comprehensive drug database
- **audit_log**: Complete change tracking
- **case_sessions**: Patient case records (PHI-scrubbed)
- **evidence_versions**: Version control and change logs

## Core Components

### 1. Ontology System (`src/ontology/core_ontology.py`)

Comprehensive medical ontology with:

- **Outcomes** (40+): Organized by organ system
  - Airway: bronchospasm, laryngospasm, difficult intubation, etc.
  - Respiratory: pneumonia, ARDS, respiratory failure, etc.
  - Cardiovascular: hypotension, arrhythmias, cardiac arrest, etc.
  - Neurologic: stroke, seizure, awareness, delirium, etc.
  - [Complete list in code]

- **Risk Factors** (120+): Exhaustive coverage
  - Demographics: age bands, sex, pregnancy, syndromes
  - Lifestyle: smoking, alcohol, exercise tolerance
  - Airway: Mallampati, neck mobility, prior difficult airway
  - Medical: cardiac, pulmonary, renal, neurologic conditions
  - [Complete list in code]

- **Medications** (100+): Modern anesthesia pharmacology
  - Induction agents, volatiles, opioids, muscle relaxants
  - Vasoactives, antiemetics, local anesthetics
  - Emergency medications, reversal agents
  - [Complete list in code]

### 2. Evidence Harvester (`src/evidence/pubmed_harvester.py`)

Automated evidence collection with:

- **Outcome-First Queries**: Systematic searches for each outcome
- **Effect Extraction**: Regex patterns for OR, RR, HR, incidence
- **Quality Grading**: A-D grades based on design, sample size, reporting
- **Raw Data Storage**: Complete XML preservation for audit
- **Rate Limiting**: Respectful API usage with/without API keys

### 3. Pooling Engine (`src/evidence/pooling_engine.py`)

Statistical meta-analysis with:

- **Random Effects**: DerSimonian-Laird and Paule-Mandel estimators
- **Quality Weighting**: Evidence grade and study quality integration
- **Heterogeneity Assessment**: I² statistics and sensitivity analysis
- **Hartung-Knapp Adjustment**: Small-study corrections
- **Confidence Intervals**: Robust estimation with multiple methods

### 4. HPI Parser (`src/core/hpi_parser.py`)

Advanced NLP processing with:

- **PHI Detection**: Comprehensive patterns for names, dates, MRNs
- **Medical Entity Extraction**: Rule-based + spaCy NLP
- **Risk Factor Mapping**: Ontology-driven extraction
- **Confidence Scoring**: Multi-factor confidence assessment
- **Anonymization**: HIPAA-compliant text de-identification

### 5. Risk Engine (`src/core/risk_engine.py`)

Clinical risk calculation with:

- **Baseline Selection**: Context-aware baseline risk retrieval
- **Modifier Application**: Odds multiplication with pooled effects
- **Confidence Intervals**: Propagated uncertainty quantification
- **Missing Evidence Handling**: Graceful degradation with logging
- **Audit Trails**: Complete calculation provenance

## Usage

### Basic Workflow

1. **Input HPI**: Paste or type patient history
2. **Parse Factors**: Extract demographics and risk factors
3. **Calculate Risks**: Compute baseline + modifier risks
4. **Generate Medications**: Evidence-based draw-up recommendations
5. **Review Evidence**: Access supporting literature
6. **Export Plan**: Structured clinical plan

### Example API Usage

```python
from src.core.hpi_parser import MedicalTextProcessor
from src.core.risk_engine import RiskEngine

# Parse HPI
processor = MedicalTextProcessor()
parsed = processor.parse_hpi("""
5-year-old male presenting for tonsillectomy. History of asthma
and recent URI 2 weeks ago. OSA with AHI of 12.
""")

# Calculate risks
risk_engine = RiskEngine()
risks = risk_engine.calculate_risks(
    parsed.extracted_factors,
    parsed.demographics
)

# Generate medications
from src.api.medication_api import MedicationEngine
med_engine = MedicationEngine()
medications = med_engine.generate_recommendations(
    parsed.extracted_factors,
    risks
)
```

## Evidence Collection

### Monthly Update Process

1. **Query Generation**: Outcome-specific PubMed searches
2. **Literature Harvest**: Fetch new publications
3. **Effect Extraction**: Automated statistical extraction
4. **Quality Assessment**: Grading and weight assignment
5. **Meta-Analysis**: Re-pool effects with new evidence
6. **Version Control**: Bump evidence version
7. **Change Documentation**: Detailed changelog generation

### Manual Evidence Addition

```python
# Add custom study
from src.evidence.pubmed_harvester import PubMedHarvester

harvester = PubMedHarvester()
paper = harvester.manual_paper_entry(
    pmid="12345678",
    outcome="LARYNGOSPASM",
    modifier="RECENT_URI_2W",
    or_estimate=2.5,
    ci_low=1.2,
    ci_high=5.1
)
```

### Guideline Integration

```python
# Add guideline recommendation
from src.evidence.guideline_parser import GuidelineParser

parser = GuidelineParser()
parser.add_recommendation(
    society="ASA",
    year=2023,
    statement="Avoid succinylcholine in patients with malignant hyperthermia susceptibility",
    class_recommendation="I",
    evidence_level="B"
)
```

## API Documentation

### Risk Assessment Endpoints

#### POST /api/risk/calculate
Calculate risks for a parsed case.

**Request:**
```json
{
    "factors": ["ASTHMA", "RECENT_URI_2W", "AGE_1_5"],
    "demographics": {
        "age_years": 5,
        "sex": "SEX_MALE",
        "procedure": "TONSILLECTOMY"
    },
    "mode": "model_based"
}
```

**Response:**
```json
{
    "risks": [
        {
            "outcome": "LARYNGOSPASM",
            "baseline_risk": 0.015,
            "adjusted_risk": 0.045,
            "confidence_interval": [0.025, 0.078],
            "risk_increase": "3.0x",
            "evidence_grade": "B",
            "citations": ["PMID:12345", "PMID:67890"]
        }
    ],
    "session_id": "risk_123456"
}
```

#### GET /api/evidence/{outcome}/{modifier}
Retrieve evidence for specific outcome-modifier combination.

### Medication Endpoints

#### POST /api/medications/recommend
Generate medication recommendations.

**Request:**
```json
{
    "factors": ["ASTHMA", "RECENT_URI_2W"],
    "risks": ["LARYNGOSPASM", "BRONCHOSPASM"],
    "procedure": "TONSILLECTOMY"
}
```

**Response:**
```json
{
    "standard": [
        {
            "medication": "PROPOFOL",
            "indication": "Induction agent - smooth airway",
            "dose": "2-3 mg/kg IV",
            "evidence_grade": "A"
        }
    ],
    "draw_now": [
        {
            "medication": "ALBUTEROL",
            "indication": "Bronchospasm treatment",
            "dose": "2.5 mg nebulized",
            "evidence_grade": "B"
        }
    ],
    "contraindicated": [
        {
            "medication": "SUCCINYLCHOLINE",
            "reason": "Avoid in recent URI - increased laryngospasm risk",
            "evidence_grade": "B"
        }
    ]
}
```

## Development

### Code Organization

- **Database Layer**: Core schema and connection management
- **Evidence Layer**: Collection, extraction, and pooling
- **NLP Layer**: Text processing and entity extraction
- **API Layer**: REST endpoints and business logic
- **Frontend Layer**: User interface and visualization

### Testing

```bash
# Run test suite
python -m pytest tests/

# Specific test categories
python -m pytest tests/test_ontology.py
python -m pytest tests/test_pooling.py
python -m pytest tests/test_hpi_parser.py

# Coverage report
python -m pytest --cov=src tests/
```

### Contributing

1. Fork repository
2. Create feature branch
3. Add comprehensive tests
4. Update documentation
5. Submit pull request

### Code Style

- **PEP 8** compliance
- **Type hints** for all functions
- **Docstrings** for all modules/classes/functions
- **Error handling** with appropriate logging
- **Audit trails** for all data modifications

## Deployment

### Docker Deployment

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ src/
COPY database/ database/

EXPOSE 8080
CMD ["python", "src/frontend/app.py"]
```

### Production Configuration

- **Load Balancing**: Multiple Flask instances
- **Database**: Shared DuckDB with file locking
- **Logging**: Centralized log aggregation
- **Monitoring**: Health checks and performance metrics
- **Security**: HTTPS, input validation, rate limiting

### Scaling Considerations

- **Evidence Updates**: Separate scheduled process
- **Database Size**: Archive old evidence versions
- **API Rate Limits**: PubMed quota management
- **Compute Resources**: Meta-analysis can be CPU-intensive

## Maintenance

### Evidence Updates

Monthly update process (automated via cron/scheduler):

```bash
# Update evidence (typically run monthly)
python scripts/update_evidence.py --outcomes ALL --max-papers 1000

# Validate pooling results
python scripts/validate_pools.py --evidence-version v2024.03

# Generate changelog
python scripts/generate_changelog.py --from v2024.02 --to v2024.03
```

### Database Maintenance

```bash
# Vacuum database
python -c "from src.core.database import get_database; get_database().conn.execute('VACUUM')"

# Archive old sessions
python scripts/archive_sessions.py --older-than 365

# Backup database
cp database/codex.duckdb backups/codex_$(date +%Y%m%d).duckdb
```

### Quality Assurance

- **Monthly Evidence Validation**: Spot-check pooling results
- **Citation Verification**: Validate PMID accessibility
- **Performance Monitoring**: Track response times
- **User Feedback Integration**: Clinical validation updates

## Troubleshooting

### Common Issues

#### Database Locked
```bash
# Check for stale connections
lsof database/codex.duckdb

# Force unlock (use with caution)
python -c "import duckdb; duckdb.connect('database/codex.duckdb').close()"
```

#### PubMed API Errors
```bash
# Check rate limiting
python -c "from src.evidence.pubmed_harvester import PubMedHarvester; h = PubMedHarvester(); print(h.search_pubmed('test', 1))"

# Verify API key
echo $NCBI_API_KEY
```

#### Missing Evidence
```bash
# Check evidence version
python -c "from src.core.database import get_database; print(get_database().get_current_evidence_version())"

# Rebuild specific outcome
python scripts/rebuild_outcome.py --outcome LARYNGOSPASM --force
```

### Logging

Comprehensive logging at multiple levels:

- **ERROR**: System failures, data corruption
- **WARNING**: Missing evidence, API rate limits
- **INFO**: Normal operations, evidence updates
- **DEBUG**: Detailed processing steps

Log files located in `logs/` directory with rotation.

### Support

For technical support:
1. Check this documentation
2. Review error logs
3. Search existing issues
4. Contact development team

---

## License

[Specify license - likely proprietary for clinical software]

## Citation

If using Codex in research:

```
Codex v2: Evidence-Based Anesthesia Risk Assessment Platform
[Your Organization] (2024)
```

---

*This documentation is maintained alongside the codebase. For the most current version, always refer to the repository documentation.*# Force redeploy to sync database - Thu, Sep 18, 2025 11:16:16 AM
