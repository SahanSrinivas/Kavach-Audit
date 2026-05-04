"""Claim-Readiness unit tests — every deduction rule, plus compounding."""
from __future__ import annotations

from typing import Any

from services.audit import claim_readiness
from services.audit.constants.csr_table import lookup_csr
from services.audit.constants.deduction_rules import (
    COMPOUNDING_PENALTY_PER_EXTRA,
    COPAY_HIGH_DEDUCTION,
    COPAY_LOW_DEDUCTION,
    CSR_LOW_DEDUCTION,
    CSR_VERY_LOW_DEDUCTION,
    ICU_CAP_DEDUCTION,
    NETWORK_DEDUCTION,
    NETWORK_TIER3_DEDUCTION,
    PED_WAITING_DEDUCTION,
    PED_WAITING_WITH_DISCLOSED_DEDUCTION,
    PERMANENT_EXCLUSION_MATCH_DEDUCTION,
    ROOM_RENT_CAP_T1_DEDUCTION,
    ROOM_RENT_CAP_T2_DEDUCTION,
    SUBLIMIT_PER_ITEM_DEDUCTION,
)
from services.audit.types import Lifestyle, Policy, UserProfile


def _user(tier: str = "tier-1", **kw: Any) -> UserProfile:
    return UserProfile(user_id="x", age=35, city="Mumbai", tier=tier,
                       lifestyle=Lifestyle(), **kw)


def _h(insurer: str = "HDFC ERGO General", sum_insured: int = 1_000_000,
       **parsed: Any) -> Policy:
    return Policy(id="h", type="health", insurer=insurer,
                  sum_insured=sum_insured, premium=20_000,
                  parsed_fields=parsed)


# ---------- Room rent cap ----------

def test_room_rent_cap_metro_deduction() -> None:
    p = _h(sum_insured=1_000_000, room_rent_cap=5_000)  # 0.5% < 1%
    b = claim_readiness.score_policy(p, _user(tier="tier-1"))
    assert b.value == 100 - ROOM_RENT_CAP_T1_DEDUCTION


def test_room_rent_cap_tier2_deduction() -> None:
    p = _h(sum_insured=1_000_000, room_rent_cap=5_000)
    b = claim_readiness.score_policy(p, _user(tier="tier-2"))
    assert b.value == 100 - ROOM_RENT_CAP_T2_DEDUCTION


def test_room_rent_no_cap_rewards() -> None:
    p = _h(sum_insured=1_000_000, room_rent_cap=0)  # explicit no cap
    b = claim_readiness.score_policy(p, _user(tier="tier-1"))
    assert b.value > 100 - 1  # rewarded; no penalty


def test_missing_room_rent_field_does_not_reward() -> None:
    """Defensive bias: parsed_fields with no room_rent_cap key → silent."""
    p = _h(sum_insured=1_000_000)  # nothing parsed
    b = claim_readiness.score_policy(p, _user(tier="tier-1"))
    # No room rent rule fires; only the default-CSR rule will (HDFC ERGO is high CSR → silent)
    assert b.value == 100


# ---------- ICU cap ----------

def test_icu_cap_low_deducts() -> None:
    p = _h(sum_insured=1_000_000, icu_cap=10_000)  # 1% < 2%
    b = claim_readiness.score_policy(p, _user(tier="tier-1"))
    assert b.value == 100 - ICU_CAP_DEDUCTION


# ---------- Co-pay ----------

def test_copay_high_deducts_15() -> None:
    p = _h(copay_percent=20)
    b = claim_readiness.score_policy(p, _user())
    assert b.value == 100 - COPAY_HIGH_DEDUCTION


def test_copay_low_deducts_5() -> None:
    p = _h(copay_percent=5)
    b = claim_readiness.score_policy(p, _user())
    assert b.value == 100 - COPAY_LOW_DEDUCTION


# ---------- Sub-limits ----------

def test_sublimit_deduction_per_item() -> None:
    p = _h(sub_limits=[{"type": "cataract", "cap": 40_000},
                       {"type": "knee_replacement", "cap": 200_000}])
    b = claim_readiness.score_policy(p, _user())
    assert b.value == 100 - SUBLIMIT_PER_ITEM_DEDUCTION * 2


# ---------- PED waiting ----------

def test_ped_waiting_long_no_disclosed_condition() -> None:
    p = _h(ped_waiting_years=4)
    b = claim_readiness.score_policy(p, _user())
    assert b.value == 100 - PED_WAITING_DEDUCTION


def test_ped_waiting_with_disclosed_condition_combined_penalty() -> None:
    p = _h(ped_waiting_years=4)
    user = _user(parents_pec=("Diabetes",))
    b = claim_readiness.score_policy(p, user)
    assert b.value == 100 - PED_WAITING_WITH_DISCLOSED_DEDUCTION


def test_ped_waiting_at_threshold_does_not_deduct() -> None:
    p = _h(ped_waiting_years=3)  # not > 3
    b = claim_readiness.score_policy(p, _user())
    assert b.value == 100


# ---------- Network ----------

def test_network_small_tier1_deducts_10() -> None:
    p = _h(network_hospitals=2_500)
    b = claim_readiness.score_policy(p, _user(tier="tier-1"))
    assert b.value == 100 - NETWORK_DEDUCTION


def test_network_small_tier3_compounds_to_15() -> None:
    p = _h(network_hospitals=2_500)
    b = claim_readiness.score_policy(p, _user(tier="tier-3"))
    assert b.value == 100 - NETWORK_TIER3_DEDUCTION


# ---------- CSR ----------

def test_csr_low_deduction_for_known_below_90() -> None:
    p = _h(insurer="ManipalCigna")  # 0.893
    b = claim_readiness.score_policy(p, _user())
    assert b.value == 100 - CSR_LOW_DEDUCTION


def test_csr_very_low_deduction() -> None:
    p = _h(insurer="Universal Sompo")  # 0.789
    b = claim_readiness.score_policy(p, _user())
    assert b.value == 100 - CSR_VERY_LOW_DEDUCTION


def test_csr_unknown_insurer_uses_default() -> None:
    canonical, csr = lookup_csr("Some Random Insurer Pvt Ltd")
    assert canonical == "_DEFAULT"
    assert csr == 0.85
    p = _h(insurer="Some Random Insurer Pvt Ltd")
    b = claim_readiness.score_policy(p, _user())
    assert b.value == 100 - CSR_LOW_DEDUCTION


# ---------- Permanent exclusion match ----------

def test_permanent_exclusion_matches_disclosed_condition() -> None:
    p = _h(permanent_exclusions=["heart conditions", "obesity"])
    user = _user(self_pec=("Heart",))
    b = claim_readiness.score_policy(p, user)
    assert b.value == 100 - PERMANENT_EXCLUSION_MATCH_DEDUCTION


def test_permanent_exclusion_no_match_no_deduction() -> None:
    p = _h(permanent_exclusions=["adventure sports", "cosmetic surgery"])
    user = _user(self_pec=("Diabetes",))
    b = claim_readiness.score_policy(p, user)
    assert b.value == 100


# ---------- Compounding rule ----------

def test_compounding_penalty_kicks_in_at_3_deductions() -> None:
    """Spec Section 4: when n ≥ 3 deductions, extra 5×(n-2) penalty."""
    p = _h(insurer="HDFC ERGO General",  # 0.967 — no CSR penalty
           room_rent_cap=5_000,           # -25 (T1)
           copay_percent=20,              # -15
           sub_limits=[{"type": "cataract", "cap": 40_000}])  # -8 (1 item)
    b = claim_readiness.score_policy(p, _user(tier="tier-1"))
    raw = 100 - 25 - 15 - 8
    expected = raw - COMPOUNDING_PENALTY_PER_EXTRA * (3 - 2)
    assert b.value == expected


def test_compounding_penalty_scales_with_count() -> None:
    p = _h(insurer="ManipalCigna",       # -15
           room_rent_cap=5_000,           # -25
           copay_percent=20,              # -15
           ped_waiting_years=4,           # -10
           network_hospitals=2_500)       # -10
    b = claim_readiness.score_policy(p, _user(tier="tier-1"))
    # 5 deductions: 100 - (15+25+15+10+10) - 5*(5-2) = 100 - 75 - 15 = 10
    assert b.value == 10


def test_score_clamped_to_zero() -> None:
    """A policy with everything wrong should clamp at 0, not go negative."""
    p = _h(insurer="Shriram General",   # -25
           room_rent_cap=2_000,          # -25 (T1)
           copay_percent=30,             # -15
           ped_waiting_years=4,          # -25 (with disclosed PED)
           sub_limits=[{"type": "cataract", "cap": 40_000},
                       {"type": "knee", "cap": 200_000},
                       {"type": "maternity", "cap": 50_000}],  # -24
           network_hospitals=1_000,      # -15 (tier-3)
           permanent_exclusions=["diabetes"])  # -20
    user = _user(tier="tier-3", self_pec=("Diabetes",))
    b = claim_readiness.score_policy(p, user)
    assert b.value == 0


# ---------- Aggregation across policies ----------

def test_user_level_score_averages_across_health() -> None:
    p1 = _h(insurer="HDFC ERGO General")  # 100 (no penalties)
    p2 = _h(insurer="HDFC ERGO General", copay_percent=20)  # 85
    b = claim_readiness.score(_user(), [p1, p2])
    assert b.value == round((100 + 85) / 2)


def test_user_level_score_returns_none_when_no_health() -> None:
    p = Policy(id="t", type="term", insurer="HDFC Life",
               sum_insured=10_000_000, premium=12_000)
    b = claim_readiness.score(_user(), [p])
    assert b.value is None


# Issue 1 regression — null sum_insured handling

def test_score_policy_returns_none_for_null_sum_insured() -> None:
    """A wording-only PDF gets sum_insured=None. score_policy must
    short-circuit (returning None) rather than crashing on percentage-
    of-SI math (room_cap / si)."""
    p = Policy(id="h", type="health", insurer="HDFC ERGO General",
               sum_insured=None, premium=None,
               parsed_fields={"room_rent_cap": 5_000, "copay_percent": 20})
    b = claim_readiness.score_policy(p, _user())
    assert b.value is None
    assert b.details["reason"] == "missing_sum_insured"


def test_user_level_score_skips_null_si_policies_in_average() -> None:
    """User has 1 wording-only + 1 real policy: averaging uses only the real one."""
    real = _h(insurer="HDFC ERGO General")  # 100 (no penalties)
    wording = Policy(id="h2", type="health", insurer="Niva Bupa",
                     sum_insured=None, premium=None,
                     parsed_fields={})
    b = claim_readiness.score(_user(), [real, wording])
    assert b.value == 100  # only the real one counts
