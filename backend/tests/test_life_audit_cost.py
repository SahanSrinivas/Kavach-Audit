from dataclasses import replace

from services.life.audit import cost
from services.life.audit.types import LifeScheduleInput, LifeUserProfile


def _profile(**overrides) -> LifeUserProfile:
    base = LifeUserProfile(user_id="u1", age=35, annual_income=1_000_000, smoker=False)
    return replace(base, **overrides)


def _schedule(**overrides) -> LifeScheduleInput:
    base = LifeScheduleInput(
        schedule_id="s1",
        product_name="Pure Term",
        sum_assured_inr=10_000_000,
        policy_term_years=25,
        premium_payment_term_years=25,
        modal_premium_inr=15_000,
        premium_frequency="Annual",
        nominee_section_likely=True,
        free_look_days=15,
    )
    return replace(base, **overrides)


def test_annualization_monthly():
    out = cost.score(_profile(), _schedule(modal_premium_inr=1_000, premium_frequency="Monthly"))
    assert out.details["annualized_premium_inr"] == 12_000


def test_annualization_quarterly():
    out = cost.score(_profile(), _schedule(modal_premium_inr=2_000, premium_frequency="Quarterly"))
    assert out.details["annualized_premium_inr"] == 8_000


def test_annualization_half_yearly():
    out = cost.score(_profile(), _schedule(modal_premium_inr=3_000, premium_frequency="Half-yearly"))
    assert out.details["annualized_premium_inr"] == 6_000


def test_annualization_annual():
    out = cost.score(_profile(), _schedule(modal_premium_inr=7_000, premium_frequency="Annual"))
    assert out.details["annualized_premium_inr"] == 7_000


def test_age_banded_expected_ratios():
    r20 = cost.score(_profile(age=28), _schedule()).details["expected_ratio_inr_per_lakh"]
    r30 = cost.score(_profile(age=35), _schedule()).details["expected_ratio_inr_per_lakh"]
    r40 = cost.score(_profile(age=45), _schedule()).details["expected_ratio_inr_per_lakh"]
    r50 = cost.score(_profile(age=55), _schedule()).details["expected_ratio_inr_per_lakh"]
    r60 = cost.score(_profile(age=65), _schedule()).details["expected_ratio_inr_per_lakh"]
    assert r20 < r30 < r40 < r50 < r60


def test_smoker_uplift_applied():
    non = cost.score(_profile(smoker=False), _schedule()).details["expected_ratio_inr_per_lakh"]
    smk = cost.score(_profile(smoker=True), _schedule()).details["expected_ratio_inr_per_lakh"]
    assert smk > non


def test_term_multiplier_short_standard_long():
    short = cost.score(_profile(), _schedule(policy_term_years=10)).details["expected_ratio_inr_per_lakh"]
    standard = cost.score(_profile(), _schedule(policy_term_years=25)).details["expected_ratio_inr_per_lakh"]
    long = cost.score(_profile(), _schedule(policy_term_years=40)).details["expected_ratio_inr_per_lakh"]
    assert short > standard
    assert long > standard


def test_endowment_penalty_applied():
    out = cost.score(_profile(), _schedule(product_name="Traditional Endowment Plan", modal_premium_inr=1_000))
    assert out.details["investment_product_penalty_applied"] is True
    assert (out.value or 0) <= 80


def test_ulip_penalty_applied():
    out = cost.score(_profile(), _schedule(product_name="ULIP Wealth Builder", modal_premium_inr=1_000))
    assert out.details["investment_product_penalty_applied"] is True
    assert (out.value or 0) <= 80


def test_returns_none_when_premium_missing():
    out = cost.score(_profile(), _schedule(modal_premium_inr=None))
    assert out.value is None
    assert out.details["reason"] == "missing_premium"


def test_returns_none_when_age_missing():
    out = cost.score(_profile(age=0), _schedule())
    assert out.value is None
    assert out.details["reason"] == "missing_age"
