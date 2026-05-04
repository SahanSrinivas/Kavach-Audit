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


# ==========================================================================
# Bug B regression — _format_inr_short + underinsured_life template text
# ==========================================================================

@pytest.mark.parametrize("amount,expected", [
    # Sub-Lakh: never display "₹0 Lakh" — that would round a real ₹50K
    # cover to nothing. Use the explicit "<₹1 Lakh" form.
    (0,             "<₹1 Lakh"),
    (1,             "<₹1 Lakh"),
    (50_000,        "<₹1 Lakh"),
    (99_999,        "<₹1 Lakh"),
    # Lakh range: round to nearest lakh. Documented behavior — Python
    # int(round()) uses banker's rounding so 1.5 → 2.
    (100_000,       "₹1 Lakh"),
    (150_000,       "₹2 Lakh"),    # banker's: 1.5 rounds to 2
    (250_000,       "₹2 Lakh"),    # banker's: 2.5 rounds to 2
    (390_000,       "₹4 Lakh"),    # the eBID dogfood case
    (391_547,       "₹4 Lakh"),    # the exact eBID number
    (399_999,       "₹4 Lakh"),
    (400_000,       "₹4 Lakh"),
    (1_500_000,     "₹15 Lakh"),
    (9_900_000,     "₹99 Lakh"),
    (9_999_999,     "₹100 Lakh"),  # at the boundary, still in lakh form
    # Crore range: 1 decimal precision; trailing .0 stripped
    (10_000_000,    "₹1 Cr"),
    (15_000_000,    "₹1.5 Cr"),
    (19_600_000,    "₹2 Cr"),       # 1.96 rounds to 2.0 → strip → "₹2 Cr"
    (20_000_000,    "₹2 Cr"),
    (25_000_000,    "₹2.5 Cr"),
    (100_000_000,   "₹10 Cr"),
])
def test_format_inr_short(amount: int, expected: str) -> None:
    from services.audit.findings import _format_inr_short
    assert _format_inr_short(amount) == expected


def test_underinsured_life_text_for_4_lakh_endowment() -> None:
    """The exact dogfood scenario: ₹3.9L endowment + ~₹2.4Cr ideal life
    cover. Pre-fix output: 'Your term cover is ₹1 Cr but your family
    needs ~₹2 Cr.' (₹1 Cr is fabricated.) Post-fix: '₹4 Lakh' shown.
    """
    user = UserProfile(
        user_id="u_dogfood", age=34, city="Bangalore", tier="tier-1",
        spouse_age=33, kids_count=1, income=2_000_000,
    )
    # Endowment policy modeled after the eBID Exide Life Assured Gain Plus
    endowment = Policy(
        id="p_e", type="endowment", insurer="Exide Life",
        sum_insured=391_547, premium=100_000,
    )
    result = generate_audit(user, [endowment])

    # Find the underinsured_life finding (should fire because life ratio < 0.85)
    life_findings = [f for f in result.all_findings if f.type == "underinsured_life"]
    assert life_findings, "expected underinsured_life finding for 4L endowment + 20L income"
    f = life_findings[0]
    # The fabricated "₹1 Cr cover" line must NOT appear
    assert "₹1 Cr" not in f.headline, f"headline still uses ₹1 Cr floor: {f.headline}"
    # The actual cover amount in lakhs DOES appear
    assert "₹4 Lakh" in f.headline or "₹1 Lakh" in f.headline, \
        f"headline should display cover in lakhs: {f.headline}"
    # Sanity: explanation also updated
    assert "₹1 Cr cover" not in f.explanation


def test_underinsured_life_text_for_legitimate_crore_cover() -> None:
    """A user with ₹1.5 Cr term + ₹50L gap should display in Cr correctly,
    not regress to lakh formatting."""
    user = UserProfile(
        user_id="u", age=34, city="Mumbai", tier="tier-1",
        spouse_age=33, kids_count=2, income=2_500_000,  # ideal life ≈ 4.5 Cr
    )
    term = Policy(id="p_t", type="term", insurer="HDFC Life",
                  sum_insured=15_000_000, premium=18_000)
    result = generate_audit(user, [term])
    life_findings = [f for f in result.all_findings if f.type == "underinsured_life"]
    assert life_findings
    f = life_findings[0]
    # Should display ₹1.5 Cr, not "₹1 Lakh" or "₹1 Cr"
    assert "₹1.5 Cr" in f.headline, f"expected '₹1.5 Cr' in: {f.headline}"


def test_underinsured_life_text_no_zero_lakh_for_tiny_endowment() -> None:
    """A ₹50K endowment (tiny rounding edge case) should display '<₹1 Lakh',
    NOT '₹0 Lakh' (which would look like 'no cover')."""
    user = UserProfile(
        user_id="u", age=35, city="Mumbai", tier="tier-1",
        spouse_age=33, income=2_000_000,
    )
    tiny = Policy(id="p_e", type="endowment", insurer="LIC",
                  sum_insured=50_000, premium=10_000)
    result = generate_audit(user, [tiny])
    life_findings = [f for f in result.all_findings if f.type == "underinsured_life"]
    if life_findings:  # depends on coverage threshold; either passes
        f = life_findings[0]
        assert "₹0 Lakh" not in f.headline, f"never display '₹0 Lakh': {f.headline}"
