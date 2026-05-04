"""Claim-Readiness Score — the most important score in the engine.

Spec reference: Kavachly_Audit_Engine_Spec.docx Section 4. "If you make a
claim for a realistic event tomorrow, what fraction of the bill will the
insurer actually pay?" Start at 100, deduct points for every clause that
reduces the actual payout, then add the compounding penalty when ≥3
deductions co-trigger on the same policy.

Per-policy scoring is for HEALTH policies only (deductions are clause-
specific to health). The user-level rollup is the unweighted average of
per-policy scores across health policies; if the user has no health
policies, the user-level claim-readiness is None (gap.py will flag the
missing health protection separately).

Defensive bias: when a parsed_field is missing (declared policies, partial
parses) we treat it as the WORSE case — declared-only policies get the
default-CSR + missing-fields treatment so they look weaker than parsed
ones. This pushes users to upload PDFs.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from services.audit.constants.csr_table import lookup_csr
from services.audit.constants.deduction_rules import (
    COMPOUNDING_PENALTY_PER_EXTRA,
    COMPOUNDING_TRIGGER_COUNT,
    COPAY_HIGH_DEDUCTION,
    COPAY_HIGH_THRESHOLD,
    COPAY_LOW_DEDUCTION,
    COPAY_LOW_THRESHOLD,
    CSR_LOW_DEDUCTION,
    CSR_LOW_THRESHOLD,
    CSR_VERY_LOW_DEDUCTION,
    CSR_VERY_LOW_THRESHOLD,
    DISCLOSED_PED_KEYWORDS,
    DISEASE_WAITING_DEDUCTION,
    DISEASE_WAITING_THRESHOLD_YEARS,
    ICU_CAP_DEDUCTION,
    ICU_CAP_PCT_OF_SI,
    NCB_HIGH_REWARD,
    NCB_HIGH_THRESHOLD,
    NETWORK_DEDUCTION,
    NETWORK_THRESHOLD,
    NETWORK_TIER3_DEDUCTION,
    NO_RESTORATION_DEDUCTION,
    PED_WAITING_DEDUCTION,
    PED_WAITING_THRESHOLD_YEARS,
    PED_WAITING_WITH_DISCLOSED_DEDUCTION,
    PERMANENT_EXCLUSION_MATCH_DEDUCTION,
    RESTORATION_UNLIMITED_REWARD,
    ROOM_RENT_CAP_PCT_OF_SI,
    ROOM_RENT_CAP_T1_DEDUCTION,
    ROOM_RENT_CAP_T2_DEDUCTION,
    ROOM_RENT_NO_CAP_REWARD,
    SUBLIMIT_PER_ITEM_DEDUCTION,
)
from services.audit.types import Policy, ScoreBreakdown, UserProfile


# A single deduction event captured during scoring; rolled up into
# ScoreBreakdown.details for downstream finding generation.
DeductionEvent = dict[str, Any]


def _collect_deductions(
    policy: Policy,
    profile: UserProfile,
) -> tuple[list[DeductionEvent], list[DeductionEvent]]:
    """Walk the policy's parsed_fields; return (penalties, rewards).

    Each event: {type, amount, ctx} where amount is positive for penalty,
    positive for reward; the sign is implied by which list it lives in.
    """
    pf: Mapping[str, Any] = policy.parsed_fields or {}
    penalties: list[DeductionEvent] = []
    rewards: list[DeductionEvent] = []

    # score_policy already short-circuits when sum_insured is None, so
    # by the time _collect_deductions runs we're guaranteed an int.
    si: int = policy.sum_insured if policy.sum_insured is not None else 0

    # --- Room rent cap ---
    room_cap = pf.get("room_rent_cap")
    if room_cap is None:
        # Defensive: declared policies report no cap clause. We can't tell
        # if it's truly absent or just unparsed, so we DO NOT reward
        # absence (which would be a free win). Skip the rule entirely.
        pass
    elif room_cap == 0 or room_cap is False:
        # Explicit "no cap" present in the parse — reward
        rewards.append({"type": "room_rent_no_cap", "amount": ROOM_RENT_NO_CAP_REWARD,
                        "ctx": {}})
    else:
        cap_pct = (room_cap / si) if si > 0 else 0
        # Tier-1 uses <= because a 1% cap is the IRDAI regulatory minimum
        # but insufficient against actual Mumbai/Delhi private room rates
        # of ₹12-20K/day. Tier-2 stays strict < because hospital costs are
        # lower and 1% there is borderline-acceptable.
        if profile.tier == "tier-1" and cap_pct <= ROOM_RENT_CAP_PCT_OF_SI:
            penalties.append({"type": "room_rent_cap_metro",
                              "amount": ROOM_RENT_CAP_T1_DEDUCTION,
                              "ctx": {"cap_per_day": int(room_cap),
                                      "user_city": profile.city or "your city"}})
        elif profile.tier == "tier-2" and cap_pct < ROOM_RENT_CAP_PCT_OF_SI:
            penalties.append({"type": "room_rent_cap_tier2",
                              "amount": ROOM_RENT_CAP_T2_DEDUCTION,
                              "ctx": {"cap_per_day": int(room_cap),
                                      "user_city": profile.city or "your city"}})
        # tier-3: not penalized at all (spec doesn't list a magnitude)

    # --- ICU cap ---
    icu_cap = pf.get("icu_cap")
    if icu_cap is not None and icu_cap > 0:
        icu_pct = (icu_cap / si) if si > 0 else 0
        if icu_pct < ICU_CAP_PCT_OF_SI:
            penalties.append({"type": "icu_cap_low", "amount": ICU_CAP_DEDUCTION,
                              "ctx": {"icu_cap": int(icu_cap),
                                      "user_city": profile.city or "your city"}})

    # --- Co-pay ---
    copay = pf.get("copay_percent")
    if copay is not None and copay > 0:
        if copay > COPAY_HIGH_THRESHOLD:
            penalties.append({"type": "copay_high", "amount": COPAY_HIGH_DEDUCTION,
                              "ctx": {"copay": int(copay)}})
        elif copay >= COPAY_LOW_THRESHOLD:
            penalties.append({"type": "copay_low", "amount": COPAY_LOW_DEDUCTION,
                              "ctx": {"copay": int(copay)}})

    # --- Disease-specific sub-limits ---
    sublimits = pf.get("sub_limits") or []
    if sublimits:
        n = len(sublimits)
        penalties.append({"type": "sublimit",
                          "amount": SUBLIMIT_PER_ITEM_DEDUCTION * n,
                          "ctx": {"count": n, "items": sublimits}})

    # --- PED waiting period ---
    ped_years = pf.get("ped_waiting_years")
    has_disclosed_ped = _has_disclosed_ped(profile)
    if ped_years is not None and ped_years > PED_WAITING_THRESHOLD_YEARS:
        if has_disclosed_ped:
            # Spec: combined penalty (replaces the standalone PED penalty,
            # not added on top — the spec lists them as distinct rows but
            # the rationale "Combined penalty" implies one fires)
            penalties.append({"type": "ped_waiting_with_disclosed_condition",
                              "amount": PED_WAITING_WITH_DISCLOSED_DEDUCTION,
                              "ctx": {"waiting_years": int(ped_years),
                                      "condition": _primary_condition(profile)}})
        else:
            penalties.append({"type": "ped_waiting_long",
                              "amount": PED_WAITING_DEDUCTION,
                              "ctx": {"waiting_years": int(ped_years)}})

    # --- Disease-specific waiting (cataract, hernia, ENT) ---
    disease_waitings = pf.get("disease_specific_waiting") or []
    long_waits = [d for d in disease_waitings
                  if isinstance(d, Mapping) and d.get("years", 0) > DISEASE_WAITING_THRESHOLD_YEARS]
    if long_waits:
        penalties.append({"type": "disease_waiting_long",
                          "amount": DISEASE_WAITING_DEDUCTION,
                          "ctx": {"waiting_years": max(int(d["years"]) for d in long_waits),
                                  "items": long_waits}})

    # --- Network size ---
    network = pf.get("network_hospitals")
    if network is not None and network < NETWORK_THRESHOLD:
        if profile.tier == "tier-3":
            penalties.append({"type": "network_small_tier3",
                              "amount": NETWORK_TIER3_DEDUCTION,
                              "ctx": {"network": int(network),
                                      "user_city": profile.city or "your city"}})
        else:
            penalties.append({"type": "network_small",
                              "amount": NETWORK_DEDUCTION,
                              "ctx": {"network": int(network)}})

    # --- Insurer CSR ---
    canonical, csr = lookup_csr(policy.insurer)
    if csr < CSR_VERY_LOW_THRESHOLD:
        penalties.append({"type": "csr_very_low", "amount": CSR_VERY_LOW_DEDUCTION,
                          "ctx": {"insurer": canonical, "csr_pct": round(csr * 100, 1),
                                  "reject_pct": round((1 - csr) * 100, 1)}})
    elif csr < CSR_LOW_THRESHOLD:
        penalties.append({"type": "csr_low", "amount": CSR_LOW_DEDUCTION,
                          "ctx": {"insurer": canonical, "csr_pct": round(csr * 100, 1)}})

    # --- Permanent exclusions matching disclosed condition ---
    exclusions = pf.get("permanent_exclusions") or []
    matched = _exclusion_matches_disclosed(exclusions, profile)
    if matched:
        penalties.append({"type": "permanent_exclusion_match",
                          "amount": PERMANENT_EXCLUSION_MATCH_DEDUCTION,
                          "ctx": {"condition": matched}})

    # --- Restoration benefit ---
    restoration = pf.get("restoration_benefit")
    restoration_unlimited = pf.get("restoration_unlimited", False)
    if restoration_unlimited:
        rewards.append({"type": "restoration_unlimited",
                        "amount": RESTORATION_UNLIMITED_REWARD, "ctx": {}})
    elif restoration is False:
        penalties.append({"type": "no_restoration",
                          "amount": NO_RESTORATION_DEDUCTION,
                          "ctx": {"sum_insured_lakh": int(si / 100_000)}})

    # --- NCB ---
    ncb = pf.get("ncb_percent")
    if ncb is not None and ncb > NCB_HIGH_THRESHOLD:
        rewards.append({"type": "ncb_high", "amount": NCB_HIGH_REWARD,
                        "ctx": {"ncb_percent": int(ncb)}})

    return penalties, rewards


def _has_disclosed_ped(profile: UserProfile) -> bool:
    haystack = " ".join([*profile.self_pec, *profile.parents_pec]).lower()
    return any(kw in haystack for kw in DISCLOSED_PED_KEYWORDS)


def _primary_condition(profile: UserProfile) -> str:
    """Pick the most specific disclosed condition for finding text."""
    for src in (profile.self_pec, profile.parents_pec):
        for cond in src:
            c = cond.lower()
            if c in {"none", "prefer not to say", ""}:
                continue
            return cond
    return "your condition"


def _exclusion_matches_disclosed(
    exclusions: Sequence[Any],
    profile: UserProfile,
) -> str | None:
    """Returns the matched exclusion clause if any disclosed condition
    matches a permanent exclusion, else None.
    """
    if not exclusions:
        return None
    disclosed = " ".join([*profile.self_pec, *profile.parents_pec]).lower()
    if not disclosed:
        return None
    for exc in exclusions:
        if not isinstance(exc, str):
            continue
        e = exc.lower()
        # crude but effective: token containment in either direction
        for kw in DISCLOSED_PED_KEYWORDS:
            if kw in disclosed and kw in e:
                return exc
    return None


EMPLOYER_GROUP_CR_MULTIPLIER = 0.8


def score_policy(policy: Policy, profile: UserProfile) -> ScoreBreakdown:
    """Score one HEALTH policy. Returns ScoreBreakdown with per-rule
    deduction details for finding generation.

    Employer-group adjustment: spec Section 2 already applies an 80%
    credit factor to employer group cover (it lapses on job change).
    For consistency across the three scores, we apply the same 0.8×
    multiplier to claim-readiness deductions and rewards — the cover is
    real-but-impermanent, so its claim characteristics deserve damped
    weighting too.

    Wording-only policy (null sum_insured): we can't compute percentage
    rules (room_rent_cap < 1% of SI, etc.). Return None so the user-
    level rollup excludes this policy. Audit-level UX response for
    "schedule required" is a separate layer (TODO(audit-schedule-required)).
    """
    if policy.type != "health":
        return ScoreBreakdown(value=None, label="claim_readiness",
                              details={"reason": "non_health_policy"})
    if policy.sum_insured is None:
        return ScoreBreakdown(value=None, label="claim_readiness",
                              details={"reason": "missing_sum_insured",
                                       "policy_id": policy.id})

    penalties, rewards = _collect_deductions(policy, profile)
    multiplier = EMPLOYER_GROUP_CR_MULTIPLIER if policy.is_employer_group else 1.0
    raw_deductions = int(sum(int(p["amount"]) for p in penalties) * multiplier)
    raw_rewards = int(sum(int(r["amount"]) for r in rewards) * multiplier)
    raw_score = 100 - raw_deductions + raw_rewards

    # Spec compounding rule: ≥3 deductions on the same policy → extra 5×(n-2)
    compounding_penalty = 0
    n = len(penalties)
    if n >= COMPOUNDING_TRIGGER_COUNT:
        compounding_penalty = int(COMPOUNDING_PENALTY_PER_EXTRA * (n - 2) * multiplier)

    final = raw_score - compounding_penalty
    value = max(0, min(100, int(final)))

    return ScoreBreakdown(
        value=value,
        label="claim_readiness",
        details={
            "policy_id": policy.id,
            "penalties": penalties,
            "rewards": rewards,
            "raw_deductions": raw_deductions,
            "raw_rewards": raw_rewards,
            "compounding_penalty": compounding_penalty,
            "employer_group_adjusted": policy.is_employer_group,
        },
    )


def score(profile: UserProfile, policies: Sequence[Policy]) -> ScoreBreakdown:
    """User-level claim-readiness: unweighted average across health policies.
    Returns None if user has no health policies.
    """
    health = [p for p in policies if p.type == "health"]
    if not health:
        return ScoreBreakdown(value=None, label="claim_readiness",
                              details={"reason": "no_health_policies"})

    per_policy = [score_policy(p, profile) for p in health]
    values = [b.value for b in per_policy if b.value is not None]
    if not values:
        return ScoreBreakdown(value=None, label="claim_readiness",
                              details={"reason": "all_policies_unscored"})

    avg = int(round(sum(values) / len(values)))
    return ScoreBreakdown(
        value=avg,
        label="claim_readiness",
        details={"per_policy": [b.details for b in per_policy],
                 "policy_scores": [b.value for b in per_policy]},
    )