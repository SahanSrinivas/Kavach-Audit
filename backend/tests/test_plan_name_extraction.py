"""Parser-level tests for the new `plan_name` / `plan_name_raw` extraction.

The wordings DB (Phase 1.5) joins user-uploaded schedules to pre-parsed
wording rules using `plan_name` as the lookup key. Without reliable
extraction, the lookup hit-rate goes to ~0% and the wordings DB is dead.
These tests pin the field's behavior at the parser boundary.
"""
from __future__ import annotations

import pytest

from services.parser.response_validator import (
    InvalidParseResponseError,
    to_engine_shape,
    validate_and_normalize,
)


def _minimal_response_with(extra: dict) -> dict:
    """Minimal valid Claude response, with extra fields layered on top."""
    base = {
        "insurer_name": "HDFC ERGO General",
        "insurer_name_raw": "HDFC ERGO General Insurance Co. Ltd.",
        "policy_type": "health_family_floater",
        "sum_insured": 1_500_000,
        "premium_annual": 22_400,
        "parsed_fields": {},
        "confidence": {"overall": "high"},
    }
    base.update(extra)
    return base


# ---------- Schema acceptance ----------

def test_validate_accepts_plan_name_string() -> None:
    """Claude returned a real product name → plan_name + plan_name_raw both stored."""
    out = validate_and_normalize(_minimal_response_with({
        "plan_name": "Optima Restore",
        "plan_name_raw": "HDFC ERGO Optima Restore Family Floater Plan",
    }))
    assert out.plan_name == "Optima Restore"
    assert out.plan_name_raw == "HDFC ERGO Optima Restore Family Floater Plan"


def test_validate_accepts_plan_name_null() -> None:
    """Wording-only PDF / generic policy → both fields null, no validation error."""
    out = validate_and_normalize(_minimal_response_with({
        "plan_name": None,
        "plan_name_raw": None,
    }))
    assert out.plan_name is None
    assert out.plan_name_raw is None


def test_validate_accepts_plan_name_omitted_entirely() -> None:
    """Old-format Claude response (pre-v0.4.2) doesn't include the field at
    all → schema defaults to None. Backward-compat with stored policies."""
    out = validate_and_normalize(_minimal_response_with({}))
    assert out.plan_name is None
    assert out.plan_name_raw is None


def test_validate_accepts_raw_only_with_null_canonical() -> None:
    """Generic 'Group Health Insurance Policy' label per prompt rule #17:
    plan_name_raw populated, plan_name null because no brand name exists."""
    out = validate_and_normalize(_minimal_response_with({
        "plan_name": None,
        "plan_name_raw": "Group Health Insurance Policy",
    }))
    assert out.plan_name is None
    assert out.plan_name_raw == "Group Health Insurance Policy"


@pytest.mark.parametrize("plan_name,plan_name_raw", [
    ("Optima Restore",     "HDFC ERGO Optima Restore Family Floater Plan"),
    ("ReAssure 2.0",       "Niva Bupa ReAssure 2.0 Individual"),
    ("Star Comprehensive", "Star Comprehensive Insurance Policy"),
    ("Health Companion",   "Niva Bupa Health Companion Variant 2"),
    ("Activ Health",       "Aditya Birla Activ Health Platinum Enhanced"),
    ("ProHealth",          "ManipalCigna ProHealth Prime Active"),
    ("Optima Secure",      "HDFC ERGO Optima Secure Plan"),
    # Life-product cases (added 2026-05-04 from real dogfood — Bug A)
    ("Click 2 Protect",    "HDFC Life Click 2 Protect Super"),
    ("iProtect Smart",     "ICICI Pru iProtect Smart Term Plan"),
    ("Assured Gain Plus",  "Exide Life Assured Gain Plus"),
])
def test_validate_round_trips_realistic_plan_names(
    plan_name: str, plan_name_raw: str,
) -> None:
    """Spot-check that realistic Indian product names survive validation
    intact — no truncation, no whitespace munging, no hidden coercion."""
    out = validate_and_normalize(_minimal_response_with({
        "plan_name": plan_name,
        "plan_name_raw": plan_name_raw,
    }))
    assert out.plan_name == plan_name
    assert out.plan_name_raw == plan_name_raw


# ---------- to_engine_shape passes plan_name through ----------

def test_to_engine_shape_includes_plan_name() -> None:
    """The flat dict that becomes policy.parsed_fields includes plan_name
    so downstream consumers (the merger, future analytics) can read it
    without going back to the rich parser_output."""
    parsed = validate_and_normalize(_minimal_response_with({
        "plan_name": "Optima Restore",
        "plan_name_raw": "HDFC ERGO Optima Restore Family Floater Plan",
    }))
    flat = to_engine_shape(parsed)
    assert flat["plan_name"] == "Optima Restore"


def test_to_engine_shape_plan_name_null_passthrough() -> None:
    """Null plan_name passes through as null — adapter must not coerce
    to empty string or some other sentinel."""
    parsed = validate_and_normalize(_minimal_response_with({"plan_name": None}))
    flat = to_engine_shape(parsed)
    assert flat["plan_name"] is None


# ---------- _derive_policy_name uses plan_name when present ----------

def test_derive_policy_name_prefers_plan_name() -> None:
    """When Claude extracted a real product name, the storage doc's
    policy_name field uses it directly — not the synthesized fallback."""
    from routers.policies_router import _derive_policy_name
    parsed = validate_and_normalize(_minimal_response_with({
        "plan_name": "Optima Restore",
        "plan_name_raw": "HDFC ERGO Optima Restore Family Floater Plan",
    }))
    assert _derive_policy_name(parsed) == "Optima Restore"


def test_derive_policy_name_falls_back_when_plan_name_null() -> None:
    """No plan_name → fall back to synthesized 'Insurer Type' string.
    Same behavior as before this feature shipped — backward-compat."""
    from routers.policies_router import _derive_policy_name
    parsed = validate_and_normalize(_minimal_response_with({"plan_name": None}))
    expected = "HDFC ERGO General Health Family Floater"
    assert _derive_policy_name(parsed) == expected


def test_derive_policy_name_does_not_use_raw_when_canonical_null() -> None:
    """If only plan_name_raw is present (generic policy w/o brand), we
    still synthesize — don't expose the raw verbatim string as the
    user-facing name. (raw is verbose; synthesized is cleaner.)"""
    from routers.policies_router import _derive_policy_name
    parsed = validate_and_normalize(_minimal_response_with({
        "plan_name": None,
        "plan_name_raw": "Group Health Insurance Policy",
    }))
    assert "Group" not in _derive_policy_name(parsed)


# ---------- Edge cases / regression guards ----------

def test_validate_does_not_inject_default_plan_name_for_non_null_other_fields() -> None:
    """A policy with copay_percent set + plan_name omitted should NOT
    accidentally pick up some default plan name (e.g., insurer_name).
    plan_name stays exactly None."""
    out = validate_and_normalize(_minimal_response_with({
        "parsed_fields": {"copay_percent": 10},
    }))
    assert out.plan_name is None


def test_validate_plan_name_with_unicode_survives() -> None:
    """Indian product names occasionally have ₹ or non-ASCII brand
    qualifiers — confirm pydantic doesn't strip or transcode."""
    out = validate_and_normalize(_minimal_response_with({
        "plan_name": "Aarogya Sanjeevani",
        "plan_name_raw": "Aarogya Sanjeevani Policy — IRDAI",
    }))
    assert out.plan_name == "Aarogya Sanjeevani"
    assert "—" in (out.plan_name_raw or "")


def test_claude_error_response_still_short_circuits_with_new_field() -> None:
    """Adding plan_name to the schema must not affect error-response
    handling — Claude's {error: ...} envelope still raises cleanly."""
    with pytest.raises(InvalidParseResponseError):
        validate_and_normalize({
            "error": "not_an_indian_insurance_policy",
            "details": "test",
        })
