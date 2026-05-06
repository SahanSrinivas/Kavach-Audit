"""Life coverage score (0-100): sufficiency of life sum assured."""

from __future__ import annotations

from services.life.audit.types import LifeScheduleInput, LifeScoreBreakdown, LifeUserProfile

# --- Income-multiple bands (first draft, aligned with common HLV conventions) ---
# 15x+ annual income is generally treated as strong income-replacement coverage.
COVERAGE_INCOME_MULTIPLE_GREAT = 15.0
# 10-15x usually covers core family obligations in vanilla scenarios.
COVERAGE_INCOME_MULTIPLE_GOOD = 10.0
# 5-10x is partial protection and still leaves replacement risk.
COVERAGE_INCOME_MULTIPLE_FAIR = 5.0

# Band scores for the ratio buckets above.
COVERAGE_SCORE_GREAT = 100
COVERAGE_SCORE_GOOD = 80
COVERAGE_SCORE_FAIR = 60
COVERAGE_SCORE_POOR = 40

# --- Required-cover model knobs (tuned frequently during dogfood) ---
# Base required multiple starts at 10x annual income.
BASE_REQUIRED_INCOME_MULTIPLE = 10.0
# Each dependent raises needed cover by +0.5x income (education/living runway).
DEPENDENT_BOOST_PER_PERSON = 0.5
# Avoid unrealistic extremes from high dependent counts in v1 scoring.
MAX_DEPENDENT_BOOST = 4.0
# Outstanding liabilities add directly to required cover (1:1).
LIABILITY_COVER_FACTOR = 1.0

# --- Blending weights ---
# Income-multiple band is the primary signal in user-facing expectations.
COVERAGE_WEIGHT_MULTIPLE_BAND = 0.7
# Required-cover ratio adds family/liability realism to the score.
COVERAGE_WEIGHT_REQUIRED_RATIO = 0.3

# Keep ratio impact bounded so one very high sum assured does not over-amplify.
REQUIRED_RATIO_CAP = 1.2


def _income_multiple_score(actual_multiple: float) -> int:
    if actual_multiple >= COVERAGE_INCOME_MULTIPLE_GREAT:
        return COVERAGE_SCORE_GREAT
    if actual_multiple >= COVERAGE_INCOME_MULTIPLE_GOOD:
        return COVERAGE_SCORE_GOOD
    if actual_multiple >= COVERAGE_INCOME_MULTIPLE_FAIR:
        return COVERAGE_SCORE_FAIR
    return COVERAGE_SCORE_POOR


def score(profile: LifeUserProfile, schedule: LifeScheduleInput) -> LifeScoreBreakdown:
    """Compute coverage score from extracted schedule + user profile.

    Returns None when key numeric inputs are absent (income or sum assured).
    """
    if profile.annual_income <= 0:
        return LifeScoreBreakdown(
            value=None,
            label="coverage",
            details={"reason": "missing_income"},
        )
    if schedule.sum_assured_inr is None:
        return LifeScoreBreakdown(
            value=None,
            label="coverage",
            details={"reason": "missing_sum_assured"},
        )

    actual_cover = int(schedule.sum_assured_inr)
    income_multiple = actual_cover / float(profile.annual_income)
    multiple_band_score = _income_multiple_score(income_multiple)

    dependent_boost = min(MAX_DEPENDENT_BOOST, profile.dependents * DEPENDENT_BOOST_PER_PERSON)
    required_multiple = BASE_REQUIRED_INCOME_MULTIPLE + dependent_boost
    required_cover = int(
        round(
            profile.annual_income * required_multiple
            + profile.liabilities_inr * LIABILITY_COVER_FACTOR
        )
    )
    required_ratio = min(REQUIRED_RATIO_CAP, actual_cover / max(1.0, float(required_cover)))

    blended = (
        multiple_band_score * COVERAGE_WEIGHT_MULTIPLE_BAND
        + (required_ratio * 100.0) * COVERAGE_WEIGHT_REQUIRED_RATIO
    )
    value = max(0, min(100, int(round(blended))))

    return LifeScoreBreakdown(
        value=value,
        label="coverage",
        details={
            "sum_assured_inr": actual_cover,
            "annual_income_inr": profile.annual_income,
            "income_multiple": round(income_multiple, 2),
            "income_multiple_band_score": multiple_band_score,
            "dependents": profile.dependents,
            "dependent_boost": round(dependent_boost, 2),
            "required_multiple": round(required_multiple, 2),
            "liabilities_inr": profile.liabilities_inr,
            "required_cover_inr": required_cover,
            "required_ratio": round(required_ratio, 3),
            "weights": {
                "multiple_band": COVERAGE_WEIGHT_MULTIPLE_BAND,
                "required_ratio": COVERAGE_WEIGHT_REQUIRED_RATIO,
            },
        },
    )
