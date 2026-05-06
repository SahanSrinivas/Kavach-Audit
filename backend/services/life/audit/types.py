"""Dataclass types for the life audit engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Optional, Sequence


@dataclass(frozen=True, slots=True)
class LifeUserProfile:
    """Snapshot of user profile fields used by life scoring."""

    user_id: str
    age: int
    gender: Optional[str] = None
    dependents: int = 0
    annual_income: int = 0
    city_tier: str = "tier-2"
    smoker: bool = False
    liabilities_inr: int = 0

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "LifeUserProfile":
        return cls(
            user_id=str(d.get("id") or d.get("user_id") or ""),
            age=int(d.get("age") or 0),
            gender=(str(d.get("gender")) if d.get("gender") else None),
            dependents=int(d.get("dependents") or d.get("kids_count") or 0),
            annual_income=int(d.get("annual_income") or d.get("income") or 0),
            city_tier=str(d.get("city_tier") or d.get("tier") or "tier-2"),
            smoker=bool(d.get("smoker") or (d.get("lifestyle") or {}).get("smoker", False)),
            liabilities_inr=int(d.get("liabilities_inr") or d.get("outstanding_loans") or 0),
        )


@dataclass(frozen=True, slots=True)
class LifeScheduleInput:
    """Normalized life schedule model consumed by life audit scoring."""

    schedule_id: Optional[str]
    product_name: Optional[str]
    sum_assured_inr: Optional[int]
    policy_term_years: Optional[int]
    premium_payment_term_years: Optional[int]
    modal_premium_inr: Optional[int]
    premium_frequency: Optional[str]
    nominee_section_likely: bool
    free_look_days: Optional[int]
    detected_riders: Sequence[str] = ()
    contingent_nominee_likely: bool = False
    autopay_likely: bool = False
    insurer_name: Optional[str] = None
    insurer_hint_id: Optional[str] = None

    @classmethod
    def from_dict(
        cls,
        life_schedule: Mapping[str, Any],
        *,
        schedule_id: str | None = None,
    ) -> "LifeScheduleInput":
        riders_raw = life_schedule.get("detectedRiders") or ()
        riders = tuple(str(x) for x in riders_raw if x)
        return cls(
            schedule_id=schedule_id,
            product_name=(
                str(life_schedule.get("productName"))
                if life_schedule.get("productName")
                else None
            ),
            sum_assured_inr=(
                int(life_schedule["sumAssuredInr"])
                if life_schedule.get("sumAssuredInr") is not None
                else None
            ),
            policy_term_years=(
                int(life_schedule["policyTermYears"])
                if life_schedule.get("policyTermYears") is not None
                else None
            ),
            premium_payment_term_years=(
                int(life_schedule["premiumPaymentTermYears"])
                if life_schedule.get("premiumPaymentTermYears") is not None
                else None
            ),
            modal_premium_inr=(
                int(life_schedule["modalPremiumInr"])
                if life_schedule.get("modalPremiumInr") is not None
                else None
            ),
            premium_frequency=(
                str(life_schedule.get("premiumFrequency"))
                if life_schedule.get("premiumFrequency")
                else None
            ),
            nominee_section_likely=bool(life_schedule.get("nomineeSectionLikely", False)),
            free_look_days=(
                int(life_schedule["freeLookDays"])
                if life_schedule.get("freeLookDays") is not None
                else None
            ),
            detected_riders=riders,
            contingent_nominee_likely=bool(
                life_schedule.get("contingentNomineeLikely", False)
            ),
            autopay_likely=bool(life_schedule.get("autopayLikely", False)),
            insurer_name=(
                str(life_schedule.get("insurerName"))
                if life_schedule.get("insurerName")
                else None
            ),
            insurer_hint_id=(
                str(life_schedule.get("insurerHintId"))
                if life_schedule.get("insurerHintId")
                else None
            ),
        )


@dataclass(frozen=True, slots=True)
class LifeScoreBreakdown:
    value: Optional[int]  # 0-100 or None when N/A
    label: str  # coverage | cost | claim_readiness | gap
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LifeFinding:
    id: str
    severity: str  # red | amber | info
    type: str
    icon: str
    headline: str
    explanation: str
    action: str
    score_impact: Mapping[str, int] = field(default_factory=dict)
    related_policy_id: Optional[str] = None
    recommendation: str = ""


@dataclass(frozen=True, slots=True)
class LifeAuditResult:
    id: str
    user_id: str
    scores: Mapping[str, Optional[int]]
    findings: Sequence[LifeFinding]
    all_findings: Sequence[LifeFinding]
    breakdowns: Mapping[str, LifeScoreBreakdown]
    data_version: str
    engine_ms: int
    generated_at: str
    warnings: Sequence[str] = ()
    def to_dict(self) -> dict[str, Any]:
        """Serialize nested dataclasses/mappings to plain JSON-ready dict."""
        return asdict(self)

