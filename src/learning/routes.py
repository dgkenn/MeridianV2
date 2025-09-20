"""
Learning module API routes
"""

import logging
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Blueprint, request, jsonify, session as flask_session
from datetime import datetime
from typing import Dict, Any

from .generator import LearningItemGenerator
from .scorer import LearningScorer
from .schemas import LearningMode, UserResponse
from .cme import CMEManager

logger = logging.getLogger(__name__)

# Create blueprint
learning_bp = Blueprint('learning', __name__, url_prefix='/api/learning')

# Initialize components
generator = LearningItemGenerator()
scorer = LearningScorer()
cme_manager = CMEManager()

@learning_bp.route('/generate', methods=['POST'])
def generate_learning_session():
    """
    Generate patient-anchored learning session

    POST /api/learning/generate
    Body: {
        mode: "basics" | "board",
        n_items: number,
        seed?: number,
        case_context: true
    }
    """
    try:
        data = request.get_json()

        # Validate required parameters
        mode_str = data.get('mode', 'basics')
        n_items = data.get('n_items', 6)
        seed = data.get('seed')
        case_context = data.get('case_context', False)

        # Parse mode
        try:
            mode = LearningMode(mode_str.lower())
        except ValueError:
            return jsonify({'error': 'Invalid mode. Use "basics" or "board"'}), 400

        # Validate n_items
        if not isinstance(n_items, int) or n_items < 1 or n_items > 20:
            return jsonify({'error': 'n_items must be between 1 and 20'}), 400

        if not case_context:
            return jsonify({'error': 'case_context must be true for patient-anchored learning'}), 400

        # Get current app state from session or request
        app_state = _get_current_app_state()
        if not app_state:
            return jsonify({'error': 'No current patient case data available'}), 400

        # Generate learning session
        learning_session = generator.generate_session(
            parsed_hpi=app_state.get('parsed_hpi', {}),
            risk_assessments=app_state.get('risk_assessments', []),
            medication_plan=app_state.get('medication_plan', {}),
            mode=mode,
            n_items=n_items,
            seed=seed,
            guidelines=app_state.get('guidelines', [])
        )

        # Convert to response format
        response_data = {
            'session_id': learning_session.session_id,
            'mode': learning_session.mode.value,
            'n_items': learning_session.n_items,
            'blueprint_distribution': {k.value: v for k, v in learning_session.blueprint_distribution.items()},
            'items': [_item_to_response_format(item) for item in learning_session.items],
            'case_hash': learning_session.case_hash,
            'started_at': learning_session.started_at.isoformat()
        }

        # Store session for scoring
        _store_session(learning_session)

        logger.info(f"Generated learning session {learning_session.session_id} with {len(learning_session.items)} items")

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error generating learning session: {e}")
        return jsonify({'error': 'Failed to generate learning session'}), 500

@learning_bp.route('/grade', methods=['POST'])
def grade_learning_session():
    """
    Grade completed learning session

    POST /api/learning/grade
    Body: {
        session_id: string,
        responses: [
            {
                item_id: string,
                selected_answers: number[],
                time_ms: number
            }
        ]
    }
    """
    try:
        data = request.get_json()

        session_id = data.get('session_id')
        responses_data = data.get('responses', [])

        if not session_id:
            return jsonify({'error': 'session_id is required'}), 400

        # Retrieve stored session
        learning_session = _get_stored_session(session_id)
        if not learning_session:
            return jsonify({'error': 'Session not found'}), 404

        # Parse responses
        responses = []
        for resp_data in responses_data:
            # Find item to validate correct answer
            item = next((item for item in learning_session.items
                        if item.item_id == resp_data.get('item_id')), None)

            if not item:
                continue

            # Check if response is correct
            selected = set(resp_data.get('selected_answers', []))
            correct = set(item.correct_keys)
            is_correct = selected == correct

            response = UserResponse(
                item_id=resp_data.get('item_id', ''),
                selected_answers=resp_data.get('selected_answers', []),
                time_ms=resp_data.get('time_ms', 0),
                correct=is_correct
            )
            responses.append(response)

        # Validate responses
        if not scorer.validate_responses(learning_session, responses):
            return jsonify({'error': 'Invalid response format'}), 400

        # Score session
        feedback = scorer.score_session(learning_session, responses)

        # Calculate CME hours
        cme_hours = scorer.calculate_cme_hours(learning_session)
        passes_cme = scorer.passes_cme_threshold(feedback)

        response_data = {
            'session_id': session_id,
            'score': feedback.score,
            'percentage': int(feedback.score * 100),
            'total_time_sec': feedback.total_time_sec,
            'avg_time_per_item': feedback.avg_time_per_item,
            'strengths': feedback.strengths,
            'weaknesses': feedback.weaknesses,
            'recommended_reading': feedback.recommended_reading,
            'item_feedback': feedback.item_feedback,
            'cme_hours': cme_hours,
            'passes_cme_threshold': passes_cme,
            'completed_at': learning_session.completed_at.isoformat() if learning_session.completed_at else None
        }

        logger.info(f"Graded session {session_id}: {feedback.score:.2f} score, {cme_hours:.2f} CME hours")

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error grading learning session: {e}")
        return jsonify({'error': 'Failed to grade learning session'}), 500

@learning_bp.route('/cme/certificate', methods=['POST'])
def generate_cme_certificate():
    """
    Generate CME certificate for completed session

    POST /api/learning/cme/certificate
    Body: {
        session_id: string,
        attestation: true
    }
    """
    try:
        data = request.get_json()

        session_id = data.get('session_id')
        attestation = data.get('attestation', False)

        if not session_id:
            return jsonify({'error': 'session_id is required'}), 400

        if not attestation:
            return jsonify({'error': 'attestation is required for CME certificate'}), 400

        # Retrieve session
        learning_session = _get_stored_session(session_id)
        if not learning_session:
            return jsonify({'error': 'Session not found'}), 404

        if not learning_session.completed_at:
            return jsonify({'error': 'Session must be completed to generate certificate'}), 400

        # Check if passes CME threshold
        if learning_session.score < scorer.passing_threshold:
            return jsonify({'error': 'Session score below CME passing threshold'}), 400

        # Generate certificate
        certificate = cme_manager.generate_certificate(learning_session)

        response_data = {
            'certificate_id': certificate.certificate_id,
            'certificate_url': f'/api/learning/cme/certificates/{certificate.certificate_id}',
            'hours': certificate.hours,
            'issued_at': certificate.issued_at.isoformat(),
            'expires_at': certificate.expires_at.isoformat() if certificate.expires_at else None
        }

        logger.info(f"Generated CME certificate {certificate.certificate_id} for session {session_id}")

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error generating CME certificate: {e}")
        return jsonify({'error': 'Failed to generate CME certificate'}), 500

@learning_bp.route('/report', methods=['POST'])
def report_problem():
    """
    Report a problem with learning module

    POST /api/learning/report
    Body: {
        route: string,
        message: string,
        include_console?: boolean
    }
    """
    try:
        data = request.get_json()

        route = data.get('route', request.referrer or 'unknown')
        message = data.get('message', '')
        include_console = data.get('include_console', False)

        if not message.strip():
            return jsonify({'error': 'message is required'}), 400

        # Create problem report
        report = {
            'route': route,
            'message': message.strip(),
            'timestamp': datetime.utcnow().isoformat(),
            'user_agent': request.headers.get('User-Agent', ''),
            'ip_address': request.remote_addr,
            'include_console': include_console
        }

        # Send email to dgkenn@bu.edu
        email_sent = _send_problem_report_email(report)

        # Store report (in production, would persist to database)
        _store_problem_report(report)

        response_data = {
            'ok': True,
            'report_id': f"LRN_{int(datetime.utcnow().timestamp())}",
            'email_sent': email_sent
        }

        logger.info(f"Problem report submitted: {route} - {message[:100]}")

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error submitting problem report: {e}")
        return jsonify({'error': 'Failed to submit problem report'}), 500

# Helper functions

def _get_current_app_state() -> Dict[str, Any]:
    """Get current app state from session or global state"""
    # In production, this would retrieve current case data
    # For now, return mock data structure
    return flask_session.get('current_case_data', {})

def _store_session(learning_session):
    """Store learning session for later retrieval"""
    # In production, store in database
    # For now, store in session
    if 'learning_sessions' not in flask_session:
        flask_session['learning_sessions'] = {}

    flask_session['learning_sessions'][learning_session.session_id] = learning_session

def _get_stored_session(session_id: str):
    """Retrieve stored learning session"""
    return flask_session.get('learning_sessions', {}).get(session_id)

def _item_to_response_format(item):
    """Convert LearningItem to response format"""
    return {
        'item_id': item.item_id,
        'stem': item.stem,
        'options': item.options,
        'item_type': item.item_type.value,
        'difficulty': item.difficulty.value,
        'domains': [d.value for d in item.domain_tags],
        'patient_anchors': item.patient_anchors
        # Note: Don't include correct_keys or rationale in generation response
    }

def _send_problem_report_email(report: Dict[str, Any]) -> bool:
    """Send problem report email to dgkenn@bu.edu"""
    try:
        # Email configuration (would be in environment variables)
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        sender_email = "noreply@meridian.app"  # Configure appropriately
        sender_password = "app_password"  # Configure appropriately
        recipient_email = "dgkenn@bu.edu"

        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = f"Meridian Learning Module Problem Report - {report['route']}"

        body = f\"\"\"
Problem Report from Meridian Learning Module

Route: {report['route']}
Time: {report['timestamp']}
User Agent: {report['user_agent']}
IP Address: {report['ip_address']}

Message:
{report['message']}

Include Console Logs: {report['include_console']}
\"\"\"

        msg.attach(MIMEText(body, 'plain'))

        # Send email (commented out for development)
        # server = smtplib.SMTP(smtp_server, smtp_port)
        # server.starttls()
        # server.login(sender_email, sender_password)
        # server.send_message(msg)
        # server.quit()

        logger.info(f"Problem report email would be sent to {recipient_email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send problem report email: {e}")
        return False

def _store_problem_report(report: Dict[str, Any]):
    """Store problem report (placeholder for database storage)"""
    # In production, store in database
    logger.info(f"Problem report stored: {json.dumps(report, indent=2)}")

# Set app state for development/testing
@learning_bp.route('/dev/set-case-data', methods=['POST'])
def set_case_data():
    """Development endpoint to set current case data"""
    try:
        data = request.get_json()
        flask_session['current_case_data'] = data
        return jsonify({'ok': True})
    except Exception as e:
        logger.error(f"Error setting case data: {e}")
        return jsonify({'error': 'Failed to set case data'}), 500