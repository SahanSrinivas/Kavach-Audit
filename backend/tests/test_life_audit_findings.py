from dataclasses import replace

from services.life.audit import findings
from services.life.audit.types import (
    LifeScheduleInput,
    LifeScoreBreakdown,
    LifeUserProfile,
)


def _profile(**overrides) -> LifeUserProfile:
    base = LifeUserProfile(user_id="u1", age=35, annual_income=100_000, dependents=1)
    return replace(base, **overrides)


def _schedule(**overrides) -> LifeScheduleInput:
    base = LifeScheduleInput(
        schedule_id="s1",
        product_name="Plan",
        sum_assured_inr=700_000,
        policy_term_years=20,
        premium_payment_term_years=20,
        modal_premium_inr=1_000,
        premium_frequency="Monthly",
        nominee_section_likely=False,
        free_look_days=10,
        detected_riders=(),
    )
    return replace(base, **overrides)


def _breakdowns(gap_deductions, *, nominee=False, endowment=False):
    return {
        "coverage": LifeScoreBreakdown(value=60, label="coverage", details={}),
        "cost": LifeScoreBreakdown(
            value=70,
            label="cost",
            details={"investment_product_penalty_applied": endowment},
        ),
        "claim_readiness": LifeScoreBreakdown(
            value=50,
            label="claim_readiness",
            details={"nominee_section_likely": nominee},
        ),
        "gap": LifeScoreBreakdown(
            value=40,
            label="gap",
            details={"deductions": gap_deductions},
        ),
    }


def test_underinsured_severity_red_and_amber():
    red = _breakdowns([{"code": "underinsured_life", "deduction": 20, "income_multiple": 4.0}])
    amber = _breakdowns([{"code": "underinsured_life", "deduction": 20, "income_multiple": 7.0}])
    _, red_all = findings.generate(_profile(), _schedule(), red)
    _, amber_all = findings.generate(_profile(), _schedule(), amber)
    assert next(f for f in red_all if f.type == "underinsured_life").severity == "red"
    assert next(f for f in amber_all if f.type == "underinsured_life").severity == "amber"


def test_term_too_short_severity_red_and_amber():
    red_b = _breakdowns([{"code": "term_too_short", "deduction": 25, "cover_end_age": 45}])
    amber_b = _breakdowns([{"code": "term_too_short", "deduction": 25, "cover_end_age": 55}])
    _, red_all = findings.generate(_profile(), _schedule(), red_b)
    _, amber_all = findings.generate(_profile(), _schedule(), amber_b)
    assert next(f for f in red_all if f.type == "term_too_short").severity == "red"
    assert next(f for f in amber_all if f.type == "term_too_short").severity == "amber"


def test_top3_ranked_by_severity_then_impact_and_all_contains_everything():
    b = _breakdowns(
        [
            {"code": "underinsured_life", "deduction": 20, "income_multiple": 4.0},
            {"code": "missing_critical_illness", "deduction": 20},
            {"code": "no_personal_accident_cover", "deduction": 10},
            {"code": "single_dependent_risk", "deduction": 10},
        ],
        nominee=False,
        endowment=True,
    )
    top, all_f = findings.generate(_profile(), _schedule(), b)
    assert len(top) == 3
    assert len(all_f) >= len(top)
    severities = [f.severity for f in top]
    assert severities == sorted(severities, key=lambda s: {"red": 3, "amber": 2, "info": 1}[s], reverse=True)


def test_no_nominee_finding_fires():
    b = _breakdowns([], nominee=False)
    _, all_f = findings.generate(_profile(), _schedule(), b)
    assert any(f.type == "no_nominee" for f in all_f)


def test_premium_overweight_finding_fires():
    b = _breakdowns([], nominee=True)
    _, all_f = findings.generate(_profile(annual_income=100_000), _schedule(modal_premium_inr=1_000, premium_frequency="Monthly"), b)
    assert any(f.type == "premium_overweight" for f in all_f)
