"""Insurer Claim Settlement Ratio.

Two distinct CSR concepts in this table — different metrics, different
sources, different semantics:

HEALTH insurers (3-year average, FY22-25):
  - IRDAI Annual Reports FY22-23, FY23-24, FY24-25 (Public Disclosures
    on Health Claims; specific page references on each row below).
  - Ditto Insurance's outcome-focused 3-year methodology, published at
    https://joinditto.in/health-insurance/top-10-claim-settlement-ratio-health-insurance-companies/
    Formula: claims_paid / (claims_paid + claims_rejected_with_reason
    + claims_closed_without_payment), excluding withdrawals.

LIFE insurers (death-claim settlement, FY23-24, IRDAI Annual Report):
  - IRDAI Annual Report FY 2023-24 Statement 49 (Public Disclosures —
    Death Claims for Life Insurers).
  - This is a CLAIMS-COUNT ratio (number-of-claims-settled / total),
    NOT the value-weighted Ditto methodology. Life insurers report
    98%+ uniformly because death is a discrete, well-documented event
    with low rejection ambiguity — fundamentally different risk profile
    from health, where claim disputes are common.
  - These values are stored here for completeness / canonicalization,
    but the audit engine's CSR penalty rules in claim_readiness.py
    only fire for type='health' policies. Life policies do not consume
    these values today; they're forward-compat for a future life-claim-
    readiness scorer.

Why we don't use the IRDAI headline "claims settled within 3 months" figure
for HEALTH: that's a process-speed metric (most insurers advertise 99%+)
and does not predict willingness-to-pay. The Ditto methodology specifically
excludes "closed without payment" tactics and gives a number that maps to
actual claim experience. See spec Section 4 for the rationale.

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

    # ---- Life insurers (death-claim settlement, FY 2023-24) ----
    # Source: IRDAI Annual Report FY 2023-24, Statement 49 (Public
    # Disclosures — Death Claims for Life Insurers). Methodology is
    # claims-count, not Ditto's value-weighted formula — see module
    # docstring. Rounded to 4 decimals.
    "LIC":                      0.9874,  # IRDAI AR FY23-24 Stmt 49 row 1
    "HDFC Life":                0.9950,  # IRDAI AR FY23-24 Stmt 49
    "ICICI Prudential Life":    0.9910,  # IRDAI AR FY23-24 Stmt 49
    "Max Life":                 0.9965,  # IRDAI AR FY23-24 Stmt 49
    "Tata AIA Life":            0.9913,  # IRDAI AR FY23-24 Stmt 49
    "SBI Life":                 0.9920,  # IRDAI AR FY23-24 Stmt 49
    "Bajaj Allianz Life":       0.9910,  # IRDAI AR FY23-24 Stmt 49
    "Aditya Birla Sun Life":    0.9890,  # IRDAI AR FY23-24 Stmt 49
    "Kotak Life":               0.9882,  # IRDAI AR FY23-24 Stmt 49
    "PNB MetLife":              0.9913,  # IRDAI AR FY23-24 Stmt 49
    "Exide Life":               0.9921,  # IRDAI AR FY22-23 Stmt 49 (last
                                         # year before HDFC Life merger
                                         # Jan 2023; legacy policies still
                                         # honored — keep as separate entry)

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
    # Life insurers — keep specific aliases above generic ones (e.g.,
    # "lic" must come before any potential "icici" prefix matcher
    # so "LIC of India" doesn't false-match elsewhere).
    "lic of india":       "LIC",
    "life insurance corporation": "LIC",
    "lic ":               "LIC",       # padded to avoid matching "Public" etc.
    "hdfc life":          "HDFC Life",
    "hdfc standard life": "HDFC Life",
    "icici prudential":   "ICICI Prudential Life",
    "icici pru":          "ICICI Prudential Life",
    "max life":           "Max Life",
    "tata aia":           "Tata AIA Life",
    "sbi life":           "SBI Life",
    "bajaj allianz life": "Bajaj Allianz Life",
    "aditya birla sun life": "Aditya Birla Sun Life",
    "absli":              "Aditya Birla Sun Life",
    "birla sun life":     "Aditya Birla Sun Life",
    "kotak life":         "Kotak Life",
    "kotak mahindra life": "Kotak Life",
    "pnb metlife":        "PNB MetLife",
    "metlife":            "PNB MetLife",
    "exide life":         "Exide Life",
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