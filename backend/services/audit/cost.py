"""Cost Score — "are you overpaying" axis.

Spec reference: Kavachly_Audit_Engine_Spec.docx Section 3.

Per-policy:
  1. Pick the quality bucket (A/B/C) from the policy's claim-readiness.
  2. Pull the benchmark range for (bucket, age band, tier, SI) from
     constants/premium_benchmarks.py.
  3. Map the user's actual premium to a percentile within that range:
        ≤ p25 → 95   (great deal for the quality)
        ≤ p50 → 85
        ≤ p65 → 75   (paying market rate)
        ≤ p80 → 60
        ≤ p90 → 45
        > p90 → 25   (overpaying for the quality you have)
  4. Total Cost Score = Σ(policy_cost_score × premium) / Σ(premium)
     across health policies.

Edge cases (spec Section 3):
  - User has only 1 policy → return None ("N/A"). Don't compare a single
    policy to itself.
  - Employer group → exclude from cost scoring entirely.
  - ULIPs / endowments → exclude (they aren't insurance for cost purposes).
"""
from __future__ import annotations

from typing import Sequence

from services.audit.claim_readiness import score_policy as _claim_readiness_for_policy
from services.audit.constants.deduction_rules import DISCLOSED_PED_KEYWORDS
from services.audit.constants.premium_benchmarks import (
    benchmark_range,
    quality_bucket,
)
from services.audit.types import Policy, ScoreBreakdown, UserProfile


# Spec Section 3 — percentile → score mapping.
PERCENTILE_SCORES: list[tuple[float, int]] = [
    (0.25, 95),
    (0.50, 85),
    (0.65, 75),
    (0.80, 60),
    (0.90, 45),
    (1.01, 25),  # > p90
]


def _percentile_thresholds(low: int, high: int) -> dict[str, float]:
    """From a (low, high) market range derive thresholds for each
    percentile band. Range encodes p25..p75; p65/p80/p90 stretch above.
    """
    p25 = float(low)
    p75 = float(high)
    p50 = (low + high) / 2
    span = p75 - p25
    p65 = p50 + 0.6 * (p75 - p50)
    # Above-p75: stretch by mid-span steps.
    p80 = p75 + 0.10 * span
    p90 = p75 + 0.30 * span
    return {"p25": p25, "p50": p50, "p65": p65, "p75": p75, "p80": p80, "p90": p90}


def _score_premium(premium: int, low: int, high: int) -> tuple[int, str]:
    """Map a premium to its percentile band score per spec Section 3.
    Returns (score, band_label) for downstream finding generation.
    """
    th = _percentile_thresholds(low, high)
    if premium <= th["p25"]:
        return (95, "p25")
    if premium <= th["p50"]:
        return (85, "p50")
    if premium <= th["p65"]:
        return (75, "p65")
    if premium <= th["p80"]:
        return (60, "p80")
    if premium <= th["p90"]:
        return (45, "p90")
    return (25, "p90+")


def _is_eligible(policy: Policy) -> bool:
    """Spec edge cases: employer group + ULIP/endowment excluded.
    Wording-only policies (null sum_insured / null premium) excluded —
    cost percentile math is meaningless without both numbers.
    """
    if policy.sum_insured is None or policy.premium is None:
        return False
    if policy.is_employer_group:
        return False
    if policy.type in ("ulip", "endowment"):
        return False
    if policy.type != "health":
        # Cost benchmarks are health-only in this seed table; term/motor/PA
        # need their own benchmarks (Phase 4 Riskcovry integration).
        return False
    return True


def _has_disclosed_ped(profile: UserProfile) -> bool:
    haystack = " ".join([*profile.self_pec, *profile.parents_pec]).lower()
    return any(kw in haystack for kw in DISCLOSED_PED_KEYWORDS)


def score(profile: UserProfile, policies: Sequence[Policy]) -> ScoreBreakdown:
    eligible = [p for p in policies if _is_eligible(p)]
    if len(eligible) == 0:
        return ScoreBreakdown(value=None, label="cost",
                              details={"reason": "no_eligible_policies"})
    if len(eligible) == 1:
        return ScoreBreakdown(value=None, label="cost",
                              details={"reason": "single_policy",
                                       "policy_id": eligible[0].id})

    has_ped = _has_disclosed_ped(profile)
    rows = []
    weighted_score = 0.0
    weighted_premium = 0

    for p in eligible:
        # _is_eligible filters out null sum_insured + null premium so
        # the asserts narrow the type for mypy without runtime cost.
        assert p.sum_insured is not None and p.premium is not None
        cr = _claim_readiness_for_policy(p, profile)
        bucket = quality_bucket(cr.value)
        low, high = benchmark_range(
            bucket=bucket,
            age=profile.age,
            tier=profile.tier,
            sum_insured=p.sum_insured,
            has_disclosed_ped=has_ped,
        )
        score_val, band = _score_premium(p.premium, low, high)
        rows.append({
            "policy_id": p.id,
            "premium": p.premium,
            "bucket": bucket,
            "benchmark_low": low,
            "benchmark_high": high,
            "percentile_band": band,
            "policy_cost_score": score_val,
        })
        weighted_score += score_val * p.premium
        weighted_premium += p.premium

    if weighted_premium == 0:
        return ScoreBreakdown(value=None, label="cost",
                              details={"reason": "zero_premium"})

    total = int(round(weighted_score / weighted_premium))
    return ScoreBreakdown(
        value=max(0, min(100, total)),
        label="cost",
        details={"per_policy": rows, "weighted_premium": weighted_premium},
    )
