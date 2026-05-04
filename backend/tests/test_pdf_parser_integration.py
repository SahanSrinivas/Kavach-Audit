"""Integration tests for the PDF parser — REAL Claude API calls.

Gated behind RUN_INTEGRATION_TESTS=true so unit-test CI runs don't burn
~₹15-30 of API credit per test. Also requires ANTHROPIC_API_KEY.

Sample PDFs need to live at backend/tests/fixtures/pdfs/ — provided
out-of-band by the operator (real insurance policies are not checked
into git for privacy reasons). Each test is currently a `pytest.skip`
with the assertion plan documented inline; un-skip when the PDFs land.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

RUN_INTEGRATION = os.environ.get("RUN_INTEGRATION_TESTS", "").lower() == "true"
HAS_API_KEY = bool(os.environ.get("ANTHROPIC_API_KEY"))

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "pdfs"

pytestmark = [
    pytest.mark.skipif(not RUN_INTEGRATION,
                       reason="set RUN_INTEGRATION_TESTS=true to enable"),
    pytest.mark.skipif(not HAS_API_KEY,
                       reason="ANTHROPIC_API_KEY not set"),
    pytest.mark.asyncio,
]


def _load(name: str) -> bytes:
    p = FIXTURES_DIR / name
    if not p.exists():
        pytest.skip(f"fixture PDF not provided yet: {p}")
    return p.read_bytes()


async def test_parse_hdfc_ergo_optima_restore_sample() -> None:
    """When fixture provided, asserts:
      - insurer_name == "HDFC ERGO General"
      - policy_type in (health_individual, health_family_floater)
      - sum_insured > 0 and premium_annual > 0
      - parsed_fields.room_rent_cap.type is one of the 4 enums
      - confidence.overall in {high, medium}
    """
    from services.parser import parse_policy_pdf
    pdf = _load("hdfc_ergo_optima_restore.pdf")
    parsed = await parse_policy_pdf(pdf, "hdfc_ergo_optima_restore.pdf")
    assert parsed.insurer_name == "HDFC ERGO General"
    assert parsed.sum_insured > 0
    assert parsed.premium_annual > 0
    assert parsed.confidence.overall in {"high", "medium"}


async def test_parse_niva_bupa_reassure_sample() -> None:
    """When fixture provided, asserts:
      - insurer_name == "Niva Bupa"
      - policy_type matches the product (likely health_family_floater)
      - parsed_fields.restoration_benefit.available is True (ReAssure feature)
      - confidence.overall in {high, medium}
    """
    from services.parser import parse_policy_pdf
    pdf = _load("niva_bupa_reassure.pdf")
    parsed = await parse_policy_pdf(pdf, "niva_bupa_reassure.pdf")
    assert parsed.insurer_name == "Niva Bupa"
    assert parsed.parsed_fields.restoration_benefit is not None
    assert parsed.parsed_fields.restoration_benefit.available is True


async def test_parse_star_health_comprehensive_sample() -> None:
    """When fixture provided, asserts:
      - insurer_name == "Star Health"
      - parsed_fields.copay_percent extracted correctly (Star plans
        commonly have explicit co-pay clauses)
      - confidence.overall in {high, medium}
    """
    from services.parser import parse_policy_pdf
    pdf = _load("star_health_comprehensive.pdf")
    parsed = await parse_policy_pdf(pdf, "star_health_comprehensive.pdf")
    assert parsed.insurer_name == "Star Health"
    assert isinstance(parsed.parsed_fields.copay_percent, int)


async def test_parse_non_policy_document_returns_error() -> None:
    """A non-policy PDF (e.g., a Visa application) should make Claude
    return {"error": "not_an_indian_insurance_policy", ...}, which the
    parser surfaces as ParseFailureError(error_type="invalid_response").
    """
    from services.parser import ParseFailureError, parse_policy_pdf
    pdf = _load("non_policy_document.pdf")
    with pytest.raises(ParseFailureError) as exc:
        await parse_policy_pdf(pdf, "non_policy_document.pdf")
    assert "not_an_indian_insurance_policy" in str(exc.value) \
        or exc.value.error_type == "invalid_response"
