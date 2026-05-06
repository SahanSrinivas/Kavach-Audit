"""Rule-based life recommendation generator from latest life audit findings."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Optional, Sequence

from services.life.audit.benchmarks import ideal_sum_assured, ideal_term_years
from services.life.audit.cost import (
    AGE_BASE_RATIO_20S,
    AGE_BASE_RATIO_30S,
    AGE_BASE_RATIO_40S,
    AGE_BASE_RATIO_50S,
    AGE_BASE_RATIO_60P,
    SMOKER_EXPECTED_MULTIPLIER,
    TERM_MULTIPLIER_STANDARD_15_30,
)
from services.life.audit.types import LifeAuditResult, LifeUserProfile

# --- Priority order (lower = more important) ---
PRIORITY_UNDERINSURED = 1
PRIORITY_NO_NOMINEE = 2
PRIORITY_MISSING_CI = 3
PRIORITY_MISSING_AD = 4
PRIORITY_TERM_TOO_SHORT = 5
PRIORITY_ENDOWMENT_LOW_RETURN = 6
PRIORITY_SINGLE_DEPENDENT_RISK = 7
PRIORITY_STAY_CURRENT = 8

# --- Finding severities and ordering ---
SEVERITY_RED = "red"
SEVERITY_AMBER = "amber"
SEVERITY_INFO = "info"
SEVERITY_SORT_ORDER = {SEVERITY_RED: 0, SEVERITY_AMBER: 1, SEVERITY_INFO: 2}
SEVERITY_DEFAULT_SORT = 3

# --- Recommendation assumptions ---
INCOME_BASELINE_MULTIPLE = 10.0
MIN_RECOMMENDED_TERM_YEARS = 10
CI_INCOME_SHARE = 0.5
CI_SUM_ASSURED_CAP_INR = 2_500_000
DIVERSIFY_FALLBACK_CURRENT_COVER_SHARE = 0.25

# --- Premium approximation controls ---
TERM_PREMIUM_RANGE_MARGIN = 0.15
RIDER_PREMIUM_RANGE_LOW_SHARE = 0.25
RIDER_PREMIUM_RANGE_HIGH_SHARE = 0.30
PREMIUM_ROUND_TO_INR = 500


@dataclass(frozen=True, slots=True)
class LifeRecommendation:
    id: str
    type: str
    title: str
    product_type: str
    suggested_sum_assured_inr: Optional[int]
    suggested_term_years: Optional[int]
    suggested_provider_tier: str
    estimated_annual_premium_range: Optional[tuple[int, int]]
    reasoning: str
    triggered_by_finding: Optional[str]
    priority_rank: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _round_to_nearest(amount: float, *, step: int) -> int:
    if amount <= 0:
        return 0
    return int(round(amount / float(step)) * step)


def _age_band_ratio(age: int) -> float:
    if age < 30:
        return AGE_BASE_RATIO_20S
    if age < 40:
        return AGE_BASE_RATIO_30S
    if age < 50:
        return AGE_BASE_RATIO_40S
    if age < 60:
        return AGE_BASE_RATIO_50S
    return AGE_BASE_RATIO_60P


def _recommended_term_years(profile: LifeUserProfile) -> int:
    return max(ideal_term_years(profile), MIN_RECOMMENDED_TERM_YEARS)


def _term_base_premium(profile: LifeUserProfile, sum_assured_inr: int) -> int:
    ratio = _age_band_ratio(profile.age) * TERM_MULTIPLIER_STANDARD_15_30
    smoker_multiplier = SMOKER_EXPECTED_MULTIPLIER if profile.smoker else 1.0
    premium = (sum_assured_inr / 100_000.0) * ratio * smoker_multiplier
    return _round_to_nearest(premium, step=PREMIUM_ROUND_TO_INR)


def _term_premium_range(profile: LifeUserProfile, sum_assured_inr: Optional[int]) -> Optional[tuple[int, int]]:
    if not sum_assured_inr or sum_assured_inr <= 0:
        return None
    base = _term_base_premium(profile, sum_assured_inr)
    low = _round_to_nearest(base * (1.0 - TERM_PREMIUM_RANGE_MARGIN), step=PREMIUM_ROUND_TO_INR)
    high = _round_to_nearest(base * (1.0 + TERM_PREMIUM_RANGE_MARGIN), step=PREMIUM_ROUND_TO_INR)
    return (low, max(low, high))


def _rider_premium_range(profile: LifeUserProfile, sum_assured_inr: Optional[int]) -> Optional[tuple[int, int]]:
    if not sum_assured_inr or sum_assured_inr <= 0:
        return None
    base = _term_base_premium(profile, sum_assured_inr)
    low = _round_to_nearest(base * RIDER_PREMIUM_RANGE_LOW_SHARE, step=PREMIUM_ROUND_TO_INR)
    high = _round_to_nearest(base * RIDER_PREMIUM_RANGE_HIGH_SHARE, step=PREMIUM_ROUND_TO_INR)
    return (low, max(low, high))


def _finding_meta(audit_result: LifeAuditResult | Mapping[str, Any]) -> dict[str, str]:
    findings_raw: Sequence[Any]
    if isinstance(audit_result, Mapping):
        findings_raw = list(audit_result.get("all_findings") or audit_result.get("findings") or [])
    else:
        findings_raw = list(audit_result.all_findings or audit_result.findings or [])

    out: dict[str, str] = {}
    for row in findings_raw:
        if isinstance(row, Mapping):
            f_type = str(row.get("type") or "")
            severity = str(row.get("severity") or SEVERITY_INFO)
        else:
            f_type = str(getattr(row, "type", "") or "")
            severity = str(getattr(row, "severity", SEVERITY_INFO) or SEVERITY_INFO)
        if not f_type:
            continue
        existing = out.get(f_type)
        if existing is None or SEVERITY_SORT_ORDER.get(severity, SEVERITY_DEFAULT_SORT) < SEVERITY_SORT_ORDER.get(
            existing, SEVERITY_DEFAULT_SORT
        ):
            out[f_type] = severity
    return out


def _current_sum_assured(audit_result: LifeAuditResult | Mapping[str, Any]) -> int:
    breakdowns: Mapping[str, Any]
    if isinstance(audit_result, Mapping):
        breakdowns = audit_result.get("breakdowns") or {}
    else:
        breakdowns = audit_result.breakdowns

    gap: Any = breakdowns.get("gap") if isinstance(breakdowns, Mapping) else None
    details: Mapping[str, Any] = {}
    if isinstance(gap, Mapping):
        details = gap.get("details") or {}
    else:
        details = getattr(gap, "details", {}) or {}
    return _to_int(details.get("sum_assured_inr"))


def _make_recommendation(
    *,
    rec_type: str,
    title: str,
    product_type: str,
    suggested_sum_assured_inr: Optional[int],
    suggested_term_years: Optional[int],
    suggested_provider_tier: str,
    estimated_annual_premium_range: Optional[tuple[int, int]],
    reasoning: str,
    triggered_by_finding: Optional[str],
    priority_rank: int,
) -> LifeRecommendation:
    trigger = triggered_by_finding or "general"
    return LifeRecommendation(
        id=f"rec-{rec_type}-{trigger}",
        type=rec_type,
        title=title,
        product_type=product_type,
        suggested_sum_assured_inr=suggested_sum_assured_inr,
        suggested_term_years=suggested_term_years,
        suggested_provider_tier=suggested_provider_tier,
        estimated_annual_premium_range=estimated_annual_premium_range,
        reasoning=reasoning,
        triggered_by_finding=triggered_by_finding,
        priority_rank=priority_rank,
    )


def _build_underinsured(profile: LifeUserProfile, current_cover_inr: int) -> LifeRecommendation:
    ideal_cover = ideal_sum_assured(profile)
    top_up = max(0, ideal_cover - current_cover_inr)
    multiple = (current_cover_inr / float(profile.annual_income)) if profile.annual_income > 0 else 0.0
    term_years = _recommended_term_years(profile)
    reasoning = (
        f"Your current life cover is {multiple:.1f}x your annual income. Industry baseline is {INCOME_BASELINE_MULTIPLE:.0f}x. "
        f"A top-up term plan adds Rs. {top_up:,} cover at low cost without disturbing your existing policy."
    )
    return _make_recommendation(
        rec_type="term_top_up",
        title="Top up your life cover",
        product_type="Term Insurance",
        suggested_sum_assured_inr=top_up,
        suggested_term_years=term_years,
        suggested_provider_tier="top-CSR insurer",
        estimated_annual_premium_range=_term_premium_range(profile, top_up),
        reasoning=reasoning,
        triggered_by_finding="underinsured_life",
        priority_rank=PRIORITY_UNDERINSURED,
    )


def generate(audit_result: LifeAuditResult | Mapping[str, Any], profile: LifeUserProfile) -> list[LifeRecommendation]:
    """Generate ranked recommendations from life audit findings."""
    finding_severity = _finding_meta(audit_result)
    has_red_or_amber = any(
        severity in {SEVERITY_RED, SEVERITY_AMBER}
        for severity in finding_severity.values()
    )
    if not has_red_or_amber:
        return [
            _make_recommendation(
                rec_type="stay_with_current",
                title="Your life cover looks healthy",
                product_type="No action needed",
                suggested_sum_assured_inr=None,
                suggested_term_years=None,
                suggested_provider_tier="N/A",
                estimated_annual_premium_range=None,
                reasoning=(
                    "Audit found no critical gaps. Your protection is reasonably aligned with your profile. "
                    "Re-audit at your next major life event or at policy renewal."
                ),
                triggered_by_finding=None,
                priority_rank=PRIORITY_STAY_CURRENT,
            )
        ]

    recs: list[LifeRecommendation] = []
    current_cover_inr = _current_sum_assured(audit_result)
    target_term_years = _recommended_term_years(profile)
    ideal_cover_inr = ideal_sum_assured(profile)

    if "underinsured_life" in finding_severity and profile.annual_income > 0:
        recs.append(_build_underinsured(profile, current_cover_inr))

    if "no_nominee" in finding_severity:
        recs.append(
            _make_recommendation(
                rec_type="set_nominee",
                title="Add a nominee to your policy",
                product_type="Action - not a new product",
                suggested_sum_assured_inr=None,
                suggested_term_years=None,
                suggested_provider_tier="Existing insurer",
                estimated_annual_premium_range=None,
                reasoning=(
                    "Add nominee details to your existing policy. Free, takes about 10 minutes via the insurer portal, "
                    "and prevents significant claim delays for your family."
                ),
                triggered_by_finding="no_nominee",
                priority_rank=PRIORITY_NO_NOMINEE,
            )
        )

    if "missing_critical_illness" in finding_severity and profile.annual_income > 0:
        ci_cover = min(int(profile.annual_income * CI_INCOME_SHARE), CI_SUM_ASSURED_CAP_INR)
        recs.append(
            _make_recommendation(
                rec_type="ci_rider_or_standalone",
                title="Add critical illness protection",
                product_type="Critical Illness Rider or Standalone Plan",
                suggested_sum_assured_inr=ci_cover,
                suggested_term_years=target_term_years,
                suggested_provider_tier="any IRDAI-registered life insurer",
                estimated_annual_premium_range=_rider_premium_range(profile, ci_cover),
                reasoning=(
                    "Critical illness diagnosis can disrupt income for 6-18 months even with health insurance "
                    "covering hospitalization. CI cover pays a lump sum on diagnosis to support non-medical costs "
                    "and recovery time."
                ),
                triggered_by_finding="missing_critical_illness",
                priority_rank=PRIORITY_MISSING_CI,
            )
        )

    if "missing_accidental_death" in finding_severity:
        ad_cover = current_cover_inr if current_cover_inr > 0 else ideal_cover_inr
        recs.append(
            _make_recommendation(
                rec_type="ad_rider",
                title="Add accidental death benefit",
                product_type="Accidental Death Rider",
                suggested_sum_assured_inr=ad_cover if ad_cover > 0 else None,
                suggested_term_years=None,
                suggested_provider_tier="any IRDAI-registered life insurer",
                estimated_annual_premium_range=_rider_premium_range(profile, ad_cover if ad_cover > 0 else None),
                reasoning=(
                    "Accidental death rider can increase payout in accident-related death scenarios. "
                    "It is usually a low-cost additive layer and often does not require separate underwriting."
                ),
                triggered_by_finding="missing_accidental_death",
                priority_rank=PRIORITY_MISSING_AD,
            )
        )

    if "term_too_short" in finding_severity:
        breakdowns = audit_result.get("breakdowns") if isinstance(audit_result, Mapping) else audit_result.breakdowns
        gap = breakdowns.get("gap") if isinstance(breakdowns, Mapping) else None
        gap_details = gap.get("details") if isinstance(gap, Mapping) else getattr(gap, "details", {})
        cover_end_age = _to_int((gap_details or {}).get("cover_end_age"))
        recs.append(
            _make_recommendation(
                rec_type="extend_term",
                title="Extend your cover until at least age 60",
                product_type="Term Insurance Extension or New Term Plan",
                suggested_sum_assured_inr=current_cover_inr if current_cover_inr > 0 else None,
                suggested_term_years=target_term_years,
                suggested_provider_tier="top-CSR insurer",
                estimated_annual_premium_range=_term_premium_range(
                    profile,
                    current_cover_inr if current_cover_inr > 0 else None,
                ),
                reasoning=(
                    f"Your current cover ends at age {cover_end_age or 'unknown'}, before key family responsibilities "
                    "typically conclude. Extending term to age 60+ closes this gap."
                ),
                triggered_by_finding="term_too_short",
                priority_rank=PRIORITY_TERM_TOO_SHORT,
            )
        )

    if "endowment_returns_low" in finding_severity and profile.annual_income > 0:
        annual_budget = _term_base_premium(profile, ideal_cover_inr)
        twenty_year_endowment = int(annual_budget * 20 * 1.05)
        twenty_year_alt = int(annual_budget * 20 * 1.10)
        recs.append(
            _make_recommendation(
                rec_type="term_plus_invest",
                title="Switch from endowment to term + mutual fund combo",
                product_type="Term Insurance + Equity Mutual Fund SIP",
                suggested_sum_assured_inr=ideal_cover_inr if ideal_cover_inr > 0 else None,
                suggested_term_years=target_term_years,
                suggested_provider_tier="top-CSR insurer (term) + SEBI-registered AMC (MF)",
                estimated_annual_premium_range=_term_premium_range(
                    profile, ideal_cover_inr if ideal_cover_inr > 0 else None
                ),
                reasoning=(
                    "Endowment plans typically return 4-6% IRR. Splitting budget into term insurance plus equity MF SIP "
                    "often improves protection and long-run growth. Example over 20 years with the same annual budget: "
                    f"about Rs. {twenty_year_endowment:,} at 5% vs Rs. {twenty_year_alt:,} at 10%."
                ),
                triggered_by_finding="endowment_returns_low",
                priority_rank=PRIORITY_ENDOWMENT_LOW_RETURN,
            )
        )

    if "single_dependent_risk" in finding_severity:
        gap_to_ideal = max(0, ideal_cover_inr - current_cover_inr)
        fallback = int(current_cover_inr * DIVERSIFY_FALLBACK_CURRENT_COVER_SHARE)
        diversify_cover = gap_to_ideal if gap_to_ideal > 0 else fallback
        recs.append(
            _make_recommendation(
                rec_type="diversify_cover",
                title="Add a second life policy layer",
                product_type="Additional Term Insurance",
                suggested_sum_assured_inr=diversify_cover if diversify_cover > 0 else None,
                suggested_term_years=target_term_years,
                suggested_provider_tier="any IRDAI-registered life insurer",
                estimated_annual_premium_range=_term_premium_range(
                    profile, diversify_cover if diversify_cover > 0 else None
                ),
                reasoning=(
                    f"Relying on one life policy with {profile.dependents} dependents creates concentration risk. "
                    "A second smaller policy from a different insurer adds resilience against policy-level disputes."
                ),
                triggered_by_finding="single_dependent_risk",
                priority_rank=PRIORITY_SINGLE_DEPENDENT_RISK,
            )
        )

    recs.sort(
        key=lambda rec: (
            SEVERITY_SORT_ORDER.get(
                finding_severity.get(rec.triggered_by_finding or "", SEVERITY_INFO),
                SEVERITY_DEFAULT_SORT,
            ),
            rec.priority_rank,
        )
    )
    return recs

