"""Adapter tests for to_engine_shape() — the joint between the rich
ParsedPolicy (parser output) and the flat dict the audit engine consumes.

Drift here corrupts every audit. Tests assert the exact mapping for
every field, every enum value, every edge case the user spec called out.
"""
from __future__ import annotations

from services.parser.response_validator import to_engine_shape
from services.parser.types import (
    ICUCap,
    NCBStructure,
    ParsedFieldsRich,
    ParsedPolicy,
    RestorationBenefit,
    RoomRentCap,
    SpecificDiseaseWaiting,
    SubLimit,
)


def _policy(sum_insured: int = 500_000, **pf_kwargs) -> ParsedPolicy:
    """Minimal ParsedPolicy with overrideable parsed_fields kwargs."""
    return ParsedPolicy(
        insurer_name="HDFC ERGO General",
        insurer_name_raw="HDFC ERGO General Insurance",
        policy_type="health_individual",
        sum_insured=sum_insured,
        premium_annual=10_000,
        parsed_fields=ParsedFieldsRich(**pf_kwargs),
    )


# ==========================================================================
# Room rent cap — all 4 enum values
# ==========================================================================

def test_room_rent_fixed_amount_passes_through_as_int() -> None:
    flat = to_engine_shape(_policy(
        room_rent_cap=RoomRentCap(type="fixed_amount", value=5000, raw_text="Rs. 5,000/day")
    ))
    assert flat["room_rent_cap"] == 5000


def test_room_rent_percentage_of_si_converts_basis_points() -> None:
    """User example: {type: percentage_of_si, value: 100} on a ₹5L SI
    must produce flat room_rent_cap: 5000 (1% of 500K)."""
    flat = to_engine_shape(_policy(
        sum_insured=500_000,
        room_rent_cap=RoomRentCap(type="percentage_of_si", value=100, raw_text="1% of SI"),
    ))
    assert flat["room_rent_cap"] == 5000


def test_room_rent_percentage_2pct_on_10L() -> None:
    """200 basis points = 2%; 2% of ₹10L = 20,000."""
    flat = to_engine_shape(_policy(
        sum_insured=1_000_000,
        room_rent_cap=RoomRentCap(type="percentage_of_si", value=200, raw_text="2% of SI"),
    ))
    assert flat["room_rent_cap"] == 20_000


def test_room_rent_no_cap_produces_zero_for_engine_reward() -> None:
    """Engine reads `room_rent_cap == 0` as the explicit "no cap" reward."""
    flat = to_engine_shape(_policy(
        room_rent_cap=RoomRentCap(type="no_cap", value=None, raw_text="Actuals")
    ))
    assert flat["room_rent_cap"] == 0


def test_room_rent_single_private_room_produces_none() -> None:
    """Engine None → rule skipped (no penalty, no reward)."""
    flat = to_engine_shape(_policy(
        room_rent_cap=RoomRentCap(type="single_private_room", value=None,
                                  raw_text="Single private AC room")
    ))
    assert flat["room_rent_cap"] is None


def test_room_rent_absent_produces_none() -> None:
    flat = to_engine_shape(_policy(room_rent_cap=None))
    assert flat["room_rent_cap"] is None


# ==========================================================================
# ICU cap — same enum logic as room rent
# ==========================================================================

def test_icu_fixed_amount() -> None:
    flat = to_engine_shape(_policy(
        icu_cap=ICUCap(type="fixed_amount", value=10000, raw_text="₹10,000/day")
    ))
    assert flat["icu_cap"] == 10000


def test_icu_percentage_of_si() -> None:
    flat = to_engine_shape(_policy(
        sum_insured=500_000,
        icu_cap=ICUCap(type="percentage_of_si", value=200, raw_text="2% of SI"),
    ))
    assert flat["icu_cap"] == 10000


def test_icu_no_cap() -> None:
    flat = to_engine_shape(_policy(icu_cap=ICUCap(type="no_cap", value=None, raw_text="Actuals")))
    assert flat["icu_cap"] == 0


def test_icu_absent() -> None:
    flat = to_engine_shape(_policy(icu_cap=None))
    assert flat["icu_cap"] is None


# ==========================================================================
# PED waiting — months → years
# ==========================================================================

def test_ped_waiting_36_months_to_3_years() -> None:
    flat = to_engine_shape(_policy(ped_waiting_months=36))
    assert flat["ped_waiting_years"] == 3


def test_ped_waiting_48_months_to_4_years() -> None:
    flat = to_engine_shape(_policy(ped_waiting_months=48))
    assert flat["ped_waiting_years"] == 4


def test_ped_waiting_24_months_to_2_years() -> None:
    flat = to_engine_shape(_policy(ped_waiting_months=24))
    assert flat["ped_waiting_years"] == 2


def test_ped_waiting_partial_months_floors() -> None:
    """30 months = 2.5 years → floors to 2 (preserves the spec's
    `> 3 years` threshold semantics: 36 won't trigger but 37+ would)."""
    flat = to_engine_shape(_policy(ped_waiting_months=30))
    assert flat["ped_waiting_years"] == 2


def test_ped_waiting_none_passes_through() -> None:
    flat = to_engine_shape(_policy(ped_waiting_months=None))
    assert flat["ped_waiting_years"] is None


# ==========================================================================
# Specific disease waiting — months → years, schema rename
# ==========================================================================

def test_specific_disease_waiting_renames_keys() -> None:
    flat = to_engine_shape(_policy(specific_disease_waiting=[
        SpecificDiseaseWaiting(category="cataract", months=24),
        SpecificDiseaseWaiting(category="hernia", months=24),
    ]))
    assert flat["disease_specific_waiting"] == [
        {"disease": "cataract", "years": 2},
        {"disease": "hernia", "years": 2},
    ]


def test_specific_disease_waiting_long_wait() -> None:
    flat = to_engine_shape(_policy(specific_disease_waiting=[
        SpecificDiseaseWaiting(category="knee_replacement", months=48),
    ]))
    assert flat["disease_specific_waiting"][0] == {
        "disease": "knee_replacement", "years": 4,
    }


def test_specific_disease_waiting_empty() -> None:
    flat = to_engine_shape(_policy(specific_disease_waiting=[]))
    assert flat["disease_specific_waiting"] == []


# ==========================================================================
# Restoration benefit — nested → two flat bools
# ==========================================================================

def test_restoration_unlimited_sets_both_flags() -> None:
    """{available: true, type: unlimited} → restoration_benefit=True,
    restoration_unlimited=True."""
    flat = to_engine_shape(_policy(
        restoration_benefit=RestorationBenefit(
            available=True, type="unlimited", applies_to="both"
        )
    ))
    assert flat["restoration_benefit"] is True
    assert flat["restoration_unlimited"] is True


def test_restoration_once_per_year_only_flag() -> None:
    flat = to_engine_shape(_policy(
        restoration_benefit=RestorationBenefit(
            available=True, type="once_per_year", applies_to="different_illness"
        )
    ))
    assert flat["restoration_benefit"] is True
    assert flat["restoration_unlimited"] is False


def test_restoration_unavailable() -> None:
    flat = to_engine_shape(_policy(
        restoration_benefit=RestorationBenefit(
            available=False, type="none", applies_to="same_illness"
        )
    ))
    assert flat["restoration_benefit"] is False
    assert flat["restoration_unlimited"] is False


def test_restoration_field_absent() -> None:
    flat = to_engine_shape(_policy(restoration_benefit=None))
    assert flat["restoration_benefit"] is False
    assert flat["restoration_unlimited"] is False


# ==========================================================================
# NCB structure — nested → flat ncb_percent
# ==========================================================================

def test_ncb_max_percent_extracted() -> None:
    flat = to_engine_shape(_policy(
        ncb_structure=NCBStructure(max_percent=100, increment_per_year=25)
    ))
    assert flat["ncb_percent"] == 100


def test_ncb_premium_plan_500_percent() -> None:
    flat = to_engine_shape(_policy(
        ncb_structure=NCBStructure(max_percent=500, increment_per_year=100)
    ))
    assert flat["ncb_percent"] == 500


def test_ncb_absent_zero() -> None:
    flat = to_engine_shape(_policy(ncb_structure=None))
    assert flat["ncb_percent"] == 0


# ==========================================================================
# Sub-limits — category→type rename, dual-format cap derivation
# ==========================================================================

def test_sublimit_uses_limit_amount_when_provided() -> None:
    flat = to_engine_shape(_policy(sub_limits=[
        SubLimit(category="cataract", limit_amount=40_000, raw_text="Rs. 40,000")
    ]))
    assert flat["sub_limits"] == [{"type": "cataract", "cap": 40_000}]


def test_sublimit_falls_back_to_percent_of_si() -> None:
    """No limit_amount → derive from percent_of_si × sum_insured.
    20% of ₹10L = ₹2L."""
    flat = to_engine_shape(_policy(
        sum_insured=1_000_000,
        sub_limits=[SubLimit(
            category="knee_replacement",
            limit_amount=None,
            limit_percent_of_si=2000,  # 20% in basis points
            raw_text="20% of SI",
        )],
    ))
    assert flat["sub_limits"] == [{"type": "knee_replacement", "cap": 200_000}]


def test_sublimit_prefers_limit_amount_over_percent() -> None:
    """If both are present (rare), prefer limit_amount."""
    flat = to_engine_shape(_policy(
        sum_insured=1_000_000,
        sub_limits=[SubLimit(
            category="maternity",
            limit_amount=50_000,
            limit_percent_of_si=2000,
            raw_text="Rs. 50,000",
        )],
    ))
    assert flat["sub_limits"] == [{"type": "maternity", "cap": 50_000}]


def test_sublimit_neither_value_present_zero_cap() -> None:
    flat = to_engine_shape(_policy(sub_limits=[
        SubLimit(category="day_care", raw_text="As per policy")
    ]))
    assert flat["sub_limits"] == [{"type": "day_care", "cap": 0}]


def test_sublimits_multiple() -> None:
    flat = to_engine_shape(_policy(sub_limits=[
        SubLimit(category="cataract",        limit_amount=40_000),
        SubLimit(category="knee_replacement", limit_amount=200_000),
        SubLimit(category="maternity",       limit_amount=50_000),
    ]))
    assert len(flat["sub_limits"]) == 3
    assert flat["sub_limits"][0]["type"] == "cataract"


# ==========================================================================
# Pass-through fields
# ==========================================================================

def test_copay_percent_pass_through() -> None:
    flat = to_engine_shape(_policy(copay_percent=20))
    assert flat["copay_percent"] == 20


def test_ambulance_cap_pass_through() -> None:
    flat = to_engine_shape(_policy(ambulance_cap=2000))
    assert flat["ambulance_cap"] == 2000


def test_network_hospital_count_pass_through() -> None:
    flat = to_engine_shape(_policy(network_hospital_count=12_500))
    assert flat["network_hospitals"] == 12_500


def test_permanent_exclusions_verbatim_and_canonical() -> None:
    flat = to_engine_shape(_policy(
        permanent_exclusions=["Type 2 diabetes", "Cosmetic surgery"],
        permanent_exclusions_canonical=["diabetes"],
    ))
    assert flat["permanent_exclusions"] == ["Type 2 diabetes", "Cosmetic surgery"]
    assert flat["permanent_exclusions_canonical"] == ["diabetes"]


# ==========================================================================
# End-to-end: engine consumes the flat shape without crashing
# ==========================================================================

def test_engine_consumes_to_engine_shape_without_crash() -> None:
    """Round-trip: feed a realistic ParsedPolicy through the adapter into
    the audit engine. No crashes, claim_readiness produces a value.
    """
    from services.audit import claim_readiness
    from services.audit.types import Policy as EnginePolicy
    from services.audit.types import UserProfile

    rich = ParsedPolicy(
        insurer_name="HDFC ERGO General",
        insurer_name_raw="HDFC ERGO General Insurance",
        policy_type="health_family_floater",
        sum_insured=1_500_000,
        premium_annual=22_400,
        parsed_fields=ParsedFieldsRich(
            room_rent_cap=RoomRentCap(type="percentage_of_si", value=100, raw_text="1% of SI"),
            icu_cap=ICUCap(type="percentage_of_si", value=200, raw_text="2% of SI"),
            copay_percent=10,
            ped_waiting_months=24,
            specific_disease_waiting=[SpecificDiseaseWaiting(category="cataract", months=24)],
            permanent_exclusions=["cosmetic surgery"],
            permanent_exclusions_canonical=[],
            network_hospital_count=12_000,
            restoration_benefit=RestorationBenefit(
                available=True, type="once_per_year", applies_to="different_illness"),
            ncb_structure=NCBStructure(max_percent=100, increment_per_year=25),
            sub_limits=[SubLimit(category="maternity", limit_amount=50_000)],
        ),
    )

    flat = to_engine_shape(rich)
    engine_policy = EnginePolicy(
        id="p1",
        type="health",
        insurer="HDFC ERGO General",
        sum_insured=1_500_000,
        premium=22_400,
        parsed_fields=flat,
    )
    user = UserProfile(user_id="u", age=34, city="Mumbai", tier="tier-1")
    breakdown = claim_readiness.score_policy(engine_policy, user)
    assert breakdown.value is not None
    assert 0 <= breakdown.value <= 100
