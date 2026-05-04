"""Gap Score unit tests — every protection × applicable/not-applicable."""
from __future__ import annotations

from services.audit import gap
from services.audit.types import Lifestyle, Policy, UserProfile


def _u(**kw: object) -> UserProfile:
    """Build a UserProfile for tests. Caller may override `lifestyle` —
    Lifestyle() is the dataclass default and applies if no override."""
    base: dict[str, object] = {"user_id": "x", "age": 30, "city": "Mumbai", "tier": "tier-1"}
    base.update(kw)
    return UserProfile(**base)  # type: ignore[arg-type]


def _hp(category: str = "health") -> Policy:
    return Policy(id=category, type=category, insurer="HDFC ERGO General",
                  sum_insured=1_000_000, premium=20_000)


# ---------- Health (always required) ----------

def test_missing_health_always_deducts() -> None:
    b = gap.score(_u(), [])
    types = {m["type"] for m in b.details["missing"]}
    assert "health" in types
    assert b.value <= 70  # at least -30 from health


# ---------- Term life ----------

def test_term_life_not_required_for_single_no_loans() -> None:
    """Spec Section 5: '0 deduction — Don't penalize. Term insurance for a
    26-year-old with no dependents is wasted spend.'"""
    user = _u(age=26)
    b = gap.score(user, [_hp("health")])
    types = {m["type"] for m in b.details["missing"]}
    assert "term_life" not in types


def test_term_life_required_when_dependents() -> None:
    user = _u(spouse_age=29, kids_count=1)
    b = gap.score(user, [_hp("health")])
    types = {m["type"] for m in b.details["missing"]}
    assert "term_life" in types


def test_term_life_required_when_loans_above_10L() -> None:
    user = _u(outstanding_loans=2_000_000)
    b = gap.score(user, [_hp("health")])
    types = {m["type"] for m in b.details["missing"]}
    assert "term_life" in types


def test_term_life_satisfied_by_term_policy() -> None:
    user = _u(spouse_age=29, kids_count=1)
    b = gap.score(user, [_hp("health"), _hp("term")])
    types = {m["type"] for m in b.details["missing"]}
    assert "term_life" not in types


# ---------- Personal accident ----------

def test_pa_required_for_two_wheeler_commuter() -> None:
    user = _u(lifestyle=Lifestyle(two_wheeler=True))
    b = gap.score(user, [_hp("health")])
    types = {m["type"] for m in b.details["missing"]}
    assert "pa" in types


def test_pa_not_required_for_solo_no_two_wheeler() -> None:
    user = _u()
    b = gap.score(user, [_hp("health")])
    types = {m["type"] for m in b.details["missing"]}
    assert "pa" not in types


# ---------- Critical illness ----------

def test_ci_required_at_age_35_plus() -> None:
    user = _u(age=36)
    b = gap.score(user, [_hp("health")])
    types = {m["type"] for m in b.details["missing"]}
    assert "ci" in types


def test_ci_not_required_under_35_no_family_history() -> None:
    user = _u(age=30)
    b = gap.score(user, [_hp("health")])
    types = {m["type"] for m in b.details["missing"]}
    assert "ci" not in types


def test_ci_required_with_family_history_under_35() -> None:
    user = _u(age=28, family_ci_history=True)
    b = gap.score(user, [_hp("health")])
    types = {m["type"] for m in b.details["missing"]}
    assert "ci" in types


# ---------- Motor ----------

def test_motor_required_when_owns_vehicle() -> None:
    user = _u(lifestyle=Lifestyle(owns_car=True))
    b = gap.score(user, [_hp("health")])
    types = {m["type"] for m in b.details["missing"]}
    assert "motor" in types


# ---------- Travel ----------

def test_travel_required_for_intl_traveler() -> None:
    user = _u(lifestyle=Lifestyle(travels_intl=True))
    b = gap.score(user, [_hp("health")])
    types = {m["type"] for m in b.details["missing"]}
    assert "travel" in types


# ---------- Home ----------

def test_home_required_when_emi_above_15K() -> None:
    user = _u(emis=20_000)
    b = gap.score(user, [_hp("health")])
    types = {m["type"] for m in b.details["missing"]}
    assert "home" in types


def test_home_required_when_self_owned() -> None:
    user = _u(self_owned_home=True)
    b = gap.score(user, [_hp("health")])
    types = {m["type"] for m in b.details["missing"]}
    assert "home" in types


# ---------- Cyber: 0 deduction in v1 ----------

def test_cyber_never_deducts_in_v1() -> None:
    user = _u(spouse_age=29, kids_count=2,
              lifestyle=Lifestyle(two_wheeler=True, owns_car=True, travels_intl=True),
              self_owned_home=True, emis=20_000)
    b = gap.score(user, [])
    types = {m["type"] for m in b.details["missing"]}
    assert "cyber" not in types


# ---------- Aggregated math ----------

def test_total_score_equals_100_minus_sum_of_deductions() -> None:
    user = _u(spouse_age=29, kids_count=2)  # term_life required
    b = gap.score(user, [])  # missing everything
    expected = 100 - b.details["total_deduction"]
    assert b.value == max(0, expected)


def test_score_clamped_at_zero() -> None:
    user = _u(spouse_age=29, kids_count=3,
              lifestyle=Lifestyle(two_wheeler=True, owns_car=True, travels_intl=True),
              age=40, family_ci_history=True, self_owned_home=True)
    b = gap.score(user, [])
    assert b.value >= 0
