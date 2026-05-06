"""Life audit orchestrator."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Callable

from services.life.audit import claim_readiness, cost, coverage, findings, gap
from services.life.audit.types import (
    LifeAuditResult,
    LifeFinding,
    LifeScheduleInput,
    LifeScoreBreakdown,
    LifeUserProfile,
)

logger = logging.getLogger("kavach.life.audit")

LIFE_AUDIT_DATA_VERSION = "life-2026.05"


def _failed_breakdown(label: str, warning: str) -> LifeScoreBreakdown:
    return LifeScoreBreakdown(
        value=None,
        label=label,
        details={"reason": "scorer_failed", "warning": warning},
    )


def _safe_score(
    label: str,
    scorer: Callable[[], LifeScoreBreakdown],
    warnings: list[str],
) -> LifeScoreBreakdown:
    try:
        return scorer()
    except Exception as exc:  # pragma: no cover - defensive orchestration guard
        warning = f"{label}_scorer_failed: {exc.__class__.__name__}"
        logger.exception("life.audit.%s.failed", label)
        warnings.append(warning)
        return _failed_breakdown(label, warning)


def run_life_audit(
    profile: LifeUserProfile,
    schedule: LifeScheduleInput,
    *,
    life_policy_count: int | None = None,
    has_personal_accident_anywhere: bool | None = None,
) -> LifeAuditResult:
    """Run life audit scorers and assemble one immutable result object."""
    start = time.perf_counter()
    warnings: list[str] = []

    coverage_b = _safe_score(
        "coverage",
        lambda: coverage.score(profile, schedule),
        warnings,
    )
    cost_b = _safe_score(
        "cost",
        lambda: cost.score(profile, schedule),
        warnings,
    )
    claim_readiness_b = _safe_score(
        "claim_readiness",
        lambda: claim_readiness.score(schedule),
        warnings,
    )
    gap_b = _safe_score(
        "gap",
        lambda: gap.score(
            profile,
            schedule,
            life_policy_count=life_policy_count,
            has_personal_accident_anywhere=has_personal_accident_anywhere,
        ),
        warnings,
    )

    breakdowns: dict[str, LifeScoreBreakdown] = {
        "coverage": coverage_b,
        "cost": cost_b,
        "claim_readiness": claim_readiness_b,
        "gap": gap_b,
    }

    top_findings, all_findings = _safe_findings(profile, schedule, breakdowns, warnings)

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    return LifeAuditResult(
        id=str(uuid.uuid4()),
        user_id=profile.user_id,
        scores={
            "coverage": coverage_b.value,
            "cost": cost_b.value,
            "claim_readiness": claim_readiness_b.value,
            "gap": gap_b.value,
        },
        findings=tuple(top_findings),
        all_findings=tuple(all_findings),
        breakdowns=breakdowns,
        data_version=LIFE_AUDIT_DATA_VERSION,
        engine_ms=elapsed_ms,
        generated_at=datetime.now(timezone.utc).isoformat(),
        warnings=tuple(warnings),
    )


def _safe_findings(
    profile: LifeUserProfile,
    schedule: LifeScheduleInput,
    breakdowns: dict[str, LifeScoreBreakdown],
    warnings: list[str],
) -> tuple[list[LifeFinding], list[LifeFinding]]:
    try:
        return findings.generate(profile, schedule, breakdowns)
    except Exception as exc:  # pragma: no cover - defensive orchestration guard
        warning = f"findings_generator_failed: {exc.__class__.__name__}"
        logger.exception("life.audit.findings.failed")
        warnings.append(warning)
        return ([], [])
