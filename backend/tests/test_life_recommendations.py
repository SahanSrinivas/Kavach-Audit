from __future__ import annotations

from dataclasses import replace

from services.life.audit.types import LifeAuditResult, LifeFinding, LifeScoreBreakdown, LifeUserProfile
from services.life.recommendations import generate


def _profile(**overrides: object) -> LifeUserProfile:
    return replace(
        LifeUserProfile(
            user_id="u1",
            age=35,
            dependents=2,
            annual_income=1_200_000,
            smoker=False,
            liabilities_inr=2_500_000,
        ),
        **overrides,
    )


def _finding(f_type: str, severity: str = "amber") -> LifeFinding:
    return LifeFinding(
        id=f"f-{f_type}",
        severity=severity,
        type=f_type,
        icon="icon",
        headline="h",
        explanation="e",
        action="a",
    )


def _audit(
    findings: list[LifeFinding],
    *,
    sum_assured: int = 8_000_000,
    cover_end_age: int = 55,
) -> LifeAuditResult:
    gap = LifeScoreBreakdown(
        value=70,
        label="gap",
        details={
            "sum_assured_inr": sum_assured,
            "cover_end_age": cover_end_age,
        },
    )
    return LifeAuditResult(
        id="audit-1",
        user_id="u1",
        scores={"coverage": 70, "cost": 70, "claim_readiness": 70, "gap": 70},
        findings=findings[:3],
        all_findings=findings,
        breakdowns={"gap": gap},
        data_version="life-2026.05",
        engine_ms=1,
        generated_at="2026-05-06T00:00:00+00:00",
    )


def test_underinsured_life_generates_term_top_up():
    profile = _profile()
    audit = _audit([_finding("underinsured_life", "red")], sum_assured=8_000_000)

    rec = generate(audit, profile)[0]
    assert rec.type == "term_top_up"
    assert rec.suggested_sum_assured_inr == 7_700_000
    assert rec.suggested_term_years == 25


def test_no_nominee_generates_action_only():
    rec = generate(_audit([_finding("no_nominee", "red")]), _profile())[0]
    assert rec.type == "set_nominee"
    assert rec.suggested_sum_assured_inr is None
    assert rec.estimated_annual_premium_range is None


def test_missing_critical_illness_generates_ci_recommendation():
    rec = generate(_audit([_finding("missing_critical_illness", "amber")]), _profile())[0]
    assert rec.type == "ci_rider_or_standalone"
    assert rec.suggested_sum_assured_inr == 600_000


def test_missing_critical_illness_caps_sum_assured_at_25_lakh():
    rec = generate(
        _audit([_finding("missing_critical_illness", "amber")]),
        _profile(annual_income=8_000_000),
    )[0]
    assert rec.suggested_sum_assured_inr == 2_500_000


def test_missing_accidental_death_generates_ad_rider():
    rec = generate(_audit([_finding("missing_accidental_death", "amber")]), _profile())[0]
    assert rec.type == "ad_rider"
    assert rec.suggested_sum_assured_inr == 8_000_000


def test_term_too_short_generates_extend_term():
    rec = generate(_audit([_finding("term_too_short", "amber")], cover_end_age=45), _profile())[0]
    assert rec.type == "extend_term"
    assert rec.suggested_term_years == 25
    assert "age 45" in rec.reasoning


def test_endowment_returns_low_generates_term_plus_invest():
    rec = generate(_audit([_finding("endowment_returns_low", "amber")]), _profile())[0]
    assert rec.type == "term_plus_invest"
    assert rec.suggested_provider_tier.startswith("top-CSR insurer")
    assert "20 years" in rec.reasoning


def test_single_dependent_risk_generates_diversify_cover():
    rec = generate(_audit([_finding("single_dependent_risk", "amber")]), _profile())[0]
    assert rec.type == "diversify_cover"
    assert rec.suggested_sum_assured_inr == 7_700_000


def test_zero_findings_returns_stay_with_current_only():
    recs = generate(_audit([]), _profile())
    assert len(recs) == 1
    assert recs[0].type == "stay_with_current"


def test_info_only_findings_returns_stay_with_current_only():
    recs = generate(_audit([_finding("no_personal_accident_cover", "info")]), _profile())
    assert len(recs) == 1
    assert recs[0].type == "stay_with_current"


def test_multiple_findings_ordered_by_priority_rank():
    recs = generate(
        _audit(
            [
                _finding("single_dependent_risk", "amber"),
                _finding("term_too_short", "amber"),
                _finding("underinsured_life", "amber"),
            ]
        ),
        _profile(),
    )
    assert [r.type for r in recs] == ["term_top_up", "extend_term", "diversify_cover"]


def test_red_triggered_recommendations_come_before_amber():
    recs = generate(
        _audit([_finding("missing_critical_illness", "amber"), _finding("no_nominee", "red")]),
        _profile(),
    )
    assert recs[0].type == "set_nominee"
    assert recs[1].type == "ci_rider_or_standalone"


def test_premium_range_for_30s_non_smoker_term_product():
    rec = generate(
        _audit([_finding("underinsured_life", "red")], sum_assured=13_000_000),
        _profile(age=35, annual_income=1_400_000, liabilities_inr=600_000),
    )[0]
    assert rec.suggested_sum_assured_inr == 3_000_000
    assert rec.estimated_annual_premium_range == (4500, 6500)


def test_smoker_uplift_applies_to_premium():
    non_smoker = generate(
        _audit([_finding("underinsured_life", "red")], sum_assured=13_000_000),
        _profile(age=35, annual_income=1_400_000, liabilities_inr=600_000, smoker=False),
    )[0]
    smoker = generate(
        _audit([_finding("underinsured_life", "red")], sum_assured=13_000_000),
        _profile(age=35, annual_income=1_400_000, liabilities_inr=600_000, smoker=True),
    )[0]
    assert smoker.estimated_annual_premium_range is not None
    assert non_smoker.estimated_annual_premium_range is not None
    assert smoker.estimated_annual_premium_range[0] > non_smoker.estimated_annual_premium_range[0]


def test_premium_ranges_are_rounded_to_nearest_500():
    recs = generate(
        _audit([_finding("underinsured_life", "red"), _finding("missing_critical_illness", "amber")]),
        _profile(),
    )
    for rec in recs:
        if rec.estimated_annual_premium_range is None:
            continue
        low, high = rec.estimated_annual_premium_range
        assert low % 500 == 0
        assert high % 500 == 0


def test_underinsured_just_below_10x_gets_small_top_up():
    profile = _profile(annual_income=1_000_000, liabilities_inr=0, dependents=0)
    rec = generate(
        _audit([_finding("underinsured_life", "amber")], sum_assured=9_500_000),
        profile,
    )[0]
    assert rec.type == "term_top_up"
    assert rec.suggested_sum_assured_inr == 500_000


def test_missing_income_skips_income_based_recs_but_keeps_actions():
    profile = _profile(annual_income=0)
    recs = generate(
        _audit([_finding("underinsured_life", "red"), _finding("no_nominee", "red")]),
        profile,
    )
    assert [r.type for r in recs] == ["set_nominee"]
