"""Cost Score unit tests — bucketing, percentile placement, edges."""
from __future__ import annotations

from services.audit import cost
from services.audit.constants.premium_benchmarks import (
    age_band,
    benchmark_range,
    quality_bucket,
)
from services.audit.types import Policy, UserProfile


def _user(**kw: object) -> UserProfile:
    base: dict[str, object] = {"user_id": "x", "age": 35, "city": "Mumbai", "tier": "tier-1"}
    base.update(kw)
    return UserProfile(**base)  # type: ignore[arg-type]


def _h(insurer: str, premium: int, sum_insured: int = 1_000_000,
       **parsed: object) -> Policy:
    return Policy(id=f"h_{insurer[:4]}_{premium}", type="health",
                  insurer=insurer, sum_insured=sum_insured, premium=premium,
                  parsed_fields=parsed)


# ---------- bucket / age band helpers ----------

def test_quality_bucket_thresholds() -> None:
    assert quality_bucket(85) == "A"
    assert quality_bucket(80) == "A"
    assert quality_bucket(79) == "B"
    assert quality_bucket(50) == "B"
    assert quality_bucket(49) == "C"
    assert quality_bucket(None) == "B"  # defensive default


def test_age_band_borders() -> None:
    assert age_band(25) == "25-35"
    assert age_band(35) == "25-35"
    assert age_band(36) == "36-45"
    assert age_band(66) == "66+"


def test_benchmark_range_scales_with_tier_and_si() -> None:
    t1 = benchmark_range("B", 35, "tier-1", 1_000_000)
    t2 = benchmark_range("B", 35, "tier-2", 1_000_000)
    t3 = benchmark_range("B", 35, "tier-3", 1_000_000)
    assert t1[0] > t2[0] > t3[0]
    high_si = benchmark_range("B", 35, "tier-1", 5_000_000)
    assert high_si[0] > t1[0]


def test_benchmark_range_ped_loading_inflates() -> None:
    base = benchmark_range("B", 35, "tier-1", 1_000_000, has_disclosed_ped=False)
    loaded = benchmark_range("B", 35, "tier-1", 1_000_000, has_disclosed_ped=True)
    assert loaded[0] > base[0]
    assert loaded[1] > base[1]


# ---------- score: edges ----------

def test_single_policy_returns_none() -> None:
    """Spec Section 3: 'don't compare a single policy to itself.'"""
    user = _user()
    b = cost.score(user, [_h("HDFC ERGO General", premium=20_000)])
    assert b.value is None
    assert b.details["reason"] == "single_policy"


def test_zero_eligible_policies_returns_none() -> None:
    user = _user()
    b = cost.score(user, [])
    assert b.value is None


def test_employer_group_excluded_from_cost() -> None:
    """Spec Section 3: 'group cover bills 70-80% lower than individual market rates.'"""
    user = _user()
    grp = Policy(id="g", type="health", insurer="ICICI Lombard",
                 sum_insured=1_000_000, premium=0, is_employer_group=True)
    individ = _h("HDFC ERGO General", premium=20_000)
    b = cost.score(user, [grp, individ])
    # Only the individual policy is eligible → fewer than 2 → N/A
    assert b.value is None


def test_ulip_excluded_from_cost() -> None:
    user = _user()
    ulip = Policy(id="u", type="ulip", insurer="HDFC Life",
                  sum_insured=10_000_000, premium=120_000)
    individ = _h("HDFC ERGO General", premium=20_000)
    b = cost.score(user, [ulip, individ])
    assert b.value is None  # ULIP excluded → 1 eligible → N/A


# ---------- score: percentile mapping ----------

def test_below_p25_scores_95() -> None:
    user = _user()
    p1 = _h("HDFC ERGO General", premium=10_000)  # well below T1 ₹10L band low
    p2 = _h("Niva Bupa", premium=10_500)
    b = cost.score(user, [p1, p2])
    # both policies are A-bucket (no deductions); T1 25-35 A range = 14k-18k
    # 10k < 14k = p25 → score 95 each
    assert b.value == 95


def test_above_p90_scores_25() -> None:
    user = _user()
    p1 = _h("HDFC ERGO General", premium=80_000)  # way above T1 25-35 A high
    p2 = _h("Niva Bupa", premium=80_000)
    b = cost.score(user, [p1, p2])
    assert b.value == 25


# Issue 1 regression — null sum_insured / premium → ineligible for cost

def test_cost_excludes_policies_with_null_premium_or_sum_insured() -> None:
    """A wording-only PDF (null SI + null premium) is ineligible for
    cost percentile math. Verify the cost score derives from real
    policies only."""
    user = _user()
    real1 = _h("HDFC ERGO General", premium=14_000)  # bottom of T1 25-35 A range
    real2 = _h("Niva Bupa", premium=14_000)
    wording = Policy(id="w", type="health", insurer="Star Health",
                     sum_insured=None, premium=None,
                     parsed_fields={})
    b = cost.score(user, [real1, real2, wording])
    # Only the two real policies score; wording skipped silently
    assert b.value is not None
    assert len(b.details["per_policy"]) == 2
