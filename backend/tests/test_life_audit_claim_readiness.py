from dataclasses import replace

from services.life.audit import claim_readiness
from services.life.audit.types import LifeScheduleInput


def _schedule(**overrides) -> LifeScheduleInput:
    base = LifeScheduleInput(
        schedule_id="s1",
        product_name="Plan",
        sum_assured_inr=10_000_000,
        policy_term_years=30,
        premium_payment_term_years=20,
        modal_premium_inr=10_000,
        premium_frequency="Annual",
        nominee_section_likely=True,
        free_look_days=30,
        detected_riders=("critical_illness",),
        contingent_nominee_likely=True,
        autopay_likely=True,
        insurer_name="HDFC Life",
    )
    return replace(base, **overrides)


def test_all_components_fire_to_max():
    out = claim_readiness.score(_schedule())
    assert out.value == 100


def test_nominee_absent_zeros_nominee_component():
    out = claim_readiness.score(_schedule(nominee_section_likely=False))
    assert out.details["components"]["nominee"] == 0


def test_csr_lookup_hits_real_insurer():
    out = claim_readiness.score(_schedule(insurer_name="HDFC Life"))
    assert out.details["insurer_csr_unknown"] is False
    assert float(out.details["insurer_csr"]) > 0.0


def test_csr_unknown_returns_zero_component_and_flag():
    out = claim_readiness.score(_schedule(insurer_name="Unknown Life Co"))
    assert out.details["insurer_csr_unknown"] is True
    assert out.details["components"]["insurer_csr"] == 0


def test_contingent_nominee_adds_10():
    lo = claim_readiness.score(_schedule(contingent_nominee_likely=False))
    hi = claim_readiness.score(_schedule(contingent_nominee_likely=True))
    assert int(hi.value or 0) - int(lo.value or 0) == 10


def test_free_look_less_than_15_zeros_component():
    out = claim_readiness.score(_schedule(free_look_days=10))
    assert out.details["components"]["free_look_active"] == 0


def test_autopay_toggle_component():
    lo = claim_readiness.score(_schedule(autopay_likely=False))
    hi = claim_readiness.score(_schedule(autopay_likely=True))
    assert int(hi.value or 0) - int(lo.value or 0) == 10


def test_empty_riders_zero_component():
    out = claim_readiness.score(_schedule(detected_riders=()))
    assert out.details["components"]["riders_documented"] == 0
