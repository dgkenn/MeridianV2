"""
CME (Continuing Medical Education) Record Management
Handles certificate generation and credit tracking
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
import uuid
import json


class CMECreditType(Enum):
    """Types of CME credits"""
    AMA_PRA_CATEGORY_1 = "ama_pra_category_1"
    SPECIALTY_CREDIT = "specialty_credit"
    SELF_DIRECTED = "self_directed"


class CMEAccreditation(Enum):
    """Accrediting bodies"""
    ACCME = "accme"
    STATE_MEDICAL_SOCIETY = "state_medical_society"
    SPECIALTY_SOCIETY = "specialty_society"


@dataclass
class CMEActivity:
    """Individual CME activity details"""
    activity_id: str
    title: str
    description: str
    credit_hours: float
    credit_type: CMECreditType
    accreditation: CMEAccreditation

    # Learning objectives
    learning_objectives: List[str]

    # Session details
    session_id: str
    questions_answered: int
    score_achieved: float  # 0.0 to 1.0
    time_spent_minutes: int

    # Requirements
    minimum_score: float = 0.70  # 70% minimum
    minimum_time_minutes: int = 30
    minimum_questions: int = 10

    @property
    def meets_requirements(self) -> bool:
        """Check if activity meets CME requirements"""
        return (
            self.score_achieved >= self.minimum_score and
            self.time_spent_minutes >= self.minimum_time_minutes and
            self.questions_answered >= self.minimum_questions
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'activity_id': self.activity_id,
            'title': self.title,
            'description': self.description,
            'credit_hours': self.credit_hours,
            'credit_type': self.credit_type.value,
            'accreditation': self.accreditation.value,
            'learning_objectives': self.learning_objectives,
            'session_id': self.session_id,
            'questions_answered': self.questions_answered,
            'score_achieved': self.score_achieved,
            'time_spent_minutes': self.time_spent_minutes,
            'minimum_score': self.minimum_score,
            'minimum_time_minutes': self.minimum_time_minutes,
            'minimum_questions': self.minimum_questions,
            'meets_requirements': self.meets_requirements
        }


@dataclass
class CMEParticipant:
    """CME participant information"""
    participant_id: str
    name: str
    email: str
    medical_license_number: Optional[str] = None
    npi_number: Optional[str] = None
    specialty: Optional[str] = None
    institution: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'participant_id': self.participant_id,
            'name': self.name,
            'email': self.email,
            'medical_license_number': self.medical_license_number,
            'npi_number': self.npi_number,
            'specialty': self.specialty,
            'institution': self.institution
        }


@dataclass
class CMERecord:
    """
    Complete CME record for certificate generation
    """
    record_id: str
    participant: CMEParticipant
    activity: CMEActivity

    # Completion details
    completed_at: datetime
    certificate_generated: bool = False
    certificate_id: Optional[str] = None

    # Verification
    verification_code: str = field(default_factory=lambda: str(uuid.uuid4())[:8].upper())

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def is_valid(self) -> bool:
        """Check if CME record is valid for certificate generation"""
        return (
            self.activity.meets_requirements and
            self.completed_at is not None
        )

    @property
    def certificate_title(self) -> str:
        """Generate certificate title"""
        return f"Meridian Learning Module - {self.activity.title}"

    def generate_certificate_data(self) -> Dict[str, Any]:
        """Generate data for certificate template"""
        return {
            'certificate_id': self.certificate_id or str(uuid.uuid4()),
            'participant_name': self.participant.name,
            'activity_title': self.activity.title,
            'credit_hours': self.activity.credit_hours,
            'credit_type_display': self._format_credit_type(),
            'completion_date': self.completed_at.strftime('%B %d, %Y'),
            'score_percentage': f"{self.activity.score_achieved:.1%}",
            'time_spent': f"{self.activity.time_spent_minutes} minutes",
            'questions_answered': self.activity.questions_answered,
            'verification_code': self.verification_code,
            'learning_objectives': self.activity.learning_objectives,
            'accreditation_statement': self._get_accreditation_statement(),
            'generated_date': datetime.now().strftime('%B %d, %Y'),
            'valid_through': (datetime.now() + timedelta(days=365*3)).strftime('%B %d, %Y')  # 3 years
        }

    def _format_credit_type(self) -> str:
        """Format credit type for display"""
        credit_map = {
            CMECreditType.AMA_PRA_CATEGORY_1: "AMA PRA Category 1 Credit™",
            CMECreditType.SPECIALTY_CREDIT: "Specialty Board Credit",
            CMECreditType.SELF_DIRECTED: "Self-Directed Learning Credit"
        }
        return credit_map.get(self.activity.credit_type, "CME Credit")

    def _get_accreditation_statement(self) -> str:
        """Get appropriate accreditation statement"""
        statements = {
            CMEAccreditation.ACCME: (
                "This activity has been planned and implemented in accordance with the "
                "accreditation requirements and policies of the Accreditation Council for "
                "Continuing Medical Education (ACCME)."
            ),
            CMEAccreditation.STATE_MEDICAL_SOCIETY: (
                "This activity has been approved by the State Medical Society for "
                "continuing medical education credit."
            ),
            CMEAccreditation.SPECIALTY_SOCIETY: (
                "This activity has been approved by the relevant specialty society for "
                "continuing medical education credit."
            )
        }
        return statements.get(
            self.activity.accreditation,
            "This activity meets the criteria for continuing medical education."
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'record_id': self.record_id,
            'participant': self.participant.to_dict(),
            'activity': self.activity.to_dict(),
            'completed_at': self.completed_at.isoformat(),
            'certificate_generated': self.certificate_generated,
            'certificate_id': self.certificate_id,
            'verification_code': self.verification_code,
            'created_at': self.created_at.isoformat(),
            'is_valid': self.is_valid
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CMERecord':
        """Create from dictionary"""
        participant = CMEParticipant(
            participant_id=data['participant']['participant_id'],
            name=data['participant']['name'],
            email=data['participant']['email'],
            medical_license_number=data['participant'].get('medical_license_number'),
            npi_number=data['participant'].get('npi_number'),
            specialty=data['participant'].get('specialty'),
            institution=data['participant'].get('institution')
        )

        activity = CMEActivity(
            activity_id=data['activity']['activity_id'],
            title=data['activity']['title'],
            description=data['activity']['description'],
            credit_hours=data['activity']['credit_hours'],
            credit_type=CMECreditType(data['activity']['credit_type']),
            accreditation=CMEAccreditation(data['activity']['accreditation']),
            learning_objectives=data['activity']['learning_objectives'],
            session_id=data['activity']['session_id'],
            questions_answered=data['activity']['questions_answered'],
            score_achieved=data['activity']['score_achieved'],
            time_spent_minutes=data['activity']['time_spent_minutes'],
            minimum_score=data['activity'].get('minimum_score', 0.70),
            minimum_time_minutes=data['activity'].get('minimum_time_minutes', 30),
            minimum_questions=data['activity'].get('minimum_questions', 10)
        )

        return cls(
            record_id=data['record_id'],
            participant=participant,
            activity=activity,
            completed_at=datetime.fromisoformat(data['completed_at']),
            certificate_generated=data.get('certificate_generated', False),
            certificate_id=data.get('certificate_id'),
            verification_code=data.get('verification_code', str(uuid.uuid4())[:8].upper()),
            created_at=datetime.fromisoformat(data['created_at'])
        )

    @staticmethod
    def generate_id() -> str:
        """Generate unique record ID"""
        return f"CME_{datetime.now().strftime('%Y%m%d')}_{str(uuid.uuid4())[:8].upper()}"


class CMECertificateGenerator:
    """Generates CME certificates from completed sessions"""

    def __init__(self):
        self.learning_objectives = {
            'anatomy_airway': [
                "Identify key anatomical landmarks for airway management",
                "Recognize predictors of difficult airway",
                "Apply evidence-based algorithms for airway management"
            ],
            'hemodynamics': [
                "Understand cardiovascular physiology in perioperative period",
                "Manage hemodynamic instability during anesthesia",
                "Apply monitoring strategies for high-risk patients"
            ],
            'pharmacology': [
                "Apply pharmacokinetic principles to anesthetic practice",
                "Recognize drug interactions in perioperative care",
                "Optimize medication dosing for patient safety"
            ],
            'regional': [
                "Understand anatomy relevant to regional anesthesia",
                "Apply ultrasound guidance for nerve blocks",
                "Recognize and manage complications of regional techniques"
            ],
            'pediatric': [
                "Apply age-specific considerations in pediatric anesthesia",
                "Manage unique physiologic challenges in children",
                "Ensure safe anesthetic care for pediatric patients"
            ]
        }

    def create_cme_record_from_session(
        self,
        session: 'LearningSession',
        participant: CMEParticipant,
        session_feedback: 'SessionFeedback'
    ) -> Optional[CMERecord]:
        """Create CME record from completed learning session"""

        if not session.is_completed:
            return None

        # Determine credit hours based on time spent and questions
        credit_hours = self._calculate_credit_hours(
            session_feedback.total_time_sec,
            len(session.item_ids)
        )

        # Generate learning objectives based on session domains
        objectives = self._generate_learning_objectives(session)

        # Create activity
        activity = CMEActivity(
            activity_id=f"MERIDIAN_{session.session_id}",
            title=f"{session.mode.value.title()} Practice Questions",
            description=f"Board-style MCQ practice in anesthesiology ({session.mode.value})",
            credit_hours=credit_hours,
            credit_type=CMECreditType.AMA_PRA_CATEGORY_1,
            accreditation=CMEAccreditation.ACCME,
            learning_objectives=objectives,
            session_id=session.session_id,
            questions_answered=len(session.responses),
            score_achieved=session_feedback.score,
            time_spent_minutes=session_feedback.total_time_sec // 60
        )

        # Only create record if requirements are met
        if not activity.meets_requirements:
            return None

        record = CMERecord(
            record_id=CMERecord.generate_id(),
            participant=participant,
            activity=activity,
            completed_at=session.completed_at or datetime.now()
        )

        return record

    def _calculate_credit_hours(self, time_seconds: int, num_questions: int) -> float:
        """Calculate appropriate credit hours"""

        # Base credit on time spent (minimum 30 minutes = 0.5 credits)
        time_minutes = time_seconds // 60
        time_credits = max(0.5, time_minutes / 60.0)

        # Base credit on number of questions (10 questions = 0.5 credits)
        question_credits = max(0.5, num_questions / 20.0)

        # Use the higher of the two, capped at 2.0 credits
        credit_hours = min(2.0, max(time_credits, question_credits))

        # Round to nearest 0.25
        return round(credit_hours * 4) / 4

    def _generate_learning_objectives(self, session: 'LearningSession') -> List[str]:
        """Generate learning objectives based on session content"""

        # Get domain weights from session
        weights = session.blueprint_weights.to_dict()

        # Find top 3 domains by weight
        top_domains = sorted(weights.items(), key=lambda x: x[1], reverse=True)[:3]

        objectives = []
        for domain, weight in top_domains:
            if weight > 0.05:  # Only include domains with >5% weight
                domain_objectives = self.learning_objectives.get(domain, [])
                if domain_objectives:
                    objectives.extend(domain_objectives[:2])  # Max 2 per domain

        # Add general objectives
        objectives.extend([
            "Apply evidence-based medicine to clinical decision making",
            "Demonstrate critical thinking in complex clinical scenarios"
        ])

        return objectives[:6]  # Maximum 6 objectives

    def generate_certificate_html(self, record: CMERecord) -> str:
        """Generate HTML certificate"""

        cert_data = record.generate_certificate_data()

        html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <title>CME Certificate - {cert_data['participant_name']}</title>
    <style>
        body {{
            font-family: 'Georgia', serif;
            max-width: 800px;
            margin: 40px auto;
            padding: 40px;
            border: 3px solid #2c3e50;
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        }}
        .header {{
            text-align: center;
            margin-bottom: 40px;
            border-bottom: 2px solid #3498db;
            padding-bottom: 20px;
        }}
        .title {{
            font-size: 28px;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 10px;
        }}
        .subtitle {{
            font-size: 18px;
            color: #7f8c8d;
        }}
        .certificate-content {{
            text-align: center;
            margin: 40px 0;
        }}
        .participant-name {{
            font-size: 36px;
            font-weight: bold;
            color: #2980b9;
            margin: 20px 0;
            text-decoration: underline;
        }}
        .completion-text {{
            font-size: 18px;
            line-height: 1.6;
            margin: 20px 0;
        }}
        .details {{
            margin: 30px 0;
            padding: 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .details-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            text-align: left;
        }}
        .detail-item {{
            padding: 8px 0;
            border-bottom: 1px solid #ecf0f1;
        }}
        .detail-label {{
            font-weight: bold;
            color: #34495e;
        }}
        .objectives {{
            text-align: left;
            margin: 20px 0;
        }}
        .objectives ul {{
            list-style-type: disc;
            margin-left: 20px;
        }}
        .footer {{
            margin-top: 40px;
            text-align: center;
            font-size: 12px;
            color: #7f8c8d;
            border-top: 1px solid #bdc3c7;
            padding-top: 20px;
        }}
        .verification {{
            background: #3498db;
            color: white;
            padding: 10px;
            border-radius: 5px;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="title">CERTIFICATE OF COMPLETION</div>
        <div class="subtitle">Continuing Medical Education</div>
    </div>

    <div class="certificate-content">
        <div class="completion-text">
            This is to certify that
        </div>

        <div class="participant-name">
            {cert_data['participant_name']}
        </div>

        <div class="completion-text">
            has successfully completed the educational activity entitled:<br>
            <strong>"{cert_data['activity_title']}"</strong>
        </div>

        <div class="details">
            <div class="details-grid">
                <div class="detail-item">
                    <div class="detail-label">Completion Date:</div>
                    <div>{cert_data['completion_date']}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">CME Credits:</div>
                    <div>{cert_data['credit_hours']} {cert_data['credit_type_display']}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Score Achieved:</div>
                    <div>{cert_data['score_percentage']}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Time Spent:</div>
                    <div>{cert_data['time_spent']}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Questions Completed:</div>
                    <div>{cert_data['questions_answered']}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">Certificate ID:</div>
                    <div>{cert_data['certificate_id']}</div>
                </div>
            </div>
        </div>

        <div class="objectives">
            <strong>Learning Objectives Achieved:</strong>
            <ul>
"""

        for objective in cert_data['learning_objectives']:
            html_template += f"                <li>{objective}</li>\n"

        html_template += f"""
            </ul>
        </div>

        <div class="verification">
            Verification Code: {cert_data['verification_code']}
        </div>
    </div>

    <div class="footer">
        <p>{cert_data['accreditation_statement']}</p>
        <p>Certificate generated on {cert_data['generated_date']} | Valid through {cert_data['valid_through']}</p>
        <p><strong>Meridian Learning Module</strong> - Evidence-Based Medical Education</p>
    </div>
</body>
</html>
        """

        return html_template

    def generate_certificate_pdf(self, record: CMERecord) -> bytes:
        """Generate PDF certificate (requires additional libraries)"""

        # This would require libraries like weasyprint or reportlab
        # For now, return placeholder
        html_content = self.generate_certificate_html(record)

        # In production, convert HTML to PDF:
        # from weasyprint import HTML
        # return HTML(string=html_content).write_pdf()

        return html_content.encode('utf-8')


def validate_cme_eligibility(session: 'LearningSession', feedback: 'SessionFeedback') -> Dict[str, Any]:
    """Validate if session is eligible for CME credit"""

    requirements = {
        'minimum_questions': 10,
        'minimum_score': 0.70,
        'minimum_time_minutes': 30
    }

    checks = {
        'has_enough_questions': len(session.responses) >= requirements['minimum_questions'],
        'meets_score_requirement': feedback.score >= requirements['minimum_score'],
        'meets_time_requirement': feedback.total_time_sec >= (requirements['minimum_time_minutes'] * 60),
        'session_completed': session.is_completed
    }

    all_passed = all(checks.values())

    return {
        'eligible': all_passed,
        'requirements': requirements,
        'checks': checks,
        'estimated_credits': min(2.0, max(0.5, len(session.responses) / 20.0)) if all_passed else 0.0
    }