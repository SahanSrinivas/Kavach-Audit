from dataclasses import replace

from services.life.audit import coverage
from services.life.audit.types import LifeScheduleInput, LifeUserProfile


def _profile(**overrides) -> LifeUserProfile:
    base = LifeUserProfile(user_id="u1", age=35, annual_income=100_000, dependents=0, liabilities_inr=0)
    return replace(base, **overrides)


def _schedule(**overrides) -> LifeScheduleInput:
    base = LifeScheduleInput(
        schedule_id="s1",
        product_name="Plan",
        sum_assured_inr=1_500_000,
        policy_term_years=25,
        premium_payment_term_years=20,
        modal_premium_inr=1_000,
        premium_frequency="Annual",
        nominee_section_likely=True,
        free_look_days=15,
    )
    return replace(base, **overrides)


def test_score_100_at_15x_income():
    out = coverage.score(_profile(), _schedule(sum_assured_inr=1_500_000))
    assert out.value == 100


def test_score_band_80_at_10_to_15x_income():
    out = coverage.score(_profile(), _schedule(sum_assured_inr=1_000_000))
    assert out.details["income_multiple_band_score"] == 80
    assert 80 <= int(out.value or 0) <= 90


def test_score_band_60_at_5_to_10x_income():
    out = coverage.score(_profile(), _schedule(sum_assured_inr=700_000))
    assert out.details["income_multiple_band_score"] == 60
    assert 60 <= int(out.value or 0) <= 70


def test_score_40_below_5x_income():
    out = coverage.score(_profile(), _schedule(sum_assured_inr=400_000))
    assert out.value == 40


def test_dependent_boost_increases_required_cover():
    low = coverage.score(_profile(dependents=0), _schedule(sum_assured_inr=1_000_000))
    high = coverage.score(_profile(dependents=3), _schedule(sum_assured_inr=1_000_000))
    assert int(high.details["required_cover_inr"]) > int(low.details["required_cover_inr"])


def test_liability_adds_to_required_cover():
    low = coverage.score(_profile(liabilities_inr=0), _schedule(sum_assured_inr=1_000_000))
    high = coverage.score(_profile(liabilities_inr=2_000_000), _schedule(sum_assured_inr=1_000_000))
    assert int(high.details["required_cover_inr"]) > int(low.details["required_cover_inr"])


def test_returns_none_when_income_missing():
    out = coverage.score(_profile(annual_income=0), _schedule())
    assert out.value is None
    assert out.details["reason"] == "missing_income"


def test_returns_none_when_sum_assured_missing():
    out = coverage.score(_profile(), _schedule(sum_assured_inr=None))
    assert out.value is None
    assert out.details["reason"] == "missing_sum_assured"
