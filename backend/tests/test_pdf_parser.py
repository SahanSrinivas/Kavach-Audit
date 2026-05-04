"""Unit tests for the PDF parser (no Claude API calls).

Covers:
  - validate_and_normalize: schema validation, type coercion, sanity checks
  - insurer canonicalizer: aliases, fuzzy match, unknown
  - canonical vocabulary: alignment with engine's CSR_TABLE
  - error path: Claude returns {error: ...}
  - prompt builder: shape + key invariants
"""
from __future__ import annotations

import pytest

from services.audit.constants.csr_table import CSR_TABLE
from services.audit.constants.deduction_rules import DISCLOSED_PED_KEYWORDS
from services.parser.canonical_vocabulary import (
    CANONICAL_EXCLUSIONS,
    CANONICAL_INSURER_NAMES,
    EXCLUSION_PHRASE_MAP,
    INSURER_ALIASES,
    UNKNOWN_INSURER,
)
from services.parser.insurer_canonicalizer import canonicalize_insurer
from services.parser.prompt_builder import build_parsing_prompt
from services.parser.response_validator import (
    InvalidParseResponseError,
    validate_and_normalize,
)


# ==========================================================================
# Canonical vocabulary alignment with engine
# ==========================================================================

def test_every_canonical_insurer_is_a_csr_table_key() -> None:
    """If a canonical name doesn't match a CSR_TABLE key, the audit
    silently degrades to _DEFAULT for that insurer. Must catch in CI.
    """
    csr_keys = set(CSR_TABLE.keys()) - {"_DEFAULT"}
    missing = set(CANONICAL_INSURER_NAMES) - csr_keys
    assert not missing, f"canonical insurers missing from CSR_TABLE: {sorted(missing)}"


def test_every_alias_resolves_to_a_canonical_name() -> None:
    targets = set(INSURER_ALIASES.values())
    invalid = targets - set(CANONICAL_INSURER_NAMES)
    assert not invalid, f"aliases targeting non-canonical names: {sorted(invalid)}"


def test_every_exclusion_phrase_maps_to_canonical() -> None:
    targets = set(EXCLUSION_PHRASE_MAP.values())
    invalid = targets - set(CANONICAL_EXCLUSIONS)
    assert not invalid, f"phrase map points to non-canonical: {sorted(invalid)}"


def test_canonical_exclusions_cover_engine_disclosed_ped_keywords() -> None:
    """Every keyword the engine substring-matches in DISCLOSED_PED_KEYWORDS
    must have a corresponding canonical category in the parser's vocab.
    Without this, the planned TODO(canonical-exclusion-match) engine swap
    to set-intersection would silently miss matches.

    Each engine keyword maps to one canonical category here. If a future
    keyword is added to the engine, this test fails until the canonical
    list is extended.
    """
    engine_kw_to_canonical = {
        "diabetes":        "diabetes",
        "bp":              "hypertension",
        "blood pressure":  "hypertension",
        "hypertension":    "hypertension",
        "heart":           "cardiac",
        "cardiac":         "cardiac",
        "cancer":          "cancer",
        "kidney":          "kidney",
        "liver":           "liver",
        "thyroid":         "thyroid",
        "asthma":          "asthma",
        "copd":            "copd",
        "stroke":          "stroke",
    }
    # Sanity: the lookup table covers exactly what the engine knows.
    assert set(engine_kw_to_canonical.keys()) == set(DISCLOSED_PED_KEYWORDS), (
        f"engine keywords drifted from test mapping: "
        f"engine={sorted(DISCLOSED_PED_KEYWORDS)}, "
        f"test={sorted(engine_kw_to_canonical.keys())}"
    )
    for kw, canon in engine_kw_to_canonical.items():
        assert canon in CANONICAL_EXCLUSIONS, (
            f"engine keyword '{kw}' would not canonicalize: missing '{canon}' "
            f"in CANONICAL_EXCLUSIONS"
        )


# ==========================================================================
# Insurer canonicalizer
# ==========================================================================

@pytest.mark.parametrize("raw,expected", [
    ("HDFC ERGO General Insurance Co. Ltd.", "HDFC ERGO General"),
    ("HDFC Ergo my:health Suraksha Gold",    "HDFC ERGO General"),
    ("Optima Restore (HDFC ERGO)",           "HDFC ERGO General"),
    ("Star Health and Allied Insurance",     "Star Health"),
    ("Star Comprehensive Insurance Policy",  "Star Health"),
    ("Niva Bupa Health Insurance Co. Ltd",   "Niva Bupa"),
    ("Max Bupa Health Insurance",            "Niva Bupa"),  # rebrand
    ("ReAssure 2.0 from Niva Bupa",          "Niva Bupa"),
    ("ICICI Lombard General Insurance",      "ICICI Lombard"),
    ("ICICI Lombard Complete Health",        "ICICI Lombard"),
    ("Care Health Insurance",                "Care Health"),
    ("Religare Health Insurance",            "Care Health"),  # legacy
    ("Tata AIG MediCare Premier",            "Tata AIG General"),
    ("Bajaj Allianz Health Care Supreme",    "Bajaj Allianz General"),
    ("Aditya Birla Activ Health Platinum",   "Aditya Birla Health"),
    ("ABHI",                                  "Aditya Birla Health"),
    ("Acko Health Insurance",                "Acko Health"),
    ("ManipalCigna ProHealth",               "ManipalCigna"),
    ("Manipal Cigna ProHealth Plus",         "ManipalCigna"),
    ("Cigna TTK ProHealth",                  "ManipalCigna"),
    ("Go Digit General Insurance",           "Go Digit Health"),
    ("Generali Central Insurance Company",   "Future Generali"),
    ("New India Assurance Co. Ltd.",         "New India Assurance"),
    ("National Insurance Co. Ltd.",          "National Insurance"),
    ("Reliance General Insurance",           "Reliance General"),
    ("IFFCO Tokio General Insurance",        "IFFCO Tokio"),
    ("Universal Sompo General Insurance",    "Universal Sompo"),
    ("Shriram General Insurance Co. Ltd.",   "Shriram General"),
])
def test_canonicalizer_substring_matches(raw: str, expected: str) -> None:
    assert canonicalize_insurer(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    # Fuzzy-match cases — single-letter typos that the 0.85 cutoff catches.
    # Bigger typos ("HDFC Errgo") fall back to UNKNOWN — better than
    # mismatching to an unrelated insurer.
    ("Niva Bupaa",         "Niva Bupa"),
    ("Star Healtth",       "Star Health"),
    ("ICICI Lombarrd",     "ICICI Lombard"),
    ("ManipalCgina",       "ManipalCigna"),
    ("Acco Health",        "Acko Health"),
])
def test_canonicalizer_fuzzy_matches(raw: str, expected: str) -> None:
    assert canonicalize_insurer(raw) == expected


@pytest.mark.parametrize("raw", [
    "Some Random Insurance Pvt Ltd",
    "Made Up Insurer Co.",
    "",
    "   ",
])
def test_canonicalizer_unknown(raw: str) -> None:
    assert canonicalize_insurer(raw) == UNKNOWN_INSURER


# ==========================================================================
# validate_and_normalize — happy path + type coercion
# ==========================================================================

def _minimal_response() -> dict:
    """A minimal-but-valid Claude response."""
    return {
        "insurer_name": "HDFC ERGO General",
        "insurer_name_raw": "HDFC ERGO General Insurance Co. Ltd.",
        "policy_type": "health_family_floater",
        "policy_number": "HE-OR-23-9087421",
        "sum_insured": 1500000,
        "premium_annual": 22400,
        "premium_frequency": "annual",
        "policy_start_date": "2024-04-01",
        "policy_end_date": "2025-03-31",
        "covered_members": [
            {"name": None, "relationship": "self", "age": 34, "gender": "female"},
        ],
        "is_employer_group": False,
        "parsed_fields": {
            "room_rent_cap": {"type": "no_cap", "value": None, "raw_text": "Actuals"},
            "icu_cap": {"type": "no_cap", "value": None, "raw_text": "Actuals"},
            "copay_percent": 0,
            "copay_applies_to": "none",
            "ped_waiting_months": 24,
            "specific_disease_waiting": [{"category": "cataract", "months": 24}],
            "initial_waiting_period_days": 30,
            "permanent_exclusions": ["cosmetic surgery", "self-inflicted injuries"],
            "permanent_exclusions_canonical": [],
            "network_hospital_count": 12000,
            "restoration_benefit": {
                "available": True, "type": "once_per_year", "applies_to": "different_illness",
            },
            "ncb_structure": {"max_percent": 100, "increment_per_year": 25},
            "sub_limits": [],
            "ambulance_cap": 2000,
            "day_care_procedures_count": 600,
        },
        "confidence": {"overall": "high", "fields_with_low_confidence": [], "warnings": []},
    }


def test_validate_minimal_response() -> None:
    out = validate_and_normalize(_minimal_response())
    assert out.insurer_name == "HDFC ERGO General"
    assert out.sum_insured == 1500000
    assert out.confidence.overall == "high"


def test_validate_coerces_string_integers() -> None:
    """Claude very occasionally quotes integers despite temperature=0."""
    raw = _minimal_response()
    raw["sum_insured"] = "1500000"
    raw["premium_annual"] = "22,400"
    out = validate_and_normalize(raw)
    assert out.sum_insured == 1500000
    assert out.premium_annual == 22400


def test_validate_coerces_lakh_format() -> None:
    raw = _minimal_response()
    raw["sum_insured"] = "Rs. 15 Lakhs"
    out = validate_and_normalize(raw)
    assert out.sum_insured == 1_500_000


def test_validate_coerces_crore_format() -> None:
    raw = _minimal_response()
    raw["sum_insured"] = "₹1.5 Cr"
    out = validate_and_normalize(raw)
    assert out.sum_insured == 15_000_000


def test_validate_canonicalizes_server_side() -> None:
    """Defense in depth: even if Claude returns a non-canonical insurer
    name, the server re-canonicalizes from insurer_name_raw."""
    raw = _minimal_response()
    raw["insurer_name"] = "HDFC Ergo"  # not canonical
    raw["insurer_name_raw"] = "HDFC ERGO General Insurance Co. Ltd."
    out = validate_and_normalize(raw)
    assert out.insurer_name == "HDFC ERGO General"


def test_validate_derives_canonical_exclusions_server_side() -> None:
    """Server-side derivation produces canonical names from verbatim list."""
    raw = _minimal_response()
    raw["parsed_fields"]["permanent_exclusions"] = [
        "Type 2 diabetes mellitus and complications thereof",
        "Hypertension management",
        "Cosmetic surgery",
    ]
    out = validate_and_normalize(raw)
    canon = out.parsed_fields.permanent_exclusions_canonical
    assert "diabetes" in canon
    assert "hypertension" in canon
    assert "cosmetic" in canon


# Issue 2 regression — surface forms from the real eBID smoke-test PDF
# that previously failed to canonicalize. Each pair is one of the spec's
# expected mappings the user listed in the v0.4 review.
@pytest.mark.parametrize("verbatim,expected_canonical", [
    ("Sterility and Infertility",                          "infertility"),
    ("In-vitro fertilisation (IVF)",                       "infertility"),
    ("Cosmetic or plastic Surgery",                        "cosmetic"),
    ("Aesthetic and cosmetic treatments",                  "cosmetic"),
    ("War or similar situations",                          "war"),
    ("Nuclear, chemical or biological weapons",            "war"),
    ("Civil war, rebellion or insurrection",               "war"),
    ("Intentional self-injury or attempted suicide",       "self_harm"),
    ("Self-inflicted injury",                              "self_harm"),
    ("Hazardous or Adventure sports",                      "hazardous_sports"),
    ("Participation in adventure sport",                   "hazardous_sports"),
    ("Treatment for Alcoholism, drug or substance abuse",  "substance_abuse"),
    ("Drug addiction or narcotic use",                     "substance_abuse"),
    ("Obesity/Weight Control treatment",                   "obesity"),
    ("Maternity expenses",                                 "maternity"),
    # Existing categories — confirm they still fire after vocab expansion
    ("Type 1 diabetes mellitus",                           "diabetes"),
    ("HTN management",                                     "hypertension"),
    ("Coronary artery disease (CAD)",                      "cardiac"),
    ("Carcinoma in situ",                                  "cancer"),
    ("Chronic kidney disease (CKD)",                       "kidney"),
    ("Hepatitis B and complications",                      "liver"),
    ("Hypothyroidism management",                          "thyroid"),
    ("Bronchial asthma",                                   "asthma"),
    ("Chronic Obstructive Pulmonary Disease",              "copd"),
    ("Stroke / Cerebrovascular accident",                  "stroke"),
    ("Psychiatric and mental disorders",                   "mental_health"),
    ("HIV/AIDS related conditions",                        "hiv_aids"),
])
def test_canonicalize_exclusions_covers_spec_surface_forms(
    verbatim: str, expected_canonical: str,
) -> None:
    from services.parser.response_validator import canonicalize_exclusions
    result = canonicalize_exclusions([verbatim])
    assert expected_canonical in result, (
        f"verbatim {verbatim!r} did not canonicalize to {expected_canonical!r}; "
        f"got {result}"
    )


def test_canonicalize_does_not_invent_categories_for_unrelated_text() -> None:
    """Issue 2's hallucination guard: 'mental_health' must NOT appear in
    canonicals unless a verbatim entry actually mentions a mental-health
    keyword. The smoke test surfaced Claude inventing this category from
    thin air. Server-side derivation is purely substring-driven —
    impossible to invent."""
    from services.parser.response_validator import canonicalize_exclusions
    verbatim_no_mental_health = [
        "Sterility and Infertility",
        "Cosmetic or plastic Surgery",
        "War or similar situations",
        "Hazardous or Adventure sports",
        "Treatment for Alcoholism",
        "Maternity expenses",
        "Obesity / Weight Control",
    ]
    result = canonicalize_exclusions(verbatim_no_mental_health)
    assert "mental_health" not in result, (
        f"derived 'mental_health' from input that mentions no mental-health "
        f"keyword: {result}"
    )


def test_canonicalize_each_verbatim_contributes_at_most_one_category() -> None:
    """A single verbatim entry shouldn't double-count across categories."""
    from services.parser.response_validator import canonicalize_exclusions
    # "Treatment for Alcoholism, drug or substance abuse" mentions
    # alcoholism + substance + drug — all map to substance_abuse. Should
    # appear once in the result.
    result = canonicalize_exclusions(["Treatment for Alcoholism, drug or substance abuse"])
    assert result.count("substance_abuse") == 1
    assert len(result) == 1


def test_canonicalize_dedupes_across_multiple_verbatim_entries() -> None:
    from services.parser.response_validator import canonicalize_exclusions
    result = canonicalize_exclusions([
        "Type 1 diabetes",
        "Type 2 diabetes mellitus",
        "DM with complications",
    ])
    assert result == ["diabetes"]  # all three map to diabetes; deduped


# Issue 1 regression — null preservation for sum_insured / premium_annual

def test_validate_preserves_null_sum_insured() -> None:
    """Wording-only PDF (no schedule): Claude returns null for sum_insured.
    Validator must NOT coerce to 0 — that would silently produce a 'zero
    coverage' audit. Engine handles null by skipping the policy."""
    raw = _minimal_response()
    raw["sum_insured"] = None
    raw["premium_annual"] = None
    out = validate_and_normalize(raw)
    assert out.sum_insured is None
    assert out.premium_annual is None
    # Validator surfaces this as a low-confidence warning
    warning_text = " ".join(out.confidence.warnings).lower()
    assert "sum_insured" in warning_text
    assert "wording" in warning_text or "schedule" in warning_text


def test_validate_zero_sum_insured_still_warns_separately_from_null() -> None:
    """Genuine zero (extraction error) is distinct from null (wording PDF)."""
    raw = _minimal_response()
    raw["sum_insured"] = 0
    out = validate_and_normalize(raw)
    assert out.sum_insured == 0
    assert any("zero or negative" in w for w in out.confidence.warnings)


def test_to_engine_shape_handles_null_sum_insured() -> None:
    """Adapter must not crash on null SI. Percentage-of-SI calcs become
    None (engine treats as 'no rule fires')."""
    from services.parser.response_validator import to_engine_shape
    raw = _minimal_response()
    raw["sum_insured"] = None
    raw["premium_annual"] = None
    raw["parsed_fields"]["room_rent_cap"] = {
        "type": "percentage_of_si", "value": 100, "raw_text": "1% of SI",
    }
    raw["parsed_fields"]["sub_limits"] = [
        {"category": "knee", "limit_amount": None,
         "limit_percent_of_si": 2000, "raw_text": "20% of SI"},
    ]
    parsed = validate_and_normalize(raw)
    flat = to_engine_shape(parsed)
    # No SI → no percentage-of-SI math → engine sees None ("no rule fires")
    assert flat["room_rent_cap"] is None
    # Percent-driven sublimit cap can't be derived without SI → 0
    assert flat["sub_limits"][0]["cap"] == 0


def test_validate_always_overwrites_claude_supplied_canonical() -> None:
    """Issue 2 fix: server-side derivation is the single source of truth.
    Even if Claude returns a canonical list (it shouldn't, post-prompt-fix),
    the server overwrites with its own deterministic derivation. This
    prevents Claude hallucinations like the smoke-test 'mental_health'
    that wasn't in any verbatim entry.
    """
    raw = _minimal_response()
    raw["parsed_fields"]["permanent_exclusions"] = ["DM Type 2"]
    raw["parsed_fields"]["permanent_exclusions_canonical"] = ["mental_health"]  # hallucinated
    out = validate_and_normalize(raw)
    # Server overwrites: derived from verbatim, not from Claude's claim
    assert out.parsed_fields.permanent_exclusions_canonical == ["diabetes"]
    assert "mental_health" not in out.parsed_fields.permanent_exclusions_canonical


# ==========================================================================
# validate_and_normalize — sanity checks
# ==========================================================================

def test_sanity_premium_exceeds_sum_insured_warns() -> None:
    raw = _minimal_response()
    raw["sum_insured"] = 100_000
    raw["premium_annual"] = 200_000
    out = validate_and_normalize(raw)
    assert any("exceeds sum_insured" in w for w in out.confidence.warnings)
    assert "premium_annual" in out.confidence.fields_with_low_confidence


def test_sanity_end_before_start_warns() -> None:
    raw = _minimal_response()
    raw["policy_start_date"] = "2024-04-01"
    raw["policy_end_date"] = "2023-04-01"
    out = validate_and_normalize(raw)
    assert any("not after" in w for w in out.confidence.warnings)
    assert "policy_end_date" in out.confidence.fields_with_low_confidence


def test_sanity_zero_sum_insured_warns() -> None:
    raw = _minimal_response()
    raw["sum_insured"] = 0
    out = validate_and_normalize(raw)
    assert any("sum_insured" in w for w in out.confidence.warnings)


def test_sanity_zero_premium_warns() -> None:
    raw = _minimal_response()
    raw["premium_annual"] = 0
    out = validate_and_normalize(raw)
    assert any("premium_annual" in w for w in out.confidence.warnings)


def test_sanity_malformed_iso_date_warns() -> None:
    raw = _minimal_response()
    raw["policy_start_date"] = "01-04-2024"  # not ISO
    raw["policy_end_date"] = "31-03-2025"
    out = validate_and_normalize(raw)
    assert any("ISO-8601" in w for w in out.confidence.warnings)


# ==========================================================================
# Error response handling
# ==========================================================================

def test_claude_returned_error_raises() -> None:
    raw = {"error": "not_an_indian_insurance_policy", "details": "Looks like a Visa application"}
    with pytest.raises(InvalidParseResponseError) as exc:
        validate_and_normalize(raw)
    assert "not_an_indian_insurance_policy" in str(exc.value)


def test_unreadable_document_raises() -> None:
    raw = {"error": "document_unreadable", "details": "no OCR layer"}
    with pytest.raises(InvalidParseResponseError) as exc:
        validate_and_normalize(raw)
    assert "document_unreadable" in str(exc.value)


def test_completely_invalid_response_raises() -> None:
    """Missing required fields → ValidationError → InvalidParseResponseError."""
    with pytest.raises(InvalidParseResponseError):
        validate_and_normalize({"insurer_name": "X"})  # missing sum_insured, premium, etc.


def test_non_dict_response_raises() -> None:
    with pytest.raises(InvalidParseResponseError):
        validate_and_normalize([1, 2, 3])  # type: ignore[arg-type]


# ==========================================================================
# Null tolerance — regression for the smoke-test bug
# ==========================================================================
# Bug: Claude returned response objects with nested fields set to null,
# Pydantic schema rejected them with schema_validation:N_errors. Fix:
# every nested type/enum/leaf field accepts null with a sensible default.

def _all_nulls_response() -> dict:
    """Every nested object exists but every leaf inside is null. The shape
    the smoke-test bug surfaced. Should validate, not raise."""
    return {
        "insurer_name": "HDFC ERGO General",
        "insurer_name_raw": "HDFC ERGO General Insurance",
        "policy_type": "term_life",  # required; can't be null
        "policy_number": None,
        "sum_insured": 10_000_000,
        "premium_annual": 14_500,
        "premium_frequency": None,           # ← was rejected
        "policy_start_date": None,
        "policy_end_date": None,
        "covered_members": [],
        "is_employer_group": None,           # ← was rejected
        "parsed_fields": {
            "room_rent_cap":   {"type": None, "value": None, "raw_text": None},   # ← was rejected
            "icu_cap":         {"type": None, "value": None, "raw_text": None},   # ← was rejected
            "copay_percent": None,                                                # ← was rejected
            "copay_applies_to": None,                                             # ← was rejected
            "ped_waiting_months": None,
            "specific_disease_waiting": [],
            "initial_waiting_period_days": None,
            "permanent_exclusions": [],
            "permanent_exclusions_canonical": [],
            "network_hospital_count": None,
            "restoration_benefit": {"available": None, "type": None, "applies_to": None},  # ← was rejected
            "ncb_structure": {"max_percent": None, "increment_per_year": None},   # ← was rejected
            "sub_limits": [],
            "ambulance_cap": None,
            "day_care_procedures_count": None,
        },
        "confidence": {
            "overall": None,                                                      # ← was rejected
            "fields_with_low_confidence": [],
            "warnings": [],
        },
    }


def test_validate_accepts_all_nested_leaves_null() -> None:
    """Every optional nested field set to null → must validate.
    This is the regression test for the smoke-test schema_validation bug.
    """
    out = validate_and_normalize(_all_nulls_response())
    # Coerced safe defaults preserve engine semantics:
    assert out.is_employer_group is False
    assert out.premium_frequency == "annual"
    assert out.parsed_fields.copay_percent == 0
    assert out.parsed_fields.copay_applies_to is None
    assert out.parsed_fields.restoration_benefit is not None
    assert out.parsed_fields.restoration_benefit.available is False
    assert out.parsed_fields.ncb_structure is not None
    assert out.parsed_fields.ncb_structure.max_percent == 0
    assert out.confidence.overall == "medium"


def test_validate_accepts_whole_nested_objects_as_null() -> None:
    """Preferred Claude shape: whole nested clause object emitted as null
    when the clause is absent from the document."""
    raw = _minimal_response()
    raw["parsed_fields"]["room_rent_cap"] = None
    raw["parsed_fields"]["icu_cap"] = None
    raw["parsed_fields"]["restoration_benefit"] = None
    raw["parsed_fields"]["ncb_structure"] = None
    out = validate_and_normalize(raw)
    assert out.parsed_fields.room_rent_cap is None
    assert out.parsed_fields.icu_cap is None
    assert out.parsed_fields.restoration_benefit is None
    assert out.parsed_fields.ncb_structure is None


def test_validate_accepts_partial_nulls_inside_nested_objects() -> None:
    """Realistic shape: clause exists but some leaves couldn't be extracted."""
    raw = _minimal_response()
    raw["parsed_fields"]["room_rent_cap"] = {
        "type": "fixed_amount", "value": 5000, "raw_text": None,  # missing quote
    }
    raw["parsed_fields"]["restoration_benefit"] = {
        "available": True, "type": None, "applies_to": None,  # known available, unknown shape
    }
    raw["parsed_fields"]["ncb_structure"] = {
        "max_percent": 50, "increment_per_year": None,  # known max, unknown step
    }
    out = validate_and_normalize(raw)
    assert out.parsed_fields.room_rent_cap is not None
    assert out.parsed_fields.room_rent_cap.value == 5000
    assert out.parsed_fields.room_rent_cap.raw_text == ""  # null → ""
    assert out.parsed_fields.restoration_benefit is not None
    assert out.parsed_fields.restoration_benefit.available is True
    assert out.parsed_fields.ncb_structure is not None
    assert out.parsed_fields.ncb_structure.increment_per_year == 0


def test_validate_drops_sublimit_with_null_category() -> None:
    """Sub-limits without a category are unusable; filter them out."""
    raw = _minimal_response()
    raw["parsed_fields"]["sub_limits"] = [
        {"category": "cataract", "limit_amount": 40_000, "raw_text": "Rs. 40,000"},
        {"category": None, "limit_amount": 50_000, "raw_text": "junk"},  # dropped
        {"limit_amount": 60_000},  # missing category — dropped
    ]
    out = validate_and_normalize(raw)
    assert len(out.parsed_fields.sub_limits) == 1
    assert out.parsed_fields.sub_limits[0].category == "cataract"


def test_validate_drops_disease_waiting_with_missing_fields() -> None:
    raw = _minimal_response()
    raw["parsed_fields"]["specific_disease_waiting"] = [
        {"category": "cataract", "months": 24},
        {"category": None, "months": 24},        # dropped
        {"category": "hernia", "months": None},  # dropped
    ]
    out = validate_and_normalize(raw)
    assert len(out.parsed_fields.specific_disease_waiting) == 1


def test_validate_drops_covered_member_without_relationship() -> None:
    raw = _minimal_response()
    raw["covered_members"] = [
        {"name": "A", "relationship": "self", "age": 34},
        {"name": "B", "relationship": None, "age": 8},  # dropped
        {"name": "C", "age": 10},                       # dropped
    ]
    out = validate_and_normalize(raw)
    assert len(out.covered_members) == 1


def test_validate_accepts_top_level_parsed_fields_null() -> None:
    """A renewal certificate with no clause data at all."""
    raw = _minimal_response()
    raw["parsed_fields"] = None
    out = validate_and_normalize(raw)
    assert out.parsed_fields is not None  # defaulted to empty
    assert out.parsed_fields.room_rent_cap is None


def test_validate_accepts_top_level_confidence_null() -> None:
    raw = _minimal_response()
    raw["confidence"] = None
    out = validate_and_normalize(raw)
    assert out.confidence is not None
    assert out.confidence.overall == "medium"


def test_engine_type_mapping_collapses_all_health_variants() -> None:
    """Issue 3 verification: the parser's fine-grained policy_type
    enum must collapse to the engine's coarser 'health' for every
    health-shaped variant, so the audit engine routes them all the
    same way regardless of which document the user uploaded."""
    from routers.policies_router import _engine_type_for
    assert _engine_type_for("health_individual") == "health"
    assert _engine_type_for("health_family_floater") == "health"
    assert _engine_type_for("health_senior") == "health"
    assert _engine_type_for("super_topup") == "health"
    # Spot-check the other collapses
    assert _engine_type_for("personal_accident") == "pa"
    assert _engine_type_for("critical_illness") == "ci"
    assert _engine_type_for("term_life") == "term"
    assert _engine_type_for("ulip") == "endowment"  # spec collapse
    assert _engine_type_for("motor_two_wheeler") == "motor"
    assert _engine_type_for("travel_international") == "travel"
    # Unknown → "other" (safe fallback)
    assert _engine_type_for("totally_made_up") == "other"


def test_to_engine_shape_handles_all_nulls_without_crashing() -> None:
    """End-to-end: the all-nulls Claude response flows through the
    adapter without raising. Engine-flat output has sensible defaults
    so the audit engine sees None for all rules → no rule fires."""
    parsed = validate_and_normalize(_all_nulls_response())
    # Note: term_life policy_type → no engine claim_readiness path,
    # but the adapter still produces a flat dict for storage.
    from services.parser.response_validator import to_engine_shape
    flat = to_engine_shape(parsed)
    assert flat["room_rent_cap"] is None
    assert flat["icu_cap"] is None
    assert flat["copay_percent"] == 0
    assert flat["restoration_benefit"] is False
    assert flat["restoration_unlimited"] is False
    assert flat["ncb_percent"] == 0
    assert flat["sub_limits"] == []
    assert flat["disease_specific_waiting"] == []
    assert flat["permanent_exclusions"] == []
    assert flat["network_hospitals"] is None
    assert flat["ambulance_cap"] is None
    assert flat["ped_waiting_years"] is None


# ==========================================================================
# Prompt builder
# ==========================================================================

def test_prompt_contains_all_canonical_insurers() -> None:
    prompt = build_parsing_prompt()
    for canonical in CANONICAL_INSURER_NAMES:
        assert f'"{canonical}"' in prompt, f"prompt missing canonical: {canonical}"


def test_prompt_contains_critical_safety_rules() -> None:
    prompt = build_parsing_prompt()
    assert "<critical_rules>" in prompt
    assert "NEVER hallucinate values" in prompt
    assert "Return ONLY valid JSON" in prompt
    assert "not_an_indian_insurance_policy" in prompt
    assert "document_unreadable" in prompt


def test_prompt_contains_extraction_examples() -> None:
    prompt = build_parsing_prompt()
    # The room_rent_cap examples are the most policy-specific —
    # if these vanish the parse quality drops noticeably.
    assert "1% of Sum Insured" in prompt
    assert "single private AC room" in prompt
    assert "Actuals" in prompt
