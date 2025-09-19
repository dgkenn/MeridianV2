"""
Meridian Learning Module
========================

A comprehensive educational system that generates board-style MCQs from
existing case data and evidence base, with CME certificate generation
and progress tracking.

Main Components:
- MCQ Generation Engine: Creates case-anchored questions
- Learning Sessions: Manages quiz sessions and responses
- CME System: Generates AMA PRA Category 1 Credit certificates
- Problem Reporting: User feedback and issue tracking
- Progress Analytics: Performance tracking and recommendations

Usage:
    from learning import render_learning_module
    render_learning_module()  # In Streamlit app

Or for individual components:
    from learning.generators import MCQGenerator
    from learning.models import LearningSession, CMERecord
    from learning.ui import LearningInterface
"""

__version__ = "1.0.0"
__author__ = "Meridian Development Team"

# Import main UI component
from .ui.learning_tabs import render_learning_module

# Import key classes for external use
from .models import (
    LearningItem, LearningSession, LearningResponse,
    CMERecord, CMECertificateGenerator,
    ProblemReport, ProblemReportManager,
    BlueprintDomain, LearningMode, DifficultyTier
)

from .generators.mcq_generator import MCQGenerator, CaseContext

__all__ = [
    # Main entry point
    'render_learning_module',

    # Core models
    'LearningItem', 'LearningSession', 'LearningResponse',
    'CMERecord', 'CMECertificateGenerator',
    'ProblemReport', 'ProblemReportManager',

    # Enums
    'BlueprintDomain', 'LearningMode', 'DifficultyTier',

    # Generators
    'MCQGenerator', 'CaseContext'
]