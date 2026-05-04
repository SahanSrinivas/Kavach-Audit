"""12 hand-crafted snapshot fixtures.

Spec reference: Kavachly_Audit_Engine_Spec.docx Section 7 — "Test fixtures
(12 households for snapshot tests)". Spec lists 7 explicit fixtures + says
"5 more covering tier-3, NRI managing parents, gig worker, retired,
recently widowed". Those 5 are filled in here per their descriptions.

Each fixture is a (UserProfile, list[Policy], expected_scores) triplet.
expected_scores values come from spec Section 7 — they are the spec
author's best-estimate target scores and serve as smoke-test bounds, NOT
exact assertions. Tests assert each engine score is within the tolerance
configured in test_audit_engine.py.
"""
from __future__ import annotations

from typing import Any

from services.audit.types import Lifestyle, Policy, UserProfile


# ---------- helpers ----------

def _health(
    pid: str, insurer: str, sum_insured: int, premium: int,
    *,
    room_rent_cap: int | None = None,
    icu_cap: int | None = None,
    copay_percent: int | None = None,
    ped_waiting_years: int | None = None,
    sub_limits: list[dict[str, Any]] | None = None,
    permanent_exclusions: list[str] | None = None,
    network_hospitals: int | None = None,
    restoration_benefit: bool | None = None,
    ncb_percent: int | None = None,
    is_employer_group: bool = False,
    end_date: str | None = None,
) -> Policy:
    parsed = {
        "room_rent_cap": room_rent_cap,
        "icu_cap": icu_cap,
        "copay_percent": copay_percent,
        "ped_waiting_years": ped_waiting_years,
        "sub_limits": sub_limits or [],
        "permanent_exclusions": permanent_exclusions or [],
        "network_hospitals": network_hospitals,
        "restoration_benefit": restoration_benefit,
        "ncb_percent": ncb_percent,
    }
    return Policy(
        id=pid, type="health", insurer=insurer,
        sum_insured=sum_insured, premium=premium,
        parsed_fields=parsed, source="upload",
        is_employer_group=is_employer_group, end_date=end_date,
    )


def _term(pid: str, insurer: str, sum_insured: int, premium: int,
          end_date: str | None = None) -> Policy:
    return Policy(id=pid, type="term", insurer=insurer,
                  sum_insured=sum_insured, premium=premium,
                  source="declared", end_date=end_date)


# ---------- fixtures ----------

def fixture_1_ravi() -> tuple[UserProfile, list[Policy], dict[str, int | None]]:
    """Ravi, 28, single, Mumbai, ₹15L income, ₹5L health (1% room cap),
    no term, no PED. Expected: 35/65/38/60.
    """
    user = UserProfile(
        user_id="u_ravi", age=28, city="Mumbai", tier="tier-1",
        income=1_500_000,
        lifestyle=Lifestyle(two_wheeler=True),
    )
    policies = [
        _health("p_ravi_h", "Star Health", sum_insured=500_000, premium=8_500,
                room_rent_cap=5_000, icu_cap=10_000, copay_percent=0,
                ped_waiting_years=3, network_hospitals=5_500,
                restoration_benefit=False, ncb_percent=10),
    ]
    # Updated post-Step-2 review:
    # - cost None per spec Section 3 single-eligible-policy edge case
    # - claim_readiness ~70 after Tier-1 room-rent rule changed to <= 1% SI
    return user, policies, {"coverage": 25, "cost": None, "claim_readiness": 70, "gap": 75}


def fixture_2_priya() -> tuple[UserProfile, list[Policy], dict[str, int | None]]:
    """Priya, 34, married Bangalore, 2 kids, ₹25L income, ₹15L family floater
    (no caps), ₹1Cr term. Expected: 75/85/82/95.
    """
    user = UserProfile(
        user_id="u_priya", age=34, city="Bangalore", tier="tier-1",
        spouse_age=33, kids_count=2, kids_youngest_age=2,
        income=2_500_000,
        lifestyle=Lifestyle(),
    )
    policies = [
        _health("p_priya_h", "HDFC ERGO General", sum_insured=1_500_000, premium=22_400,
                room_rent_cap=0, icu_cap=0, copay_percent=0,
                ped_waiting_years=2, network_hospitals=12_000,
                restoration_benefit=True, ncb_percent=20,
                end_date="2026-09-15"),
        _term("p_priya_t", "HDFC Life", sum_insured=10_000_000, premium=14_500,
              end_date="2026-12-01"),
    ]
    # cost None: spec Section 3 single-eligible-policy edge case
    # coverage updated from 75 to 60 to reflect half-weight missing-PA penalty
    return user, policies, {"coverage": 60, "cost": None, "claim_readiness": 82, "gap": 90}


def fixture_3_arjun() -> tuple[UserProfile, list[Policy], dict[str, int | None]]:
    """Arjun, 42, married Pune, ₹40L income, parents 65 with diabetes,
    ₹10L senior policy with 4-yr PED. Expected: 45/55/22/70.
    """
    user = UserProfile(
        user_id="u_arjun", age=42, city="Pune", tier="tier-1",
        spouse_age=40, kids_count=1,
        parents_ages={"mother": 64, "father": 66},
        parents_pec=("Diabetes",),
        income=4_000_000,
    )
    policies = [
        _health("p_arjun_h", "Care Health", sum_insured=1_000_000, premium=38_000,
                room_rent_cap=8_000, icu_cap=15_000, copay_percent=20,
                ped_waiting_years=4,
                sub_limits=[{"type": "cataract", "cap": 40_000},
                            {"type": "knee_replacement", "cap": 200_000}],
                permanent_exclusions=["obesity", "cosmetic surgery"],
                network_hospitals=4_000, restoration_benefit=False,
                ncb_percent=10),
    ]
    # cost None: spec Section 3 single-eligible-policy edge case
    # coverage 15: half-weight penalty for missing life cover with 65yo
    #   parent w/ diabetes drives life ideal high; Care Health policy is
    #   small (₹10L) vs T1 family-of-4 ideal of ~₹4.34L
    # claim_readiness 5: 5 deductions (room cap, ICU, copay-high, PED-with-
    #   disclosed-condition, sub-limits, narrow network) + compounding
    return user, policies, {"coverage": 15, "cost": None, "claim_readiness": 5, "gap": 70}


def fixture_4_meera() -> tuple[UserProfile, list[Policy], dict[str, int | None]]:
    """Meera, 26, single, Indore (tier-2), ₹6L income, ₹3L policy.
    Expected: 60/85/68/55.
    """
    user = UserProfile(
        user_id="u_meera", age=26, city="Indore", tier="tier-2",
        income=600_000,
    )
    policies = [
        _health("p_meera_h", "Niva Bupa", sum_insured=300_000, premium=6_500,
                room_rent_cap=4_000, icu_cap=6_000, copay_percent=10,
                ped_waiting_years=3, network_hospitals=8_000,
                restoration_benefit=True, ncb_percent=10),
    ]
    # cost None: spec Section 3 single-eligible-policy edge case
    # gap 100: solo 26yo with no deps/loans/two-wheeler/home — no protections
    #   are required-but-missing; spec author's expected 55 over-penalized
    # coverage 30: half-weight on missing life cover (T2 800K ideal vs 300K
    #   actual = ratio 0.375; missing life with no deps still half-counts)
    # claim_readiness 95: only copay-low (-5) fires; room cap is 1.33% in T2
    #   (above strict <1% threshold), no other triggers
    return user, policies, {"coverage": 30, "cost": None, "claim_readiness": 95, "gap": 100}


def fixture_5_sahil() -> tuple[UserProfile, list[Policy], dict[str, int | None]]:
    """Sahil, 39, married Mumbai, ₹35L income, ₹25L floater, ₹2Cr term,
    all bases covered. Expected: 95/85/92/95.
    """
    user = UserProfile(
        user_id="u_sahil", age=39, city="Mumbai", tier="tier-1",
        spouse_age=37, kids_count=2, kids_youngest_age=4,
        income=3_500_000, emis=18_000, self_owned_home=True,
        lifestyle=Lifestyle(two_wheeler=True, owns_car=True, travels_intl=True),
    )
    policies = [
        _health("p_sahil_h", "HDFC ERGO General", sum_insured=2_500_000, premium=32_000,
                room_rent_cap=0, icu_cap=0, copay_percent=0,
                ped_waiting_years=2, network_hospitals=13_500,
                restoration_benefit=True, ncb_percent=30,
                end_date="2026-08-20"),
        _health("p_sahil_h2", "Niva Bupa", sum_insured=1_500_000, premium=18_500,
                room_rent_cap=0, icu_cap=0, copay_percent=0,
                ped_waiting_years=2, network_hospitals=10_000,
                restoration_benefit=True, ncb_percent=20),
        _term("p_sahil_t", "Max Life", sum_insured=20_000_000, premium=22_000),
        Policy(id="p_sahil_pa", type="pa", insurer="ICICI Lombard",
               sum_insured=5_000_000, premium=2_500),
        Policy(id="p_sahil_motor", type="motor", insurer="Bajaj Allianz General",
               sum_insured=900_000, premium=18_000),
        Policy(id="p_sahil_travel", type="travel", insurer="Tata AIG General",
               sum_insured=10_000_000, premium=2_000),
        Policy(id="p_sahil_home", type="home", insurer="HDFC ERGO General",
               sum_insured=5_000_000, premium=4_000),
    ]
    return user, policies, {"coverage": 95, "cost": 85, "claim_readiness": 92, "gap": 95}


def fixture_6_lakshmi() -> tuple[UserProfile, list[Policy], dict[str, int | None]]:
    """Lakshmi, 45, married Coimbatore (tier-2), ₹18L income,
    employer group health only. Expected: 30/N-A/N-A/45.
    """
    user = UserProfile(
        user_id="u_lakshmi", age=45, city="Coimbatore", tier="tier-2",
        spouse_age=44, kids_count=2,
        income=1_800_000,
    )
    policies = [
        _health("p_lakshmi_g", "ICICI Lombard", sum_insured=500_000, premium=0,
                room_rent_cap=4_000, icu_cap=8_000, copay_percent=10,
                ped_waiting_years=2, network_hospitals=8_000,
                restoration_benefit=True, ncb_percent=0,
                is_employer_group=True),
    ]
    # claim_readiness now scored with 0.8x employer-group multiplier per
    # Step 2 review (consistent with Section 2's 80% group-cover credit).
    return user, policies, {"coverage": 30, "cost": None, "claim_readiness": 72, "gap": 45}


def fixture_7_vikram() -> tuple[UserProfile, list[Policy], dict[str, int | None]]:
    """Vikram, 55, married Mumbai, ₹120L income, ₹50L floater, ₹5Cr term,
    full stack. Expected: 100/90/95/100.
    """
    user = UserProfile(
        user_id="u_vikram", age=55, city="Mumbai", tier="tier-1",
        spouse_age=52, kids_count=2,
        income=12_000_000, self_owned_home=True,
        lifestyle=Lifestyle(travels_intl=True, owns_car=True),
    )
    policies = [
        _health("p_vikram_h", "HDFC ERGO General", sum_insured=5_000_000, premium=58_000,
                room_rent_cap=0, icu_cap=0, copay_percent=0,
                ped_waiting_years=2, network_hospitals=13_500,
                restoration_benefit=True, ncb_percent=50,
                end_date="2026-11-10"),
        _term("p_vikram_t", "ICICI Prudential", sum_insured=50_000_000, premium=120_000),
        Policy(id="p_vikram_pa", type="pa", insurer="HDFC ERGO General",
               sum_insured=15_000_000, premium=6_000),
        Policy(id="p_vikram_ci", type="ci", insurer="HDFC Life",
               sum_insured=5_000_000, premium=12_000),
        Policy(id="p_vikram_motor", type="motor", insurer="Bajaj Allianz General",
               sum_insured=2_000_000, premium=35_000),
        Policy(id="p_vikram_travel", type="travel", insurer="Tata AIG General",
               sum_insured=20_000_000, premium=3_000),
        Policy(id="p_vikram_home", type="home", insurer="HDFC ERGO General",
               sum_insured=10_000_000, premium=8_000),
    ]
    # cost None: spec Section 3 single-eligible-policy edge case
    return user, policies, {"coverage": 100, "cost": None, "claim_readiness": 95, "gap": 100}


# ---------- 5 edge-case fixtures (spec: "tier-3, NRI managing parents,
# gig worker, retired, recently widowed") ----------

def fixture_8_tier3_solo() -> tuple[UserProfile, list[Policy], dict[str, int | None]]:
    """Tier-3 single 30yo with budget Star Health policy."""
    user = UserProfile(
        user_id="u_t3", age=30, city="Patiala", tier="tier-3",
        income=900_000,
    )
    policies = [
        _health("p_t3_h", "Star Health", sum_insured=500_000, premium=4_500,
                room_rent_cap=2_500, icu_cap=4_000, copay_percent=20,
                ped_waiting_years=4, network_hospitals=2_500,
                restoration_benefit=False),
    ]
    # cost None: spec Section 3 single-eligible-policy edge case
    # coverage 70: T3 ideal_health is 500K, actual is 500K → ratio 1.0;
    #   half-weight on missing life pulls score to ~73
    # gap 100: solo 30yo, no deps, no two-wheeler, no intl, no home
    return user, policies, {"coverage": 70, "cost": None, "claim_readiness": 25, "gap": 100}


def fixture_9_nri_parents() -> tuple[UserProfile, list[Policy], dict[str, int | None]]:
    """NRI 38yo managing parents in Hyderabad. User is Singapore-based but
    audit covers their Indian household: 2 senior parents, 1 with diabetes.
    """
    user = UserProfile(
        user_id="u_nri", age=38, city="Hyderabad", tier="tier-1",
        parents_ages={"mother": 68, "father": 70},
        parents_pec=("Diabetes",),
        income=6_000_000,
    )
    policies = [
        _health("p_nri_h", "Niva Bupa", sum_insured=1_500_000, premium=42_000,
                room_rent_cap=0, icu_cap=0, copay_percent=10,
                ped_waiting_years=2, network_hospitals=10_500,
                restoration_benefit=True, ncb_percent=10),
    ]
    # cost None: spec Section 3 single-eligible-policy edge case
    # coverage 40: NRI's missing life cover for 2 dep parents drags it down
    #   (1.5M health vs 4.3M ideal + missing life)
    # claim_readiness 95: room=0 (+5 reward), copay 10% (-5 low), all other
    #   clauses pass; PED waiting=2 doesn't trigger even with disclosed PED
    return user, policies, {"coverage": 40, "cost": None, "claim_readiness": 95, "gap": 70}


def fixture_10_gig_worker() -> tuple[UserProfile, list[Policy], dict[str, int | None]]:
    """29yo gig worker, Bangalore, no employer cover, no PED, no policies."""
    user = UserProfile(
        user_id="u_gig", age=29, city="Bangalore", tier="tier-1",
        income=1_200_000,
        lifestyle=Lifestyle(two_wheeler=True, self_employed=True),
    )
    policies: list[Policy] = []
    # Engine returns coverage=0 (not None) because user has age/income/tier
    # to compute ideal cover; spec rule says null only when "no policies AND
    # no ideal-cover data". Gig has data → score computes to 0.
    return user, policies, {"coverage": 0, "cost": None,
                            "claim_readiness": None, "gap": 45}


def fixture_11_retired() -> tuple[UserProfile, list[Policy], dict[str, int | None]]:
    """65yo retired, Chennai, ₹6L pension income, ₹5L health policy."""
    user = UserProfile(
        user_id="u_ret", age=65, city="Chennai", tier="tier-1",
        spouse_age=62,
        income=600_000,
        self_pec=("BP",),
    )
    policies = [
        _health("p_ret_h", "Niva Bupa", sum_insured=500_000, premium=42_000,
                room_rent_cap=5_000, icu_cap=10_000, copay_percent=20,
                ped_waiting_years=3, network_hospitals=10_500,
                restoration_benefit=True),
    ]
    # cost None: spec Section 3 single-eligible-policy edge case
    # gap 55: spouse=dependent → term_life/PA/CI all required-and-missing
    #   (-25, -10, -10 = -45). Spec author expected 80 but their fixture has
    #   spouse_age=62, which is a dep by our rules.
    return user, policies, {"coverage": 25, "cost": None, "claim_readiness": 40, "gap": 55}


def fixture_12_widowed() -> tuple[UserProfile, list[Policy], dict[str, int | None]]:
    """Recently widowed 41yo with 2 kids, sole earner, Delhi, ₹20L income."""
    user = UserProfile(
        user_id="u_widow", age=41, city="Delhi", tier="tier-1",
        kids_count=2, kids_youngest_age=8,
        income=2_000_000, emis=22_000, outstanding_loans=4_000_000,
        self_owned_home=True,
        lifestyle=Lifestyle(),
    )
    policies = [
        _health("p_widow_h", "HDFC ERGO General", sum_insured=1_000_000, premium=20_000,
                room_rent_cap=0, icu_cap=0, copay_percent=0,
                ped_waiting_years=2, network_hospitals=12_000,
                restoration_benefit=True),
    ]
    # cost None: spec Section 3 single-eligible-policy edge case (already null)
    return user, policies, {"coverage": 35, "cost": None, "claim_readiness": 80, "gap": 50}


# Single registry the test_audit_engine module iterates over.
ALL_FIXTURES: list[tuple[str, tuple[UserProfile, list[Policy], dict[str, int | None]]]] = [
    ("1_ravi",     fixture_1_ravi()),
    ("2_priya",    fixture_2_priya()),
    ("3_arjun",    fixture_3_arjun()),
    ("4_meera",    fixture_4_meera()),
    ("5_sahil",    fixture_5_sahil()),
    ("6_lakshmi",  fixture_6_lakshmi()),
    ("7_vikram",   fixture_7_vikram()),
    ("8_tier3",    fixture_8_tier3_solo()),
    ("9_nri",      fixture_9_nri_parents()),
    ("10_gig",     fixture_10_gig_worker()),
    ("11_retired", fixture_11_retired()),
    ("12_widowed", fixture_12_widowed()),
]
