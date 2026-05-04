"""End-to-end snapshot tests for the audit engine + perf assertion.

Tolerance is ±20: the four-axis scores are intentionally directional, not
exact. Each fixture's expected values reflect the post-Step-2-review
calibration (Tier-1 room-rent <= 1%, half-weight for missing coverage
categories, 0.8x employer-group multiplier in claim_readiness, single-
eligible-policy → cost N/A per spec Section 3 edge case).
"""
from __future__ import annotations

import time

import pytest

from services.audit import generate_audit
from tests.audit_fixtures import ALL_FIXTURES


SCORE_TOLERANCE = 20


def _within(actual: int | None, expected: int | None) -> bool:
    if expected is None:
        return actual is None
    if actual is None:
        return False
    return abs(actual - expected) <= SCORE_TOLERANCE


@pytest.mark.parametrize("name,bundle", ALL_FIXTURES, ids=[n for n, _ in ALL_FIXTURES])
def test_snapshot_scores_within_tolerance(name: str, bundle: tuple) -> None:
    user, policies, expected = bundle
    result = generate_audit(user, policies)
    misses = []
    for key in ("coverage", "cost", "claim_readiness", "gap"):
        if not _within(result.scores[key], expected[key]):
            misses.append(f"{key}: got {result.scores[key]}, expected {expected[key]} ±{SCORE_TOLERANCE}")
    assert not misses, f"fixture {name} drifted: {'; '.join(misses)}"


def test_perf_under_50ms_for_5_policies() -> None:
    """Spec Section 7: 'must complete in < 50ms for a 5-policy user.'"""
    user, policies, _ = ALL_FIXTURES[4][1]   # Sahil — 7 policies, exceeds the 5-policy bar
    # warm caches (lru_cache, lookup_csr) so the first call doesn't include
    # one-time import/lookup costs
    generate_audit(user, policies)
    start = time.perf_counter()
    for _ in range(10):
        generate_audit(user, policies)
    avg_ms = ((time.perf_counter() - start) / 10) * 1000
    assert avg_ms < 50, f"engine averaged {avg_ms:.1f}ms per audit (target <50ms)"


def test_engine_is_deterministic() -> None:
    user, policies, _ = ALL_FIXTURES[1][1]   # Priya
    a = generate_audit(user, policies)
    b = generate_audit(user, policies)
    assert a.scores == b.scores
    assert [f.type for f in a.findings] == [f.type for f in b.findings]


def test_top_findings_count_is_at_most_3() -> None:
    for name, (user, policies, _) in ALL_FIXTURES:
        result = generate_audit(user, policies)
        assert len(result.findings) <= 3, f"{name}: returned {len(result.findings)} top findings"


def test_finding_shape_matches_frontend_contract() -> None:
    """Every Finding must include the exact 7 keys the frontend reads."""
    required = {"id", "severity", "type", "icon", "headline", "explanation", "action"}
    user, policies, _ = ALL_FIXTURES[2][1]   # Arjun — many findings
    result = generate_audit(user, policies)
    assert len(result.findings) >= 1
    for f in result.findings:
        missing = required - set(f.__dataclass_fields__.keys())
        assert not missing, f"finding missing keys: {missing}"
        assert f.severity in ("red", "amber", "info"), f.severity
        assert f.icon in ("alert-triangle", "shield-off", "clock"), f.icon


def test_top_findings_have_stable_f1_f2_f3_ids() -> None:
    user, policies, _ = ALL_FIXTURES[2][1]   # Arjun
    result = generate_audit(user, policies)
    expected_ids = [f"f{i}" for i in range(1, len(result.findings) + 1)]
    assert [f.id for f in result.findings] == expected_ids
