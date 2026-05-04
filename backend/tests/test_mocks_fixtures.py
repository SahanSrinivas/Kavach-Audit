"""Shape-parity tests for mocks/fixtures.py.

The dashboard reads /audit/latest and renders the same React tree
regardless of USE_MOCKS. That only works if make_mock_audit emits the
same top-level keys as the real engine's AuditResult dataclass — and
links findings to real policy ids when the caller has them.

These tests are cheap and catch the most common drift: someone adds a
field to AuditResult but forgets the mock fixture, breaking dashboard
dev mode.
"""
from __future__ import annotations

from mocks.fixtures import make_mock_audit
from services.audit.types import AuditResult


def test_mock_audit_has_all_audit_result_top_level_fields() -> None:
    """Every field on the AuditResult dataclass must appear as a key in
    the mock dict — otherwise dashboard code paths that read e.g.
    audit.breakdowns crash silently under USE_MOCKS=true."""
    mock = make_mock_audit("user-x")
    expected_keys = {f.name for f in AuditResult.__dataclass_fields__.values()}
    actual_keys = set(mock.keys())
    missing = expected_keys - actual_keys
    assert not missing, f"mock fixture missing AuditResult fields: {missing}"


def test_mock_audit_links_first_finding_to_first_policy_when_ids_provided() -> None:
    """policy_ids → related_policy_id stamping enables the dashboard's
    per-policy chip and detail-view filter under USE_MOCKS=true.

    The first and third findings (room_rent_cap, ped_waiting) point at the
    user's health policy. The middle finding (term_life_gap) is a
    missing-policy finding and must stay None — it doesn't belong to any
    existing row."""
    pid = "policy-abc-123"
    mock = make_mock_audit("user-x", policy_ids=[pid])
    assert mock["findings"][0]["related_policy_id"] == pid
    assert mock["findings"][1]["related_policy_id"] is None
    assert mock["findings"][2]["related_policy_id"] == pid
    # Older callers that don't pass policy_ids still get a valid fixture
    # (just with related_policy_id=None on every finding).
    no_ids = make_mock_audit("user-x")
    assert all(f["related_policy_id"] is None for f in no_ids["findings"])
