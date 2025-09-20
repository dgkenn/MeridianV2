#!/usr/bin/env python3
"""
Risk Display API - Endpoints for patient-centric risk organization and display
"""

import logging
from flask import Blueprint, request, jsonify
from typing import Dict, List, Any
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.risk_display import RiskDisplayService

logger = logging.getLogger(__name__)

# Create blueprint
risk_display_bp = Blueprint('risk_display', __name__, url_prefix='/api/risk')

# Initialize service
try:
    risk_display_service = RiskDisplayService()
    logger.info("Risk display service initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize risk display service: {e}")
    risk_display_service = None

@risk_display_bp.route('/score', methods=['POST'])
def organize_risk_scores():
    """
    Organize risk scores for patient-centric display

    POST /api/risk/score
    Body: {
        risk_outcomes: [
            {
                outcome: string,
                outcome_label: string,
                window: string,
                baseline_risk: float,
                adjusted_risk: float,
                risk_difference: float,
                evidence_grade: string,
                has_mitigation?: boolean,
                is_time_critical?: boolean,
                is_applicable?: boolean,
                is_calibrated?: boolean,
                baseline_banner?: boolean
            }
        ]
    }

    Returns: {
        top_strip: RiskOutcome[],
        organ_groups: {[organ]: RiskOutcome[]},
        hidden_count: number,
        total_outcomes: number,
        priority_stats: object,
        config_snapshot: object
    }
    """
    try:
        if not risk_display_service:
            return jsonify({'error': 'Risk display service not available'}), 500

        data = request.get_json()
        if not data or 'risk_outcomes' not in data:
            return jsonify({'error': 'risk_outcomes required'}), 400

        risk_outcomes = data['risk_outcomes']
        if not isinstance(risk_outcomes, list):
            return jsonify({'error': 'risk_outcomes must be an array'}), 400

        # Validate and enrich risk outcomes
        enriched_outcomes = _enrich_risk_outcomes(risk_outcomes)

        # Compute priorities and organize
        prioritized_outcomes = risk_display_service.compute_risk_priorities(enriched_outcomes)
        organized_display = risk_display_service.organize_for_display(prioritized_outcomes)

        # Add individual outcome data for frontend
        organized_display['outcomes'] = [_outcome_to_dict(o) for o in prioritized_outcomes]

        # Emit telemetry
        if risk_display_service.config:
            risk_display_service.emit_telemetry_event('risk_display_rendered', {
                'total_outcomes': organized_display['total_outcomes'],
                'top_strip_count': len(organized_display['top_strip']),
                'organ_groups_count': len(organized_display['organ_groups']),
                'hidden_count': organized_display['hidden_count'],
                'variant': organized_display['config_snapshot']['variant']
            })

        logger.info(f"Organized {len(prioritized_outcomes)} risk outcomes for display")
        return jsonify(organized_display)

    except Exception as e:
        logger.error(f"Error organizing risk scores: {e}")
        return jsonify({'error': 'Failed to organize risk scores'}), 500

@risk_display_bp.route('/hidden', methods=['POST'])
def get_hidden_risks():
    """
    Get hidden risk outcomes, optionally filtered by search

    POST /api/risk/hidden
    Body: {
        risk_outcomes: RiskOutcome[],
        search_term?: string
    }
    """
    try:
        if not risk_display_service:
            return jsonify({'error': 'Risk display service not available'}), 500

        data = request.get_json()
        if not data or 'risk_outcomes' not in data:
            return jsonify({'error': 'risk_outcomes required'}), 400

        risk_outcomes = data['risk_outcomes']
        search_term = data.get('search_term')

        # Process outcomes through service
        enriched_outcomes = _enrich_risk_outcomes(risk_outcomes)
        prioritized_outcomes = risk_display_service.compute_risk_priorities(enriched_outcomes)
        risk_display_service.organize_for_display(prioritized_outcomes)

        # Get hidden outcomes
        hidden_outcomes = risk_display_service.get_hidden_outcomes(
            prioritized_outcomes, search_term
        )

        # Emit telemetry
        risk_display_service.emit_telemetry_event('hidden_risks_searched', {
            'search_term': search_term,
            'results_count': len(hidden_outcomes)
        })

        return jsonify({
            'hidden_outcomes': [_outcome_to_dict(o) for o in hidden_outcomes],
            'search_term': search_term,
            'total_hidden': len([o for o in prioritized_outcomes if o.show_section == "hidden"])
        })

    except Exception as e:
        logger.error(f"Error getting hidden risks: {e}")
        return jsonify({'error': 'Failed to get hidden risks'}), 500

@risk_display_bp.route('/config', methods=['GET'])
def get_risk_display_config():
    """Get current risk display configuration"""
    try:
        if not risk_display_service:
            return jsonify({'error': 'Risk display service not available'}), 500

        config = risk_display_service.config

        return jsonify({
            'display_thresholds': {
                'min_show_phat': config.min_show_phat,
                'min_show_delta_pp': config.min_show_delta_pp,
                'hide_floor_phat': config.hide_floor_phat,
                'hide_floor_delta_pp': config.hide_floor_delta_pp,
                'confidence_hide': config.confidence_hide,
                'top_overall': config.top_overall,
                'top_per_organ': config.top_per_organ
            },
            'priority_weights': {
                'w_phat': config.w_phat,
                'w_delta': config.w_delta,
                'w_conf': config.w_conf,
                'w_mod': config.w_mod,
                'w_time': config.w_time,
                'w_cal': config.w_cal
            },
            'variant': config.variant,
            'last_updated': config.last_updated,
            'weights_valid': risk_display_service.validate_weights()
        })

    except Exception as e:
        logger.error(f"Error getting config: {e}")
        return jsonify({'error': 'Failed to get configuration'}), 500

@risk_display_bp.route('/config', methods=['POST'])
def update_risk_display_config():
    """
    Update risk display configuration at runtime

    POST /api/risk/config
    Body: {
        min_show_phat?: float,
        min_show_delta_pp?: float,
        w_phat?: float,
        // ... other config fields
    }
    """
    try:
        if not risk_display_service:
            return jsonify({'error': 'Risk display service not available'}), 500

        data = request.get_json()
        if not data:
            return jsonify({'error': 'Configuration updates required'}), 400

        # Validate numeric ranges
        for key, value in data.items():
            if key.startswith('w_') and (value < 0 or value > 1):
                return jsonify({'error': f'Weight {key} must be between 0 and 1'}), 400
            if key.endswith('_phat') and (value < 0 or value > 1):
                return jsonify({'error': f'Risk threshold {key} must be between 0 and 1'}), 400

        # Update configuration
        success = risk_display_service.update_config(data)

        if not success:
            return jsonify({'error': 'Failed to update configuration'}), 500

        # Validate weights after update
        weights_valid = risk_display_service.validate_weights()
        if not weights_valid:
            return jsonify({'error': 'Updated weights do not sum to 1.0'}), 400

        # Emit telemetry
        risk_display_service.emit_telemetry_event('config_updated', {
            'updates': data,
            'variant': risk_display_service.config.variant
        })

        logger.info(f"Updated risk display config: {data}")

        return jsonify({
            'success': True,
            'updated_fields': list(data.keys()),
            'weights_valid': weights_valid,
            'timestamp': risk_display_service.config.last_updated
        })

    except Exception as e:
        logger.error(f"Error updating config: {e}")
        return jsonify({'error': 'Failed to update configuration'}), 500

@risk_display_bp.route('/telemetry', methods=['POST'])
def log_risk_interaction():
    """
    Log user interactions for A/B testing and optimization

    POST /api/risk/telemetry
    Body: {
        event_type: "risk_tile_clicked" | "mitigation_link_clicked" | "organ_tab_selected",
        outcome: string,
        section: "top" | "organ" | "hidden",
        dwell_time_ms?: number,
        additional_data?: object
    }
    """
    try:
        if not risk_display_service:
            return jsonify({'error': 'Risk display service not available'}), 500

        data = request.get_json()
        if not data or 'event_type' not in data:
            return jsonify({'error': 'event_type required'}), 400

        event_type = data['event_type']
        allowed_events = [
            'risk_tile_clicked',
            'mitigation_link_clicked',
            'organ_tab_selected',
            'show_all_toggled',
            'search_hidden_used'
        ]

        if event_type not in allowed_events:
            return jsonify({'error': f'Invalid event_type. Must be one of: {allowed_events}'}), 400

        # Emit telemetry event
        risk_display_service.emit_telemetry_event(event_type, data)

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Error logging telemetry: {e}")
        return jsonify({'error': 'Failed to log interaction'}), 500

# Helper functions

def _enrich_risk_outcomes(risk_outcomes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Enrich risk outcomes with default values and computed fields"""
    enriched = []

    for outcome in risk_outcomes:
        # Set defaults for optional fields
        enriched_outcome = {
            'has_mitigation': False,
            'is_time_critical': False,
            'is_applicable': True,
            'is_calibrated': False,
            'baseline_banner': False,
            **outcome  # Override with provided values
        }

        # Compute baseline banner flag based on high baseline risk
        baseline_risk = enriched_outcome.get('baseline_risk', 0.0)
        if baseline_risk > 0.05:  # 5% baseline triggers banner
            enriched_outcome['baseline_banner'] = True

        # Determine time-critical based on outcome type
        outcome_name = enriched_outcome.get('outcome', '').upper()
        time_critical_outcomes = {
            'ANAPHYLAXIS', 'MALIGNANT_HYPERTHERMIA', 'CARDIAC_ARREST',
            'ASPIRATION', 'FAILED_INTUBATION', 'MASSIVE_TRANSFUSION'
        }
        if outcome_name in time_critical_outcomes:
            enriched_outcome['is_time_critical'] = True

        # Determine mitigation availability based on outcome and evidence
        evidence_grade = enriched_outcome.get('evidence_grade', 'D')
        if evidence_grade in ['A', 'B'] and baseline_risk > 0.01:
            enriched_outcome['has_mitigation'] = True

        enriched.append(enriched_outcome)

    return enriched

def _outcome_to_dict(outcome) -> Dict[str, Any]:
    """Convert RiskOutcome object to dictionary for JSON response"""
    return {
        'outcome': outcome.outcome,
        'outcome_label': outcome.outcome_label,
        'window': outcome.window,
        'organ_system': outcome.organ_system,
        'p0': outcome.p0,
        'p_hat': outcome.p_hat,
        'delta_pp': outcome.delta_pp,
        'confidence_score': outcome.confidence_score,
        'confidence_letter': outcome.confidence_letter,
        'has_mitigation': outcome.has_mitigation,
        'is_time_critical': outcome.is_time_critical,
        'is_applicable': outcome.is_applicable,
        'is_calibrated': outcome.is_calibrated,
        'baseline_banner': outcome.baseline_banner,
        'priority': outcome.priority,
        'rank_phat': outcome.rank_phat,
        'rank_delta': outcome.rank_delta,
        'show_section': outcome.show_section,
        'why_shown': outcome.why_shown
    }