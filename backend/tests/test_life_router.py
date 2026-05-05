"""Life router: stats JSON + PDF extraction endpoint."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("USE_MOCKS", "true")
os.environ.setdefault("DISABLE_RATE_LIMIT", "true")
os.environ.setdefault("JWT_SECRET", "test-secret")

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402

from routers import life_router  # noqa: E402
from server import app  # noqa: E402


def _mini_pdf_bytes() -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (72, 100),
        "Sum Assured Rs. 50,00,000\nPolicy Term 25 years\nModal Premium Rs. 12,000 yearly\nNominee as per proposal",
    )
    raw = doc.tobytes()
    doc.close()
    return raw


def _client() -> TestClient:
    return TestClient(app)


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
