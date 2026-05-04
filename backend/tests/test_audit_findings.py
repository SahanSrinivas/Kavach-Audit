"""Findings unit tests — template rendering, ranking, top-3 selection."""
from __future__ import annotations

import pytest

from services.audit import findings, generate_audit
from services.audit.constants.templates import TEMPLATES, SEVERITY_FROM_SPEC
from services.audit.explanations import (
    TemplateNotFound,
    claude_fallback,
    map_severity,
    render,
)
from services.audit.types import Lifestyle, Policy, UserProfile


# ---------- Template registry ----------

def test_registry_has_at_least_25_templates() -> None:
    assert len(TEMPLATES) >= 25


@pytest.mark.parametrize("ftype", list(TEMPLATES.keys()))
def test_every_template_renders_with_safe_dict(ftype: str) -> None:
    """Missing context keys must not raise; should produce visible
    placeholder strings instead.
    """
    out = render(ftype, {})
    for key in ("severity_default", "icon", "headline", "explanation", "action", "cta"):
        assert key in out
    assert out["icon"] in ("alert-triangle", "shield-off", "clock")
    # severity_default in templates uses spec wording (critical/high/medium/low);
    # the frontend-facing red/amber/info mapping happens in findings.py.
    assert out["severity_default"] in ("critical", "high", "medium", "low")


def test_render_substitutes_context_values() -> None:
    out = render("room_rent_cap_metro", {
        "cap_per_day": 5000, "user_city": "Mumbai",
        "actual_cost": 15000, "overage": 10000, "sum_insured_lakh": 5,
    })
    assert "₹5,000" in out["headline"]
    assert "Mumbai" in out["headline"]
    assert "15,000" in out["explanation"]


def test_render_unknown_template_raises() -> None:
    with pytest.raises(TemplateNotFound):
        render("totally_made_up_finding", {})


# ---------- Severity mapping ----------

def test_severity_map_critical_high_to_red() -> None:
    assert map_severity("critical") == "red"
    assert map_severity("high") == "red"


def test_severity_map_medium_to_amber() -> None:
    assert map_severity("medium") == "amber"


def test_severity_map_low_to_info() -> None:
    assert map_severity("low") == "info"


def test_severity_map_unknown_defaults_to_amber() -> None:
    assert map_severity("nonsense") == "amber"


def test_severity_from_spec_dict_covers_all_levels() -> None:
    assert set(SEVERITY_FROM_SPEC.keys()) == {"critical", "high", "medium", "low"}


# ---------- Claude fallback stub ----------

def test_claude_fallback_returns_template_version() -> None:
    """Stub returns the deterministic template render — real Claude lands later."""
    a = render("missing_health", {"user_city": "Mumbai", "ideal_lakh": 15})
    b = claude_fallback("missing_health", {"user_city": "Mumbai", "ideal_lakh": 15})
    assert a == b


# ---------- Top-3 selection + ranking ----------

def _u_with_red_flags() -> tuple[UserProfile, list[Policy]]:
    user = UserProfile(
        user_id="x", age=42, city="Mumbai", tier="tier-1",
        spouse_age=40, kids_count=2,
        parents_ages={"mother": 65}, parents_pec=("Diabetes",),
        income=2_500_000, lifestyle=Lifestyle(two_wheeler=True),
    )
    policies = [
        Policy(id="h", type="health", insurer="Care Health",
               sum_insured=1_000_000, premium=38_000,
               parsed_fields={
                   "room_rent_cap": 5_000,
                   "icu_cap": 10_000,
                   "copay_percent": 20,
                   "ped_waiting_years": 4,
                   "sub_limits": [{"type": "cataract", "cap": 40_000}],
                   "permanent_exclusions": [],
                   "network_hospitals": 4_000,
                   "restoration_benefit": False,
               }),
    ]
    return user, policies


def test_top_findings_capped_at_3() -> None:
    user, pol = _u_with_red_flags()
    result = generate_audit(user, pol)
    assert len(result.findings) <= 3


def test_all_findings_includes_more_than_top() -> None:
    user, pol = _u_with_red_flags()
    result = generate_audit(user, pol)
    assert len(result.all_findings) >= len(result.findings)


def test_top_finding_has_higher_rank_score_than_tail() -> None:
    user, pol = _u_with_red_flags()
    result = generate_audit(user, pol)
    if len(result.all_findings) <= len(result.findings):
        pytest.skip("not enough findings to compare ranking")
    top_rank = findings._rank_score(result.findings[0])
    tail_rank = findings._rank_score(result.all_findings[-1])
    assert top_rank >= tail_rank


def test_critical_finding_outranks_low_finding() -> None:
    """User-proximity-driven: ped_waiting_with_disclosed_condition (critical,
    user-proximity 1.0) should outrank disease_waiting_long (low, 0.2)."""
    user, pol = _u_with_red_flags()
    result = generate_audit(user, pol)
    # Find both finding types in the full ranked list
    types = [f.type for f in result.all_findings]
    if "ped_waiting_with_disclosed_condition" in types and "disease_waiting_long" in types:
        ped_idx = types.index("ped_waiting_with_disclosed_condition")
        dwl_idx = types.index("disease_waiting_long")
        assert ped_idx < dwl_idx


def test_finding_id_pattern_for_top_three() -> None:
    user, pol = _u_with_red_flags()
    result = generate_audit(user, pol)
    expected = [f"f{i}" for i in range(1, len(result.findings) + 1)]
    assert [f.id for f in result.findings] == expected


def test_finding_severity_is_frontend_compatible() -> None:
    user, pol = _u_with_red_flags()
    result = generate_audit(user, pol)
    for f in result.findings:
        assert f.severity in ("red", "amber", "info")
        assert f.icon in ("alert-triangle", "shield-off", "clock")
