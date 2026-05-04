"""Finding explanation templates.

Spec reference: Kavachly_Audit_Engine_Spec.docx Section 6 — "Generation
strategy: 80% deterministic, 20% Claude". This module supplies the
deterministic 80%. Each template has placeholders rendered with `.format()`
in explanations.py. Claude integration is stubbed (returns the template
version) until the prompt template ships in a follow-up session.

A template is one record per finding type with these keys:
    severity_default — spec-style "critical" | "high" | "medium" | "low"
                       (frontend-mapped via SEVERITY_FROM_SPEC; the
                       authoritative per-type severity map lives in
                       findings._SEVERITY_BY_TYPE — this template field
                       is documentation only)
    icon             — "alert-triangle" | "shield-off" | "clock"
    headline         — single-line, in user voice
    explanation      — 2-3 paragraphs with example arithmetic
    action           — single-line actionable (spec calls this `recommendation`)
    cta              — "audit" | "recommend" | "educate"

Frontend reads only severity/icon/headline/explanation/action — extra
template fields (cta, severity_default) are stored on the Finding for
forward-compat.
"""
from __future__ import annotations

from typing import Final, TypedDict


class TemplateRecord(TypedDict):
    severity_default: str
    icon: str
    headline: str
    explanation: str
    action: str
    cta: str


# Spec mapping: critical/high → red, medium → amber, low → info.
SEVERITY_FROM_SPEC: Final[dict[str, str]] = {
    "critical": "red",
    "high": "red",
    "medium": "amber",
    "low": "info",
}


# 25 finding types — see findings.py for which deductions trigger which.
TEMPLATES: Final[dict[str, TemplateRecord]] = {
    # --- Claim-readiness driven (policy-clause based) ---
    "room_rent_cap_metro": {
        "severity_default": "critical",
        "icon": "alert-triangle",
        "headline": "Your room rent cap is ₹{cap_per_day:,}/day, but a private room in {user_city} costs ~₹{actual_cost:,}/day.",
        "explanation": (
            "In {user_city}, a single AC private room in a corporate hospital costs roughly "
            "₹{actual_cost:,}/day. Your policy caps room rent at ₹{cap_per_day:,}/day. If you "
            "choose a regular private room, your insurer applies a 'proportionate deduction' — "
            "they reduce ALL your hospital bills (surgeon, ICU, medicines) by the same percentage "
            "as your room overage.\n\n"
            "Example: a ₹5L hospitalization with a ₹10,000/day room (₹{overage:,} over your cap) "
            "across 5 days means the insurer pays only ~₹2.5L. You pay ₹2.5L out of pocket — "
            "even though you have a ₹{sum_insured_lakh}L policy."
        ),
        "action": "Switch to a no-room-rent-cap policy. The premium difference is typically ₹1,500–3,000/year.",
        "cta": "recommend",
    },
    "room_rent_cap_tier2": {
        "severity_default": "high",
        "icon": "alert-triangle",
        "headline": "Your room rent cap is ₹{cap_per_day:,}/day. In {user_city} corporate hospitals, that's tight.",
        "explanation": (
            "Mid-tier corporate hospitals in {user_city} charge ₹6,000–10,000/day for a private "
            "room. Your ₹{cap_per_day:,}/day cap means proportionate deduction kicks in if you "
            "step up to a better room — every line of the bill (surgery, doctor, meds) gets "
            "reduced by the room overage percentage. On a ₹3L bill that can mean ₹50K–₹80K out of pocket."
        ),
        "action": "Look for plans without a room rent sub-limit when you next port.",
        "cta": "recommend",
    },
    "icu_cap_low": {
        "severity_default": "high",
        "icon": "alert-triangle",
        "headline": "ICU cap of ₹{icu_cap:,}/day is too low for {user_city}.",
        "explanation": (
            "ICU stay in a {user_city} corporate hospital runs ₹25,000–50,000/day. Your policy "
            "caps ICU at ₹{icu_cap:,}/day — the gap leaks immediately on any ICU admission. "
            "On a 4-day ICU stay, that's ₹{leak:,} out of pocket before any other proportionate "
            "deduction is applied."
        ),
        "action": "Shortlist policies with no ICU sub-limit (most premium plans now offer this).",
        "cta": "recommend",
    },
    "copay_high": {
        "severity_default": "high",
        "icon": "alert-triangle",
        "headline": "Your policy has a {copay}% co-pay clause on every claim.",
        "explanation": (
            "Co-pay means YOU pay {copay}% of every approved hospital bill, no exceptions. "
            "On a ₹5L hospitalization that's ₹{copay_amount:,} out of pocket — even after the "
            "insurer settles. Co-pay clauses are common in budget plans and senior-citizen "
            "policies, but on a serious claim they materially erode your coverage."
        ),
        "action": "Look for plans with zero co-pay; the premium step-up is usually under ₹2,000/year.",
        "cta": "recommend",
    },
    "copay_low": {
        "severity_default": "medium",
        "icon": "alert-triangle",
        "headline": "There's a {copay}% co-pay clause buried in your policy.",
        "explanation": (
            "On every approved claim, you pay {copay}% out of pocket. On a ₹3L hospitalization "
            "that's ₹{copay_amount:,}. It's a small bite per claim but it adds up across years."
        ),
        "action": "Worth checking alternatives — many comparable policies have no co-pay at all.",
        "cta": "recommend",
    },
    "sublimit": {
        "severity_default": "medium",
        "icon": "alert-triangle",
        "headline": "{count} disease-specific sub-limits in your policy can shrink real claim payouts.",
        "explanation": (
            "Your policy has caps on specific procedures: {sublimits_summary}. The actual cost "
            "of these procedures in {user_city} runs 2–3× the cap, so the gap comes out of your "
            "pocket. Knee replacement in particular is commonly capped at ₹2L while the real "
            "cost is ₹4–6L."
        ),
        "action": "Move to a plan without disease-specific sub-limits — shortlist available.",
        "cta": "recommend",
    },
    "ped_waiting_long": {
        "severity_default": "medium",
        "icon": "clock",
        "headline": "{waiting_years}-year pre-existing-disease waiting period — market standard is now 2 years.",
        "explanation": (
            "If you (or any covered family member) develop a pre-existing condition like diabetes, "
            "hypertension, or thyroid, your insurer won't pay claims related to it for the first "
            "{waiting_years} years. Newer policies have brought PED waiting down to 24 months, "
            "and a few premium plans offer 12 months. You're locked out of treatment for an "
            "extra year compared to the market."
        ),
        "action": "Compare policies with 24-month PED waiting from your renewal date.",
        "cta": "recommend",
    },
    "ped_waiting_with_disclosed_condition": {
        "severity_default": "critical",
        "icon": "clock",
        "headline": "You disclosed {condition}, but your policy has a {waiting_years}-year wait for pre-existing claims.",
        "explanation": (
            "You mentioned {condition} during signup. Your current policy waits {waiting_years} "
            "years before covering claims related to pre-existing conditions. That means until the "
            "waiting period ends, any hospitalization caused by your {condition} or related "
            "complications will not be covered — you pay 100% out of pocket.\n\n"
            "For context: most modern health policies have 2–3 year PED waiting; some premium "
            "plans offer 1-year. Yours is on the longer end. If {condition} is well-managed, "
            "this might not bite, but a complication during the waiting period is uninsured."
        ),
        "action": (
            "Look for plans with shorter PED waiting (2–3 years). When porting, your existing "
            "waiting period credits transfer — you don't restart the clock."
        ),
        "cta": "recommend",
    },
    "disease_waiting_long": {
        "severity_default": "low",
        "icon": "clock",
        "headline": "Some procedures (cataract, hernia, ENT) have a {waiting_years}-year waiting period.",
        "explanation": (
            "Specific-disease waiting is normal for cataract, hernia, ENT and similar planned "
            "procedures, but {waiting_years} years is on the longer end. Most policies have 2-year "
            "waiting; yours is excessive."
        ),
        "action": "When porting, ask explicitly about disease-specific waiting reduction.",
        "cta": "recommend",
    },
    "network_small": {
        "severity_default": "medium",
        "icon": "alert-triangle",
        "headline": "Network of {network} hospitals nationwide — cashless may fail in an emergency.",
        "explanation": (
            "Your insurer's network is {network} hospitals nationwide. Cashless treatment depends "
            "on the hospital being in-network; with a small network, you're more likely to fall "
            "back to reimbursement (pay first, claim later) — which is painful at 3am with a "
            "sick child. Mainstream insurers run 7,000–13,000+ network hospitals."
        ),
        "action": "Move to an insurer with a 10,000+ hospital network when you renew.",
        "cta": "recommend",
    },
    "network_small_tier3": {
        "severity_default": "high",
        "icon": "alert-triangle",
        "headline": "{network} network hospitals AND you're in a Tier-3 city — cashless will likely fail.",
        "explanation": (
            "Your insurer's nationwide network is only {network} hospitals, and {user_city} is a "
            "Tier-3 city — the combination almost guarantees no nearby network hospital in an "
            "emergency. You'll be forced into reimbursement claims, which slow payout and shift "
            "cashflow risk to you."
        ),
        "action": "Switch to an insurer with a wider network in your region — shortlist available.",
        "cta": "recommend",
    },
    "csr_low": {
        "severity_default": "high",
        "icon": "shield-off",
        "headline": "{insurer}'s 3-year claim settlement ratio is {csr_pct}% — below the 90% mark.",
        "explanation": (
            "Claim Settlement Ratio is the % of claims an insurer actually pays. We use Ditto's "
            "outcome-focused 3-year average (not the IRDAI 3-month figure that everyone advertises) "
            "because it captures real willingness-to-pay. {insurer} settles {csr_pct}% — below the "
            "90% threshold we treat as a yellow flag. Top insurers settle 95%+."
        ),
        "action": "When renewing, prefer an insurer with 95%+ CSR — shortlist available.",
        "cta": "recommend",
    },
    "csr_very_low": {
        "severity_default": "critical",
        "icon": "shield-off",
        "headline": "{insurer}'s 3-year CSR is {csr_pct}% — genuinely high-risk.",
        "explanation": (
            "{insurer} settles only {csr_pct}% of claims on a 3-year outcome-focused basis. That "
            "means roughly {reject_pct}% of claims are rejected, contested, or closed without "
            "payment. The policy is genuinely high-risk; even if the premium is attractive, you're "
            "buying coverage you may not be able to use."
        ),
        "action": "Strongly consider porting to a top-CSR insurer (95%+) at renewal.",
        "cta": "recommend",
    },
    "permanent_exclusion_match": {
        "severity_default": "critical",
        "icon": "shield-off",
        "headline": "Policy permanently excludes {condition} — and you disclosed {condition}.",
        "explanation": (
            "Permanent exclusions are clauses that the insurer will never pay against, regardless "
            "of waiting period. Your policy lists '{condition}' as a permanent exclusion, and you "
            "disclosed {condition} during signup — meaning any hospitalization linked to it is "
            "uninsured for the life of the policy. This is the silent killer of health policies: "
            "you have coverage on paper but not for the condition you're most likely to claim on."
        ),
        "action": "Port to a plan that does not permanently exclude {condition}.",
        "cta": "recommend",
    },
    "no_restoration": {
        "severity_default": "low",
        "icon": "alert-triangle",
        "headline": "No restoration benefit — once your sum insured runs out, you're done for the year.",
        "explanation": (
            "Restoration benefit refills your sum insured after a claim, so a second illness in "
            "the same year is still covered. Without it, if your ₹{sum_insured_lakh}L policy is "
            "exhausted in a hospitalization, any further claim that year is paid 100% by you. "
            "Most modern policies include restoration as standard."
        ),
        "action": "Look for plans with 100%+ restoration benefit when porting.",
        "cta": "recommend",
    },
    # --- Gap-driven (missing protections) ---
    "missing_health": {
        "severity_default": "critical",
        "icon": "shield-off",
        "headline": "You have no health insurance. In Indian metros, one hospitalization can wipe out years of savings.",
        "explanation": (
            "Going without health insurance is the #1 cause of household financial ruin in India. "
            "A single cardiac event in a {user_city} corporate hospital costs ₹4–8 lakh; cancer "
            "treatment runs ₹15–30 lakh. At your age and city tier, ideal cover is around "
            "₹{ideal_lakh}L — and a comprehensive plan typically costs ₹14,000–22,000/year."
        ),
        "action": "Take a ₹{ideal_lakh}L family floater with a top-CSR insurer. We can shortlist 3 options.",
        "cta": "recommend",
    },
    "missing_term_life": {
        "severity_default": "critical",
        "icon": "shield-off",
        "headline": "You have no term life cover. Your dependents need ~₹{ideal_cr} crore.",
        "explanation": (
            "Term life is the cheapest insurance per rupee of cover. At your age (non-smoker), "
            "₹{ideal_cr} Cr cover typically costs ₹14,000–22,000/year. Without it, your family "
            "would lose 12–15 years of income replacement if something happens to you. Term "
            "insurance is the single most under-bought policy in India."
        ),
        "action": "Add term life of ₹{ideal_cr} Cr from a top-CSR insurer — shortlist available.",
        "cta": "recommend",
    },
    "missing_pa": {
        "severity_default": "medium",
        "icon": "alert-triangle",
        "headline": "No personal accident cover — disability cover for your earning capacity is missing.",
        "explanation": (
            "PA cover pays a lump sum on accidental death, permanent disability, or temporary "
            "disability — bridging income loss while you recover. Two-wheeler accidents and road "
            "incidents are a top cause of loss-of-income in India. ₹{ideal_lakh}L PA cover costs "
            "roughly ₹500–1,500/year and is one of the most underused cheap protections."
        ),
        "action": "Add a standalone PA policy or bundle one with your motor renewal.",
        "cta": "recommend",
    },
    "missing_ci": {
        "severity_default": "medium",
        "icon": "alert-triangle",
        "headline": "No critical illness cover — and you're at the age where this matters.",
        "explanation": (
            "Critical illness cover pays a lump sum on diagnosis of cancer, heart attack, stroke, "
            "or other listed conditions — independent of hospitalization costs. The lump sum "
            "bridges 12–18 months of income while you focus on treatment. At your age, ₹25–50L "
            "CI cover is appropriate and costs ₹3,000–6,000/year."
        ),
        "action": "Add CI cover as a rider on existing health/term policy or as a standalone.",
        "cta": "recommend",
    },
    "missing_motor": {
        "severity_default": "high",
        "icon": "shield-off",
        "headline": "You own a vehicle but have no own-damage motor insurance.",
        "explanation": (
            "Third-party motor insurance is mandatory by law, but own-damage cover is optional — "
            "and almost always worth it. Without own-damage, theft, accidental damage, fire, or "
            "natural disaster damage to your vehicle is paid entirely by you. Own-damage premium "
            "is typically 1–2% of vehicle IDV per year."
        ),
        "action": "Add a comprehensive (third-party + own-damage) motor policy at next renewal.",
        "cta": "recommend",
    },
    "missing_travel": {
        "severity_default": "low",
        "icon": "alert-triangle",
        "headline": "You travel internationally but don't have travel insurance.",
        "explanation": (
            "International medical bills are denominated in dollars/euros — a single ER visit in "
            "the US can run $5,000–15,000. Travel insurance is the cheapest insurance per rupee "
            "of cover (₹500–2,000 for a 2-week trip) and covers medical, baggage, and trip "
            "cancellation."
        ),
        "action": "Buy per-trip travel cover before your next international flight (takes ~2 minutes online).",
        "cta": "educate",
    },
    "missing_home": {
        "severity_default": "medium",
        "icon": "alert-triangle",
        "headline": "No home insurance — your largest asset is uninsured against fire, flood, and theft.",
        "explanation": (
            "Home insurance covers the structure (₹2,000–5,000/year for ₹50L cover) and contents "
            "(₹1,000–3,000/year for ₹10L cover) against fire, flood, earthquake, theft, and "
            "burglary. Most Indians underinsure their home — typically the largest single asset "
            "in the household."
        ),
        "action": "Add a basic home insurance policy — total cost is usually under ₹5,000/year.",
        "cta": "recommend",
    },
    "underinsured_health": {
        "severity_default": "high",
        "icon": "alert-triangle",
        "headline": "Your health cover is ₹{actual_lakh}L but you need ~₹{ideal_lakh}L for {user_city}.",
        "explanation": (
            "Based on your city tier, age, family size, and any flagged conditions, your ideal "
            "health cover is around ₹{ideal_lakh}L. You currently have ₹{actual_lakh}L — a gap "
            "of ₹{gap_lakh}L. The cheapest way to close it is usually a super top-up (kicks in "
            "above your existing cover) rather than a full replacement, which would lose your "
            "existing PED waiting credits."
        ),
        "action": "Add a ₹{topup_lakh}L super top-up with a ₹{actual_lakh}L deductible — typically ₹3,000–6,000/year.",
        "cta": "recommend",
    },
    "underinsured_life": {
        "severity_default": "high",
        "icon": "alert-triangle",
        # Uses pre-formatted strings (e.g., "₹4 Lakh", "₹1.5 Cr") rather
        # than raw integers — see findings._format_inr_short() for the
        # rules. Avoids the "₹1 Cr floor" misreporting bug where any
        # sub-crore cover incorrectly displayed as "₹1 Cr".
        "headline": "Your life cover is {actual_str} but your family needs ~{ideal_str}.",
        "explanation": (
            "Based on your income, age, and dependents, ideal life cover is around {ideal_str}. "
            "You currently have {actual_str}. The gap of {gap_str} can be closed with a "
            "top-up term policy from a different insurer (cheaper than upgrading the existing "
            "one and gives diversification across insurers)."
        ),
        "action": "Add {gap_str} top-up term cover — at your age, ~₹500–800/year per ₹1 Cr.",
        "cta": "recommend",
    },
    # --- Cost-driven ---
    "cost_overpaying": {
        "severity_default": "medium",
        "icon": "alert-triangle",
        "headline": "You're paying ₹{premium:,}/year for a policy that should cost ~₹{benchmark:,}.",
        "explanation": (
            "Adjusted for your policy's quality bucket, age band, city tier, and sum insured, the "
            "market rate for comparable cover is around ₹{benchmark:,}/year. You're paying "
            "₹{premium:,} — about ₹{overage:,} above market. Same coverage, lower premium is "
            "usually achievable by porting at renewal."
        ),
        "action": "Compare quotes for equivalent cover at renewal — typical savings ₹3,000–8,000/year.",
        "cta": "recommend",
    },
}


# Sanity: spec asks for 25 templates. Counted at module load to catch
# accidental drops in PRs.
assert len(TEMPLATES) >= 25, f"templates dropped below 25: have {len(TEMPLATES)}"