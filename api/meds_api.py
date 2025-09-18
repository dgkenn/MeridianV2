#!/usr/bin/env python3
"""
Medication Recommendation API for Meridian
Provides REST endpoints for medication recommendations
"""

from flask import Blueprint, request, jsonify
from typing import Dict, Any
import logging
from pathlib import Path

from nlp.pipeline import parse_hpi
from risk_engine.baseline import BaselineRiskEngine
from risk_engine.schema import RiskConfig, AgeBand, SurgeryType, Urgency, TimeWindow
from services.meds_engine import create_meds_engine, PatientParameters

logger = logging.getLogger(__name__)

# Create Blueprint
meds_api = Blueprint('meds_api', __name__, url_prefix='/api/meds')

# Initialize engines
config = RiskConfig()
risk_engine = BaselineRiskEngine(config)
meds_engine = create_meds_engine()

@meds_api.route('/recommend', methods=['POST'])
def recommend_medications():
    """
    Generate medication recommendations based on HPI and risk assessment

    Request JSON:
    {
        "hpi_text": "4-year-old for T&A with asthma and recent URI",
        "patient_params": {
            "age_years": 4,
            "weight_kg": 18,
            "height_cm": 100,
            "sex": "M",
            "urgency": "elective",
            "surgery_domain": "ENT",
            "allergies": [],
            "renal_function": null,
            "hepatic_function": null
        },
        "risk_assessment_params": {
            "age_band": "4-6",
            "surgery_type": "ENT",
            "urgency": "elective"
        }
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        hpi_text = data.get('hpi_text', '')
        if not hpi_text:
            return jsonify({'error': 'hpi_text is required'}), 400

        # Parse HPI
        parsed_hpi = parse_hpi(hpi_text)

        # Extract patient parameters
        patient_data = data.get('patient_params', {})
        patient_params = PatientParameters(
            age_years=patient_data.get('age_years'),
            weight_kg=patient_data.get('weight_kg'),
            height_cm=patient_data.get('height_cm'),
            sex=patient_data.get('sex'),
            urgency=patient_data.get('urgency', 'elective'),
            surgery_domain=patient_data.get('surgery_domain'),
            allergies=patient_data.get('allergies', []),
            renal_function=patient_data.get('renal_function'),
            hepatic_function=patient_data.get('hepatic_function'),
            npo_status=patient_data.get('npo_status')
        )

        # Perform risk assessment
        risk_assessment_params = data.get('risk_assessment_params', {})
        risk_summary = calculate_risk_summary(parsed_hpi, risk_assessment_params)

        # Generate medication recommendations
        recommendations = meds_engine.generate_recommendations(
            parsed_hpi=parsed_hpi,
            risk_summary=risk_summary,
            patient_params=patient_params
        )

        return jsonify(recommendations)

    except Exception as e:
        logger.error(f"Error in medication recommendation: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500

@meds_api.route('/dose-calculator', methods=['POST'])
def calculate_dose():
    """
    Calculate dose for specific medication

    Request JSON:
    {
        "agent": "Ondansetron",
        "weight_kg": 18,
        "age_years": 4,
        "indication": "PONV_prophylaxis",
        "route": "IV",
        "renal_function": null,
        "hepatic_function": null
    }
    """
    try:
        data = request.get_json()

        agent = data.get('agent')
        weight_kg = data.get('weight_kg')
        age_years = data.get('age_years')

        if not all([agent, weight_kg, age_years]):
            return jsonify({'error': 'agent, weight_kg, and age_years are required'}), 400

        # Create patient parameters
        patient_params = PatientParameters(
            age_years=age_years,
            weight_kg=weight_kg,
            renal_function=data.get('renal_function'),
            hepatic_function=data.get('hepatic_function')
        )

        # Calculate dose using meds engine
        dose_calc = meds_engine._calculate_dose(
            agent=agent,
            dose_info=meds_engine.dosing_rules.get('dosing_rules', {}).get(agent, {}),
            patient_params=patient_params
        )

        if not dose_calc:
            return jsonify({'error': f'Could not calculate dose for {agent}'}), 400

        # Get preparation instructions
        prep_instructions = meds_engine._get_preparation_instructions(
            agent, dose_calc, patient_params
        )

        response = {
            'agent': agent,
            'dose_calculation': {
                'mg': dose_calc.mg,
                'mcg': dose_calc.mcg,
                'volume_ml': dose_calc.volume_ml,
                'concentration': dose_calc.concentration
            },
            'preparation_instructions': prep_instructions,
            'route': data.get('route', 'IV')
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error in dose calculation: {e}")
        return jsonify({
            'error': 'Dose calculation failed',
            'message': str(e)
        }), 500

@meds_api.route('/check-contraindications', methods=['POST'])
def check_contraindications():
    """
    Check contraindications for specific medications

    Request JSON:
    {
        "agents": ["Succinylcholine", "Propofol"],
        "features": ["MH_HISTORY", "ASTHMA"],
        "allergies": ["EGG_SOY_ALLERGY"],
        "age_years": 4,
        "weight_kg": 18
    }
    """
    try:
        data = request.get_json()

        agents = data.get('agents', [])
        features = data.get('features', [])
        allergies = data.get('allergies', [])

        patient_params = PatientParameters(
            age_years=data.get('age_years'),
            weight_kg=data.get('weight_kg'),
            allergies=allergies
        )

        results = {}

        for agent in agents:
            # Find medication class for this agent
            med_class = None
            for class_name, class_info in meds_engine.formulary.get('medication_classes', {}).items():
                if agent in class_info.get('agents', {}):
                    med_class = class_name
                    break

            if med_class:
                is_contraindicated, reason = meds_engine._check_contraindications(
                    agent, med_class, features, patient_params
                )

                results[agent] = {
                    'contraindicated': is_contraindicated,
                    'reason': reason,
                    'alternatives': meds_engine._get_alternatives(med_class, features, patient_params) if is_contraindicated else []
                }
            else:
                results[agent] = {
                    'contraindicated': None,
                    'reason': 'Agent not found in formulary',
                    'alternatives': []
                }

        return jsonify({
            'contraindication_results': results
        })

    except Exception as e:
        logger.error(f"Error checking contraindications: {e}")
        return jsonify({
            'error': 'Contraindication check failed',
            'message': str(e)
        }), 500

@meds_api.route('/formulary', methods=['GET'])
def get_formulary():
    """Get available medications in formulary"""
    try:
        formulary_summary = {}

        for class_name, class_info in meds_engine.formulary.get('medication_classes', {}).items():
            agents = list(class_info.get('agents', {}).keys())
            preferred = class_info.get('preferred_agent')

            formulary_summary[class_name] = {
                'preferred_agent': preferred,
                'available_agents': agents,
                'agent_count': len(agents)
            }

        return jsonify({
            'medication_classes': formulary_summary,
            'total_classes': len(formulary_summary)
        })

    except Exception as e:
        logger.error(f"Error retrieving formulary: {e}")
        return jsonify({
            'error': 'Formulary retrieval failed',
            'message': str(e)
        }), 500

@meds_api.route('/guidelines/<outcome>', methods=['GET'])
def get_guidelines(outcome: str):
    """Get guideline information for specific outcome"""
    try:
        outcome_upper = outcome.upper()
        guideline_info = meds_engine.guideline_map.get('guideline_mapping', {}).get(outcome_upper, {})

        if not guideline_info:
            return jsonify({'error': f'No guidelines found for {outcome}'}), 404

        return jsonify({
            'outcome': outcome_upper,
            'guidelines': guideline_info
        })

    except Exception as e:
        logger.error(f"Error retrieving guidelines for {outcome}: {e}")
        return jsonify({
            'error': 'Guideline retrieval failed',
            'message': str(e)
        }), 500

def calculate_risk_summary(parsed_hpi: Any, risk_params: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate risk summary for medication recommendations"""
    try:
        # Extract risk calculation parameters
        age_band_str = risk_params.get('age_band', '7-12')
        surgery_type_str = risk_params.get('surgery_type', 'General')
        urgency_str = risk_params.get('urgency', 'elective')

        # Convert to enums
        age_band = AgeBand(age_band_str)
        surgery_type = SurgeryType(surgery_type_str)
        urgency = Urgency(urgency_str)

        # Calculate risks for key outcomes
        outcomes = ['LARYNGOSPASM', 'BRONCHOSPASM', 'PONV', 'HYPOTENSION']
        risks = {}

        for outcome in outcomes:
            try:
                baseline = risk_engine.get_baseline_risk(
                    outcome=outcome,
                    window=TimeWindow.INTRAOP,
                    age_band=age_band,
                    surgery=surgery_type,
                    urgency=urgency
                )

                if baseline:
                    # For now, use baseline as absolute risk
                    # In full implementation, this would include risk modifiers
                    risks[outcome] = {
                        'absolute_risk': baseline.p0,
                        'delta_vs_baseline': 0.0,  # Would be calculated with risk modifiers
                        'confidence': 'B'  # Would be determined by evidence quality
                    }
                else:
                    # Default minimal risk if no baseline found
                    risks[outcome] = {
                        'absolute_risk': 0.01,
                        'delta_vs_baseline': 0.0,
                        'confidence': 'C'
                    }

            except Exception as e:
                logger.warning(f"Could not calculate risk for {outcome}: {e}")
                risks[outcome] = {
                    'absolute_risk': 0.05,  # Conservative default
                    'delta_vs_baseline': 0.0,
                    'confidence': 'D'
                }

        return {'risks': risks}

    except Exception as e:
        logger.error(f"Error calculating risk summary: {e}")
        return {'risks': {}}

# Error handlers
@meds_api.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@meds_api.errorhandler(405)
def method_not_allowed(error):
    return jsonify({'error': 'Method not allowed'}), 405

@meds_api.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500