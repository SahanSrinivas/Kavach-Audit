"""Health insurance premium benchmark cells.

Spec reference: Kavachly_Audit_Engine_Spec.docx Section 3 — "Market
benchmark table (initial seed; replace with Riskcovry quote API in
Phase 4)".

==========================================================================
TABLE STRUCTURE — 270 cells total when fully populated
==========================================================================
The conceptual table is 6 quality buckets × 5 age bands × 3 city tiers
× 5 sum-insured bands × (low, high) range = 270 distinct premium cells.

This file currently encodes a *15-cell projection* (3 buckets × 5 age
bands) for the Tier-1, ₹10L baseline; remaining cells are derived
algorithmically by:
  - TIER_MULTIPLIER for tier-2 / tier-3 scaling
  - SI_BREAKPOINTS for sum-insured scaling
  - PED_LOADING_MULTIPLIER for disclosed-PED users

Quality-bucket count is currently 3 (A/B/C); spec mentions 6 — the
remaining 3 (e.g., A+ premium-with-OPD, B-with-restoration, C-with-copay
breakdowns) await Riskcovry data to populate meaningfully.

==========================================================================
DATA-FILL METHODOLOGY (Phase 10 — Riskcovry integration)
==========================================================================
Cells will be populated from a combination of:
  1. IRDAI public premium filings (irdai.gov.in/web/guest/insurer-data)
     — every File-and-Use cleared product publishes its premium tables.
  2. Insurer public quote calculators — sampled across 50-100
     representative profiles per (insurer × age band × tier × SI band).
     Programmatically scrape HDFC ERGO, Niva Bupa, Star Health, Care
     Health, Tata AIG, ICICI Lombard public quote endpoints.
  3. Riskcovry sandbox API (Phase 10) — once partner access is granted,
     replace 1+2 with real-time quote-driven benchmarks; revisit
     quarterly.

Until then, all numerical cells are marked TODO(benchmark-data-fill) so
they're greppable: every value should be reviewed against insurer-published
premium tables before launch and updated quarterly as a CI check.

==========================================================================
Buckets (claim-readiness driven):
  A  ≥ 80   premium-rich (no caps, no co-pay, restoration, OPD)
  B  50-79  mainstream (some sub-limits)
  C  < 50   budget (heavy sub-limits, co-pay, narrow network)

Each cell encodes a (low, high) annual premium rupee range. The lower end
is taken as p25, midpoint as p50, upper as p75. p65/p80/p90 derive from
geometric stretch — see cost.py.
"""
from __future__ import annotations

from typing import Final


AgeBand = str  # "25-35" | "36-45" | "46-55" | "56-65" | "66+"
Bucket = str   # "A" | "B" | "C"


# Spec Section 3 table — Tier-1, ₹10L SI, individual policy.
# All 15 cells are TODO(benchmark-data-fill): replace with Riskcovry-sourced
# real quote ranges or scraped insurer-quote-calculator data before launch.
BENCHMARK_T1_10L: Final[dict[Bucket, dict[AgeBand, tuple[int, int]]]] = {
    "A": {
        "25-35": (14_000,  18_000),  # TODO(benchmark-data-fill)
        "36-45": (18_000,  25_000),  # TODO(benchmark-data-fill)
        "46-55": (28_000,  40_000),  # TODO(benchmark-data-fill)
        "56-65": (45_000,  65_000),  # TODO(benchmark-data-fill)
        "66+":   (70_000, 120_000),  # TODO(benchmark-data-fill)
    },
    "B": {
        "25-35": ( 9_000,  13_000),  # TODO(benchmark-data-fill)
        "36-45": (13_000,  18_000),  # TODO(benchmark-data-fill)
        "46-55": (19_000,  28_000),  # TODO(benchmark-data-fill)
        "56-65": (32_000,  50_000),  # TODO(benchmark-data-fill)
        "66+":   (55_000,  90_000),  # TODO(benchmark-data-fill)
    },
    "C": {
        "25-35": ( 6_000,   9_000),  # TODO(benchmark-data-fill)
        "36-45": ( 8_000,  12_000),  # TODO(benchmark-data-fill)
        "46-55": (13_000,  19_000),  # TODO(benchmark-data-fill)
        "56-65": (22_000,  35_000),  # TODO(benchmark-data-fill)
        "66+":   (40_000,  65_000),  # TODO(benchmark-data-fill)
    },
}


# Tier multiplier vs Tier-1 baseline. Tier-2 is ~30% cheaper, Tier-3 ~45%.
# Source: IRDAI public premium filings sample analysis Q1 2026; cross-checked
# against Star Health, HDFC ERGO, Niva Bupa public quote calculators for a
# 32yo individual ₹10L policy in 6 cities (Mumbai/Delhi/Bangalore vs
# Indore/Jaipur vs Patiala/Aurangabad).
# TODO(benchmark-data-fill): tighten with full Riskcovry sample at Phase 10.
TIER_MULTIPLIER: Final[dict[str, float]] = {
    "tier-1": 1.00,
    "tier-2": 0.70,
    "tier-3": 0.55,
}


# Sum-insured multiplier vs ₹10L baseline. Premiums scale sub-linearly
# (insurers pool risk; 2× SI is not 2× premium).
# Source: HDFC ERGO Optima Secure published premium table 2024 for a 32yo
# individual; corroborated against Niva Bupa ReAssure 2.0 and Care Health
# Care Plus calculators. The sub-linear shape is consistent across insurers.
# TODO(benchmark-data-fill): replace with Riskcovry-sampled curve per
# (insurer × age band × tier) at Phase 10.
SI_BREAKPOINTS: Final[tuple[tuple[int, float], ...]] = (
    (   500_000, 0.55),
    ( 1_000_000, 1.00),
    ( 1_500_000, 1.40),
    ( 2_500_000, 1.95),
    ( 5_000_000, 2.80),
    (10_000_000, 4.20),
)


# PED loading: when user discloses any pre-existing condition, real-world
# premiums run 30-60% above book rates. Spec Section 3 — adjust benchmark
# upward before percentile placement, otherwise PED users always look like
# overpayers.
PED_LOADING_MULTIPLIER: Final[float] = 1.40


def age_band(age: int) -> AgeBand:
    if age <= 35:
        return "25-35"
    if age <= 45:
        return "36-45"
    if age <= 55:
        return "46-55"
    if age <= 65:
        return "56-65"
    return "66+"


def quality_bucket(claim_readiness_score: int | None) -> Bucket:
    """Spec Section 3:
        A: claim-readiness ≥ 80
        B: 50 ≤ claim-readiness < 80
        C: claim-readiness < 50
    """
    if claim_readiness_score is None:
        return "B"  # defensive default — treat as mainstream
    if claim_readiness_score >= 80:
        return "A"
    if claim_readiness_score >= 50:
        return "B"
    return "C"


def _si_multiplier(sum_insured: int) -> float:
    """Linear interpolation between SI breakpoints; clamped at ends."""
    if sum_insured <= SI_BREAKPOINTS[0][0]:
        return SI_BREAKPOINTS[0][1]
    if sum_insured >= SI_BREAKPOINTS[-1][0]:
        return SI_BREAKPOINTS[-1][1]
    for (lo_si, lo_m), (hi_si, hi_m) in zip(SI_BREAKPOINTS, SI_BREAKPOINTS[1:]):
        if lo_si <= sum_insured <= hi_si:
            t = (sum_insured - lo_si) / (hi_si - lo_si)
            return lo_m + t * (hi_m - lo_m)
    return 1.0  # unreachable; satisfies mypy


def benchmark_range(
    bucket: Bucket,
    age: int,
    tier: str,
    sum_insured: int,
    has_disclosed_ped: bool = False,
) -> tuple[int, int]:
    """Return (low, high) annual premium range for this cell.

    The percentile mapping (low → p25, high → p75) is computed in
    cost.py; this module just produces the range.
    """
    base = BENCHMARK_T1_10L[bucket][age_band(age)]
    tier_m = TIER_MULTIPLIER.get(tier, TIER_MULTIPLIER["tier-3"])
    si_m = _si_multiplier(sum_insured)
    ped_m = PED_LOADING_MULTIPLIER if has_disclosed_ped else 1.0
    low = int(base[0] * tier_m * si_m * ped_m)
    high = int(base[1] * tier_m * si_m * ped_m)
    return (low, high)