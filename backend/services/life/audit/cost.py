"""Life cost score (0-100): whether premium is efficient for protection bought.

v1 approximation model (intentionally simple, deterministic):
  - Compute annualized premium-to-cover ratio:
      ratio = annual_premium / (sum_assured / 1,00,000)
    i.e., INR premium paid per INR 1 lakh of cover per year.
  - Adjust expected ratio by age and policy term:
      expected = base(age) * term_multiplier(term)
  - Score by how actual compares to expected:
      <= 1.0x expected -> 100
      <= 1.25x         -> 80
      <= 1.5x          -> 60
      <= 2.0x          -> 30
      > 2.0x           -> 0

This is a heuristic until we have insurer-level actuarial benchmarks.

TODO(cost-benchmark-data): replace expected-ratio heuristics with calibrated
IRDAI mortality table + product-segment benchmark curves.
"""

from __future__ import annotations

from services.life.audit.types import LifeScheduleInput, LifeScoreBreakdown, LifeUserProfile

# --- Frequency normalization ---
# Convert modal premium to annual equivalent so comparisons are apples-to-apples.
ANNUALIZATION_FACTORS = {
    "monthly": 12.0,
    "quarterly": 4.0,
    "half-yearly": 2.0,
    "annual": 1.0,
}

# --- Age benchmark anchors (INR per 1L cover per year) ---
# Term protection tends to get costlier with age; these are broad market
# approximations for non-smoker online term products in v1.
AGE_BASE_RATIO_20S = 120.0
AGE_BASE_RATIO_30S = 180.0
AGE_BASE_RATIO_40S = 300.0
AGE_BASE_RATIO_50S = 520.0
AGE_BASE_RATIO_60P = 900.0

# Smokers are usually priced materially higher; conservative uplift.
SMOKER_EXPECTED_MULTIPLIER = 1.35

# --- Term multipliers ---
# Very short terms are often less efficient for pure protection planning;
# medium-long terms are typically the market norm.
TERM_MULTIPLIER_SHORT_LT15 = 1.15
TERM_MULTIPLIER_STANDARD_15_30 = 1.0
TERM_MULTIPLIER_LONG_GT30 = 1.08

# --- Score thresholds ---
# The "2x market => 0" requirement is preserved as a hard floor.
COST_RELATIVE_GREAT_MAX = 1.0
COST_RELATIVE_GOOD_MAX = 1.25
COST_RELATIVE_FAIR_MAX = 1.5
COST_RELATIVE_POOR_MAX = 2.0

COST_SCORE_GREAT = 100
COST_SCORE_GOOD = 80
COST_SCORE_FAIR = 60
COST_SCORE_POOR = 30
COST_SCORE_OVERPRICED = 0

# Endowment/ULIP usually price protection inefficiently vs term-first designs.
INVESTMENT_PRODUCT_COST_PENALTY = 20


def _annualized_premium(schedule: LifeScheduleInput) -> int | None:
    premium = schedule.modal_premium_inr
    if premium is None or premium <= 0:
        return None
    freq_raw = (schedule.premium_frequency or "annual").strip().lower()
    factor = ANNUALIZATION_FACTORS.get(freq_raw, 1.0)
    return int(round(premium * factor))


def _expected_ratio_by_age(age: int) -> float:
    if age < 30:
        return AGE_BASE_RATIO_20S
    if age < 40:
        return AGE_BASE_RATIO_30S
    if age < 50:
        return AGE_BASE_RATIO_40S
    if age < 60:
        return AGE_BASE_RATIO_50S
    return AGE_BASE_RATIO_60P


def _term_multiplier(term_years: int | None) -> float:
    if term_years is None or term_years <= 0:
        return TERM_MULTIPLIER_STANDARD_15_30
    if term_years < 15:
        return TERM_MULTIPLIER_SHORT_LT15
    if term_years <= 30:
        return TERM_MULTIPLIER_STANDARD_15_30
    return TERM_MULTIPLIER_LONG_GT30


def _relative_cost_score(relative_cost: float) -> int:
    if relative_cost <= COST_RELATIVE_GREAT_MAX:
        return COST_SCORE_GREAT
    if relative_cost <= COST_RELATIVE_GOOD_MAX:
        return COST_SCORE_GOOD
    if relative_cost <= COST_RELATIVE_FAIR_MAX:
        return COST_SCORE_FAIR
    if relative_cost <= COST_RELATIVE_POOR_MAX:
        return COST_SCORE_POOR
    return COST_SCORE_OVERPRICED


def score(profile: LifeUserProfile, schedule: LifeScheduleInput) -> LifeScoreBreakdown:
    """Compute cost score using age/term-adjusted premium-per-lakh heuristics."""
    annual_premium = _annualized_premium(schedule)
    if annual_premium is None:
        return LifeScoreBreakdown(
            value=None,
            label="cost",
            details={"reason": "missing_premium"},
        )
    if schedule.sum_assured_inr is None or schedule.sum_assured_inr <= 0:
        return LifeScoreBreakdown(
            value=None,
            label="cost",
            details={"reason": "missing_sum_assured"},
        )
    if profile.age <= 0:
        return LifeScoreBreakdown(
            value=None,
            label="cost",
            details={"reason": "missing_age"},
        )

    cover_lakh = schedule.sum_assured_inr / 100_000.0
    actual_ratio = annual_premium / max(0.01, cover_lakh)

    expected_ratio = _expected_ratio_by_age(profile.age) * _term_multiplier(
        schedule.policy_term_years
    )
    if profile.smoker:
        expected_ratio *= SMOKER_EXPECTED_MULTIPLIER

    relative_cost = actual_ratio / max(1.0, expected_ratio)
    value = _relative_cost_score(relative_cost)

    product_name = (schedule.product_name or "").lower()
    if "endowment" in product_name or "ulip" in product_name:
        value = max(COST_SCORE_OVERPRICED, value - INVESTMENT_PRODUCT_COST_PENALTY)

    return LifeScoreBreakdown(
        value=value,
        label="cost",
        details={
            "annualized_premium_inr": annual_premium,
            "sum_assured_inr": schedule.sum_assured_inr,
            "actual_ratio_inr_per_lakh": round(actual_ratio, 2),
            "expected_ratio_inr_per_lakh": round(expected_ratio, 2),
            "relative_cost": round(relative_cost, 3),
            "age": profile.age,
            "smoker": profile.smoker,
            "policy_term_years": schedule.policy_term_years,
            "investment_product_penalty_applied": (
                "endowment" in product_name or "ulip" in product_name
            ),
        },
    )
