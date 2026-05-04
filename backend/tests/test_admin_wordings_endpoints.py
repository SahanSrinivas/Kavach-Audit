"""Route-level tests for /api/admin/wordings/* CRUD.

Mirrors the pattern in test_admin_beta_endpoints.py:
  - FakeDb stand-in for Mongo
  - TestClient against the live FastAPI app
  - Bearer auth via ADMIN_PASSWORD env var

The /wordings/parse endpoint normally calls Claude via parse_policy_pdf;
tests monkeypatch that import to a deterministic fake so we don't burn
API credits or require a real PDF on every run.
"""
from __future__ import annotations

import os
from typing import Iterator

import pytest

# Required env BEFORE importing the FastAPI app
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "kavach_test")
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod" * 2)
os.environ.setdefault("USE_MOCKS", "true")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-pw")
ADMIN_TOKEN = os.environ["ADMIN_PASSWORD"]

from fastapi.testclient import TestClient   # noqa: E402

from server import app                                                       # noqa: E402
from services.parser.types import (                                          # noqa: E402
    ICUCap,
    NCBStructure,
    ParseConfidence,
    ParsedFieldsRich,
    ParsedPolicy,
    RestorationBenefit,
    RoomRentCap,
    SubLimit,
)
from tests._fake_mongo import FakeDb                                         # noqa: E402


def _admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {ADMIN_TOKEN}"}


def _client() -> TestClient:
    return TestClient(app)


def _fake_parsed_policy(
    insurer: str = "HDFC ERGO General",
    plan_name: str = "Optima Restore",
) -> ParsedPolicy:
    """Realistic ParsedPolicy with rules populated — what Claude would
    produce for the Optima Restore wording."""
    return ParsedPolicy(
        insurer_name=insurer,
        insurer_name_raw=f"{insurer} Insurance Co. Ltd.",
        policy_type="health_family_floater",
        plan_name=plan_name,
        plan_name_raw=f"{insurer} {plan_name} Family Floater Plan",
        sum_insured=None,        # wording-only
        premium_annual=None,
        parsed_fields=ParsedFieldsRich(
            room_rent_cap=RoomRentCap(type="no_cap", value=None, raw_text="No cap"),
            icu_cap=ICUCap(type="no_cap", value=None, raw_text="No cap"),
            copay_percent=0,
            ped_waiting_months=24,
            initial_waiting_period_days=30,
            permanent_exclusions=["Cosmetic surgery", "War or similar situations"],
            permanent_exclusions_canonical=["cosmetic", "war"],
            network_hospital_count=12000,
            restoration_benefit=RestorationBenefit(
                available=True, type="once_per_year", applies_to="different_illness",
            ),
            ncb_structure=NCBStructure(max_percent=100, increment_per_year=25),
            sub_limits=[SubLimit(category="cataract", limit_amount=40_000)],
        ),
        confidence=ParseConfidence(overall="high", warnings=[]),
    )


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch: pytest.MonkeyPatch, tmp_path) -> Iterator[None]:  # type: ignore[no-untyped-def]
    """Fresh fake-db + monkeypatched parser per test.

    The fake parser skips the real Claude API call and returns a
    deterministic ParsedPolicy, so admin-endpoint tests verify the
    routing/validation logic independently of parser behavior.
    """
    fake = FakeDb()
    fake.wordings.add_unique_index("insurer_canonical", "plan_name_normalized")
    app.state.db = fake

    # Patch the parser import IN the admin_router module (where it's used)
    async def fake_parse_policy_pdf(pdf_bytes: bytes, filename: str) -> ParsedPolicy:
        # Default: HDFC ERGO Optima Restore wording. Tests can override
        # via monkeypatch on this fixture's setup.
        return _fake_parsed_policy()

    monkeypatch.setattr(
        "routers.admin_router.parse_policy_pdf", fake_parse_policy_pdf,
    )
    yield
    app.state.db = None  # type: ignore[assignment]


def _write_dummy_pdf(tmp_path, name: str = "wording.pdf") -> str:  # type: ignore[no-untyped-def]
    """Write a minimal byte string to a real on-disk path so the
    endpoint's file-validation passes. Content doesn't matter — the
    parser is monkeypatched."""
    p = tmp_path / name
    p.write_bytes(b"%PDF-1.4 fake bytes for test\n")
    return str(p)


# ==========================================================================
# Auth
# ==========================================================================

def test_parse_without_auth_returns_401(tmp_path) -> None:  # type: ignore[no-untyped-def]
    pdf = _write_dummy_pdf(tmp_path)
    r = _client().post(
        "/api/admin/wordings/parse",
        json={"pdf_path": pdf, "insurer_canonical": "HDFC ERGO General",
              "plan_name": "Optima Restore"},
    )
    assert r.status_code == 401


def test_parse_with_wrong_token_returns_401(tmp_path) -> None:  # type: ignore[no-untyped-def]
    pdf = _write_dummy_pdf(tmp_path)
    r = _client().post(
        "/api/admin/wordings/parse",
        json={"pdf_path": pdf, "insurer_canonical": "HDFC ERGO General",
              "plan_name": "Optima Restore"},
        headers={"Authorization": "Bearer wrong"},
    )
    assert r.status_code == 401


def test_list_without_auth_returns_401() -> None:
    assert _client().get("/api/admin/wordings").status_code == 401


def test_get_without_auth_returns_401() -> None:
    assert _client().get("/api/admin/wordings/some-id").status_code == 401


def test_qa_update_without_auth_returns_401() -> None:
    r = _client().patch(
        "/api/admin/wordings/some-id/qa",
        json={"status": "human_verified"},
    )
    assert r.status_code == 401


def test_delete_without_auth_returns_401() -> None:
    assert _client().delete("/api/admin/wordings/some-id").status_code == 401


# ==========================================================================
# POST /wordings/parse — happy path
# ==========================================================================

def test_parse_stores_wording_with_auto_parsed_status(tmp_path) -> None:  # type: ignore[no-untyped-def]
    pdf = _write_dummy_pdf(tmp_path, "optima-restore.pdf")
    r = _client().post(
        "/api/admin/wordings/parse",
        json={
            "pdf_path": pdf,
            "insurer_canonical": "HDFC ERGO General",
            "plan_name": "Optima Restore",
            "source_url": "https://hdfcergo.com/optima-restore.pdf",
            "wording_uin": "HDFHLIP26055V102526",
        },
        headers=_admin_headers(),
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["wording_id"]
    w = body["wording"]
    assert w["insurer_canonical"] == "HDFC ERGO General"
    assert w["plan_name"] == "Optima Restore"
    assert w["plan_name_normalized"] == "optimarestore"
    assert w["qa_status"] == "auto_parsed"
    assert w["wording_uin"] == "HDFHLIP26055V102526"
    assert w["source_url"] == "https://hdfcergo.com/optima-restore.pdf"
    assert w["source_filename"] == "optima-restore.pdf"
    assert "rules" in w
    assert w["rules"]["ped_waiting_months"] == 24
    assert "Cosmetic surgery" in w["rules"]["permanent_exclusions"]
    assert "parsed_at" in w
    # Forward-compat fields default to empty (parser doesn't extract them today)
    assert w["available_sum_insured_lakhs"] == []
    assert w["add_ons"] == []


def test_parse_stores_into_mongo_via_upsert(tmp_path) -> None:  # type: ignore[no-untyped-def]
    pdf = _write_dummy_pdf(tmp_path)
    _client().post(
        "/api/admin/wordings/parse",
        json={"pdf_path": pdf, "insurer_canonical": "HDFC ERGO General",
              "plan_name": "Optima Restore"},
        headers=_admin_headers(),
    )
    fake: FakeDb = app.state.db
    assert len(fake.wordings.docs) == 1


def test_parse_idempotent_on_same_insurer_and_plan(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Re-parse same plan → updates existing row, doesn't create duplicate.
    Same idempotency contract as upsert_wording (see test_wordings_service.py)."""
    pdf = _write_dummy_pdf(tmp_path)
    payload = {
        "pdf_path": pdf, "insurer_canonical": "HDFC ERGO General",
        "plan_name": "Optima Restore",
    }
    r1 = _client().post("/api/admin/wordings/parse", json=payload, headers=_admin_headers())
    r2 = _client().post("/api/admin/wordings/parse", json=payload, headers=_admin_headers())
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["data"]["wording_id"] == r2.json()["data"]["wording_id"]
    fake: FakeDb = app.state.db
    assert len(fake.wordings.docs) == 1  # still one row


# ==========================================================================
# POST /wordings/parse — validation errors
# ==========================================================================

def test_parse_rejects_unknown_insurer_canonical(tmp_path) -> None:  # type: ignore[no-untyped-def]
    pdf = _write_dummy_pdf(tmp_path)
    r = _client().post(
        "/api/admin/wordings/parse",
        json={"pdf_path": pdf, "insurer_canonical": "Made Up Insurer",
              "plan_name": "Test Plan"},
        headers=_admin_headers(),
    )
    assert r.status_code == 400
    assert "invalid_insurer_canonical" in r.text


def test_parse_rejects_missing_pdf_path() -> None:
    r = _client().post(
        "/api/admin/wordings/parse",
        json={"pdf_path": "/tmp/nonexistent-12345.pdf",
              "insurer_canonical": "HDFC ERGO General",
              "plan_name": "Test Plan"},
        headers=_admin_headers(),
    )
    assert r.status_code == 400
    assert "pdf_not_found" in r.text


def test_parse_rejects_non_pdf_extension(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "wording.txt"
    p.write_text("not a pdf")
    r = _client().post(
        "/api/admin/wordings/parse",
        json={"pdf_path": str(p),
              "insurer_canonical": "HDFC ERGO General",
              "plan_name": "Test Plan"},
        headers=_admin_headers(),
    )
    assert r.status_code == 400
    assert "pdf_wrong_extension" in r.text


def test_parse_rejects_too_large_pdf(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Cap is 10 MB; simulate a PDF over the limit."""
    monkeypatch.setattr("routers.admin_router.MAX_WORDING_PDF_BYTES", 100)
    p = tmp_path / "huge.pdf"
    p.write_bytes(b"x" * 200)  # 200 bytes > 100 byte cap
    r = _client().post(
        "/api/admin/wordings/parse",
        json={"pdf_path": str(p),
              "insurer_canonical": "HDFC ERGO General",
              "plan_name": "Test Plan"},
        headers=_admin_headers(),
    )
    assert r.status_code == 413
    assert "pdf_too_large" in r.text


def test_parse_rejects_directory_as_pdf(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Directory ending in .pdf should fail the is_file() check."""
    d = tmp_path / "fake.pdf"
    d.mkdir()
    r = _client().post(
        "/api/admin/wordings/parse",
        json={"pdf_path": str(d),
              "insurer_canonical": "HDFC ERGO General",
              "plan_name": "Test Plan"},
        headers=_admin_headers(),
    )
    assert r.status_code == 400
    assert "pdf_not_a_file" in r.text


# ==========================================================================
# POST /wordings/parse — parser-level errors propagate as 502
# ==========================================================================

def test_parse_propagates_parser_failure_as_502(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Parser raises ParseFailureError → endpoint returns 502 with structured detail."""
    from services.parser import ParseFailureError

    async def failing_parse(pdf_bytes: bytes, filename: str) -> ParsedPolicy:
        raise ParseFailureError("api_unavailable", "Anthropic timed out")

    monkeypatch.setattr("routers.admin_router.parse_policy_pdf", failing_parse)
    pdf = _write_dummy_pdf(tmp_path)
    r = _client().post(
        "/api/admin/wordings/parse",
        json={"pdf_path": pdf, "insurer_canonical": "HDFC ERGO General",
              "plan_name": "Optima Restore"},
        headers=_admin_headers(),
    )
    assert r.status_code == 502
    assert "api_unavailable" in r.text


# ==========================================================================
# GET /wordings — list with filters
# ==========================================================================

def _seed_wordings(client: TestClient, tmp_path) -> dict[str, str]:  # type: ignore[no-untyped-def]
    """Helper: parse two wordings (different insurers) into the fake DB."""
    pdf = _write_dummy_pdf(tmp_path, "w1.pdf")
    a = client.post("/api/admin/wordings/parse",
                    json={"pdf_path": pdf, "insurer_canonical": "HDFC ERGO General",
                          "plan_name": "Optima Restore"},
                    headers=_admin_headers())
    b = client.post("/api/admin/wordings/parse",
                    json={"pdf_path": pdf, "insurer_canonical": "Niva Bupa",
                          "plan_name": "ReAssure 2.0"},
                    headers=_admin_headers())
    return {"a": a.json()["data"]["wording_id"],
            "b": b.json()["data"]["wording_id"]}


def test_list_returns_all_wordings_no_filter(tmp_path) -> None:  # type: ignore[no-untyped-def]
    c = _client()
    _seed_wordings(c, tmp_path)
    r = c.get("/api/admin/wordings", headers=_admin_headers())
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["count"] == 2
    assert len(body["wordings"]) == 2


def test_list_filters_by_insurer(tmp_path) -> None:  # type: ignore[no-untyped-def]
    c = _client()
    _seed_wordings(c, tmp_path)
    r = c.get("/api/admin/wordings?insurer=Niva Bupa", headers=_admin_headers())
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["count"] == 1
    assert body["wordings"][0]["plan_name"] == "ReAssure 2.0"


def test_list_filters_by_qa_status(tmp_path) -> None:  # type: ignore[no-untyped-def]
    c = _client()
    seeded = _seed_wordings(c, tmp_path)
    # Promote one to human_verified
    c.patch(f"/api/admin/wordings/{seeded['a']}/qa",
            json={"status": "human_verified", "notes": "QA passed"},
            headers=_admin_headers())
    r = c.get("/api/admin/wordings?qa_status=human_verified", headers=_admin_headers())
    body = r.json()["data"]
    assert body["count"] == 1
    assert body["wordings"][0]["id"] == seeded["a"]


def test_list_rejects_invalid_qa_status() -> None:
    r = _client().get("/api/admin/wordings?qa_status=garbage", headers=_admin_headers())
    assert r.status_code == 400
    assert "invalid_qa_status" in r.text


def test_list_rejects_invalid_insurer() -> None:
    r = _client().get("/api/admin/wordings?insurer=Made+Up+Insurer", headers=_admin_headers())
    assert r.status_code == 400
    assert "invalid_insurer" in r.text


def test_list_empty_returns_zero_count() -> None:
    r = _client().get("/api/admin/wordings", headers=_admin_headers())
    assert r.status_code == 200
    assert r.json()["data"]["count"] == 0


# ==========================================================================
# GET /wordings/{id}
# ==========================================================================

def test_get_one_returns_full_rules(tmp_path) -> None:  # type: ignore[no-untyped-def]
    c = _client()
    seeded = _seed_wordings(c, tmp_path)
    r = c.get(f"/api/admin/wordings/{seeded['a']}", headers=_admin_headers())
    assert r.status_code == 200
    w = r.json()["data"]["wording"]
    assert w["id"] == seeded["a"]
    # Rules block included in full
    assert "rules" in w
    assert w["rules"]["ped_waiting_months"] == 24


def test_get_one_returns_404_for_unknown_id() -> None:
    r = _client().get("/api/admin/wordings/nonexistent", headers=_admin_headers())
    assert r.status_code == 404
    assert "wording_not_found" in r.text


# ==========================================================================
# PATCH /wordings/{id}/qa
# ==========================================================================

def test_qa_update_promotes_to_human_verified(tmp_path) -> None:  # type: ignore[no-untyped-def]
    c = _client()
    seeded = _seed_wordings(c, tmp_path)
    r = c.patch(
        f"/api/admin/wordings/{seeded['a']}/qa",
        json={"status": "human_verified", "notes": "Reviewed; rules accurate"},
        headers=_admin_headers(),
    )
    assert r.status_code == 200
    w = r.json()["data"]["wording"]
    assert w["qa_status"] == "human_verified"
    assert w["qa_notes"] == "Reviewed; rules accurate"
    assert w["qa_verified_by"] == "admin"
    assert "qa_verified_at" in w


def test_qa_update_flags_needs_review(tmp_path) -> None:  # type: ignore[no-untyped-def]
    c = _client()
    seeded = _seed_wordings(c, tmp_path)
    r = c.patch(
        f"/api/admin/wordings/{seeded['a']}/qa",
        json={"status": "needs_review"},
        headers=_admin_headers(),
    )
    assert r.status_code == 200
    assert r.json()["data"]["wording"]["qa_status"] == "needs_review"


def test_qa_update_rejects_invalid_status(tmp_path) -> None:  # type: ignore[no-untyped-def]
    c = _client()
    seeded = _seed_wordings(c, tmp_path)
    r = c.patch(
        f"/api/admin/wordings/{seeded['a']}/qa",
        json={"status": "garbage"},
        headers=_admin_headers(),
    )
    assert r.status_code == 400
    assert "invalid_qa_status" in r.text


def test_qa_update_returns_404_for_unknown_id() -> None:
    r = _client().patch(
        "/api/admin/wordings/nonexistent/qa",
        json={"status": "human_verified"},
        headers=_admin_headers(),
    )
    assert r.status_code == 404
    assert "wording_not_found" in r.text


# ==========================================================================
# DELETE /wordings/{id}
# ==========================================================================

def test_delete_removes_wording(tmp_path) -> None:  # type: ignore[no-untyped-def]
    c = _client()
    seeded = _seed_wordings(c, tmp_path)
    r = c.delete(f"/api/admin/wordings/{seeded['a']}", headers=_admin_headers())
    assert r.status_code == 200
    assert r.json()["data"]["deleted"] is True
    fake: FakeDb = app.state.db
    assert len(fake.wordings.docs) == 1  # only the other one remains


def test_delete_returns_404_for_unknown_id() -> None:
    r = _client().delete("/api/admin/wordings/nonexistent", headers=_admin_headers())
    assert r.status_code == 404
