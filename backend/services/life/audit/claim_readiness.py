"""Life claim-readiness score (0-100): operational readiness of claim setup."""

from __future__ import annotations

from services.audit.constants.csr_table import lookup_csr
from services.life.audit.types import LifeScheduleInput, LifeScoreBreakdown

# --- Component weights (user-requested first draft) ---
# Nominee presence is the strongest operational readiness factor.
NOMINEE_SCORE = 30
# Contingent nominee reduces single-point failure in nominee chain.
CONTINGENT_NOMINEE_SCORE = 10
# Riders being identified/documented improves clarity at claim time.
RIDERS_DOCUMENTED_SCORE = 20
# Insurer claim-settlement ratio quality signal.
CSR_SCORE_MAX = 20
# Free-look still open gives tactical corrective flexibility.
FREE_LOOK_ACTIVE_SCORE = 10
# Autopay reduces lapse risk and therefore claim rejection risk.
AUTOPAY_SCORE = 10

# --- CSR scaling thresholds ---
# >95% treated as full marks in this axis.
CSR_FULL_SCORE_THRESHOLD = 0.95

# --- Free-look window heuristic ---
# If extraction says free-look period exists (typically 15-30 days), we
# assume "potentially active" in v1 because issue-date extraction is not yet wired.
FREE_LOOK_ACTIVE_MIN_DAYS = 15

# Rider list sanity threshold for considering riders as "documented".
RIDERS_DOCUMENTED_MIN_COUNT = 1


def _csr_component(csr: float) -> int:
    bounded = max(0.0, min(1.0, csr))
    if bounded >= CSR_FULL_SCORE_THRESHOLD:
        return CSR_SCORE_MAX
    scaled = int(round((bounded / CSR_FULL_SCORE_THRESHOLD) * CSR_SCORE_MAX))
    return max(0, min(CSR_SCORE_MAX, scaled))


def _lookup_insurer_csr(schedule: LifeScheduleInput) -> tuple[float | None, bool, str | None]:
    """Return (csr, unknown_flag, canonical_name) from schedule insurer hints.

    Option A behavior: unknown insurer gets 0 points on CSR component.
    """
    probe = (schedule.insurer_name or schedule.insurer_hint_id or "").strip()
    if not probe:
        return (None, True, None)
    canonical, csr = lookup_csr(probe)
    if canonical == "_DEFAULT":
        return (None, True, None)
    return (float(csr), False, canonical)


def score(
    schedule: LifeScheduleInput,
) -> LifeScoreBreakdown:
    """Compute claim-readiness score from life schedule extraction signals."""
    nominee_component = NOMINEE_SCORE if schedule.nominee_section_likely else 0
    contingent_component = (
        CONTINGENT_NOMINEE_SCORE if schedule.contingent_nominee_likely else 0
    )
    riders_component = (
        RIDERS_DOCUMENTED_SCORE
        if len(tuple(schedule.detected_riders)) >= RIDERS_DOCUMENTED_MIN_COUNT
        else 0
    )
    insurer_csr, csr_unknown, csr_canonical = _lookup_insurer_csr(schedule)
    csr_component = _csr_component(insurer_csr) if insurer_csr is not None else 0
    free_look_component = (
        FREE_LOOK_ACTIVE_SCORE
        if (schedule.free_look_days or 0) >= FREE_LOOK_ACTIVE_MIN_DAYS
        else 0
    )
    autopay_component = AUTOPAY_SCORE if schedule.autopay_likely else 0

    value = (
        nominee_component
        + contingent_component
        + riders_component
        + csr_component
        + free_look_component
        + autopay_component
    )
    value = max(0, min(100, int(value)))

    return LifeScoreBreakdown(
        value=value,
        label="claim_readiness",
        details={
            "nominee_section_likely": schedule.nominee_section_likely,
            "contingent_nominee_likely": schedule.contingent_nominee_likely,
            "detected_riders_count": len(tuple(schedule.detected_riders)),
            "insurer_name": schedule.insurer_name,
            "insurer_hint_id": schedule.insurer_hint_id,
            "insurer_csr": insurer_csr,
            "insurer_csr_unknown": csr_unknown,
            "insurer_csr_canonical": csr_canonical,
            "free_look_days": schedule.free_look_days,
            "autopay_likely": schedule.autopay_likely,
            "components": {
                "nominee": nominee_component,
                "contingent_nominee": contingent_component,
                "riders_documented": riders_component,
                "insurer_csr": csr_component,
                "free_look_active": free_look_component,
                "autopay": autopay_component,
            },
        },
    )
