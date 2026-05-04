"""Dataclass types for the audit engine.

Inputs: UserProfile, Policy, Lifestyle. Outputs: AuditResult, Finding,
ScoreBreakdown, PortfolioSummary. All frozen + slotted for cheap equality
and small memory footprint.

Spec: Kavachly_Audit_Engine_Spec.docx Section 7 (architecture).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence


# ---------- Inputs ----------

@dataclass(frozen=True, slots=True)
class Lifestyle:
    smoker: bool = False
    travels_intl: bool = False
    two_wheeler: bool = False
    self_employed: bool = False
    owns_car: bool = False
    planned_events: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class UserProfile:
    """Snapshot of the user at audit time. Immutable.

    `tier` is one of "tier-1" | "tier-2" | "tier-3" (already classified by
    the user_router on profile update).
    """
    user_id: str
    age: int
    city: str
    tier: str
    family_composition: Optional[str] = None
    spouse_age: Optional[int] = None
    kids_count: int = 0
    kids_youngest_age: Optional[int] = None
    parents_ages: Mapping[str, int] = field(default_factory=dict)
    parents_pec: tuple[str, ...] = ()
    self_pec: tuple[str, ...] = ()
    family_ci_history: bool = False
    self_owned_home: bool = False
    income: int = 0
    emis: int = 0
    monthly_expenses: int = 0
    liquid_assets: int = 0
    outstanding_loans: int = 0
    lifestyle: Lifestyle = field(default_factory=Lifestyle)

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "UserProfile":
        ls_raw = d.get("lifestyle") or {}
        events = ls_raw.get("planned_events") or []
        ls = Lifestyle(
            smoker=bool(ls_raw.get("smoker", False)),
            travels_intl=bool(ls_raw.get("travels_intl", False)),
            two_wheeler=bool(ls_raw.get("two_wheeler", False)),
            self_employed=bool(ls_raw.get("self_employed", False)),
            owns_car=bool(ls_raw.get("owns_car", False)),
            planned_events=tuple(events),
        )
        return cls(
            user_id=str(d.get("id") or d.get("user_id") or ""),
            age=int(d.get("age") or 0),
            city=str(d.get("city") or ""),
            tier=str(d.get("tier") or "tier-3"),
            family_composition=d.get("family_composition"),
            spouse_age=d.get("spouse_age"),
            kids_count=int(d.get("kids_count") or 0),
            kids_youngest_age=d.get("kids_youngest_age"),
            parents_ages=dict(d.get("parents_ages") or {}),
            parents_pec=tuple(d.get("parents_pec") or ()),
            self_pec=tuple(d.get("self_pec") or ()),
            family_ci_history=bool(d.get("family_ci_history", False)),
            self_owned_home=bool(d.get("self_owned_home", False)),
            income=int(d.get("income") or 0),
            emis=int(d.get("emis") or 0),
            monthly_expenses=int(d.get("monthly_expenses") or 0),
            liquid_assets=int(d.get("liquid_assets") or 0),
            outstanding_loans=int(d.get("outstanding_loans") or 0),
            lifestyle=ls,
        )


@dataclass(frozen=True, slots=True)
class Policy:
    """One insurance policy. `parsed_fields` holds insurer-specific clauses for
    deep parsing (room rent cap, ICU cap, sub-limits, etc.). For declared
    policies it's an empty dict — claim-readiness then runs in defensive mode.

    sum_insured / premium are Optional[int]: a wording-only PDF (no
    schedule) yields None for both. Coverage and Cost scoring exclude
    such policies; claim_readiness produces None per-policy. The
    audit-level UX response for "schedule required" is a separate layer
    (see TODO(audit-schedule-required)).
    """
    id: str
    type: str
    insurer: str
    sum_insured: Optional[int]
    premium: Optional[int]
    parsed_fields: Mapping[str, Any] = field(default_factory=dict)
    source: str = "declared"
    is_employer_group: bool = False
    end_date: Optional[str] = None
    # TODO(household-policy-linkage): when household policies arrive, route by
    # covered_member instead of attributing everything to the user.
    covered_member: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Policy":
        si = d.get("sum_insured")
        pr = d.get("premium")
        return cls(
            id=str(d.get("id") or ""),
            type=str(d.get("type") or "other").lower(),
            insurer=str(d.get("insurer") or ""),
            sum_insured=int(si) if si is not None else None,
            premium=int(pr) if pr is not None else None,
            parsed_fields=dict(d.get("parsed_fields") or {}),
            source=str(d.get("source") or "declared"),
            is_employer_group=bool(d.get("is_employer_group", False)),
            end_date=d.get("end_date"),
            covered_member=d.get("covered_member"),
        )


# ---------- Outputs ----------

@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    """Score with the arithmetic that produced it. Frontend ignores `details`
    today, but it's the basis for "show your work" expandable views.
    """
    value: Optional[int]  # 0-100 or None when N/A
    label: str            # "coverage" | "cost" | "claim_readiness" | "gap"
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Finding:
    """One red flag for the user.

    Frontend reads: id, severity, type, icon, headline, explanation, action.
    Extra fields (score_impact, related_policy_id, cta, recommendation,
    user_proximity, actionability) are forward-compatible and ignored today.
    """
    id: str
    severity: str          # "red" | "amber" | "info"
    type: str              # finding-type identifier; see findings.py
    icon: str              # "alert-triangle" | "shield-off" | "clock"
    headline: str
    explanation: str
    action: str            # frontend's name for spec's `recommendation`
    score_impact: int = 0
    related_policy_id: Optional[str] = None
    cta: str = "audit"     # "audit" | "recommend" | "educate"
    recommendation: str = ""  # alias of action; kept for spec parity
    user_proximity: float = 0.0
    actionability: float = 0.0


@dataclass(frozen=True, slots=True)
class PortfolioRow:
    type: str
    current: int
    ideal: int
    ratio: int  # 0-100, capped at 100 in the UI bar


@dataclass(frozen=True, slots=True)
class PortfolioSummary:
    total_cover: int
    total_premium: int
    active_policies: int
    next_renewal: Optional[str]
    by_type: Sequence[PortfolioRow]


@dataclass(frozen=True, slots=True)
class AuditResult:
    id: str
    user_id: str
    scores: Mapping[str, Optional[int]]   # {"coverage", "cost", "claim_readiness", "gap"}
    findings: Sequence[Finding]           # top 3
    all_findings: Sequence[Finding]       # everything ranked
    portfolio: PortfolioSummary
    breakdowns: Mapping[str, ScoreBreakdown]  # one per score key
    data_version: str
    engine_ms: int
    generated_at: str