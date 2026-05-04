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


# Endowment / ULIP threshold for satisfying the term_life gap requirement.
# A policy must provide >= ENDOWMENT_TERM_LIFE_FLOOR_X * annual income
# in sum insured to count as meaningful term-life cover.
#
# Why 5x:
#   - Conservative compromise. Indian financial-planning convention for
#     true term life HLV is 10-15x annual income; below that, the death
#     benefit is too small to replace the breadwinner's earnings.
#   - 5x is the floor for "meaningful protection" per LIC's own training
#     materials; below it, endowment is purely a savings vehicle, not a
#     term-life substitute.
#
# Debatable extension: a stricter rule would be "endowment NEVER satisfies
# term_life regardless of SI" because the product design is fundamentally
# investment-with-death-rider, not pure protection. We did NOT implement
# that here — surfaces too many false-negatives for users with high-SI
# legacy endowment policies. Revisit with domain-expert review when we
# have audit data on the false-positive rate at 5x.
ENDOWMENT_TERM_LIFE_FLOOR_X: int = 5


def _policy_satisfies_category(p: Policy, category: str, profile: UserProfile) -> bool:
    """Per-category eligibility check beyond simple type-match.

    For term_life: endowment/ULIP only count toward the requirement if
    sum_insured >= ENDOWMENT_TERM_LIFE_FLOOR_X × annual income. Without
    this floor, a ₹4L endowment falsely satisfies the term_life gap for
    a user earning ₹15L (real bug surfaced in DOGFOOD_NOTES.md / Exide
    Life Assured Gain Plus dogfood).

    If income is unknown (profile.income == 0), we don't apply the floor
    — treat any endowment as satisfying. This avoids penalizing users
    who haven't filled out the money stage of the audit.
    """
    if category == "term_life" and p.type in ("endowment", "ulip"):
        if p.sum_insured is None:
            return False
        if profile.income > 0 and p.sum_insured < ENDOWMENT_TERM_LIFE_FLOOR_X * profile.income:
            return False
    return True


def _has(policies: Sequence[Policy], category: str, profile: UserProfile) -> bool:
    """Returns True if any policy meaningfully satisfies the category.
    See _policy_satisfies_category for the per-category eligibility rules."""
    for p in policies:
        if _HAS_PROTECTION.get(p.type) != category:
            continue
        if not _policy_satisfies_category(p, category, profile):
            continue
        return True
    return False


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
        if _has(policies, category, profile):
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
