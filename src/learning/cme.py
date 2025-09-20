"""
CME certificate generation and management
"""

import uuid
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from .schemas import LearningSession, CMERecord

logger = logging.getLogger(__name__)

class CMEManager:
    """Manages CME certificate generation and tracking"""

    def __init__(self):
        self.accreditor = "Accreditation Council for Graduate Medical Education (ACGME)"
        self.provider = "Meridian Anesthesia Learning Platform"
        self.activity_type = "Knowledge-based"
        self.passing_threshold = 0.7

    def generate_certificate(self, session: LearningSession,
                           user_id: Optional[str] = None) -> CMERecord:
        """
        Generate CME certificate for completed learning session

        Args:
            session: Completed learning session
            user_id: Optional user identifier

        Returns:
            CMERecord with certificate details
        """
        # Validate session is complete and passing
        if not session.completed_at:
            raise ValueError("Session must be completed to generate certificate")

        if not session.score or session.score < self.passing_threshold:
            raise ValueError(f"Session score {session.score:.1%} below passing threshold {self.passing_threshold:.1%}")

        # Calculate CME hours
        hours = self._calculate_cme_hours(session)

        # Generate certificate
        certificate_id = self._generate_certificate_id()
        issued_at = datetime.utcnow()
        expires_at = issued_at + timedelta(days=365 * 3)  # 3 years

        # Determine learning objectives covered
        objectives = self._determine_objectives_covered(session)

        certificate = CMERecord(
            certificate_id=certificate_id,
            session_id=session.session_id,
            user_id=user_id,
            hours=hours,
            passed=True,
            score=session.score,
            objectives_covered=objectives,
            issued_at=issued_at,
            expires_at=expires_at
        )

        logger.info(f"Generated CME certificate {certificate_id} for session {session.session_id}")
        return certificate

    def _calculate_cme_hours(self, session: LearningSession) -> float:
        """Calculate CME hours based on session content and performance"""
        # Base calculation: 15 minutes per item for BASICS, 20 minutes for BOARD
        if session.mode.value == 'board':
            base_minutes_per_item = 20
        else:
            base_minutes_per_item = 15

        total_minutes = len(session.items) * base_minutes_per_item

        # Convert to hours and round to nearest 0.25
        hours = total_minutes / 60
        return round(hours * 4) / 4  # Round to nearest quarter hour

    def _generate_certificate_id(self) -> str:
        """Generate unique certificate ID"""
        timestamp = datetime.utcnow().strftime("%Y%m%d")
        random_suffix = str(uuid.uuid4())[:8].upper()
        return f"MER-{timestamp}-{random_suffix}"

    def _determine_objectives_covered(self, session: LearningSession) -> list:
        """Determine learning objectives covered based on session content"""
        objectives = []

        # Analyze domains covered
        domains_covered = set()
        for item in session.items:
            domains_covered.update(item.domain_tags)

        # Map domains to learning objectives
        domain_objectives = {
            'pharmacology': "Apply evidence-based pharmacological principles in anesthetic management",
            'hemodynamics': "Assess and manage perioperative hemodynamic changes",
            'airway_anatomy': "Demonstrate competency in airway assessment and management",
            'regional': "Perform regional anesthetic techniques safely and effectively",
            'pediatric': "Adapt anesthetic care for pediatric patients",
            'obstetric': "Provide safe anesthetic care for obstetric patients",
            'neuro': "Manage neuroanesthetic considerations",
            'pain': "Apply multimodal pain management strategies",
            'icu_vent': "Manage critically ill patients requiring anesthetic care"
        }

        for domain in domains_covered:
            domain_key = domain.value if hasattr(domain, 'value') else str(domain)
            if domain_key in domain_objectives:
                objectives.append(domain_objectives[domain_key])

        # Add patient-specific objectives
        if session.case_hash:
            objectives.append("Apply case-based clinical reasoning to patient-specific scenarios")

        return objectives

    def validate_certificate(self, certificate_id: str) -> Optional[Dict[str, Any]]:
        """
        Validate a CME certificate

        Args:
            certificate_id: Certificate ID to validate

        Returns:
            Certificate validation data or None if invalid
        """
        # In production, would query database
        # For now, validate format
        if not certificate_id.startswith("MER-"):
            return None

        parts = certificate_id.split("-")
        if len(parts) != 3:
            return None

        try:
            # Validate date format
            datetime.strptime(parts[1], "%Y%m%d")
            return {
                'valid': True,
                'certificate_id': certificate_id,
                'provider': self.provider,
                'accreditor': self.accreditor
            }
        except ValueError:
            return None

    def generate_certificate_pdf(self, certificate: CMERecord,
                                learner_name: str = "Learner") -> bytes:
        """
        Generate PDF certificate

        Args:
            certificate: CME certificate record
            learner_name: Name of learner for certificate

        Returns:
            PDF certificate as bytes
        """
        # This would use a PDF generation library like reportlab
        # For now, return placeholder
        certificate_text = f"""
CERTIFICATE OF COMPLETION

{self.provider}

This certifies that

{learner_name}

has successfully completed

{certificate.hours:.2f} hours of continuing medical education

Activity ID: {certificate.certificate_id}
Date: {certificate.issued_at.strftime('%B %d, %Y')}
Score: {certificate.score:.1%}

Learning Objectives Completed:
{chr(10).join('• ' + obj for obj in certificate.objectives_covered)}

This activity has been planned and implemented in accordance with the
accreditation requirements and policies of the {self.accreditor}.

Certificate expires: {certificate.expires_at.strftime('%B %d, %Y')}
"""

        # In production, would generate actual PDF
        logger.info(f"Generated PDF certificate for {certificate.certificate_id}")
        return certificate_text.encode('utf-8')

    def get_cme_summary(self, user_id: str,
                       start_date: Optional[datetime] = None,
                       end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get CME summary for user

        Args:
            user_id: User identifier
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            CME summary data
        """
        # In production, would query database for user's certificates
        # For now, return placeholder structure
        return {
            'user_id': user_id,
            'total_hours': 0.0,
            'certificates': [],
            'objectives_completed': [],
            'last_activity': None,
            'summary_period': {
                'start_date': start_date.isoformat() if start_date else None,
                'end_date': end_date.isoformat() if end_date else None
            }
        }