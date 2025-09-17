#!/usr/bin/env python3
"""
CODEX v2 Error Code System
Provides specific, auditable error codes for debugging and monitoring.
"""

from enum import Enum
from typing import Dict, Any, Optional
import logging
import traceback
from datetime import datetime
import json

class ErrorCode(Enum):
    """Specific error codes for CODEX v2 system components"""

    # HPI Analysis Errors (HPI_xxx)
    HPI_PARSE_EMPTY_TEXT = "HPI_001"
    HPI_PARSE_INVALID_FORMAT = "HPI_002"
    HPI_EXTRACT_NO_FACTORS = "HPI_003"
    HPI_EXTRACT_REGEX_FAILURE = "HPI_004"

    # Risk Engine Errors (RISK_xxx)
    RISK_NO_BASELINE_DATA = "RISK_001"
    RISK_EMPTY_ESTIMATES = "RISK_002"
    RISK_MAX_EMPTY_SEQUENCE = "RISK_003"
    RISK_INVALID_POPULATION = "RISK_004"
    RISK_MISSING_OUTCOME = "RISK_005"
    RISK_CALCULATION_OVERFLOW = "RISK_006"

    # Database Errors (DB_xxx)
    DB_CONNECTION_FAILED = "DB_001"
    DB_SCHEMA_MISMATCH = "DB_002"
    DB_MISSING_TABLE = "DB_003"
    DB_MISSING_COLUMN = "DB_004"
    DB_QUERY_TIMEOUT = "DB_005"
    DB_CONSTRAINT_VIOLATION = "DB_006"

    # Evidence Errors (EVID_xxx)
    EVID_PUBMED_RATE_LIMIT = "EVID_001"
    EVID_PUBMED_CONNECTION = "EVID_002"
    EVID_NO_PAPERS_FOUND = "EVID_003"
    EVID_EXTRACTION_FAILED = "EVID_004"
    EVID_INVALID_PMID = "EVID_005"

    # Clinical Recommendation Errors (CLIN_xxx)
    CLIN_NO_GUIDELINES = "CLIN_001"
    CLIN_INSUFFICIENT_DATA = "CLIN_002"
    CLIN_CONTRAINDICATION = "CLIN_003"

    # API/Application Errors (APP_xxx)
    APP_INVALID_REQUEST = "APP_001"
    APP_MISSING_PARAMETER = "APP_002"
    APP_AUTHORIZATION_FAILED = "APP_003"
    APP_RATE_LIMIT_EXCEEDED = "APP_004"
    APP_INTERNAL_ERROR = "APP_005"

    # Configuration Errors (CFG_xxx)
    CFG_MISSING_ENV_VAR = "CFG_001"
    CFG_INVALID_CONFIG = "CFG_002"
    CFG_FILE_NOT_FOUND = "CFG_003"

class CodexError(Exception):
    """Base exception class for CODEX v2 with specific error codes"""

    def __init__(
        self,
        error_code: ErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        self.original_exception = original_exception
        self.timestamp = datetime.utcnow().isoformat()
        self.trace_id = self._generate_trace_id()

        super().__init__(f"[{error_code.value}] {message}")

    def _generate_trace_id(self) -> str:
        """Generate unique trace ID for error tracking"""
        import uuid
        return str(uuid.uuid4())[:8]

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for logging/API responses"""
        return {
            "error_code": self.error_code.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
            "original_error": str(self.original_exception) if self.original_exception else None
        }

    def to_json(self) -> str:
        """Convert error to JSON string"""
        return json.dumps(self.to_dict(), indent=2)

class ErrorLogger:
    """Centralized error logging with structured output"""

    def __init__(self, logger_name: str = "codex"):
        self.logger = logging.getLogger(logger_name)

    def log_error(self, error: CodexError, level: int = logging.ERROR):
        """Log error with structured format"""
        error_dict = error.to_dict()

        # Log with structured format for easy parsing
        self.logger.log(
            level,
            f"CODEX_ERROR: {error.error_code.value} - {error.message}",
            extra={
                "error_code": error.error_code.value,
                "trace_id": error.trace_id,
                "details": error.details,
                "timestamp": error.timestamp
            }
        )

        # Log stack trace if original exception exists
        if error.original_exception:
            self.logger.debug(
                f"Original exception for {error.trace_id}:",
                exc_info=error.original_exception
            )

def handle_risk_empty_sequence_error(outcome_token: str, population: str) -> CodexError:
    """Create specific error for max() empty sequence in risk calculations"""
    return CodexError(
        error_code=ErrorCode.RISK_MAX_EMPTY_SEQUENCE,
        message=f"No risk estimates available for {outcome_token} in {population} population",
        details={
            "outcome_token": outcome_token,
            "population": population,
            "suggested_action": "Check evidence database for baseline risk data",
            "fallback_available": True
        }
    )

def handle_database_missing_column_error(table: str, column: str) -> CodexError:
    """Create specific error for missing database columns"""
    return CodexError(
        error_code=ErrorCode.DB_MISSING_COLUMN,
        message=f"Column '{column}' not found in table '{table}'",
        details={
            "table": table,
            "column": column,
            "suggested_action": "Run database migration or update schema",
            "compatibility_mode": True
        }
    )

def handle_hpi_parse_error(hpi_text: str, original_error: Exception) -> CodexError:
    """Create specific error for HPI parsing failures"""
    return CodexError(
        error_code=ErrorCode.HPI_PARSE_INVALID_FORMAT,
        message="Failed to parse HPI text",
        details={
            "hpi_length": len(hpi_text) if hpi_text else 0,
            "error_type": type(original_error).__name__,
            "suggested_action": "Check HPI text format and parser configuration"
        },
        original_exception=original_error
    )

# Error code mapping for quick lookups
ERROR_CODE_DESCRIPTIONS = {
    ErrorCode.RISK_MAX_EMPTY_SEQUENCE: "Risk calculation failed due to empty estimates",
    ErrorCode.DB_MISSING_COLUMN: "Database schema incompatibility",
    ErrorCode.HPI_PARSE_INVALID_FORMAT: "HPI text parsing failure",
    ErrorCode.EVID_PUBMED_RATE_LIMIT: "PubMed API rate limit exceeded",
    ErrorCode.RISK_NO_BASELINE_DATA: "No baseline risk data available"
}

def get_error_description(error_code: ErrorCode) -> str:
    """Get human-readable description for error code"""
    return ERROR_CODE_DESCRIPTIONS.get(error_code, "Unknown error")