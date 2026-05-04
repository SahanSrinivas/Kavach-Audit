"""Coverage Score — "is your sum insured enough" axis.

Spec reference: Kavachly_Audit_Engine_Spec.docx Section 2. Pure function on
(profile, policies). No I/O.

Algorithm:
  1. Compute ideal cover per category from the formulas in
     constants/ideal_cover.py.
  2. Compute actual cover per category by summing policy sum_insured,
     applying credit factors (employer group → 80%, ULIP/endowment → 30%).
  3. coverage_ratio = min(actual / ideal, 1.2)  per spec
  4. Weighted sum across health/life/motor/pa/other; renormalize over the
     subset of categories where ideal > 0 so categories that don't apply
     (e.g., user owns no vehicle → motor not relevant) don't drag the
     score down — Gap Score handles "missing protections" separately.
"""
from __future__ import annotations

from typing import Sequence

from services.audit.constants.deduction_rules import (
    COVERAGE_RATIO_CAP,
    COVERAGE_WEIGHTS,
    EMPLOYER_GROUP_CREDIT,
    INVESTMENT_PRODUCT_CREDIT,
)
from services.audit.constants.ideal_cover import (
    ideal_health_cover,
    ideal_life_cover,
    ideal_motor_cover,
    ideal_pa_cover,
)
from services.audit.types import Policy, ScoreBreakdown, UserProfile


# Map raw policy.type values to coverage-score categories.
# Investment products (endowment/ulip) count toward "life" but at the
# credit factor below (spec Section 2 edge case).
_TYPE_TO_CATEGORY: dict[str, str] = {
    "health": "health",
    "term": "life",
    "term_life": "life",
    "endowment": "life",
    "ulip": "life",
    "motor": "motor",
    "two_wheeler": "motor",
    "car": "motor",
    "pa": "pa",
    "personal_accident": "pa",
    "ci": "other",
    "critical_illness": "other",
    "travel": "other",
    "home": "other",
    "cyber": "other",
}


def _credited_sum_insured(policy: Policy) -> int:
    """Apply spec edge cases:
       - employer group health → 80% credit (lapses on job change)
       - ULIP / endowment → 30% credit (face value, not real protection)
       - sum_insured None → 0 credit (wording-only PDF; engine excludes
         such policies from category aggregation in _actual_by_category)
    """
    si = policy.sum_insured
    if si is None:
        return 0
    if policy.is_employer_group and policy.type == "health":
        return int(si * EMPLOYER_GROUP_CREDIT)
    if policy.type in ("ulip", "endowment"):
        return int(si * INVESTMENT_PRODUCT_CREDIT)
    return si


def _actual_by_category(policies: Sequence[Policy]) -> dict[str, int]:
    """Sum credited cover per category. Multiple policies of same type sum.
    Policies with null sum_insured (wording-only PDFs) are excluded so they
    don't dilute the user's coverage with phantom zero-cover entries.
    """
    totals: dict[str, int] = {"health": 0, "life": 0, "motor": 0, "pa": 0, "other": 0}
    for p in policies:
        if p.sum_insured is None:
            continue
        cat = _TYPE_TO_CATEGORY.get(p.type, "other")
        totals[cat] += _credited_sum_insured(p)
    return totals


def _ideal_by_category(profile: UserProfile) -> dict[str, int]:
    return {
        "health": ideal_health_cover(profile),
        "life":   ideal_life_cover(profile),
        "motor":  ideal_motor_cover(profile),
        "pa":     ideal_pa_cover(profile),
        "other":  0,  # no formula in spec; treated as N/A in ratio math
    }


def score(profile: UserProfile, policies: Sequence[Policy]) -> ScoreBreakdown:
    """Returns Coverage Score (0-100) with full per-category breakdown.

    Edge case: if there are no policies AND no profile data to compute
    ideal cover (income == 0 and tier missing), return None — spec says
    "show as null with messaging 'upload a policy or declare to see your
    coverage score.'" rather than 0, which implies failure.
    """
    if not policies and profile.income == 0 and not profile.tier:
        return ScoreBreakdown(value=None, label="coverage", details={"reason": "no_data"})

    actuals = _actual_by_category(policies)
    ideals = _ideal_by_category(profile)

    # Categories that genuinely don't apply (no vehicle → motor ideal=0;
    # no deps & no two-wheeler → PA ideal=0) are skipped entirely.
    #
    # Categories that DO apply but have zero actual coverage get
    # half-weight credit instead of being skipped (or treated at full
    # weight × 0 ratio, which would double-penalize with Gap Score). The
    # half-weight rule means a missing health policy contributes
    # 0.5 × 0.40 × 100 = -20 to the score (vs. -40 full or 0 skipped),
    # capturing the real coverage gap without double-counting.
    rows: dict[str, dict[str, float | int | None]] = {}
    weighted_sum = 0.0
    weight_total = 0.0

    for cat, weight in COVERAGE_WEIGHTS.items():
        actual = actuals.get(cat, 0)
        ideal = ideals.get(cat, 0)
        if ideal <= 0:
            # category doesn't apply (no vehicle / no PA need)
            rows[cat] = {"actual": actual, "ideal": ideal, "ratio": None, "weight": 0.0}
            continue
        if actual <= 0:
            # missing protection: half-weight, ratio implicitly 0
            rows[cat] = {"actual": 0, "ideal": ideal, "ratio": 0.0, "weight": weight * 0.5}
            weight_total += weight * 0.5
            continue
        ratio = min(actual / ideal, COVERAGE_RATIO_CAP)
        rows[cat] = {"actual": actual, "ideal": ideal, "ratio": round(ratio, 4), "weight": weight}
        weighted_sum += ratio * weight
        weight_total += weight

    if weight_total == 0:
        return ScoreBreakdown(value=None, label="coverage", details={"reason": "no_applicable_categories"})

    raw = (weighted_sum / weight_total) * 100
    value = max(0, min(100, int(round(raw))))
    return ScoreBreakdown(
        value=value,
        label="coverage",
        details={"by_category": rows, "weighted_sum": round(weighted_sum, 4),
                 "weight_total": round(weight_total, 4)},
    )