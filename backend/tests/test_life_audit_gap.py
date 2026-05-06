from dataclasses import replace

import pytest

from services.life.audit import gap
from services.life.audit.types import LifeScheduleInput, LifeUserProfile


def _profile(**overrides) -> LifeUserProfile:
    base = LifeUserProfile(user_id="u1", age=35, annual_income=100_000, dependents=0, liabilities_inr=0)
    return replace(base, **overrides)


def _schedule(**overrides) -> LifeScheduleInput:
    base = LifeScheduleInput(
        schedule_id="s1",
        product_name="Plan",
        sum_assured_inr=1_200_000,
        policy_term_years=30,
        premium_payment_term_years=20,
        modal_premium_inr=10_000,
        premium_frequency="Annual",
        nominee_section_likely=True,
        free_look_days=15,
        detected_riders=("critical_illness", "accidental_death", "personal_accident"),
    )
    return replace(base, **overrides)


def test_each_deduction_triggered_independently():
    assert gap.score(_profile(), _schedule(detected_riders=("accidental_death", "personal_accident"))).value == 80
    assert gap.score(_profile(), _schedule(detected_riders=("critical_illness", "personal_accident"))).value == 85
    assert gap.score(_profile(age=25), _schedule(policy_term_years=20)).value == 75
    assert gap.score(_profile(), _schedule(sum_assured_inr=900_000)).value == 80
    assert gap.score(_profile(), _schedule(detected_riders=("critical_illness", "accidental_death"))).value == 90
    assert gap.score(_profile(dependents=2), _schedule(), life_policy_count=1).value == 90


def test_multiple_deductions_stack_correctly():
    out = gap.score(
        _profile(age=30, dependents=2, annual_income=100_000),
        _schedule(
            sum_assured_inr=300_000,
            policy_term_years=15,
            detected_riders=(),
        ),
        life_policy_count=1,
    )
    assert out.value == 0
    assert int(out.details["total_deduction"]) >= 100


def test_score_floors_at_zero():
    out = gap.score(
        _profile(age=30, dependents=3),
        _schedule(sum_assured_inr=200_000, policy_term_years=10, detected_riders=()),
        life_policy_count=1,
    )
    assert out.value == 0


@pytest.mark.parametrize(
    ("profile_overrides", "schedule_overrides", "reason"),
    [
        ({"age": 0}, {}, "missing_age"),
        ({"annual_income": 0}, {}, "missing_income"),
        ({}, {"sum_assured_inr": None}, "missing_sum_assured"),
        ({}, {"policy_term_years": None}, "missing_policy_term"),
    ],
)
def test_returns_none_when_critical_inputs_missing(profile_overrides, schedule_overrides, reason):
    out = gap.score(_profile(**profile_overrides), _schedule(**schedule_overrides))
    assert out.value is None
    assert out.details["reason"] == reason


def test_rider_keyword_matching_mixed_case():
    out = gap.score(_profile(), _schedule(detected_riders=("Critical Illness Rider", "accidental death benefit", "personal accident")))
    codes = [d["code"] for d in out.details["deductions"]]
    assert "missing_critical_illness" not in codes
    assert "missing_accidental_death" not in codes


def test_rider_tag_matching_critical_illness():
    out = gap.score(_profile(), _schedule(detected_riders=("critical_illness", "accidental_death", "personal_accident")))
    codes = [d["code"] for d in out.details["deductions"]]
    assert "missing_critical_illness" not in codes


def test_single_dependent_risk_only_with_dependents_and_single_policy():
    no_dep = gap.score(_profile(dependents=0), _schedule(), life_policy_count=1)
    multi_pol = gap.score(_profile(dependents=2), _schedule(), life_policy_count=2)
    one_pol = gap.score(_profile(dependents=2), _schedule(), life_policy_count=1)
    assert "single_dependent_risk" not in [d["code"] for d in no_dep.details["deductions"]]
    assert "single_dependent_risk" not in [d["code"] for d in multi_pol.details["deductions"]]
    assert "single_dependent_risk" in [d["code"] for d in one_pol.details["deductions"]]


def test_has_personal_accident_anywhere_overrides_schedule_riders():
    out = gap.score(
        _profile(),
        _schedule(detected_riders=("critical_illness", "accidental_death")),
        has_personal_accident_anywhere=True,
    )
    codes = [d["code"] for d in out.details["deductions"]]
    assert "no_personal_accident_cover" not in codes
