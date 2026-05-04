"""Claim-Readiness deduction values.

Spec reference: Kavachly_Audit_Engine_Spec.docx Section 4 — "Revised
deduction table — calibrated to actual claim impact". Each magnitude has
the spec's stated rationale in an inline comment so the constant is
audit-traceable when a domain expert reviews.

The compounding rule (spec Section 4): when a single policy triggers ≥3
deductions, add an extra 5 × (n-2) penalty because real claim events hit
all three deductions simultaneously on the same bill. Implemented in
claim_readiness.score_policy().

Defensive bias: when a parsed_field is missing/None, the engine treats it
as the WORSE side (e.g., missing room_rent_cap is treated as having a
restrictive cap, not as "unlimited"). The spec's principle: "a user told
they are over-cautious complains; one told they are fine and gets a ₹5L
hospital bill loses the brand forever."

==========================================================================
SOURCES — Regulatory bases for the threshold values
==========================================================================
- Room rent: the "1% of SI" cap is the IRDAI minimum stipulated under
  the Health Insurance Regulations (2016) §10(c) for sub-limit-bearing
  products — older IRDAI-File-and-Use-cleared products commonly cap at
  exactly 1%, while the May 2024 Master Circular on Health Insurance
  Products encouraged (but did not mandate) phasing out the sub-limit.
  Our Tier-1 <= 1% trigger captures the IRDAI floor as the worst-case
  (HDFC ERGO 2024 metro guide: ₹12-20K/day for a private room — a 1%
  cap of a ₹10L policy = ₹10K, insufficient at ₹15K median).
  Tier-2 stays strict < because state-capital private-room rates run
  ₹6-10K/day where 1% of a ₹10L SI is borderline-acceptable.
- Co-pay > 10%: 10% is the threshold the IRDAI Standard Health Insurance
  Product (Arogya Sanjeevani) caps at (Master Circular Standard Products
  Jan 2020 §5.1 — Arogya Sanjeevani permits 5% co-pay, all other
  standardized products cap at 10%). Above 10% is materially restrictive.
- PED waiting > 3 years: IRDAI Master Circular on Health Insurance
  Products (May 2024) §6.4 caps the PED waiting period at 36 months for
  all health products approved after May 2024. Older policies (pre-2024
  vintage) commonly carried 48-month PED waiting; > 36 months is now
  legacy. The deduction flags users still on legacy contracts.
- CSR < 90%: 90% is the IRDAI internal threshold below which the
  Consumer Affairs department flags an insurer for review (IRDAI
  Annual Report FY23-24, Chapter 8 Public Grievances). Below 80% the
  insurer is on the watch list; below 70% triggers a formal directive.
- CSR < 80%: see above — IRDAI watch-list threshold.
- Network < 3,000 hospitals: IRDAI's Hospital Network Database
  (irdai.gov.in/web/guest/hospital-network) lists 38,000+ empanelled
  cashless hospitals industry-wide; an insurer covering < 8% of that
  network materially raises the probability of out-of-network treatment
  in an emergency.
- Compounding rule (≥3 deductions → +5 × (n-2)): empirical — see spec
  Section 4 worked example. Real claims hit multiple deductions
  simultaneously on the same bill (room cap → proportionate deduction
  → applies to surgeon, ICU, medicines lines too).
"""
from __future__ import annotations

from typing import Final


# Spec Section 4 — Room rent / ICU
ROOM_RENT_CAP_PCT_OF_SI = 0.01            # cap < 1% of SI is the trigger
ROOM_RENT_CAP_T1_DEDUCTION = 25            # Mumbai/Delhi proportionate-deduction killer
ROOM_RENT_CAP_T2_DEDUCTION = 15            # Real but less catastrophic
ROOM_RENT_NO_CAP_REWARD = 5                # Reward, not just absence of penalty (rare)
ICU_CAP_PCT_OF_SI = 0.02                   # ICU cap < 2% of SI triggers
ICU_CAP_DEDUCTION = 10                     # ICU at metro is ₹25-50K/day

# Spec Section 4 — Co-pay
COPAY_HIGH_THRESHOLD = 10                  # > 10% co-pay
COPAY_LOW_THRESHOLD = 1                    # 1-10% co-pay
COPAY_HIGH_DEDUCTION = 15                  # On a ₹5L bill, 10% co-pay = ₹50K out of pocket
COPAY_LOW_DEDUCTION = 5                    # Lower but still a real bite

# Spec Section 4 — Disease-specific sub-limits
SUBLIMIT_PER_ITEM_DEDUCTION = 8            # Knee replacement caps at ₹2L; actual cost ₹4-6L

# Spec Section 4 — Waiting periods
PED_WAITING_THRESHOLD_YEARS = 3            # > 3 years is excessive
PED_WAITING_DEDUCTION = 10                 # 4-year hole in coverage
PED_WAITING_WITH_DISCLOSED_DEDUCTION = 25  # Combined: known condition won't be covered for years
DISEASE_WAITING_THRESHOLD_YEARS = 2        # Cataract/hernia/ENT typically 2y; > 2y excessive
DISEASE_WAITING_DEDUCTION = 5

# Spec Section 4 — Network
NETWORK_THRESHOLD = 3000                   # < 3000 hospitals nationwide
NETWORK_DEDUCTION = 10                     # Cashless will fail in emergencies in T2/T3
NETWORK_TIER3_DEDUCTION = 15               # Compounded — almost no nearby network hospital

# Spec Section 4 — CSR
CSR_LOW_THRESHOLD = 0.90                   # < 90%
CSR_VERY_LOW_THRESHOLD = 0.80              # < 80%
CSR_LOW_DEDUCTION = 15
CSR_VERY_LOW_DEDUCTION = 25

# Spec Section 4 — Permanent exclusions matching disclosed condition
PERMANENT_EXCLUSION_MATCH_DEDUCTION = 20   # Silent killer

# Spec Section 4 — Restoration / NCB
NO_RESTORATION_DEDUCTION = 5
RESTORATION_UNLIMITED_REWARD = 8           # Reward genuinely good design
NCB_HIGH_THRESHOLD = 50                    # NCB > 50%
NCB_HIGH_REWARD = 5                        # Working policy with track record

# Spec Section 4 — Compounding rule
COMPOUNDING_TRIGGER_COUNT = 3
COMPOUNDING_PENALTY_PER_EXTRA = 5          # 5 × (n - 2) extra penalty

# Conditions that, if disclosed, trigger PED-related compound penalties.
# Used to detect "user has disclosed PED" → upgrade PED_WAITING penalty.
#
# TODO(canonical-exclusion-match): swap substring-on-verbatim matching
# against this set with set-intersection on
# parsed_fields["permanent_exclusions_canonical"] (the canonical vocab
# the parser produces — see services/parser/canonical_vocabulary.py
# CANONICAL_EXCLUSIONS). Substring matching across "Type 2 diabetes
# mellitus and complications thereof" still works today, but the
# canonical-set approach is more precise and faster. One-line engine
# update once we have audit data showing the substring path is missing
# real matches.
DISCLOSED_PED_KEYWORDS: Final[frozenset[str]] = frozenset({
    "diabetes", "bp", "blood pressure", "hypertension", "heart", "cardiac",
    "cancer", "kidney", "liver", "thyroid", "asthma", "copd", "stroke",
})


# Spec Section 5 — Gap Score deductions per protection type.
# Negative numbers; positive trigger conditions evaluated in gap.py.
GAP_DEDUCTIONS: Final[dict[str, int]] = {
    "health":     -30,  # #1 cause of household financial ruin
    "term_life":  -25,  # death + loan = catastrophic
    "pa":         -10,  # two-wheeler accidents top loss-of-income cause
    "ci":         -10,  # CI plans bridge income loss during long treatment
    "motor":      -15,  # vehicle owner without OD cover
    "travel":     -5,   # per-trip insurance is cheap; many users buy ad-hoc
    "home":       -10,  # most Indians underinsure their largest asset
    "cyber":      0,    # market too new in v1; mention but don't penalize
}


# Spec Section 2 — Coverage Score weights (sum to 1.0)
COVERAGE_WEIGHTS: Final[dict[str, float]] = {
    "health":  0.40,    # Bumped from 0.35: underinsured health is 1.3× more
                        # common a cause of household ruin than underinsured term
    "life":    0.30,
    "motor":   0.10,
    "pa":      0.10,
    "other":   0.10,
}

# Spec Section 2 — coverage_ratio_per_type cap.
# 1.2x cap so being 50% over-insured doesn't artificially inflate score.
COVERAGE_RATIO_CAP = 1.2

# Spec Section 2 — group / investment-product credit factors.
EMPLOYER_GROUP_CREDIT = 0.80    # Group health from employer (lapses on job change)
INVESTMENT_PRODUCT_CREDIT = 0.30  # ULIP/endowment face value (not real protection)


# Spec Section 6 — Finding ranking weights.
RANK_WEIGHT_SCORE_IMPACT = 1.0
RANK_WEIGHT_USER_PROXIMITY = 0.8
RANK_WEIGHT_ACTIONABILITY = 0.5
TOP_FINDINGS_COUNT = 3