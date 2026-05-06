"""Shared life benchmark helpers used by life scoring modules."""

from __future__ import annotations

from services.life.audit.types import LifeUserProfile

# Base life-cover planning multiple.
BASE_IDEAL_INCOME_MULTIPLE = 10.0
# Dependent uplift in income multiple.
DEPENDENT_BOOST_PER_PERSON = 0.5
# Keep dependent uplift bounded (same logic as coverage.py).
MAX_DEPENDENT_BOOST = 4.0
# Liabilities add 1:1 to required sum assured.
LIABILITY_COVER_FACTOR = 1.0

# Retirement-age anchor used for "term till retirement" heuristic.
RETIREMENT_AGE = 60

# Premium affordability guardrail.
PREMIUM_TO_INCOME_CAP = 0.05

# Optional insurer tier cutoffs from CSR.
INSURER_TIER_TOP_MIN = 0.97
INSURER_TIER_GOOD_MIN = 0.93


def ideal_sum_assured(profile: LifeUserProfile) -> int:
    """Income + dependent + liability based ideal sum assured."""
    dependent_boost = min(MAX_DEPENDENT_BOOST, profile.dependents * DEPENDENT_BOOST_PER_PERSON)
    multiple = BASE_IDEAL_INCOME_MULTIPLE + dependent_boost
    return int(
        round(
            profile.annual_income * multiple
            + profile.liabilities_inr * LIABILITY_COVER_FACTOR
        )
    )


def ideal_term_years(profile: LifeUserProfile) -> int:
    """Recommended cover term until retirement-age baseline."""
    return max(RETIREMENT_AGE - profile.age, 0)


def insurer_tier(csr: float) -> str:
    """CSR classification for explanatory labels in UI/insights."""
    if csr > INSURER_TIER_TOP_MIN:
        return "top"
    if csr > INSURER_TIER_GOOD_MIN:
        return "good"
    return "watch"
