"""Generate user-facing findings from raw score breakdowns + rank them.

Spec reference: Kavachly_Audit_Engine_Spec.docx Section 6.

Two sources feed findings:
  - claim_readiness breakdowns: per-policy penalty events (room rent cap,
    co-pay, sub-limits, PED waiting, network, CSR, exclusions, restoration)
  - gap breakdown: missing protections (health, term, PA, CI, motor,
    travel, home)
  - coverage breakdown (per-category): underinsurance (health, life)
  - cost breakdown: per-policy overpayment

Each is rendered via explanations.render() then ranked per spec:

    rank_score = score_impact * 1.0
               + user_proximity * 0.8
               + actionability * 0.5
"""
from __future__ import annotations

import uuid
from typing import Any, Mapping, Sequence

from services.audit.constants.deduction_rules import (
    RANK_WEIGHT_ACTIONABILITY,
    RANK_WEIGHT_SCORE_IMPACT,
    RANK_WEIGHT_USER_PROXIMITY,
    TOP_FINDINGS_COUNT,
)
from services.audit.explanations import map_severity, render
from services.audit.types import Finding, Policy, ScoreBreakdown, UserProfile


# Per spec Section 6: critical/high/medium/low → red/amber/info plus a
# numeric severity weight used for actionability defaults.
_SEVERITY_BY_TYPE: dict[str, str] = {
    "room_rent_cap_metro": "critical",
    "room_rent_cap_tier2": "high",
    "icu_cap_low": "high",
    "copay_high": "high",
    "copay_low": "medium",
    "sublimit": "medium",
    "ped_waiting_long": "medium",
    "ped_waiting_with_disclosed_condition": "critical",
    "disease_waiting_long": "low",
    "network_small": "medium",
    "network_small_tier3": "high",
    "csr_low": "high",
    "csr_very_low": "critical",
    "permanent_exclusion_match": "critical",
    "no_restoration": "low",
    "missing_health": "critical",
    "missing_term_life": "critical",
    "missing_pa": "medium",
    "missing_ci": "medium",
    "missing_motor": "high",
    "missing_travel": "low",
    "missing_home": "medium",
    "underinsured_health": "high",
    "underinsured_life": "high",
    "cost_overpaying": "medium",
}

# user_proximity (spec Section 6): is the finding triggered by THIS user's
# specific data (e.g., disclosed PED) vs. a generic policy clause? 1.0 =
# user-specific, 0.5 = generic clause, 0.0 = market-wide.
_USER_PROXIMITY_BY_TYPE: dict[str, float] = {
    "permanent_exclusion_match": 1.0,
    "ped_waiting_with_disclosed_condition": 1.0,
    "missing_health": 0.9,
    "missing_term_life": 0.9,
    "underinsured_health": 0.8,
    "underinsured_life": 0.8,
    "missing_motor": 0.8,
    "missing_pa": 0.7,
    "missing_ci": 0.7,
    "missing_home": 0.7,
    "room_rent_cap_metro": 0.6,
    "room_rent_cap_tier2": 0.6,
    "icu_cap_low": 0.6,
    "ped_waiting_long": 0.4,
    "csr_low": 0.5,
    "csr_very_low": 0.6,
    "cost_overpaying": 0.4,
    "no_restoration": 0.3,
    "missing_travel": 0.3,
    "network_small": 0.4,
    "network_small_tier3": 0.6,
    "sublimit": 0.5,
    "copay_high": 0.5,
    "copay_low": 0.3,
    "disease_waiting_long": 0.2,
}

# actionability: can the user actually do something about this? 1.0 = yes
# (port to a different plan), 0.5 = only at next renewal, 0.0 = nothing
# they can do.
_ACTIONABILITY_BY_TYPE: dict[str, float] = {
    "missing_health": 1.0,
    "missing_term_life": 1.0,
    "missing_pa": 1.0,
    "missing_ci": 1.0,
    "missing_motor": 1.0,
    "missing_travel": 1.0,
    "missing_home": 1.0,
    "underinsured_health": 0.9,
    "underinsured_life": 0.9,
    "cost_overpaying": 0.6,
    "room_rent_cap_metro": 0.5,
    "room_rent_cap_tier2": 0.5,
    "icu_cap_low": 0.5,
    "copay_high": 0.5,
    "copay_low": 0.5,
    "sublimit": 0.5,
    "ped_waiting_long": 0.3,
    "ped_waiting_with_disclosed_condition": 0.4,
    "disease_waiting_long": 0.2,
    "csr_low": 0.5,
    "csr_very_low": 0.6,
    "permanent_exclusion_match": 0.6,
    "no_restoration": 0.4,
    "network_small": 0.4,
    "network_small_tier3": 0.5,
}


def _new_finding(
    finding_type: str,
    score_impact: int,
    ctx: Mapping[str, Any],
    related_policy_id: str | None = None,
    fid: str | None = None,
) -> Finding:
    rendered = render(finding_type, ctx)
    spec_sev = _SEVERITY_BY_TYPE.get(finding_type, "medium")
    severity = map_severity(spec_sev)
    return Finding(
        id=fid or f"f_{uuid.uuid4().hex[:8]}",
        severity=severity,
        type=finding_type,
        icon=rendered["icon"],
        headline=rendered["headline"],
        explanation=rendered["explanation"],
        action=rendered["action"],
        score_impact=score_impact,
        related_policy_id=related_policy_id,
        cta=rendered["cta"],
        recommendation=rendered["action"],
        user_proximity=_USER_PROXIMITY_BY_TYPE.get(finding_type, 0.4),
        actionability=_ACTIONABILITY_BY_TYPE.get(finding_type, 0.4),
    )


def _from_claim_readiness(
    cr_breakdown: ScoreBreakdown,
    profile: UserProfile,
    policies: Sequence[Policy],
) -> list[Finding]:
    findings: list[Finding] = []
    per_policy = cr_breakdown.details.get("per_policy", []) if cr_breakdown.details else []
    for policy_details in per_policy:
        policy_id = policy_details.get("policy_id")
        for ev in policy_details.get("penalties", []):
            ftype = ev["type"]
            ctx = dict(ev.get("ctx", {}))
            # Extra ctx fields commonly needed by templates.
            policy = next((p for p in policies if p.id == policy_id), None)
            if policy is not None and policy.sum_insured is not None:
                ctx.setdefault("sum_insured_lakh", int(policy.sum_insured / 100_000))
                ctx.setdefault("actual_cost", _metro_room_rate(profile.tier))
                if "cap_per_day" in ctx and "actual_cost" in ctx:
                    cap = int(ctx["cap_per_day"])
                    actual = int(ctx["actual_cost"])
                    ctx.setdefault("overage", max(0, actual - cap))
                if ftype == "icu_cap_low":
                    ctx.setdefault("leak", (50_000 - int(ctx["icu_cap"])) * 4)
                if ftype in ("copay_high", "copay_low"):
                    ctx["copay_amount"] = int(500_000 * (int(ctx["copay"]) / 100))
                if ftype == "sublimit":
                    items = ctx.get("items") or []
                    summary_parts = [
                        f"{(it.get('type') if isinstance(it, dict) else str(it))} ₹{(it.get('cap') if isinstance(it, dict) else 0):,}"
                        for it in items[:3]
                    ]
                    ctx["sublimits_summary"] = "; ".join(summary_parts) or "various procedures"
            findings.append(_new_finding(ftype, int(ev["amount"]), ctx, policy_id))
    return findings


def _from_gap(
    gap_breakdown: ScoreBreakdown,
    profile: UserProfile,
) -> list[Finding]:
    findings: list[Finding] = []
    if not gap_breakdown.details:
        return findings
    missing = gap_breakdown.details.get("missing", [])
    type_to_finding = {
        "health": "missing_health",
        "term_life": "missing_term_life",
        "pa": "missing_pa",
        "ci": "missing_ci",
        "motor": "missing_motor",
        "travel": "missing_travel",
        "home": "missing_home",
    }
    for m in missing:
        ftype = type_to_finding.get(m["type"])
        if not ftype:
            continue
        ctx: dict[str, Any] = {"user_city": profile.city or "your city"}
        if ftype == "missing_health":
            from services.audit.constants.ideal_cover import ideal_health_cover
            ideal = ideal_health_cover(profile)
            ctx["ideal_lakh"] = max(5, int(round(ideal / 100_000)))
        elif ftype == "missing_term_life":
            from services.audit.constants.ideal_cover import ideal_life_cover
            ideal = ideal_life_cover(profile)
            ctx["ideal_cr"] = max(1, int(round(ideal / 10_000_000)))
        elif ftype in ("missing_pa", "missing_ci"):
            ctx["ideal_lakh"] = max(10, int(round((profile.income * 5) / 100_000)))
        findings.append(_new_finding(ftype, int(m["deduction"]), ctx))
    return findings


def _from_coverage(
    cov_breakdown: ScoreBreakdown,
    profile: UserProfile,
    policies: Sequence[Policy],
) -> list[Finding]:
    findings: list[Finding] = []
    if not cov_breakdown.details:
        return findings
    by_cat = cov_breakdown.details.get("by_category", {})
    # Health underinsurance (only if user has SOME health cover; missing is gap.py's job)
    h = by_cat.get("health", {})
    if h.get("actual", 0) > 0 and h.get("ratio") is not None and h["ratio"] < 0.85:
        actual_lakh = max(1, int(round(h["actual"] / 100_000)))
        ideal_lakh = max(actual_lakh + 1, int(round(h["ideal"] / 100_000)))
        ctx = {
            "user_city": profile.city or "your city",
            "actual_lakh": actual_lakh,
            "ideal_lakh": ideal_lakh,
            "gap_lakh": ideal_lakh - actual_lakh,
            "topup_lakh": ideal_lakh - actual_lakh,
        }
        findings.append(_new_finding("underinsured_health",
                                     score_impact=int((1 - h["ratio"]) * 30),
                                     ctx=ctx))
    # Life underinsurance
    l = by_cat.get("life", {})
    if l.get("actual", 0) > 0 and l.get("ratio") is not None and l["ratio"] < 0.85:
        actual_cr = max(1, int(round(l["actual"] / 10_000_000)))
        ideal_cr = max(actual_cr + 1, int(round(l["ideal"] / 10_000_000)))
        ctx = {
            "actual_cr": actual_cr,
            "ideal_cr": ideal_cr,
            "gap_cr": ideal_cr - actual_cr,
        }
        findings.append(_new_finding("underinsured_life",
                                     score_impact=int((1 - l["ratio"]) * 25),
                                     ctx=ctx))
    return findings


def _from_cost(
    cost_breakdown: ScoreBreakdown,
    profile: UserProfile,
    policies: Sequence[Policy],
) -> list[Finding]:
    findings: list[Finding] = []
    if not cost_breakdown.details or "per_policy" not in cost_breakdown.details:
        return findings
    for row in cost_breakdown.details["per_policy"]:
        if row["policy_cost_score"] >= 75:
            continue  # not overpaying
        ctx = {
            "premium": int(row["premium"]),
            "benchmark": int((row["benchmark_low"] + row["benchmark_high"]) / 2),
            "overage": max(0, int(row["premium"] - (row["benchmark_low"] + row["benchmark_high"]) / 2)),
        }
        impact = (75 - row["policy_cost_score"]) // 5  # rough: 0-10 points
        findings.append(_new_finding("cost_overpaying", score_impact=impact,
                                     ctx=ctx, related_policy_id=row["policy_id"]))
    return findings


def _metro_room_rate(tier: str) -> int:
    """Approximate private-room rate for the rendered example arithmetic."""
    return {"tier-1": 15_000, "tier-2": 8_000, "tier-3": 5_000}.get(tier, 8_000)


def _rank_score(f: Finding) -> float:
    return (
        f.score_impact * RANK_WEIGHT_SCORE_IMPACT
        + f.user_proximity * RANK_WEIGHT_USER_PROXIMITY * 25  # scale to score-impact range
        + f.actionability * RANK_WEIGHT_ACTIONABILITY * 25
    )


def generate(
    profile: UserProfile,
    policies: Sequence[Policy],
    breakdowns: Mapping[str, ScoreBreakdown],
) -> tuple[list[Finding], list[Finding]]:
    """Returns (top_3_findings, all_findings_ranked).

    Stable id assignment: top 3 get f1/f2/f3 to match the mock fixture's
    naming, the rest keep their auto-generated ids. The `id` field is what
    the frontend uses in `/recommendations?finding_id=...`.
    """
    all_f: list[Finding] = []
    cr = breakdowns.get("claim_readiness")
    if cr is not None:
        all_f.extend(_from_claim_readiness(cr, profile, policies))
    gap = breakdowns.get("gap")
    if gap is not None:
        all_f.extend(_from_gap(gap, profile))
    cov = breakdowns.get("coverage")
    if cov is not None:
        all_f.extend(_from_coverage(cov, profile, policies))
    cost = breakdowns.get("cost")
    if cost is not None:
        all_f.extend(_from_cost(cost, profile, policies))

    all_f.sort(key=_rank_score, reverse=True)

    # Re-id top 3 to f1/f2/f3 for stable frontend behavior. Keep all keys
    # otherwise unchanged.
    top: list[Finding] = []
    for i, f in enumerate(all_f[:TOP_FINDINGS_COUNT], start=1):
        top.append(Finding(
            id=f"f{i}",
            severity=f.severity, type=f.type, icon=f.icon,
            headline=f.headline, explanation=f.explanation, action=f.action,
            score_impact=f.score_impact, related_policy_id=f.related_policy_id,
            cta=f.cta, recommendation=f.recommendation,
            user_proximity=f.user_proximity, actionability=f.actionability,
        ))
    # Replace the first N in all_f with the re-id'd versions to keep ordering coherent
    all_f_out = list(top) + all_f[TOP_FINDINGS_COUNT:]
    return top, all_f_out
