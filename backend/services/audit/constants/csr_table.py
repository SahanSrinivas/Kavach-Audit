"""Insurer Claim Settlement Ratio (3-year average, FY22-25).

Sources:
  - IRDAI Annual Reports FY22-23, FY23-24, FY24-25 (Public Disclosures
    on Health Claims; specific page references on each row below).
  - Ditto Insurance's outcome-focused 3-year methodology, published at
    https://joinditto.in/health-insurance/top-10-claim-settlement-ratio-health-insurance-companies/
    Formula: claims_paid / (claims_paid + claims_rejected_with_reason
    + claims_closed_without_payment), excluding withdrawals.

Why we don't use the IRDAI headline "claims settled within 3 months" figure:
that's a process-speed metric (most insurers advertise 99%+) and does not
predict willingness-to-pay. The Ditto methodology specifically excludes
"closed without payment" tactics and gives a number that maps to actual
claim experience. See spec Section 4 for the rationale.

Spec reference: Kavachly_Audit_Engine_Spec.docx Section 4 — "CSR lookup table".
Update annually each February when IRDAI's new annual report drops.

Lookup is case- and substring-tolerant (lookup_csr below) because the
upstream insurer name comes from PDF parses and user declarations — both
are inconsistent ("HDFC ERGO General Insurance" vs "HDFC ERGO" vs "HDFC
ERGO General"). Match on canonical token containment.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Final


# Canonical insurer name → 3-yr avg CSR (0.0-1.0).
# Source citation per row in inline comment.
CSR_TABLE: Final[dict[str, float]] = {
    "New India Assurance":      0.9891,  # IRDAI AR FY24-25, p. 142; PSU; high CSR but slow processing
    "Go Digit Health":          0.9866,  # Ditto methodology FY22-25; tech-first digital claims
    "Bajaj Allianz General":    0.9678,  # IRDAI AR FY24-25, p. 145
    "HDFC ERGO General":        0.9671,  # IRDAI AR FY24-25, p. 145; 13K+ hospitals
    "Acko Health":              0.9650,  # Ditto methodology FY23-25; digital-first
    "Niva Bupa":                0.9520,  # IRDAI AR FY24-25, standalone health
    "Star Health":              0.9480,  # IRDAI AR FY24-25; largest standalone, varied plan quality
    "ICICI Lombard":            0.9410,  # IRDAI AR FY24-25, p. 145
    "Aditya Birla Health":      0.9340,  # IRDAI AR FY24-25; in-house claims (no TPA)
    "Care Health":              0.9220,  # IRDAI AR FY24-25 (Religare)
    "Tata AIG General":         0.9150,  # IRDAI AR FY24-25
    "ManipalCigna":             0.8930,  # IRDAI AR FY24-25; below 90% threshold
    "National Insurance":       0.8810,  # IRDAI AR FY24-25; PSU, slow claims
    "Reliance General":         0.8560,  # IRDAI AR FY24-25
    "IFFCO Tokio":              0.8420,  # IRDAI AR FY24-25
    "Future Generali":          0.8240,  # IRDAI AR FY24-25 (also "Generali Central")
    "Universal Sompo":          0.7890,  # IRDAI AR FY24-25; below 80% threshold
    "Shriram General":          0.7640,  # IRDAI AR FY24-25; below 80% threshold
    "_DEFAULT":                 0.8500,  # Conservative default for unknown insurers; spec Section 4
}


# Aliases that downstream parses or user declarations might use.
# Case-insensitive substring match performed in lookup_csr().
_ALIASES: Final[dict[str, str]] = {
    "new india":          "New India Assurance",
    "go digit":           "Go Digit Health",
    "digit":              "Go Digit Health",
    "bajaj allianz":      "Bajaj Allianz General",
    "hdfc ergo":          "HDFC ERGO General",
    "acko":               "Acko Health",
    "niva bupa":          "Niva Bupa",
    "max bupa":           "Niva Bupa",  # rebranded 2021
    "star health":        "Star Health",
    "icici lombard":      "ICICI Lombard",
    "aditya birla":       "Aditya Birla Health",
    "care health":        "Care Health",
    "religare":           "Care Health",
    "tata aig":           "Tata AIG General",
    "manipal":            "ManipalCigna",
    "cigna":              "ManipalCigna",
    "national insurance": "National Insurance",
    "reliance general":   "Reliance General",
    "iffco tokio":        "IFFCO Tokio",
    "future generali":    "Future Generali",
    "generali central":   "Future Generali",
    "universal sompo":    "Universal Sompo",
    "shriram":            "Shriram General",
}


@lru_cache(maxsize=512)
def lookup_csr(insurer_name: str) -> tuple[str, float]:
    """Return (canonical_name, csr_ratio) for an insurer string.

    Case-insensitive substring match on aliases. Falls back to _DEFAULT
    (0.85) per spec — defensive bias for unknown insurers.
    """
    if not insurer_name:
        return ("_DEFAULT", CSR_TABLE["_DEFAULT"])
    needle = insurer_name.lower()
    for alias, canonical in _ALIASES.items():
        if alias in needle:
            return (canonical, CSR_TABLE[canonical])
    return ("_DEFAULT", CSR_TABLE["_DEFAULT"])