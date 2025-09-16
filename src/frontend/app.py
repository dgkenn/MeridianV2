"""
Main Flask application for Codex v2.
Clinician-first interface with comprehensive risk assessment and medication recommendations.
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS

from core.database import get_database
from core.hpi_parser import MedicalTextProcessor
from core.risk_engine import RiskEngine
from api.medication_engine import MedicationEngine
from ontology.core_ontology import AnesthesiaOntology

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure app
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'codex-dev-key-change-in-production')
app.config['DATABASE_PATH'] = os.environ.get('DATABASE_PATH', 'database/codex.duckdb')

# Initialize core components
db = get_database()
text_processor = MedicalTextProcessor()
risk_engine = RiskEngine()
medication_engine = MedicationEngine()
ontology = AnesthesiaOntology()

# Sample HPIs for demo
SAMPLE_HPIS = [
    {
        "hpi": "5-year-old male presenting for tonsillectomy and adenoidectomy. History significant for recurrent tonsillitis with 8 episodes in the past year, moderate OSA with AHI of 12 on recent sleep study, and recent URI 10 days ago with persistent dry cough. Mother reports loud snoring and witnessed apneic episodes during sleep lasting up to 15 seconds. Patient is otherwise healthy with no known drug allergies. Current weight 18 kg (25th percentile), height 105 cm. Parents report good exercise tolerance when well. Last solid food 8 hours ago, clear apple juice 3 hours ago. No fever in past 48 hours.",
        "population": "pediatric",
        "procedure": "ENT",
        "complexity": "moderate"
    },
    {
        "hpi": "3-year-old female scheduled for bilateral myringotomy with PE tube placement. Born at 34 weeks gestation, NICU stay for 3 weeks for respiratory support, now with appropriate developmental milestones. History of chronic otitis media with 6 documented episodes requiring antibiotics in the past year. Recent URI treated with amoxicillin 2 weeks ago, currently resolved. Both parents smoke in the home (combined 30 pack-years exposure). Physical exam reveals mild bilateral wheeze on expiration, no acute distress. Weight 12 kg (10th percentile for age). NPO since midnight for 8am surgical case. Immunizations up to date.",
        "population": "pediatric",
        "procedure": "ENT",
        "complexity": "high"
    },
    {
        "hpi": "7-year-old male for comprehensive dental rehabilitation under general anesthesia. Medical history significant for autism spectrum disorder with moderate communication delays, GERD managed with daily omeprazole 10mg, and well-controlled asthma (last exacerbation 8 months ago, uses albuterol PRN). Parents report significant behavioral challenges with dental compliance requiring sedation for routine care. Patient has extensive dental caries requiring multiple extractions, restorations, and root canals. Recent growth parameters: weight 25 kg (75th percentile), height 115 cm (50th percentile). No recent illnesses or medication changes. Last meal 10 hours ago.",
        "population": "pediatric",
        "procedure": "dental",
        "complexity": "moderate"
    }
]

# Routes

@app.route('/')
def index():
    """Main application page."""
    return render_template('index.html')

@app.route('/api/health')
def health_check():
    """System health check."""
    try:
        # Check database connection
        papers_count = db.conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
        ontology_count = db.conn.execute("SELECT COUNT(*) FROM ontology").fetchone()[0]

        return jsonify({
            "status": "healthy",
            "version": "2.0.0",
            "evidence_version": db.get_current_evidence_version() or "v1.0.0",
            "database": {
                "status": "connected",
                "papers": papers_count,
                "ontology_terms": ontology_count
            },
            "services": {
                "nlp_processor": "loaded",
                "risk_engine": "ready",
                "medication_engine": "ready"
            },
            "uptime_seconds": 0,  # Would track actual uptime
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route('/api/hpi/examples')
def get_hpi_examples():
    """Get random example HPIs."""
    population = request.args.get('population', 'all')

    examples = SAMPLE_HPIS
    if population != 'all':
        examples = [hpi for hpi in SAMPLE_HPIS if hpi['population'] == population]

    return jsonify({
        "examples": examples
    })

@app.route('/api/hpi/parse', methods=['POST'])
def parse_hpi():
    """Parse HPI and extract risk factors."""
    try:
        data = request.get_json()
        hpi_text = data.get('hpi_text', '').strip()

        if not hpi_text:
            return jsonify({"error": "HPI text is required"}), 400

        session_id = data.get('session_id')

        # Parse HPI
        parsed = text_processor.parse_hpi(hpi_text, session_id)

        # Generate risk summary
        risk_summary = text_processor.generate_risk_summary(parsed.extracted_factors)

        # Convert to JSON-serializable format
        response = {
            "session_id": parsed.session_id,
            "demographics": parsed.demographics,
            "extracted_factors": [
                {
                    "token": f.token,
                    "plain_label": f.plain_label,
                    "confidence": f.confidence,
                    "evidence_text": f.evidence_text,
                    "factor_type": f.factor_type,
                    "category": f.category,
                    "severity_weight": f.severity_weight,
                    "context": f.context
                }
                for f in parsed.extracted_factors
            ],
            "risk_summary": risk_summary,
            "phi_detected": parsed.phi_detected,
            "phi_locations": parsed.phi_locations,
            "anonymized_text": parsed.anonymized_text,
            "confidence_score": parsed.confidence_score,
            "parsed_at": parsed.parsed_at.isoformat()
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"HPI parsing error: {e}")
        return jsonify({"error": f"Parsing failed: {str(e)}"}), 500

@app.route('/api/risk/calculate', methods=['POST'])
def calculate_risks():
    """Calculate perioperative risks."""
    try:
        data = request.get_json()

        factor_tokens = data.get('factors', [])
        demographics = data.get('demographics', {})
        mode = data.get('mode', 'model_based')
        context_label = data.get('context_label')
        session_id = data.get('session_id')

        if not factor_tokens:
            return jsonify({"error": "Risk factors are required"}), 400

        # Convert factor tokens to ExtractedFactor objects (simplified)
        factors = []
        for token in factor_tokens:
            term = ontology.get_term(token)
            if term:
                from core.hpi_parser import ExtractedFactor
                factors.append(ExtractedFactor(
                    token=token,
                    plain_label=term.plain_label,
                    confidence=0.8,
                    evidence_text=f"Factor: {term.plain_label}",
                    factor_type=term.type,
                    category=term.category,
                    severity_weight=term.severity_weight,
                    context=""
                ))

        # Calculate risks
        risk_summary = risk_engine.calculate_risks(
            factors, demographics, mode, context_label, session_id
        )

        # Convert to JSON-serializable format
        response = {
            "session_id": risk_summary.session_id,
            "evidence_version": risk_summary.evidence_version,
            "mode": risk_summary.mode,
            "risks": [
                {
                    "outcome": r.outcome,
                    "outcome_label": r.outcome_label,
                    "category": r.category,
                    "baseline_risk": r.baseline_risk,
                    "baseline_context": r.baseline_context,
                    "adjusted_risk": r.adjusted_risk,
                    "confidence_interval": list(r.confidence_interval),
                    "risk_ratio": r.risk_ratio,
                    "risk_difference": r.risk_difference,
                    "evidence_grade": r.evidence_grade,
                    "k_studies": r.k_studies,
                    "contributing_factors": r.contributing_factors,
                    "citations": r.citations,
                    "last_updated": r.last_updated.isoformat(),
                    "no_evidence": r.no_evidence
                }
                for r in risk_summary.risks
            ],
            "summary": risk_summary.summary,
            "calculated_at": risk_summary.calculated_at.isoformat()
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Risk calculation error: {e}")
        return jsonify({"error": f"Risk calculation failed: {str(e)}"}), 500

@app.route('/api/medications/recommend', methods=['POST'])
def recommend_medications():
    """Generate medication recommendations."""
    try:
        data = request.get_json()

        factor_tokens = data.get('factors', [])
        risk_data = data.get('risks', [])
        demographics = data.get('demographics', {})
        preferences = data.get('preferences', {})

        # Convert factor tokens to ExtractedFactor objects
        factors = []
        for token in factor_tokens:
            term = ontology.get_term(token)
            if term:
                from core.hpi_parser import ExtractedFactor
                factors.append(ExtractedFactor(
                    token=token,
                    plain_label=term.plain_label,
                    confidence=0.8,
                    evidence_text=f"Factor: {term.plain_label}",
                    factor_type=term.type,
                    category=term.category,
                    severity_weight=term.severity_weight,
                    context=""
                ))

        # Convert risk data to RiskAssessment objects (simplified)
        risks = []
        for risk_item in risk_data:
            from core.risk_engine import RiskAssessment
            risks.append(RiskAssessment(
                outcome=risk_item.get('outcome', ''),
                outcome_label=risk_item.get('outcome_label', ''),
                category=risk_item.get('category', ''),
                baseline_risk=risk_item.get('baseline_risk', 0),
                baseline_context=risk_item.get('baseline_context', ''),
                adjusted_risk=risk_item.get('adjusted_risk', 0),
                confidence_interval=(0, 0),
                risk_ratio=risk_item.get('risk_ratio', 1),
                risk_difference=risk_item.get('risk_difference', 0),
                evidence_grade=risk_item.get('evidence_grade', 'D'),
                k_studies=risk_item.get('k_studies', 0),
                contributing_factors=[],
                citations=[],
                last_updated=datetime.now()
            ))

        # Generate recommendations
        medication_plan = medication_engine.generate_recommendations(
            factors, risks, demographics, preferences
        )

        # Convert to JSON-serializable format
        response = {
            "session_id": medication_plan.session_id,
            "recommendations": {
                category: [
                    {
                        "medication": rec.medication,
                        "generic_name": rec.generic_name,
                        "indication": rec.indication,
                        "dose": rec.dose,
                        "preparation": rec.preparation,
                        "evidence_grade": rec.evidence_grade,
                        "citations": rec.citations,
                        "category": rec.category,
                        "urgency": rec.urgency,
                        "conditions": rec.conditions or [],
                        "alternatives": rec.alternatives or [],
                        "contraindication_reason": rec.contraindication_reason
                    }
                    for rec in recommendations
                ]
                for category, recommendations in medication_plan.recommendations.items()
            },
            "drug_interactions": [
                {
                    "drug1": interaction.drug1,
                    "drug2": interaction.drug2,
                    "interaction": interaction.interaction,
                    "severity": interaction.severity,
                    "management": interaction.management
                }
                for interaction in medication_plan.drug_interactions
            ],
            "total_medications": medication_plan.total_medications,
            "generated_at": medication_plan.generated_at.isoformat()
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Medication recommendation error: {e}")
        return jsonify({"error": f"Medication recommendation failed: {str(e)}"}), 500

@app.route('/api/evidence/<outcome>')
def get_evidence(outcome):
    """Get evidence for a specific outcome."""
    try:
        modifier = request.args.get('modifier')
        context = request.args.get('context')

        modifiers = [modifier] if modifier else []
        evidence = risk_engine.get_outcome_evidence(outcome, modifiers, context)

        return jsonify(evidence)

    except Exception as e:
        logger.error(f"Evidence retrieval error: {e}")
        return jsonify({"error": f"Evidence retrieval failed: {str(e)}"}), 500

@app.route('/api/plan/generate', methods=['POST'])
def generate_plan():
    """Generate structured clinical plan."""
    try:
        data = request.get_json()
        session_id = data.get('session_id')

        if not session_id:
            return jsonify({"error": "Session ID is required"}), 400

        # Retrieve session data
        session_data = db.conn.execute("""
            SELECT hpi_text, parsed_factors, risk_scores, medication_recommendations
            FROM case_sessions WHERE session_id = ?
        """, [session_id]).fetchone()

        if not session_data:
            return jsonify({"error": "Session not found"}), 404

        hpi_text, parsed_factors_json, risk_scores_json, med_recs_json = session_data

        # Parse stored data
        parsed_factors = json.loads(parsed_factors_json) if parsed_factors_json else []
        risk_scores = json.loads(risk_scores_json) if risk_scores_json else {}
        med_recs = json.loads(med_recs_json) if med_recs_json else {}

        # Generate structured plan (simplified for demo)
        plan = {
            "case_summary": {
                "patient": "Patient case",
                "procedure": "Scheduled procedure",
                "key_risks": [f"{risk['outcome_label']} ({risk['adjusted_risk']:.1%})"
                            for risk in risk_scores.get('risks', [])[:3]],
                "primary_concerns": ", ".join([f['plain_label'] for f in parsed_factors[:3]])
            },
            "airway": {
                "approach": "Standard laryngoscopy with backup plan",
                "equipment": ["Laryngoscope", "ETT", "Stylet"],
                "considerations": ["Monitor for complications based on risk factors"]
            },
            "induction": {
                "technique": "Smooth IV induction",
                "medications": [rec['medication'] for rec in med_recs.get('recommendations', {}).get('standard', [])[:2]],
                "special_notes": "Adjust based on patient factors"
            },
            "maintenance": {
                "technique": "Balanced anesthesia",
                "volatile": "Sevoflurane",
                "monitoring": "Standard ASA monitors"
            },
            "emergence": {
                "strategy": "Smooth emergence",
                "medications": [rec['medication'] for rec in med_recs.get('recommendations', {}).get('draw_now', [])[:2]],
                "monitoring": "Continuous monitoring"
            }
        }

        # Generate copyable text
        copyable_text = f"""ANESTHETIC PLAN

Patient: {plan['case_summary']['patient']}
Procedure: {plan['case_summary']['procedure']}
Key Risks: {', '.join(plan['case_summary']['key_risks'])}

AIRWAY: {plan['airway']['approach']}
INDUCTION: {plan['induction']['technique']}
MAINTENANCE: {plan['maintenance']['technique']}
EMERGENCE: {plan['emergence']['strategy']}

Generated by Codex v2 at {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""

        response = {
            "plan": plan,
            "key_evidence": [],
            "generated_at": datetime.now().isoformat(),
            "copyable_text": copyable_text
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Plan generation error: {e}")
        return jsonify({"error": f"Plan generation failed: {str(e)}"}), 500

# Error handlers

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

# Static files
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

if __name__ == '__main__':
    # Ensure database directory exists
    os.makedirs('database', exist_ok=True)

    # Development server
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 8080)),
        debug=os.environ.get('FLASK_ENV') == 'development'
    )