"""Single source of truth for canonical vocabulary used by the PDF parser.

This module exists so three places can never drift:
  - The Claude prompt's <canonical_insurer_names> + <exclusion_canonicalization>
    blocks (built in prompt_builder.py)
  - The InsurerCanonicalizer's hardcoded mapping (insurer_canonicalizer.py)
  - The audit engine's CSR_TABLE keys (csr_table.py) and DISCLOSED_PED_KEYWORDS
    (deduction_rules.py)

Drift here = silent breakage. The CSR lookup falls through to _DEFAULT
(0.85) when the canonical name doesn't match a CSR_TABLE key, which
quietly applies a `-15` deduction to every audit using that insurer.

Module-load assertion at the bottom verifies CANONICAL_INSURER_NAMES is a
subset of CSR_TABLE keys. The matching test in test_pdf_parser.py asserts
the same in CI.
"""
from __future__ import annotations

from typing import Final

from services.audit.constants.csr_table import CSR_TABLE


# ==========================================================================
# CANONICAL INSURER NAMES — must match CSR_TABLE keys exactly
# ==========================================================================

CANONICAL_INSURER_NAMES: Final[tuple[str, ...]] = (
    "New India Assurance",
    "Go Digit Health",
    "Bajaj Allianz General",
    "HDFC ERGO General",
    "Acko Health",
    "Niva Bupa",
    "Star Health",
    "ICICI Lombard",
    "Aditya Birla Health",
    "Care Health",
    "Tata AIG General",
    "ManipalCigna",
    "National Insurance",
    "Reliance General",
    "IFFCO Tokio",
    "Future Generali",
    "Universal Sompo",
    "Shriram General",
)


# Maps raw substring (lowercase) → canonical name.
# Order matters: the first substring match wins. Keep the more-specific
# substring (e.g., "max bupa") above the less-specific one.
INSURER_ALIASES: Final[dict[str, str]] = {
    # New India Assurance
    "new india":          "New India Assurance",
    "nia":                "New India Assurance",
    # Go Digit Health
    "go digit":           "Go Digit Health",
    "digit insurance":    "Go Digit Health",
    "digit general":      "Go Digit Health",
    # Bajaj Allianz General
    "bajaj allianz":      "Bajaj Allianz General",
    # HDFC ERGO General
    "hdfc ergo":          "HDFC ERGO General",
    "hdfc-ergo":          "HDFC ERGO General",
    "my:health":          "HDFC ERGO General",  # HDFC product line
    "optima restore":     "HDFC ERGO General",  # HDFC product line
    "optima secure":      "HDFC ERGO General",
    "health suraksha":    "HDFC ERGO General",
    # Acko Health
    "acko":               "Acko Health",
    # Niva Bupa (formerly Max Bupa)
    "niva bupa":          "Niva Bupa",
    "max bupa":           "Niva Bupa",
    "reassure":           "Niva Bupa",          # Niva product line
    # Star Health
    "star health":        "Star Health",
    "star comprehensive": "Star Health",
    "star allied":        "Star Health",
    # ICICI Lombard
    "icici lombard":      "ICICI Lombard",
    "complete health":    "ICICI Lombard",      # ICICI product line
    # Aditya Birla Health
    "aditya birla":       "Aditya Birla Health",
    "abhi":               "Aditya Birla Health",
    "activ health":       "Aditya Birla Health",
    # Care Health (formerly Religare)
    "care health":        "Care Health",
    "religare":           "Care Health",
    # Tata AIG General
    "tata aig":           "Tata AIG General",
    "medicare":           "Tata AIG General",
    # ManipalCigna
    "manipal":            "ManipalCigna",
    "manipalcigna":       "ManipalCigna",
    "cigna ttk":          "ManipalCigna",
    "cigna":              "ManipalCigna",
    # National Insurance
    "national insurance": "National Insurance",
    # Reliance General
    "reliance general":   "Reliance General",
    "reliance health":    "Reliance General",
    # IFFCO Tokio
    "iffco tokio":        "IFFCO Tokio",
    "iffco-tokio":        "IFFCO Tokio",
    # Future Generali (also Generali Central post-2023 rebrand)
    "future generali":    "Future Generali",
    "generali central":   "Future Generali",
    # Universal Sompo
    "universal sompo":    "Universal Sompo",
    # Shriram General
    "shriram":            "Shriram General",
}


# Sentinel for unmatched insurer — parser stores raw name in
# insurer_name_raw and engine falls through to CSR _DEFAULT.
UNKNOWN_INSURER: Final[str] = "_UNKNOWN"


# ==========================================================================
# CANONICAL PERMANENT EXCLUSIONS — for permanent_exclusions_canonical
# ==========================================================================
# Keep this aligned with claim_readiness.DISCLOSED_PED_KEYWORDS.
# The engine substring-matches today; a follow-up will swap to
# set-intersection on the canonical list. See TODO(canonical-exclusion-match)
# in claim_readiness.py.

CANONICAL_EXCLUSIONS: Final[tuple[str, ...]] = (
    # Disease / condition categories (12)
    "diabetes",
    "hypertension",
    "obesity",
    "cardiac",
    "cancer",
    "kidney",
    "liver",
    "thyroid",
    "asthma",
    "copd",
    "stroke",
    "mental_health",
    "hiv_aids",
    "maternity",
    "infertility",          # added 2026-05-04 from real-policy smoke test
    "ped_general",
    # Lifestyle / behavioral categories (5)
    "cosmetic",             # cosmetic / plastic surgery
    "war",                  # war / civil unrest / nuclear
    "self_harm",            # intentional self-injury, attempted suicide
    "hazardous_sports",     # adventure sports, racing
    "substance_abuse",      # alcohol, drug, narcotic abuse
)


# Phrase → canonical exclusion. Substring match (lowercase). See
# <exclusion_canonicalization> in prompt_builder.py for the same table
# Claude is taught to apply.
EXCLUSION_PHRASE_MAP: Final[dict[str, str]] = {
    # diabetes
    "diabetes":                 "diabetes",
    "diabetes mellitus":        "diabetes",
    "type 1 diabetes":          "diabetes",
    "type 2 diabetes":          "diabetes",
    "type i diabetes":          "diabetes",
    "type ii diabetes":         "diabetes",
    "dm type":                  "diabetes",
    " dm ":                     "diabetes",
    # hypertension
    "hypertension":             "hypertension",
    "high blood pressure":      "hypertension",
    "htn":                      "hypertension",
    " bp ":                     "hypertension",
    "blood pressure":           "hypertension",
    # obesity
    "obesity":                  "obesity",
    "morbid obesity":           "obesity",
    "bmi > 30":                 "obesity",
    "bmi greater than 30":      "obesity",
    # cardiac (note: bare "heart" mirrors engine's DISCLOSED_PED_KEYWORDS
    # which substring-matches "heart" across user PEC + exclusion text;
    # accepts the small false-positive risk on terms like "heartburn")
    "cardiac":                  "cardiac",
    "heart disease":            "cardiac",
    "heart":                    "cardiac",
    "coronary artery disease":  "cardiac",
    "cad":                      "cardiac",
    "myocardial infarction":    "cardiac",
    " mi ":                     "cardiac",
    # cancer
    "cancer":                   "cancer",
    "malignancy":               "cancer",
    "carcinoma":                "cancer",
    "tumor":                    "cancer",
    "neoplasm":                 "cancer",
    # kidney
    "kidney":                   "kidney",
    "renal failure":            "kidney",
    "ckd":                      "kidney",
    "esrd":                     "kidney",
    "chronic kidney":           "kidney",
    # liver
    "liver":                    "liver",
    "hepatitis":                "liver",
    "cirrhosis":                "liver",
    # thyroid
    "thyroid":                  "thyroid",
    "hypothyroidism":           "thyroid",
    "hyperthyroidism":          "thyroid",
    "thyroid disorder":         "thyroid",
    # asthma
    "asthma":                   "asthma",
    "bronchial asthma":         "asthma",
    # copd (chronic obstructive pulmonary disease)
    "copd":                                       "copd",
    "chronic obstructive pulmonary disease":      "copd",
    "emphysema":                                  "copd",
    "chronic bronchitis":                         "copd",
    # stroke (CVA / TIA padded with spaces — the validator pads exclusion
    # text with leading/trailing spaces so " cva " matches at word
    # boundaries without false-positive matches inside longer English
    # words like "negotiation" or "credentials")
    "stroke":                                     "stroke",
    "cerebrovascular accident":                   "stroke",
    " cva ":                                      "stroke",
    " tia ":                                      "stroke",
    "transient ischemic attack":                  "stroke",
    # mental_health
    "mental illness":           "mental_health",
    "psychiatric":              "mental_health",
    "depression":               "mental_health",
    "bipolar":                  "mental_health",
    "schizophrenia":            "mental_health",
    # hiv_aids
    "hiv":                      "hiv_aids",
    "aids":                     "hiv_aids",
    # maternity
    "pregnancy":                "maternity",
    "maternity":                "maternity",
    "childbirth":               "maternity",
    # infertility (separate from maternity — typically a distinct exclusion
    # clause: "Sterility and Infertility", "IVF", "ART procedures")
    "infertility":              "infertility",
    "sterility":                "infertility",
    "ivf":                      "infertility",
    "in vitro":                 "infertility",
    "art procedures":           "infertility",
    "assisted reproduction":    "infertility",
    # cosmetic / plastic surgery
    "cosmetic":                 "cosmetic",
    "plastic surgery":          "cosmetic",
    "aesthetic":                "cosmetic",
    "rhinoplasty":              "cosmetic",
    # war / hostilities
    "war":                      "war",
    "warlike":                  "war",
    "civil war":                "war",
    "rebellion":                "war",
    "insurrection":             "war",
    "nuclear":                  "war",
    "radioactive":              "war",
    # self_harm
    "self-injury":              "self_harm",
    "self injury":              "self_harm",
    "self-inflicted":           "self_harm",
    "self inflicted":           "self_harm",
    "attempted suicide":        "self_harm",
    "suicide":                  "self_harm",
    "intentional injury":       "self_harm",
    # hazardous_sports
    "hazardous":                "hazardous_sports",
    "adventure sport":          "hazardous_sports",
    "adventure sports":         "hazardous_sports",
    "racing":                   "hazardous_sports",
    "scuba":                    "hazardous_sports",
    "skydiving":                "hazardous_sports",
    "mountaineering":           "hazardous_sports",
    "bungee":                   "hazardous_sports",
    # substance_abuse
    "alcoholism":               "substance_abuse",
    "alcohol abuse":            "substance_abuse",
    "drug abuse":               "substance_abuse",
    "substance abuse":          "substance_abuse",
    "narcotic":                 "substance_abuse",
    "intoxication":             "substance_abuse",
    "addiction":                "substance_abuse",
    # ped_general (catch-all when the policy excludes a generic "pre-existing
    # condition" without naming a specific disease)
    "pre-existing":             "ped_general",
    "pre existing":             "ped_general",
    "ped":                      "ped_general",
}


# ==========================================================================
# Module-load sanity check — catch typos at import time
# ==========================================================================
# A canonical name that's not in CSR_TABLE silently degrades every audit
# for that insurer (CSR lookup falls through to _DEFAULT = 0.85). Catch
# the typo here, not in production.

_csr_keys = {k for k in CSR_TABLE.keys() if k != "_DEFAULT"}
_missing_in_csr = set(CANONICAL_INSURER_NAMES) - _csr_keys
assert not _missing_in_csr, (
    f"canonical_vocabulary.CANONICAL_INSURER_NAMES contains insurers not "
    f"present in csr_table.CSR_TABLE: {sorted(_missing_in_csr)}. "
    f"This would silently degrade audits — fix the typo."
)

# All ALIAS targets must also be canonical names.
_invalid_alias_targets = set(INSURER_ALIASES.values()) - set(CANONICAL_INSURER_NAMES)
assert not _invalid_alias_targets, (
    f"INSURER_ALIASES has targets not in CANONICAL_INSURER_NAMES: "
    f"{sorted(_invalid_alias_targets)}"
)

# All EXCLUSION_PHRASE_MAP targets must be in CANONICAL_EXCLUSIONS.
_invalid_excl_targets = set(EXCLUSION_PHRASE_MAP.values()) - set(CANONICAL_EXCLUSIONS)
assert not _invalid_excl_targets, (
    f"EXCLUSION_PHRASE_MAP has targets not in CANONICAL_EXCLUSIONS: "
    f"{sorted(_invalid_excl_targets)}"
)
