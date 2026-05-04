"""Audit Scoring Engine — Kavachly's brand-defining file.

Public entrypoint:
    from services.audit.engine import generate_audit
"""
from services.audit.engine import generate_audit
from services.audit.types import (
    AuditResult,
    Finding,
    Lifestyle,
    Policy,
    PortfolioSummary,
    PortfolioRow,
    ScoreBreakdown,
    UserProfile,
)
from services.audit.version import DATA_VERSION

__all__ = [
    "generate_audit",
    "AuditResult",
    "Finding",
    "Lifestyle",
    "Policy",
    "PortfolioSummary",
    "PortfolioRow",
    "ScoreBreakdown",
    "UserProfile",
    "DATA_VERSION",
]