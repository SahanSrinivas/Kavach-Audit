"""Life router: stats JSON + PDF extraction endpoint."""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from unittest.mock import MagicMock

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("USE_MOCKS", "true")
os.environ.setdefault("DISABLE_RATE_LIMIT", "true")
os.environ.setdefault("JWT_SECRET", "test-secret")

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402

import services.rate_limit as rate_limit_module  # noqa: E402
from auth import get_current_user, verify_csrf  # noqa: E402
from routers import life_router  # noqa: E402
from server import app  # noqa: E402
from services.life.extract_schedule import extract_life_schedule as real_extract_life_schedule  # noqa: E402
from tests._fake_mongo import FakeDb  # noqa: E402
from tests.life_preflight_fixtures import (  # noqa: E402
    encrypted_minimal_life_pdf,
    mini_borderline_life_pdf,
    resume_pdf,
)


def _mini_pdf_bytes() -> bytes:
    """Synthetic CIS-like PDF for integration tests (borderline band; ≥10 KiB)."""
    return mini_borderline_life_pdf()


def _client() -> TestClient:
    return TestClient(app)


@contextmanager
def _life_extract_test_db() -> Iterator[FakeDb]:
    """Extract uses async Motor; TestClient + thread pool can race with loop teardown.
    Use in-memory FakeDb for parse_attempts during extract tests."""
    prev = app.state.db
    fake = FakeDb()
    app.state.db = fake
    try:
        yield fake
    finally:
        app.state.db = prev


def _auth_with_fake_db() -> FakeDb:
    fake = FakeDb()
    fake.users.docs.append(
        {
            "id": "u1",
            "user_id": "u1",
            "mobile": "9999999999",
            "age": 35,
            "gender": "male",
            "dependents": 2,
            "annual_income": 1_200_000,
            "city_tier": "tier-1",
            "liabilities_inr": 2_500_000,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    app.state.db = fake
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "u1", "mobile": "9999999999"}
    app.dependency_overrides[verify_csrf] = lambda: None
    return fake


def _seed_audit(
    fake: FakeDb,
    *,
    findings: list[dict[str, str]] | None = None,
    created_at: str = "2026-05-06T10:00:00+00:00",
) -> None:
    fake.life_audits.docs.append(
        {
            "id": "audit-1",
            "user_id": "u1",
            "scores": {"coverage": 70, "cost": 70, "claim_readiness": 70, "gap": 70},
            "findings": findings or [],
            "all_findings": findings or [],
            "breakdowns": {"gap": {"value": 70, "label": "gap", "details": {"sum_assured_inr": 8_000_000}}},
            "data_version": "life-2026.05",
            "engine_ms": 5,
            "generated_at": "2026-05-06T09:59:00+00:00",
            "created_at": created_at,
            "warnings": [],
        }
    )


def test_life_stats_index_ok():
    r = _client().get("/api/life/stats/index")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert "defaultFy" in body["data"]


def test_life_stats_bundle_fy():
    r = _client().get("/api/life/stats/2023-24")
    assert r.status_code == 200
    assert r.json()["data"]["fy"] == "2023-24"
    assert len(r.json()["data"]["insurers"]) >= 1


def test_extract_requires_both_files():
    r = _client().post("/api/life/extract")
    assert r.status_code == 400


def test_extract_two_pdfs():
    with _life_extract_test_db():
        pdf = _mini_pdf_bytes()
        r = _client().post(
            "/api/life/extract",
            files=[
                ("cis", ("cis.pdf", pdf, "application/pdf")),
                ("bond", ("bond.pdf", pdf, "application/pdf")),
            ],
            data={"insurer_id": "lic"},
        )
        assert r.status_code == 200, r.text
        payload = r.json()["data"]
        assert payload["lifeSchedule"]["sumAssuredInr"] == 5_000_000
        assert payload["meta"]["insurerId"] == "lic"
        assert len(payload.get("fieldConfidenceUi") or []) >= 1


def test_save_schedule_requires_auth():
    r = _client().post(
        "/api/life/schedules",
        json={"lifeSchedule": {"schemaVersion": 1}, "confidence": {}},
    )
    assert r.status_code == 401


def test_overlap_hints_requires_auth():
    r = _client().get("/api/life/overlap-hints")
    assert r.status_code == 401


def test_extract_llm_fallback_refines_and_sets_meta(monkeypatch):
    pdf = _mini_pdf_bytes()
    monkeypatch.setenv("LIFE_EXTRACT_LLM_FALLBACK", "true")
    monkeypatch.setenv("LIFE_EXTRACT_LLM_THRESHOLD", "0.99")
    monkeypatch.setenv("LIFE_EXTRACT_LLM_MERGE_THRESHOLD", "0.99")
    monkeypatch.setenv("LIFE_LLM_MODEL", "test-model")

    async def _fake_llm(*_args, **_kwargs):
        return {
            "lifeSchedule": {
                "sumAssuredInr": 7_500_000,
                "productName": "Refined Plan",
                "detectedRiders": ["critical_illness"],
            },
            "confidence": {
                "sumAssuredInr": 0.9,
                "productName": 0.85,
                "overall": 0.88,
            },
        }

    monkeypatch.setattr(life_router, "llm_refine_life_schedule", _fake_llm)
    with _life_extract_test_db():
        r = _client().post(
            "/api/life/extract",
            files=[
                ("cis", ("cis.pdf", pdf, "application/pdf")),
                ("bond", ("bond.pdf", pdf, "application/pdf")),
            ],
            data={"insurer_id": "lic"},
        )
        assert r.status_code == 200, r.text
        payload = r.json()["data"]
        assert payload["lifeSchedule"]["sumAssuredInr"] == 7_500_000
        assert payload["lifeSchedule"]["productName"] == "Refined Plan"
        assert "critical_illness" in (payload["lifeSchedule"].get("detectedRiders") or [])
        assert payload["meta"]["llmRefinement"] is True
        assert payload["meta"]["llmModel"] == "test-model"


def test_extract_rejects_resume_pdf(monkeypatch):
    spy = MagicMock()
    monkeypatch.setattr(life_router, "extract_life_schedule", spy)

    cis = resume_pdf()
    bond = mini_borderline_life_pdf()

    with _life_extract_test_db() as fake:
        r = _client().post(
            "/api/life/extract",
            files=[
                ("cis", ("cis.pdf", cis, "application/pdf")),
                ("bond", ("bond.pdf", bond, "application/pdf")),
            ],
            data={"insurer_id": "lic"},
        )

    assert r.status_code == 400
    detail = r.json()["detail"]
    assert isinstance(detail, dict)
    assert detail.get("error") == "not_insurance_document"
    assert detail.get("detected_type_hint") == "resume"

    rejects = [
        row
        for row in fake.parse_attempts.docs
        if row.get("preflight_outcome") == "reject"
    ]
    assert any(row.get("detected_type_hint") == "resume" for row in rejects)

    spy.assert_not_called()


def test_extract_logs_borderline_to_parse_attempts(monkeypatch):
    traced = MagicMock(wraps=real_extract_life_schedule)
    monkeypatch.setattr(life_router, "extract_life_schedule", traced)

    pdf = mini_borderline_life_pdf()
    with _life_extract_test_db() as fake:
        r = _client().post(
            "/api/life/extract",
            files=[
                ("cis", ("cis.pdf", pdf, "application/pdf")),
                ("bond", ("bond.pdf", pdf, "application/pdf")),
            ],
            data={"insurer_id": "lic"},
        )

    assert r.status_code == 200, r.text
    assert any(row.get("preflight_outcome") == "borderline" for row in fake.parse_attempts.docs)
    traced.assert_called()


def test_extract_structural_reject_on_encrypted_pdf(monkeypatch):
    monkeypatch.setattr(rate_limit_module, "_DISABLED", False)

    before = dict(rate_limit_module.rate_limit_metrics_snapshot())

    cis = encrypted_minimal_life_pdf()
    bond = mini_borderline_life_pdf()

    with _life_extract_test_db() as fake:
        r = _client().post(
            "/api/life/extract",
            files=[
                ("cis", ("cis.pdf", cis, "application/pdf")),
                ("bond", ("bond.pdf", bond, "application/pdf")),
            ],
            data={"insurer_id": "lic"},
        )

    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail.get("error") == "encrypted_pdf"

    after = dict(rate_limit_module.rate_limit_metrics_snapshot())
    assert after["memory_checks"] == before["memory_checks"]
    assert after["redis_checks"] == before["redis_checks"]

    structural = [
        row
        for row in fake.parse_attempts.docs
        if row.get("preflight_outcome") == "structural_reject"
    ]
    assert any(row.get("preflight_error") == "encrypted_pdf" for row in structural)


def test_post_life_audit_returns_valid_audit_for_user_schedule():
    fake = _auth_with_fake_db()
    fake.life_schedules.docs.append(
        {
            "_id": "sched-1",
            "user_id": "u1",
            "created_at": "2026-05-05T10:00:00+00:00",
            "life_schedule": {
                "productName": "HDFC Life Click 2 Protect",
                "sumAssuredInr": 12_000_000,
                "policyTermYears": 30,
                "premiumPaymentTermYears": 25,
                "modalPremiumInr": 18_000,
                "premiumFrequency": "Annual",
                "nomineeSectionLikely": True,
                "freeLookDays": 30,
                "detectedRiders": ["critical_illness", "personal_accident"],
                "insurerName": "HDFC Life",
            },
        }
    )
    r = _client().post("/api/life/audit")
    app.dependency_overrides.clear()
    assert r.status_code == 200, r.text
    audit = r.json()["data"]["audit"]
    assert audit["user_id"] == "u1"
    assert set(audit["scores"].keys()) == {"coverage", "cost", "claim_readiness", "gap"}
    assert audit["data_version"] == "life-2026.05"
    assert len(fake.life_audits.docs) == 1


def test_post_life_audit_404_when_no_schedule():
    _auth_with_fake_db()
    r = _client().post("/api/life/audit")
    app.dependency_overrides.clear()
    assert r.status_code == 404
    assert r.json()["detail"] == "life_schedule_not_found"


def test_get_life_audit_latest_returns_most_recent():
    fake = _auth_with_fake_db()
    fake.life_audits.docs.extend(
        [
            {"user_id": "u1", "created_at": "2026-05-05T10:00:00+00:00", "scores": {"gap": 70}},
            {"user_id": "u1", "created_at": "2026-05-06T10:00:00+00:00", "scores": {"gap": 90}},
        ]
    )
    r = _client().get("/api/life/audit/latest")
    app.dependency_overrides.clear()
    assert r.status_code == 200, r.text
    assert r.json()["data"]["audit"]["scores"]["gap"] == 90


def test_get_life_audit_latest_404_when_none():
    _auth_with_fake_db()
    r = _client().get("/api/life/audit/latest")
    app.dependency_overrides.clear()
    assert r.status_code == 404
    assert r.json()["detail"] == "life_audit_not_found"


def test_get_life_recommendations_returns_data_when_audit_and_user_exist():
    fake = _auth_with_fake_db()
    _seed_audit(fake, findings=[{"type": "underinsured_life", "severity": "red"}])
    r = _client().get("/api/life/recommendations")
    app.dependency_overrides.clear()
    assert r.status_code == 200, r.text
    recs = r.json()["data"]["recommendations"]
    assert len(recs) >= 1
    assert recs[0]["type"] == "term_top_up"


def test_get_life_recommendations_404_when_no_audit():
    _auth_with_fake_db()
    r = _client().get("/api/life/recommendations")
    app.dependency_overrides.clear()
    assert r.status_code == 404
    assert r.json()["detail"] == "life_audit_not_found"


def test_get_life_recommendations_404_when_user_missing():
    fake = FakeDb()
    app.state.db = fake
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "u1", "mobile": "9999999999"}
    app.dependency_overrides[verify_csrf] = lambda: None
    _seed_audit(fake, findings=[{"type": "underinsured_life", "severity": "red"}])
    r = _client().get("/api/life/recommendations")
    app.dependency_overrides.clear()
    assert r.status_code == 404
    assert r.json()["detail"] == "user_not_found"


def test_get_life_recommendations_returns_stay_with_current_for_clean_audit():
    fake = _auth_with_fake_db()
    _seed_audit(fake, findings=[])
    r = _client().get("/api/life/recommendations")
    app.dependency_overrides.clear()
    assert r.status_code == 200, r.text
    recs = r.json()["data"]["recommendations"]
    assert len(recs) == 1
    assert recs[0]["type"] == "stay_with_current"
