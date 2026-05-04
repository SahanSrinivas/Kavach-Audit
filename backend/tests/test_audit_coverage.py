"""Coverage Score unit tests — ideal cover formulas + ratio math + edges."""
from __future__ import annotations

from services.audit import coverage
from services.audit.constants.ideal_cover import (
    HEALTH_BASE_BY_TIER,
    HEALTH_FAMILY_FACTOR_MAX,
    LIFE_FLOOR,
    ideal_health_cover,
    ideal_life_cover,
    ideal_motor_cover,
    ideal_pa_cover,
)
from services.audit.types import Lifestyle, Policy, UserProfile


# ---------- ideal health cover ----------

def test_health_baseline_solo_tier1_under_45() -> None:
    user = UserProfile(user_id="x", age=30, city="Mumbai", tier="tier-1")
    assert ideal_health_cover(user) == HEALTH_BASE_BY_TIER["tier-1"]


def test_health_age_uplift_45_to_60() -> None:
    user = UserProfile(user_id="x", age=50, city="Pune", tier="tier-1")
    assert ideal_health_cover(user) == int(HEALTH_BASE_BY_TIER["tier-1"] * 1.3)


def test_health_age_uplift_60_plus_via_parent_age() -> None:
    user = UserProfile(user_id="x", age=35, city="Mumbai", tier="tier-1",
                       parents_ages={"mother": 65})
    raw = HEALTH_BASE_BY_TIER["tier-1"] * 1.6 * (1.0 + 0.30)
    assert ideal_health_cover(user) == int(raw)


def test_health_family_factor_caps_at_max() -> None:
    """All under-45 so age_uplift stays 1.0; family factor clamps at 2.5."""
    user = UserProfile(user_id="x", age=40, city="Mumbai", tier="tier-1",
                       spouse_age=38, kids_count=8)  # massive family, should clamp
    raw = HEALTH_BASE_BY_TIER["tier-1"] * 1.0 * HEALTH_FAMILY_FACTOR_MAX
    assert ideal_health_cover(user) == int(raw)


def test_health_ceiling_caps_at_50L() -> None:
    """Spec Section 2: ceiling = 50L; beyond this, super top-up is the answer."""
    user = UserProfile(user_id="x", age=40, city="Mumbai", tier="tier-1",
                       spouse_age=38, kids_count=8,
                       parents_ages={"mother": 60, "father": 62})
    assert ideal_health_cover(user) == 5_000_000


def test_health_chronic_buffer_added_when_disclosed_ped() -> None:
    base = UserProfile(user_id="x", age=35, city="Mumbai", tier="tier-1")
    with_pec = UserProfile(user_id="x", age=35, city="Mumbai", tier="tier-1",
                           parents_pec=("Diabetes",))
    assert ideal_health_cover(with_pec) > ideal_health_cover(base)
    # exactly +500_000
    assert ideal_health_cover(with_pec) == ideal_health_cover(base) + 500_000


def test_health_floor_and_ceiling() -> None:
    tier3_solo = UserProfile(user_id="x", age=25, city="Patiala", tier="tier-3")
    assert ideal_health_cover(tier3_solo) >= 500_000
    big = UserProfile(user_id="x", age=70, city="Mumbai", tier="tier-1",
                      spouse_age=68, kids_count=4,
                      parents_ages={"mother": 90}, parents_pec=("Heart",))
    assert ideal_health_cover(big) <= 5_000_000


# ---------- ideal life cover (HLV-Light) ----------

def test_life_age_curve_steps_down() -> None:
    base = lambda age: ideal_life_cover(  # noqa: E731
        UserProfile(user_id="x", age=age, city="Mumbai", tier="tier-1",
                    spouse_age=30, income=2_000_000)
    )
    # 28 (mult 20) > 35 (mult 18) > 45 (mult 15) > 53 (mult 10) > 58 (mult 6)
    assert base(28) > base(35) > base(45) > base(53) > base(58)


def test_life_no_dependents_modifier_minus_2() -> None:
    solo = UserProfile(user_id="x", age=28, city="Mumbai", tier="tier-1",
                       income=1_500_000)
    married = UserProfile(user_id="x", age=28, city="Mumbai", tier="tier-1",
                          spouse_age=27, income=1_500_000)
    assert ideal_life_cover(solo) < ideal_life_cover(married)


def test_life_floor() -> None:
    user = UserProfile(user_id="x", age=70, city="Mumbai", tier="tier-1", income=0)
    assert ideal_life_cover(user) == LIFE_FLOOR


def test_life_includes_outstanding_loans_and_subtracts_assets() -> None:
    user = UserProfile(user_id="x", age=35, city="Mumbai", tier="tier-1",
                       spouse_age=33, kids_count=1,
                       income=2_000_000, outstanding_loans=5_000_000,
                       liquid_assets=1_000_000)
    expected = 2_000_000 * 18 + 5_000_000 - 1_000_000
    assert ideal_life_cover(user) == expected


# ---------- ideal motor / PA ----------

def test_motor_zero_when_no_vehicle() -> None:
    user = UserProfile(user_id="x", age=30, city="Mumbai", tier="tier-1")
    assert ideal_motor_cover(user) == 0


def test_motor_idv_sums_two_wheeler_and_car() -> None:
    user = UserProfile(user_id="x", age=30, city="Mumbai", tier="tier-1",
                       lifestyle=Lifestyle(two_wheeler=True, owns_car=True))
    assert ideal_motor_cover(user) == 200_000 + 800_000


def test_pa_zero_when_no_deps_and_no_two_wheeler() -> None:
    user = UserProfile(user_id="x", age=30, city="Mumbai", tier="tier-1",
                       income=1_500_000)
    assert ideal_pa_cover(user) == 0


def test_pa_uses_10x_income_when_required() -> None:
    user = UserProfile(user_id="x", age=30, city="Mumbai", tier="tier-1",
                       spouse_age=29, income=1_500_000)
    assert ideal_pa_cover(user) == 15_000_000


# ---------- coverage.score: ratio cap, weights, edges ----------

def test_coverage_zero_policies_zero_data_returns_none() -> None:
    user = UserProfile(user_id="x", age=0, city="", tier="")
    b = coverage.score(user, [])
    assert b.value is None


def test_coverage_ratio_caps_at_120pct() -> None:
    """Spec Section 2: cap at 1.2× so 50% over-insured doesn't inflate."""
    user = UserProfile(user_id="x", age=30, city="Mumbai", tier="tier-1")
    huge = Policy(id="h", type="health", insurer="HDFC ERGO General",
                  sum_insured=20_000_000, premium=50_000)  # way over ideal
    b = coverage.score(user, [huge])
    by_cat = b.details["by_category"]
    assert by_cat["health"]["ratio"] == 1.2  # hard cap


def test_employer_group_health_credited_at_80pct() -> None:
    user = UserProfile(user_id="x", age=30, city="Mumbai", tier="tier-1")
    grp = Policy(id="h", type="health", insurer="ICICI Lombard",
                 sum_insured=1_000_000, premium=0, is_employer_group=True)
    b = coverage.score(user, [grp])
    actual = b.details["by_category"]["health"]["actual"]
    assert actual == int(1_000_000 * 0.80)


def test_ulip_credited_at_30pct_for_life() -> None:
    user = UserProfile(user_id="x", age=30, city="Mumbai", tier="tier-1",
                       spouse_age=29, income=1_500_000)
    ulip = Policy(id="u", type="ulip", insurer="HDFC Life",
                  sum_insured=10_000_000, premium=120_000)
    b = coverage.score(user, [ulip])
    actual = b.details["by_category"]["life"]["actual"]
    assert actual == int(10_000_000 * 0.30)


def test_multiple_health_policies_sum() -> None:
    user = UserProfile(user_id="x", age=30, city="Mumbai", tier="tier-1")
    p1 = Policy(id="h1", type="health", insurer="HDFC ERGO General",
                sum_insured=500_000, premium=10_000)
    p2 = Policy(id="h2", type="health", insurer="Niva Bupa",
                sum_insured=1_000_000, premium=15_000)
    b = coverage.score(user, [p1, p2])
    assert b.details["by_category"]["health"]["actual"] == 1_500_000


# Issue 1 regression — wording-only policy (null sum_insured) excluded

def test_coverage_excludes_policy_with_null_sum_insured() -> None:
    """A wording-only PDF (no schedule) has sum_insured=None. It must
    not contribute to coverage aggregation as if it were ₹0 cover —
    that would silently dilute scores."""
    user = UserProfile(user_id="x", age=30, city="Mumbai", tier="tier-1")
    real = Policy(id="h1", type="health", insurer="HDFC ERGO General",
                  sum_insured=1_000_000, premium=15_000)
    wording = Policy(id="h2", type="health", insurer="Niva Bupa",
                     sum_insured=None, premium=None)
    b = coverage.score(user, [real, wording])
    # Only the real policy's SI counts toward the health total
    assert b.details["by_category"]["health"]["actual"] == 1_000_000


def test_coverage_does_not_crash_on_only_wording_policy() -> None:
    """If the user uploaded ONLY wording PDFs, coverage gracefully
    reports None for the affected categories (engine should not raise)."""
    user = UserProfile(user_id="x", age=30, city="Mumbai", tier="tier-1")
    wording = Policy(id="h1", type="health", insurer="Niva Bupa",
                     sum_insured=None, premium=None)
    b = coverage.score(user, [wording])
    # Health row records actual=0 (no real cover), ratio=None (no contribution)
    assert b.details["by_category"]["health"]["actual"] == 0
