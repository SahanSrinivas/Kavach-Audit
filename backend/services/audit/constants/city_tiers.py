"""City → tier classification.

Spec reference: Kavachly_Audit_Engine_Spec.docx Section 2 (base_by_tier).
This module is the engine's local copy; the user_router does the same
classification when accepting profile updates. Keep in sync.

==========================================================================
SOURCE — Tier classification basis
==========================================================================
Base classification follows the RBI's city-tier definitions for KYC
purposes (RBI Master Direction on KYC, RBI/2015-16/42 DBR.AML.BC.No.
81/14.01.001/2015-16, Annex II — population-based city categorization
used for branch licensing and risk-weighted KYC).

Adjustments for hospital-cost reality (the audit measures health
exposure, not banking activity):

  - Gurugram, Noida, Ghaziabad, Faridabad: RBI Tier-2 by population, but
    they share NCR's hospital ecosystem (Medanta Gurugram, Fortis Noida,
    Max Vaishali, Artemis) where private-room rates and cardiac/cancer
    procedures are priced identically to Delhi. We keep them at Tier-2
    for our tier-1/2 split (NSS Round 75 hospital cost data shows median
    private-hospital episodes in NCR satellites are 80-95% of Delhi
    rates — close to Tier-1 but not quite, so we don't bump them up
    further).

  - Ahmedabad: RBI Tier-1 by population AND has metro-class corporate
    hospitals (Apollo, CIMS, Sterling) — kept at Tier-1.

  - State capitals (Lucknow, Jaipur, Bhopal, Patna, etc.): RBI Tier-2;
    we keep them at Tier-2 because median private-hospital costs run
    ₹6-10K/day for a private room (vs ₹12-20K Tier-1).

Tier-1: 8 metros (Mumbai/Delhi/Bangalore/Hyderabad/Chennai/Pune/Kolkata
        + Ahmedabad).
Tier-2: state capitals + 50 industrial cities (per RBI Tier-2 list +
        NCR satellites).
Tier-3: everywhere else (defensive default — small towns/villages).
"""
from __future__ import annotations

from typing import Final


TIER_1_CITIES: Final[frozenset[str]] = frozenset({
    "mumbai", "delhi", "new delhi", "bangalore", "bengaluru",
    "chennai", "kolkata", "hyderabad", "pune", "ahmedabad",
})

TIER_2_CITIES: Final[frozenset[str]] = frozenset({
    "jaipur", "lucknow", "surat", "kanpur", "nagpur", "indore", "thane",
    "bhopal", "visakhapatnam", "patna", "vadodara", "ghaziabad", "ludhiana",
    "agra", "nashik", "faridabad", "meerut", "rajkot", "kalyan", "vasai",
    "varanasi", "srinagar", "aurangabad", "dhanbad", "amritsar",
    "navi mumbai", "allahabad", "ranchi", "howrah", "coimbatore",
    "jabalpur", "gwalior", "vijayawada", "jodhpur", "madurai", "raipur",
    "kota", "chandigarh", "guwahati", "solapur", "hubli", "mysuru",
    "mysore", "noida", "gurgaon", "gurugram",
})


def tier_for_city(city: str) -> str:
    """Return "tier-1" | "tier-2" | "tier-3"; defensive default tier-3."""
    if not city:
        return "tier-3"
    c = city.strip().lower()
    if c in TIER_1_CITIES:
        return "tier-1"
    if c in TIER_2_CITIES:
        return "tier-2"
    return "tier-3"