"""Gap Score — "what protection do you completely lack" axis.

Spec reference: Kavachly_Audit_Engine_Spec.docx Section 5.

Algorithm: start at 100. For each protection type, check the trigger
condition. If the user IS required to have that protection AND it's
missing from their portfolio, deduct the magnitude. Only deduct when
the protection actually applies — a single 26yo with no dependents and
no loans should not be penalized for lacking term life.

Returns a ScoreBreakdown with `details.missing` listing every
{type, deduction, reason} so findings.py can mint the corresponding
"missing_*" findings.
"""
from __future__ import annotations

from typing import Sequence

from services.audit.constants.deduction_rules import GAP_DEDUCTIONS
from services.audit.types import Policy, ScoreBreakdown, UserProfile


# Threshold from spec Section 5: "Term life required if outstanding_loans > ₹10L".
TERM_LIFE_LOAN_THRESHOLD = 1_000_000

# Spec Section 5: "Home insurance required if home loan (infer from money
# snapshot EMI > ₹15K) OR self-owned home declared".
HOME_LOAN_EMI_THRESHOLD = 15_000

# Spec Section 5: "CI required if age ≥ 35 OR family history of critical illness".
CI_AGE_THRESHOLD = 35


# Map raw policy.type strings to the gap-score categories.
_HAS_PROTECTION: dict[str, str] = {
    "health": "health",
    "term": "term_life",
    "term_life": "term_life",
    "endowment": "term_life",  # endowment provides death benefit; counts
    "ulip": "term_life",       # same — death cover at face value
    "pa": "pa",
    "personal_accident": "pa",
    "ci": "ci",
    "critical_illness": "ci",
    "motor": "motor",
    "two_wheeler": "motor",
    "car": "motor",
    "travel": "travel",
    "home": "home",
    "cyber": "cyber",
}


def _has(policies: Sequence[Policy], category: str) -> bool:
    return any(_HAS_PROTECTION.get(p.type) == category for p in policies)


def _has_dependents(profile: UserProfile) -> bool:
    return (
        profile.spouse_age is not None
        or profile.kids_count > 0
        or len(profile.parents_ages) > 0
    )


def _term_life_required(profile: UserProfile) -> bool:
    """Spec Section 5: required if (dependents) OR (outstanding_loans > ₹10L).

    Single 28yo with no deps and no loans → not required → no deduction.
    """
    if _has_dependents(profile):
        return True
    if profile.outstanding_loans > TERM_LIFE_LOAN_THRESHOLD:
        return True
    return False


def _pa_required(profile: UserProfile) -> bool:
    """Spec Section 5: required if dependents OR daily two-wheeler commute."""
    return _has_dependents(profile) or profile.lifestyle.two_wheeler


def _ci_required(profile: UserProfile) -> bool:
    """Spec Section 5: required if age ≥ 35 OR family CI history."""
    return profile.age >= CI_AGE_THRESHOLD or profile.family_ci_history


def _motor_required(profile: UserProfile) -> bool:
    """Spec Section 5: required if owns vehicle (two_wheeler OR car flag)."""
    return profile.lifestyle.two_wheeler or profile.lifestyle.owns_car


def _travel_required(profile: UserProfile) -> bool:
    """Spec Section 5: required if international travel ≥ 2x/year."""
    return profile.lifestyle.travels_intl


def _home_required(profile: UserProfile) -> bool:
    """Spec Section 5: required if home loan (proxy: monthly EMI > ₹15K)
    OR self-owned home declared.
    """
    if profile.self_owned_home:
        return True
    if profile.emis > HOME_LOAN_EMI_THRESHOLD:
        return True
    return False


def score(profile: UserProfile, policies: Sequence[Policy]) -> ScoreBreakdown:
    checks: list[tuple[str, bool]] = [
        ("health",    True),  # always required
        ("term_life", _term_life_required(profile)),
        ("pa",        _pa_required(profile)),
        ("ci",        _ci_required(profile)),
        ("motor",     _motor_required(profile)),
        ("travel",    _travel_required(profile)),
        ("home",      _home_required(profile)),
        # cyber: 0 deduction in v1 (spec) — included for completeness
        ("cyber",     False),
    ]

    missing: list[dict[str, object]] = []
    total_deduction = 0
    for category, required in checks:
        if not required:
            continue
        if _has(policies, category):
            continue
        ded = GAP_DEDUCTIONS.get(category, 0)
        if ded == 0:
            continue
        # ded is negative; track as positive magnitude
        total_deduction += -ded
        missing.append({"type": category, "deduction": -ded,
                        "reason": "required_and_missing"})

    value = max(0, 100 - total_deduction)
    return ScoreBreakdown(
        value=value,
        label="gap",
        details={"missing": missing, "total_deduction": total_deduction},
    )
