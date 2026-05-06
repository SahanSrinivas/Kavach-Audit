from datetime import datetime

from services.life.audit import runner
from services.life.audit.types import (
    LifeScheduleInput,
    LifeScoreBreakdown,
    LifeUserProfile,
)


def _profile() -> LifeUserProfile:
    return LifeUserProfile(user_id="u1", age=35, annual_income=500_000, dependents=1)


def _schedule() -> LifeScheduleInput:
    return LifeScheduleInput(
        schedule_id="s1",
        product_name="Plan",
        sum_assured_inr=5_000_000,
        policy_term_years=25,
        premium_payment_term_years=20,
        modal_premium_inr=1_000,
        premium_frequency="Monthly",
        nominee_section_likely=True,
        free_look_days=15,
        detected_riders=("critical_illness",),
    )


def _b(label: str, value: int | None) -> LifeScoreBreakdown:
    return LifeScoreBreakdown(value=value, label=label, details={})


def test_happy_path_returns_valid_result(monkeypatch):
    monkeypatch.setattr(runner.coverage, "score", lambda *_: _b("coverage", 90))
    monkeypatch.setattr(runner.cost, "score", lambda *_: _b("cost", 80))
    monkeypatch.setattr(runner.claim_readiness, "score", lambda *_: _b("claim_readiness", 70))
    monkeypatch.setattr(runner.gap, "score", lambda *_args, **_kwargs: _b("gap", 60))
    monkeypatch.setattr(runner.findings, "generate", lambda *_: ([], []))
    out = runner.run_life_audit(_profile(), _schedule())
    assert out.scores["coverage"] == 90
    assert out.scores["gap"] == 60
    assert isinstance(out.engine_ms, int)
    assert out.engine_ms >= 0
    datetime.fromisoformat(out.generated_at)


def test_coverage_scorer_raises_only_coverage_none(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise RuntimeError("x")

    monkeypatch.setattr(runner.coverage, "score", _boom)
    monkeypatch.setattr(runner.cost, "score", lambda *_: _b("cost", 80))
    monkeypatch.setattr(runner.claim_readiness, "score", lambda *_: _b("claim_readiness", 70))
    monkeypatch.setattr(runner.gap, "score", lambda *_args, **_kwargs: _b("gap", 60))
    monkeypatch.setattr(runner.findings, "generate", lambda *_: ([], []))
    out = runner.run_life_audit(_profile(), _schedule())
    assert out.scores["coverage"] is None
    assert out.scores["cost"] == 80
    assert any("coverage_scorer_failed" in w for w in out.warnings)


def test_all_scorers_fail_no_crash(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise RuntimeError("x")

    monkeypatch.setattr(runner.coverage, "score", _boom)
    monkeypatch.setattr(runner.cost, "score", _boom)
    monkeypatch.setattr(runner.claim_readiness, "score", _boom)
    monkeypatch.setattr(runner.gap, "score", _boom)
    monkeypatch.setattr(runner.findings, "generate", lambda *_: ([], []))
    out = runner.run_life_audit(_profile(), _schedule())
    assert all(v is None for v in out.scores.values())
    assert len(out.warnings) >= 4


def test_engine_ms_positive_int():
    out = runner.run_life_audit(_profile(), _schedule())
    assert isinstance(out.engine_ms, int)
    assert out.engine_ms >= 0


def test_generated_at_is_valid_iso_timestamp():
    out = runner.run_life_audit(_profile(), _schedule())
    datetime.fromisoformat(out.generated_at)


def test_findings_generator_raises_returns_empty_findings_with_warning(monkeypatch):
    monkeypatch.setattr(runner.findings, "generate", lambda *_: (_ for _ in ()).throw(RuntimeError("x")))
    out = runner.run_life_audit(_profile(), _schedule())
    assert list(out.findings) == []
    assert list(out.all_findings) == []
    assert any("findings_generator_failed" in w for w in out.warnings)
