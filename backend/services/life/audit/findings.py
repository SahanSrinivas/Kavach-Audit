"""Life findings generator from score breakdowns."""

from __future__ import annotations

from typing import Mapping, Sequence

from services.life.audit.types import (
    LifeFinding,
    LifeScheduleInput,
    LifeScoreBreakdown,
    LifeUserProfile,
)

# --- Ranking ---
SEVERITY_RANK = {"red": 3, "amber": 2, "info": 1}
TOP_FINDINGS_COUNT = 3

# --- Common thresholds used for derived findings ---
# Premium >5% of annual income is treated as affordability stress.
PREMIUM_OVERWEIGHT_RATIO = 0.05
# Very low coverage multiple (for red underinsurance severity).
UNDERINSURED_RED_MAX_MULTIPLE = 5.0
# Term ending before age 50 is severe; 50-60 is amber.
TERM_TOO_SHORT_RED_AGE = 50
TERM_TOO_SHORT_AMBER_AGE = 60

# --- Type metadata ---
ICON_BY_TYPE = {
    "underinsured_life": "shield-off",
    "missing_critical_illness": "heart-pulse",
    "missing_accidental_death": "alert-triangle",
    "term_too_short": "clock",
    "no_personal_accident_cover": "shield-alert",
    "single_dependent_risk": "users",
    "endowment_returns_low": "trending-down",
    "no_nominee": "user-x",
    "premium_overweight": "wallet",
}

RECOMMENDATION_BY_TYPE = {
    "underinsured_life": "buy_term_top_up",
    "missing_critical_illness": "add_ci_rider",
    "missing_accidental_death": "add_adb_rider",
    "term_too_short": "increase_term",
    "no_personal_accident_cover": "buy_pa_cover",
    "single_dependent_risk": "add_contingent_nominee",
    "endowment_returns_low": "switch_to_term_plus_invest",
    "no_nominee": "set_nominee",
    "premium_overweight": "rebalance_cover_mix",
}

# Synthetic equivalence values so derived findings have comparable impact ordering.
NOMINEE_PENALTY_EQUIVALENT = 20
ENDOWMENT_COST_PENALTY_EQUIVALENT = 15
PREMIUM_OVERWEIGHT_PENALTY_EQUIVALENT = 10


def _severity_for_gap(code: str, deduction: Mapping[str, object]) -> str:
    if code == "underinsured_life":
        multiple = float(deduction.get("income_multiple") or 0.0)
        return "red" if multiple < UNDERINSURED_RED_MAX_MULTIPLE else "amber"
    if code == "missing_critical_illness":
        return "amber"
    if code == "missing_accidental_death":
        return "amber"
    if code == "term_too_short":
        cover_end_age = int(deduction.get("cover_end_age") or 0)
        if cover_end_age < TERM_TOO_SHORT_RED_AGE:
            return "red"
        if cover_end_age < TERM_TOO_SHORT_AMBER_AGE:
            return "amber"
        return "info"
    if code == "no_personal_accident_cover":
        return "info"
    if code == "single_dependent_risk":
        return "amber"
    return "info"


def _render_gap_copy(code: str, d: Mapping[str, object]) -> tuple[str, str, str]:
    if code == "underinsured_life":
        multiple = float(d.get("income_multiple") or 0.0)
        headline = f"Life cover is only {multiple:.1f}x income."
        explanation = (
            "Your family may face a major income-replacement gap if something happens to you. "
            "Most life planning baselines start around 10x annual income."
        )
        action = "Increase term cover to at least 10x annual income."
        return headline, explanation, action
    if code == "missing_critical_illness":
        return (
            "Critical illness protection is missing.",
            "A major diagnosis can disrupt income and savings even when hospitalization is covered. "
            "Life plans without CI support leave this gap open.",
            "Add a critical illness rider or standalone CI plan.",
        )
    if code == "missing_accidental_death":
        return (
            "Accidental death benefit is missing.",
            "Base life cover may not provide additional support in accidental-death scenarios. "
            "AD benefit helps protect dependents in high-shock events.",
            "Add accidental death benefit to your life plan.",
        )
    if code == "term_too_short":
        cover_end_age = int(d.get("cover_end_age") or 0)
        return (
            f"Life cover ends by age {cover_end_age}.",
            "Your protection may stop before key family responsibilities are over. "
            "A short term can leave dependents exposed later in life.",
            "Extend policy term so cover continues to at least age 60.",
        )
    if code == "no_personal_accident_cover":
        return (
            "No personal accident cover detected.",
            "Accident disability/death risks are often outside base life policy payouts. "
            "Even a modest PA layer improves resilience.",
            "Add standalone personal accident cover.",
        )
    if code == "single_dependent_risk":
        return (
            "Family risk is concentrated in one life policy.",
            "With dependents, relying on a single policy structure can create payout and continuity risk. "
            "A layered setup is generally safer.",
            "Create a second protection layer and add contingent nominee.",
        )
    return (
        code.replace("_", " ").title(),
        "Potential protection gap detected.",
        "Review this coverage area.",
    )


def _make_finding(
    finding_type: str,
    *,
    severity: str,
    schedule_id: str | None,
    headline: str,
    explanation: str,
    action: str,
    score_impact: Mapping[str, int],
) -> LifeFinding:
    policy_id = schedule_id or "life"
    return LifeFinding(
        id=f"f-{finding_type}-{policy_id}",
        severity=severity,
        type=finding_type,
        icon=ICON_BY_TYPE.get(finding_type, "alert-circle"),
        headline=headline,
        explanation=explanation,
        action=action,
        score_impact=dict(score_impact),
        related_policy_id=schedule_id,
        recommendation=RECOMMENDATION_BY_TYPE.get(finding_type, "review_policy"),
    )


def _impact_value(f: LifeFinding) -> int:
    return int(sum(abs(v) for v in f.score_impact.values()))


def generate(
    profile: LifeUserProfile,
    schedule: LifeScheduleInput,
    breakdowns: Mapping[str, LifeScoreBreakdown],
) -> tuple[list[LifeFinding], list[LifeFinding]]:
    """Build (top_3, all_ranked) findings from score breakdowns."""
    out: list[LifeFinding] = []

    # Gap-driven findings
    gap = breakdowns.get("gap")
    for d in (gap.details.get("deductions", []) if gap and gap.details else []):
        if not isinstance(d, Mapping):
            continue
        code = str(d.get("code") or "")
        if not code:
            continue
        deduction = int(d.get("deduction") or 0)
        severity = _severity_for_gap(code, d)
        headline, explanation, action = _render_gap_copy(code, d)
        out.append(
            _make_finding(
                code,
                severity=severity,
                schedule_id=schedule.schedule_id,
                headline=headline,
                explanation=explanation,
                action=action,
                score_impact={"gap": -deduction},
            )
        )

    # Claim-readiness: no nominee => red
    claim_readiness = breakdowns.get("claim_readiness")
    if claim_readiness and claim_readiness.details:
        if not bool(claim_readiness.details.get("nominee_section_likely", False)):
            out.append(
                _make_finding(
                    "no_nominee",
                    severity="red",
                    schedule_id=schedule.schedule_id,
                    headline="Nominee details are missing or unclear.",
                    explanation=(
                        "Claims can slow down significantly when nominee designation is missing. "
                        "This creates avoidable stress for dependents at settlement time."
                    ),
                    action="Add and verify nominee details in policy records.",
                    score_impact={"claim_readiness": -NOMINEE_PENALTY_EQUIVALENT},
                )
            )

    # Cost-derived: endowment/ULIP inefficiency flag
    cost = breakdowns.get("cost")
    if cost and cost.details and bool(cost.details.get("investment_product_penalty_applied", False)):
        out.append(
            _make_finding(
                "endowment_returns_low",
                severity="amber",
                schedule_id=schedule.schedule_id,
                headline="Current plan likely mixes insurance with low-return savings.",
                explanation=(
                    "Investment-oriented life products often provide inefficient protection per rupee premium. "
                    "A term + separate investment approach is usually more cost-effective."
                ),
                action="Review switch to term cover plus separate long-term investments.",
                score_impact={"cost": -ENDOWMENT_COST_PENALTY_EQUIVALENT},
            )
        )

    # Derived affordability finding: premium overweight
    if (
        profile.annual_income > 0
        and schedule.modal_premium_inr is not None
        and schedule.modal_premium_inr > 0
    ):
        # Approximate annual premium from known frequencies.
        freq = (schedule.premium_frequency or "annual").strip().lower()
        factor = {"monthly": 12, "quarterly": 4, "half-yearly": 2, "annual": 1}.get(freq, 1)
        annualized = int(schedule.modal_premium_inr * factor)
        ratio = annualized / float(profile.annual_income)
        if ratio > PREMIUM_OVERWEIGHT_RATIO:
            out.append(
                _make_finding(
                    "premium_overweight",
                    severity="amber",
                    schedule_id=schedule.schedule_id,
                    headline=f"Annual premium is {ratio * 100:.1f}% of income.",
                    explanation=(
                        "When life premium load is too high, long-term continuity suffers and lapse risk rises. "
                        "This can reduce real protection exactly when needed."
                    ),
                    action="Optimize premium burden to around 5% of annual income or less.",
                    score_impact={"cost": -PREMIUM_OVERWEIGHT_PENALTY_EQUIVALENT},
                )
            )

    out.sort(key=lambda f: (SEVERITY_RANK.get(f.severity, 0), _impact_value(f)), reverse=True)
    top = out[:TOP_FINDINGS_COUNT]
    return top, out


