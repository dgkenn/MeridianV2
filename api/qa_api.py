#!/usr/bin/env python3
"""
Q+A API - Clinical question answering endpoints with guideline sourcing
"""

import logging
import json
from flask import Blueprint, request, jsonify
from typing import Dict, List, Any
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.qa_service import QAService

logger = logging.getLogger(__name__)

# Create blueprint
qa_bp = Blueprint('qa', __name__, url_prefix='/api/qa')

# Initialize service
try:
    qa_service = QAService()
    logger.info("Q+A service initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Q+A service: {e}")
    qa_service = None

@qa_bp.route('/ask', methods=['POST'])
def ask_question():
    """
    Answer clinical questions with patient context and guideline sourcing

    POST /api/qa/ask
    Body: {
        question: string,
        case_id: string,
        seed?: number,
        allow_web?: boolean,
        tools_allowed?: string[]
    }

    Returns: {
        answer_md: string,
        citations: string[],
        links: {label: string, url: string}[],
        used_features: string[],
        risk_refs: {outcome: string, window: string, p0: number, phat: number, conf: string}[],
        actions: {type: string, label: string, href: string}[],
        audit: object
    }
    """
    try:
        if not qa_service:
            return jsonify({'error': 'Q+A service not available'}), 500

        data = request.get_json()
        if not data or 'question' not in data:
            return jsonify({'error': 'question required'}), 400

        question = data['question']
        if not question.strip():
            return jsonify({'error': 'question cannot be empty'}), 400

        case_id = data.get('case_id', 'default')
        seed = data.get('seed')
        allow_web = data.get('allow_web', True)
        tools_allowed = data.get('tools_allowed', [
            "dose_math", "risk_convert", "guideline_lookup_local",
            "web_guideline_search", "web_guideline_fetch", "feature_finder"
        ])

        # Validate tools
        valid_tools = {
            "dose_math", "risk_convert", "guideline_lookup_local",
            "web_guideline_search", "web_guideline_fetch", "feature_finder"
        }

        invalid_tools = set(tools_allowed) - valid_tools
        if invalid_tools:
            return jsonify({
                'error': f'Invalid tools: {list(invalid_tools)}',
                'valid_tools': list(valid_tools)
            }), 400

        # Check for potential off-allowlist requests
        question_lower = question.lower()
        forbidden_patterns = [
            'wikipedia', 'webmd', 'reddit', 'facebook', 'twitter',
            'blog', 'forum', 'patient story', 'personal experience'
        ]

        if any(pattern in question_lower for pattern in forbidden_patterns):
            return jsonify({
                'error': 'Question appears to reference non-allowlisted sources',
                'allowed_alternatives': [
                    'ASA guidelines at asahq.org',
                    'ASRA guidelines at asra.com',
                    'PubMed literature at pubmed.ncbi.nlm.nih.gov',
                    'Society recommendations from professional organizations'
                ]
            }), 422

        # Load case bundle if available
        # In production, this would load from database using case_id
        # For now, use mock data or app state
        case_bundle = _get_case_bundle(case_id)
        if case_bundle:
            qa_service.load_case_bundle(case_bundle)

        # Process the question
        response = qa_service.ask_question(
            question=question,
            case_id=case_id,
            seed=seed,
            allow_web=allow_web,
            tools_allowed=tools_allowed
        )

        # Convert to JSON format
        response_data = {
            'answer_md': response.answer_md,
            'citations': response.citations,
            'links': response.links,
            'used_features': response.used_features,
            'risk_refs': response.risk_refs,
            'actions': response.actions,
            'audit': response.audit
        }

        # Log metrics (privacy-safe)
        _log_qa_metrics(question, response.audit, case_id)

        logger.info(f"Processed Q+A for case {case_id}, tools: {response.audit.get('tools_used', [])}")
        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error processing Q+A request: {e}")
        return jsonify({'error': 'Failed to process question'}), 500

@qa_bp.route('/dose-calc', methods=['POST'])
def calculate_dose():
    """
    Calculate drug dose and volume

    POST /api/qa/dose-calc
    Body: {
        drug: string,
        weight_kg: number,
        concentration: string
    }
    """
    try:
        if not qa_service:
            return jsonify({'error': 'Q+A service not available'}), 500

        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request data required'}), 400

        drug = data.get('drug')
        weight_kg = data.get('weight_kg')
        concentration = data.get('concentration')

        if not all([drug, weight_kg, concentration]):
            return jsonify({'error': 'drug, weight_kg, and concentration required'}), 400

        if not isinstance(weight_kg, (int, float)) or weight_kg <= 0:
            return jsonify({'error': 'weight_kg must be a positive number'}), 400

        result = qa_service.dose_math(weight_kg, drug, concentration)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error calculating dose: {e}")
        return jsonify({'error': 'Failed to calculate dose'}), 500

@qa_bp.route('/risk-convert', methods=['POST'])
def convert_risk():
    """
    Convert relative risk to absolute risk for patient

    POST /api/qa/risk-convert
    Body: {
        p0: number,           // baseline risk
        effect_type: string,  // "relative_risk", "odds_ratio", "absolute_increase"
        effect_value: number,
        ci?: [number, number] // confidence interval
    }
    """
    try:
        if not qa_service:
            return jsonify({'error': 'Q+A service not available'}), 500

        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request data required'}), 400

        p0 = data.get('p0')
        effect_type = data.get('effect_type')
        effect_value = data.get('effect_value')
        ci = data.get('ci')

        if not all([p0 is not None, effect_type, effect_value is not None]):
            return jsonify({'error': 'p0, effect_type, and effect_value required'}), 400

        if not isinstance(p0, (int, float)) or not 0 <= p0 <= 1:
            return jsonify({'error': 'p0 must be between 0 and 1'}), 400

        if effect_type not in ['relative_risk', 'odds_ratio', 'absolute_increase']:
            return jsonify({'error': 'effect_type must be relative_risk, odds_ratio, or absolute_increase'}), 400

        result = qa_service.risk_convert(p0, effect_type, effect_value, ci)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error converting risk: {e}")
        return jsonify({'error': 'Failed to convert risk'}), 500

@qa_bp.route('/features', methods=['POST'])
def identify_features():
    """
    Identify relevant patient features from text

    POST /api/qa/features
    Body: {
        text: string,
        case_id?: string
    }
    """
    try:
        if not qa_service:
            return jsonify({'error': 'Q+A service not available'}), 500

        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({'error': 'text required'}), 400

        text = data['text']
        case_id = data.get('case_id')

        # Load case bundle if available
        if case_id:
            case_bundle = _get_case_bundle(case_id)
            if case_bundle:
                qa_service.load_case_bundle(case_bundle)

        features = qa_service._identify_features(text)

        return jsonify({
            'features': features,
            'text': text
        })

    except Exception as e:
        logger.error(f"Error identifying features: {e}")
        return jsonify({'error': 'Failed to identify features'}), 500

@qa_bp.route('/config', methods=['GET'])
def get_qa_config():
    """Get Q+A service configuration"""
    try:
        if not qa_service:
            return jsonify({'error': 'Q+A service not available'}), 500

        config_data = {
            'allow_domains': qa_service.config.allow_domains,
            'cache_hours': qa_service.config.cache_hours,
            'max_results': qa_service.config.max_results,
            'recency_days_default': qa_service.config.recency_days_default,
            'dose_limits': qa_service.dose_limits
        }

        return jsonify(config_data)

    except Exception as e:
        logger.error(f"Error getting Q+A config: {e}")
        return jsonify({'error': 'Failed to get configuration'}), 500

@qa_bp.route('/cache/stats', methods=['GET'])
def get_cache_stats():
    """Get guideline cache statistics"""
    try:
        if not qa_service:
            return jsonify({'error': 'Q+A service not available'}), 500

        cache_size = len(qa_service.guideline_cache)

        # Count cache hits/misses (would be tracked in production)
        stats = {
            'cache_size': cache_size,
            'cache_hours': qa_service.config.cache_hours,
            'cached_guidelines': list(qa_service.guideline_cache.keys())
        }

        return jsonify(stats)

    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return jsonify({'error': 'Failed to get cache statistics'}), 500

# Helper functions

def _get_case_bundle(case_id: str) -> Dict[str, Any]:
    """
    Get case bundle data for the case
    In production, this would query the database
    For now, return mock data or use app state
    """
    try:
        # Try to get current app state (if available)
        # This is a simplified approach - in production you'd have
        # a proper case management system

        # Mock case bundle structure
        mock_bundle = {
            'hpi_features': {
                'age': '45',
                'weight_kg': 70,
                'surgery_domain': 'orthopedic',
                'urgency': 'elective',
                'meridian_codes': ['ASTHMA', 'DIABETES', 'HTN']
            },
            'risk_summary': {
                'risks': [
                    {
                        'outcome_label': 'Bronchospasm',
                        'window': 'intraop',
                        'baseline_risk': 0.02,
                        'adjusted_risk': 0.08,
                        'evidence_grade': 'B'
                    },
                    {
                        'outcome_label': 'Hypotension',
                        'window': 'intraop',
                        'baseline_risk': 0.15,
                        'adjusted_risk': 0.25,
                        'evidence_grade': 'A'
                    }
                ]
            },
            'med_plan': {
                'recommended': [],
                'contraindicated': [],
                'alternatives': []
            },
            'evidence_cards': {
                'asra_neuraxial_2023': {
                    'title': 'ASRA Neuraxial Anesthesia and Anticoagulation Guidelines',
                    'organization': 'ASRA',
                    'pub_date': '2023',
                    'section': 'Anticoagulation Management',
                    'url': 'https://asra.com/guidelines-articles/2023/04/01/asra-neuraxial-anesthesia-and-anticoagulation-guidelines',
                    'confidence': 'A',
                    'content': 'Guidelines for neuraxial anesthesia in anticoagulated patients...'
                }
            }
        }

        return mock_bundle

    except Exception as e:
        logger.error(f"Error getting case bundle for {case_id}: {e}")
        return {}

def _log_qa_metrics(question: str, audit: Dict[str, Any], case_id: str) -> None:
    """
    Log privacy-safe Q+A metrics for analytics
    Never log the actual question text or PHI
    """
    try:
        metrics = {
            'timestamp': audit.get('timestamp'),
            'question_hash': audit.get('question_hash'),
            'tools_used': audit.get('tools_used', []),
            'web_sources_count': len(audit.get('web_sources', [])),
            'dose_calcs_count': len(audit.get('dose_calcs', [])),
            'response_length': len(audit.get('grounding_snippets', [])),
            'used_web_guidelines': 'used_web_guidelines:true' in audit.get('flags', []),
            'case_id_hash': case_id[:8] if case_id else None  # Truncated for privacy
        }

        # In production, send to analytics service
        logger.info(f"Q+A metrics", extra=metrics)

    except Exception as e:
        logger.warning(f"Failed to log Q+A metrics: {e}")

# Error handlers

@qa_bp.errorhandler(422)
def handle_off_allowlist(error):
    """Handle off-allowlist requests"""
    return jsonify({
        'error': 'Request references sources outside allowed domains',
        'allowed_domains': qa_service.config.allow_domains if qa_service else [],
        'suggestions': [
            'Use society guidelines (ASA, ASRA, etc.)',
            'Reference PubMed literature',
            'Consult institutional protocols'
        ]
    }), 422

@qa_bp.errorhandler(409)
def handle_missing_data(error):
    """Handle missing case bundle data"""
    return jsonify({
        'error': 'Required case data missing',
        'required_fields': [
            'hpi_features',
            'risk_summary',
            'med_plan'
        ]
    }), 409