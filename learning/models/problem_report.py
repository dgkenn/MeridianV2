"""
Problem Report System for Learning Module
Handles user feedback and issue reporting
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
import uuid
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

logger = logging.getLogger(__name__)


class ProblemType(Enum):
    """Types of problems that can be reported"""
    INCORRECT_ANSWER = "incorrect_answer"
    WRONG_EXPLANATION = "wrong_explanation"
    TECHNICAL_BUG = "technical_bug"
    CONTENT_SUGGESTION = "content_suggestion"
    UI_ISSUE = "ui_issue"
    PERFORMANCE_ISSUE = "performance_issue"
    OTHER = "other"


class ProblemPriority(Enum):
    """Priority levels for problem reports"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ProblemStatus(Enum):
    """Status of problem reports"""
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    DUPLICATE = "duplicate"


@dataclass
class ProblemReport:
    """
    Individual problem report from a user
    """
    report_id: str
    problem_type: ProblemType
    title: str
    description: str

    # Reporter information
    reporter_name: Optional[str] = None
    reporter_email: Optional[str] = None

    # Context information
    question_id: Optional[str] = None
    session_id: Optional[str] = None
    user_agent: Optional[str] = None
    url: Optional[str] = None

    # Additional data
    browser_info: Optional[Dict[str, Any]] = None
    screenshot_path: Optional[str] = None
    reproduction_steps: Optional[List[str]] = None

    # Management fields
    priority: ProblemPriority = ProblemPriority.MEDIUM
    status: ProblemStatus = ProblemStatus.SUBMITTED
    assigned_to: Optional[str] = None

    # Timestamps
    submitted_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None

    # Internal notes
    internal_notes: List[str] = field(default_factory=list)
    resolution_notes: Optional[str] = None

    def add_internal_note(self, note: str, author: str = "System") -> None:
        """Add an internal note to the report"""
        timestamp = datetime.now().isoformat()
        self.internal_notes.append(f"[{timestamp}] {author}: {note}")
        self.updated_at = datetime.now()

    def update_status(self, new_status: ProblemStatus, note: Optional[str] = None) -> None:
        """Update the status of the problem report"""
        old_status = self.status
        self.status = new_status
        self.updated_at = datetime.now()

        if new_status == ProblemStatus.RESOLVED:
            self.resolved_at = datetime.now()

        # Add status change note
        status_note = f"Status changed from {old_status.value} to {new_status.value}"
        if note:
            status_note += f": {note}"
        self.add_internal_note(status_note)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'report_id': self.report_id,
            'problem_type': self.problem_type.value,
            'title': self.title,
            'description': self.description,
            'reporter_name': self.reporter_name,
            'reporter_email': self.reporter_email,
            'question_id': self.question_id,
            'session_id': self.session_id,
            'user_agent': self.user_agent,
            'url': self.url,
            'browser_info': self.browser_info,
            'screenshot_path': self.screenshot_path,
            'reproduction_steps': self.reproduction_steps,
            'priority': self.priority.value,
            'status': self.status.value,
            'assigned_to': self.assigned_to,
            'submitted_at': self.submitted_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'internal_notes': self.internal_notes,
            'resolution_notes': self.resolution_notes
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProblemReport':
        """Create from dictionary"""
        return cls(
            report_id=data['report_id'],
            problem_type=ProblemType(data['problem_type']),
            title=data['title'],
            description=data['description'],
            reporter_name=data.get('reporter_name'),
            reporter_email=data.get('reporter_email'),
            question_id=data.get('question_id'),
            session_id=data.get('session_id'),
            user_agent=data.get('user_agent'),
            url=data.get('url'),
            browser_info=data.get('browser_info'),
            screenshot_path=data.get('screenshot_path'),
            reproduction_steps=data.get('reproduction_steps'),
            priority=ProblemPriority(data.get('priority', 'medium')),
            status=ProblemStatus(data.get('status', 'submitted')),
            assigned_to=data.get('assigned_to'),
            submitted_at=datetime.fromisoformat(data['submitted_at']),
            updated_at=datetime.fromisoformat(data['updated_at']),
            resolved_at=datetime.fromisoformat(data['resolved_at']) if data.get('resolved_at') else None,
            internal_notes=data.get('internal_notes', []),
            resolution_notes=data.get('resolution_notes')
        )

    @staticmethod
    def generate_id() -> str:
        """Generate unique report ID"""
        return f"RPT_{datetime.now().strftime('%Y%m%d')}_{str(uuid.uuid4())[:8].upper()}"


class ProblemReportManager:
    """Manages problem reports and notifications"""

    def __init__(self, admin_email: str = "dgkenn@bu.edu"):
        self.admin_email = admin_email
        self.smtp_config = self._get_smtp_config()

    def _get_smtp_config(self) -> Dict[str, Any]:
        """Get SMTP configuration for email notifications"""
        # In production, these would come from environment variables
        return {
            'host': 'smtp.gmail.com',
            'port': 587,
            'username': 'meridian.reports@gmail.com',  # Would be configured
            'password': 'app_password',  # Would be from environment
            'use_tls': True
        }

    def submit_report(
        self,
        problem_type: ProblemType,
        title: str,
        description: str,
        reporter_name: Optional[str] = None,
        reporter_email: Optional[str] = None,
        **context_data
    ) -> ProblemReport:
        """Submit a new problem report"""

        report = ProblemReport(
            report_id=ProblemReport.generate_id(),
            problem_type=problem_type,
            title=title,
            description=description,
            reporter_name=reporter_name,
            reporter_email=reporter_email,
            **{k: v for k, v in context_data.items() if hasattr(ProblemReport, k)}
        )

        # Determine priority based on problem type
        report.priority = self._determine_priority(problem_type, description)

        # Auto-assign based on problem type
        report.assigned_to = self._auto_assign(problem_type)

        # Send notification email
        try:
            self._send_notification_email(report)
            report.add_internal_note("Notification email sent successfully")
        except Exception as e:
            logger.error(f"Failed to send notification email: {e}")
            report.add_internal_note(f"Failed to send notification: {e}")

        # Store report (in production, this would save to database)
        self._store_report(report)

        return report

    def _determine_priority(self, problem_type: ProblemType, description: str) -> ProblemPriority:
        """Determine priority based on problem type and description"""

        # High priority keywords
        high_priority_keywords = [
            'crash', 'error', 'broken', 'cannot', 'unable', 'fail',
            'wrong answer', 'incorrect', 'dangerous', 'safety'
        ]

        # Critical keywords
        critical_keywords = [
            'patient safety', 'dangerous dose', 'medical error',
            'contraindication', 'allergy', 'fatal'
        ]

        description_lower = description.lower()

        # Check for critical issues
        if any(keyword in description_lower for keyword in critical_keywords):
            return ProblemPriority.CRITICAL

        # Check for high priority issues
        if (problem_type in [ProblemType.INCORRECT_ANSWER, ProblemType.TECHNICAL_BUG] or
            any(keyword in description_lower for keyword in high_priority_keywords)):
            return ProblemPriority.HIGH

        # Content suggestions and UI issues are typically medium priority
        if problem_type in [ProblemType.CONTENT_SUGGESTION, ProblemType.UI_ISSUE]:
            return ProblemPriority.MEDIUM

        return ProblemPriority.MEDIUM

    def _auto_assign(self, problem_type: ProblemType) -> str:
        """Auto-assign reports based on problem type"""

        assignment_map = {
            ProblemType.INCORRECT_ANSWER: "Content Team",
            ProblemType.WRONG_EXPLANATION: "Content Team",
            ProblemType.TECHNICAL_BUG: "Development Team",
            ProblemType.PERFORMANCE_ISSUE: "Development Team",
            ProblemType.UI_ISSUE: "UX Team",
            ProblemType.CONTENT_SUGGESTION: "Content Team",
            ProblemType.OTHER: "General Support"
        }

        return assignment_map.get(problem_type, "General Support")

    def _send_notification_email(self, report: ProblemReport) -> None:
        """Send notification email to admin"""

        subject = f"[Meridian] New Problem Report: {report.title} ({report.priority.value.upper()})"

        # Create email body
        body = self._create_email_body(report)

        # Send email
        self._send_email(
            to_email=self.admin_email,
            subject=subject,
            body=body,
            reply_to=report.reporter_email
        )

    def _create_email_body(self, report: ProblemReport) -> str:
        """Create detailed email body for problem report"""

        body = f"""
New Problem Report Submitted
============================

Report ID: {report.report_id}
Type: {report.problem_type.value.replace('_', ' ').title()}
Priority: {report.priority.value.upper()}
Submitted: {report.submitted_at.strftime('%Y-%m-%d %H:%M:%S UTC')}

Reporter Information:
- Name: {report.reporter_name or 'Anonymous'}
- Email: {report.reporter_email or 'Not provided'}

Problem Details:
- Title: {report.title}
- Description: {report.description}

Context Information:
- Question ID: {report.question_id or 'N/A'}
- Session ID: {report.session_id or 'N/A'}
- User Agent: {report.user_agent or 'N/A'}
- URL: {report.url or 'N/A'}

Auto-Assignment: {report.assigned_to}

"""

        if report.reproduction_steps:
            body += "\nReproduction Steps:\n"
            for i, step in enumerate(report.reproduction_steps, 1):
                body += f"{i}. {step}\n"

        if report.browser_info:
            body += f"\nBrowser Information:\n{json.dumps(report.browser_info, indent=2)}\n"

        body += f"""
---
This is an automated notification from the Meridian Learning Module.
Report ID: {report.report_id}
Priority: {report.priority.value.upper()}
"""

        return body

    def _send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        reply_to: Optional[str] = None
    ) -> None:
        """Send email using SMTP"""

        # In production, this would use proper SMTP credentials
        # For now, just log the email content
        logger.info(f"EMAIL NOTIFICATION:\nTo: {to_email}\nSubject: {subject}\nBody:\n{body}")

        # Uncomment for actual email sending:
        """
        msg = MIMEMultipart()
        msg['From'] = self.smtp_config['username']
        msg['To'] = to_email
        msg['Subject'] = subject

        if reply_to:
            msg['Reply-To'] = reply_to

        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(self.smtp_config['host'], self.smtp_config['port'])
        server.starttls()
        server.login(self.smtp_config['username'], self.smtp_config['password'])
        server.send_message(msg)
        server.quit()
        """

    def _store_report(self, report: ProblemReport) -> None:
        """Store report to database/file system"""

        # In production, this would save to a database
        # For now, save to a JSON file
        import os
        reports_dir = "reports"
        os.makedirs(reports_dir, exist_ok=True)

        report_file = os.path.join(reports_dir, f"{report.report_id}.json")

        try:
            with open(report_file, 'w') as f:
                json.dump(report.to_dict(), f, indent=2)
            logger.info(f"Problem report saved: {report_file}")
        except Exception as e:
            logger.error(f"Failed to save report: {e}")

    def get_report(self, report_id: str) -> Optional[ProblemReport]:
        """Retrieve a problem report by ID"""

        report_file = f"reports/{report_id}.json"

        try:
            with open(report_file, 'r') as f:
                data = json.load(f)
            return ProblemReport.from_dict(data)
        except FileNotFoundError:
            return None
        except Exception as e:
            logger.error(f"Failed to load report {report_id}: {e}")
            return None

    def update_report(self, report: ProblemReport) -> None:
        """Update an existing problem report"""
        report.updated_at = datetime.now()
        self._store_report(report)

    def list_reports(
        self,
        status: Optional[ProblemStatus] = None,
        problem_type: Optional[ProblemType] = None,
        priority: Optional[ProblemPriority] = None,
        limit: int = 50
    ) -> List[ProblemReport]:
        """List problem reports with optional filtering"""

        import os
        import glob

        reports = []
        report_files = glob.glob("reports/*.json")

        for report_file in report_files[:limit]:
            try:
                with open(report_file, 'r') as f:
                    data = json.load(f)
                report = ProblemReport.from_dict(data)

                # Apply filters
                if status and report.status != status:
                    continue
                if problem_type and report.problem_type != problem_type:
                    continue
                if priority and report.priority != priority:
                    continue

                reports.append(report)
            except Exception as e:
                logger.error(f"Failed to load report {report_file}: {e}")

        # Sort by submission date (newest first)
        reports.sort(key=lambda r: r.submitted_at, reverse=True)
        return reports

    def get_statistics(self) -> Dict[str, Any]:
        """Get problem report statistics"""

        reports = self.list_reports(limit=1000)

        stats = {
            'total_reports': len(reports),
            'by_status': {},
            'by_type': {},
            'by_priority': {},
            'resolution_time_avg': None,
            'recent_reports': len([r for r in reports if (datetime.now() - r.submitted_at).days <= 7])
        }

        # Count by status
        for status in ProblemStatus:
            stats['by_status'][status.value] = len([r for r in reports if r.status == status])

        # Count by type
        for problem_type in ProblemType:
            stats['by_type'][problem_type.value] = len([r for r in reports if r.problem_type == problem_type])

        # Count by priority
        for priority in ProblemPriority:
            stats['by_priority'][priority.value] = len([r for r in reports if r.priority == priority])

        # Calculate average resolution time
        resolved_reports = [r for r in reports if r.resolved_at]
        if resolved_reports:
            resolution_times = [
                (r.resolved_at - r.submitted_at).total_seconds() / 3600  # hours
                for r in resolved_reports
            ]
            stats['resolution_time_avg'] = sum(resolution_times) / len(resolution_times)

        return stats


def create_problem_report_from_ui(
    problem_type_str: str,
    title: str,
    description: str,
    question_id: Optional[str] = None,
    reporter_name: Optional[str] = None,
    reporter_email: Optional[str] = None,
    session_context: Optional[Dict[str, Any]] = None
) -> ProblemReport:
    """Helper function to create problem report from UI inputs"""

    # Parse problem type
    try:
        problem_type = ProblemType(problem_type_str.lower().replace(' ', '_').replace('-', '_'))
    except ValueError:
        problem_type = ProblemType.OTHER

    # Create manager and submit report
    manager = ProblemReportManager()

    context_data = {}
    if question_id:
        context_data['question_id'] = question_id

    if session_context:
        context_data.update({
            'session_id': session_context.get('session_id'),
            'user_agent': session_context.get('user_agent', 'Streamlit Learning Module'),
            'url': session_context.get('url', 'https://meridian-zr3e.onrender.com'),
            'browser_info': session_context.get('browser_info')
        })

    return manager.submit_report(
        problem_type=problem_type,
        title=title,
        description=description,
        reporter_name=reporter_name,
        reporter_email=reporter_email,
        **context_data
    )