"""Audit engine entrypoint.

Spec reference: Kavachly_Audit_Engine_Spec.docx Section 7 — "Pure Python,
no I/O: the entire scoring engine should run in < 50ms for a typical user
(5 policies). All computations are simple arithmetic on small dicts."

The function `generate_audit(user, policies)` is the single public entry.
The router in routers/audit_router.py is responsible for the Mongo round
trip + serialization; the engine itself never touches IO.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Sequence

from services.audit import claim_readiness, cost, coverage, findings, gap
from services.audit.version import DATA_VERSION
from services.audit.constants.ideal_cover import (
    ideal_health_cover,
    ideal_life_cover,
    ideal_motor_cover,
    ideal_pa_cover,
)
from services.audit.types import (
    AuditResult,
    Policy,
    PortfolioRow,
    PortfolioSummary,
    UserProfile,
)


def generate_audit(
    user: UserProfile,
    policies: Sequence[Policy],
) -> AuditResult:
    """Compute all four scores, the top-3 findings, and the portfolio
    summary. Pure function — no I/O, no global mutation.

    TODO(audit-schedule-required): when ALL policies have null sum_insured
    (every upload was a wording PDF, never a schedule), produce a
    structured "schedule_required" audit response instead of computing
    scores on whatever subset has data. See Issue 4 in the v0.4-pdf-parser
    review thread. Deferred to a separate session.
    """
    start = time.perf_counter()

    coverage_b = coverage.score(user, policies)
    claim_readiness_b = claim_readiness.score(user, policies)
    # Cost depends on per-policy claim-readiness; we recompute inside cost
    # to keep modules independent (cheap: small list, no allocations of note).
    cost_b = cost.score(user, policies)
    gap_b = gap.score(user, policies)

    breakdowns = {
        "coverage": coverage_b,
        "cost": cost_b,
        "claim_readiness": claim_readiness_b,
        "gap": gap_b,
    }
    top, all_findings = findings.generate(user, policies, breakdowns)
    portfolio = _portfolio(user, policies)

    elapsed_ms = int((time.perf_counter() - start) * 1000)

    return AuditResult(
        id=str(uuid.uuid4()),
        user_id=user.user_id,
        scores={
            "coverage": coverage_b.value,
            "cost": cost_b.value,
            "claim_readiness": claim_readiness_b.value,
            "gap": gap_b.value,
        },
        findings=tuple(top),
        all_findings=tuple(all_findings),
        portfolio=portfolio,
        breakdowns=breakdowns,
        data_version=DATA_VERSION,
        engine_ms=elapsed_ms,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def _portfolio(user: UserProfile, policies: Sequence[Policy]) -> PortfolioSummary:
    """Build the portfolio block the frontend dashboard renders.

    by_type ordering matches the mock fixture exactly so the dashboard's
    progress-bar list looks identical between mock and real outputs.
    """
    # Skip wording-only policies (null SI/premium) from the headline
    # totals so the portfolio header doesn't flash "₹0 covered" against
    # a real policy the user uploaded.
    total_cover = sum(p.sum_insured for p in policies if p.sum_insured is not None)
    total_premium = sum(p.premium for p in policies if p.premium is not None)
    next_renewal = _next_renewal(policies)

    actual_per_cat = _actual_by_label(policies)
    rows = [
        _row("Health", actual_per_cat.get("Health", 0), ideal_health_cover(user)),
        _row("Term Life", actual_per_cat.get("Term Life", 0), ideal_life_cover(user)),
        _row("Personal Accident", actual_per_cat.get("Personal Accident", 0), ideal_pa_cover(user)),
        _row("Motor", actual_per_cat.get("Motor", 0), ideal_motor_cover(user)),
        _row("Travel", actual_per_cat.get("Travel", 0), 0),
    ]

    return PortfolioSummary(
        total_cover=total_cover,
        total_premium=total_premium,
        active_policies=len(policies),
        next_renewal=next_renewal,
        by_type=tuple(rows),
    )


def _actual_by_label(policies: Sequence[Policy]) -> dict[str, int]:
    label_map: dict[str, str] = {
        "health": "Health",
        "term": "Term Life",
        "term_life": "Term Life",
        "endowment": "Term Life",
        "ulip": "Term Life",
        "pa": "Personal Accident",
        "personal_accident": "Personal Accident",
        "motor": "Motor",
        "two_wheeler": "Motor",
        "car": "Motor",
        "travel": "Travel",
    }
    out: dict[str, int] = {}
    for p in policies:
        if p.sum_insured is None:
            continue
        label = label_map.get(p.type, "Other")
        out[label] = out.get(label, 0) + p.sum_insured
    return out


def _row(label: str, current: int, ideal: int) -> PortfolioRow:
    """Build a portfolio row. Ratio is current/ideal as percent, capped 0-100.
    For categories that don't apply (ideal == 0), report ratio 100 so the
    UI bar shows full (and the row is informational only).
    """
    if ideal <= 0:
        return PortfolioRow(type=label, current=current, ideal=ideal, ratio=100)
    raw = (current / ideal) * 100
    return PortfolioRow(type=label, current=current, ideal=ideal,
                        ratio=max(0, min(100, int(round(raw)))))


def _next_renewal(policies: Sequence[Policy]) -> str | None:
    """Earliest end_date across policies; None if nothing dated."""
    dates = [p.end_date for p in policies if p.end_date]
    if not dates:
        return None
    return min(dates)
