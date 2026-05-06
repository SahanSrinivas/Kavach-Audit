"""Life insurance: IRDAI stat packs + CIS/bond PDF extraction + saved schedules."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from auth import get_current_user, verify_csrf
from services.life.audit.runner import run_life_audit
from services.life.audit.types import LifeScheduleInput, LifeUserProfile
from services.life.extract_schedule import extract_life_schedule
from services.life.recommendations import generate as generate_life_recommendations
from services.life.llm_schedule import (
    llm_metrics_snapshot,
    llm_refine_life_schedule,
    merge_heuristic_and_llm,
)
from services.life.overlap import build_overlap_hints
from services.life.pdf_text import pdf_bytes_to_text
from services.life.preflight import (
    OUTCOME_REJECT as LIFE_PF_REJECT,
    OUTCOME_SKIPPED as LIFE_PF_SKIPPED,
    OUTCOME_STRUCTURAL as LIFE_PF_STRUCTURAL,
    preflight_check_life,
)
from services.parser.preflight import PreflightResult
from services.rate_limit import (
    client_ip_from_request,
    enforce_extract_rate_limit,
    rate_limit_metrics_snapshot,
)

logger = logging.getLogger("kavach.life")

router = APIRouter(prefix="/life", tags=["life"])

LIFE_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "life"

MAX_PDF_BYTES = 15 * 1024 * 1024


def _ok(data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"success": True, "data": data or {}, "error": None}


def _load_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@router.get("/stats/index")
async def life_stats_index() -> dict[str, Any]:
    """FY manifest (same schema as frontend/public/data/life/index.json)."""
    path = LIFE_DATA_DIR / "index.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="life_stats_index_missing")
    return _ok(_load_json(path))


@router.get("/stats/{fy}")
async def life_stats_bundle(fy: str) -> dict[str, Any]:
    """Bundled insurers + sources for one FY key (e.g. 2023-24)."""
    idx_path = LIFE_DATA_DIR / "index.json"
    if not idx_path.is_file():
        raise HTTPException(status_code=404, detail="life_stats_index_missing")
    index = _load_json(idx_path)
    data_files: dict[str, str] = index.get("dataFiles") or {}
    fname = data_files.get(fy)
    if not fname:
        raise HTTPException(status_code=404, detail="fy_not_found")
    path = LIFE_DATA_DIR / fname
    if not path.is_file():
        raise HTTPException(status_code=404, detail="life_bundle_missing")
    return _ok(_load_json(path))


async def _require_pdf(upload: UploadFile, label: str) -> bytes:
    raw = await upload.read()
    if len(raw) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail=f"{label}_too_large")
    name = (upload.filename or "").lower()
    if not name.endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail=f"{label}_must_be_pdf",
        )
    if len(raw) < 64:
        raise HTTPException(status_code=400, detail=f"{label}_empty")
    return raw


def _life_client_ip_hash(request: Request) -> str | None:
    """SHA-256 hex of client IP, truncated — never store raw IPs."""
    ip = client_ip_from_request(request).strip()
    if not ip or ip == "unknown":
        return None
    digest = hashlib.sha256(ip.encode("utf-8")).hexdigest()
    return digest[:32]


def _life_preflight_parse_outcome(pf_outcome: str) -> str:
    """Normalize for Mongo + analytics."""
    if pf_outcome == LIFE_PF_SKIPPED:
        return "skipped"
    if pf_outcome == LIFE_PF_STRUCTURAL:
        return "structural_reject"
    return pf_outcome


async def _log_life_preflight_attempt(
    db: Any,
    *,
    user_id: str | None,
    preflight: PreflightResult,
    ip_hash: str | None,
) -> None:
    await db.parse_attempts.insert_one(
        {
            "_id": str(uuid.uuid4()),
            "user_id": user_id,
            "pipeline": "life",
            "preflight_outcome": _life_preflight_parse_outcome(preflight.outcome),
            "preflight_score": preflight.score,
            "preflight_signals": dict(preflight.signals),
            "preflight_ms": preflight.elapsed_ms,
            "preflight_page_count": preflight.page_count,
            "detected_type_hint": preflight.detected_type_hint,
            "preflight_error": preflight.error,
            "ip_hash": ip_hash,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )


def _life_structural_http_detail(
    err_code: str, page_count: int | None = None,
) -> dict[str, Any]:
    """Structured 400 for life extract structural rejects (parity with policies preflight envelope)."""
    messages: dict[str, str] = {
        "not_a_pdf": "File doesn't appear to be a PDF.",
        "invalid_pdf": "File doesn't appear to be a PDF.",
        "encrypted_pdf": "This PDF is password-protected. Remove the password and try again.",
        "pdf_too_many_pages": (
            "PDF has too many pages. Life policy documents are usually 1-100 pages."
        ),
        "pdf_too_few_pages": "PDF appears empty. Make sure you uploaded the right file.",
        "pdf_too_small": (
            "This file is too small to be a valid PDF. Try re-downloading your CIS or bond."
        ),
        "pdf_too_large": (
            "This file is too large for this upload endpoint. Try a shorter CIS/bond PDF."
        ),
    }
    user_actions = {
        "not_a_pdf": "Upload a real PDF (CIS or policy bond from your insurer).",
        "invalid_pdf": "Upload a real PDF (CIS or policy bond from your insurer).",
        "encrypted_pdf": "Remove PDF password protection and upload again.",
        "pdf_too_many_pages": "Use the CIS or bond PDF (usually a few pages), not a full wording pack.",
        "pdf_too_few_pages": "Re-download the CIS or bond from your insurer portal or email.",
        "pdf_too_small": "Ensure the PDF downloaded completely and wasn't truncated.",
        "pdf_too_large": "Compress or split large files per insurer guidance, or use a smaller excerpt.",
    }
    api_err = err_code if err_code != "invalid_pdf" else "not_a_pdf"
    return {
        "error": api_err,
        "message": messages.get(err_code, messages["invalid_pdf"]),
        "user_action": user_actions.get(err_code, user_actions["invalid_pdf"]),
        "page_count": page_count,
    }


def _life_not_insurance_detail(preflight: PreflightResult) -> dict[str, Any]:
    return {
        "error": "not_insurance_document",
        "preflight_score": preflight.score,
        "detected_type_hint": preflight.detected_type_hint,
        "message": (
            "This doesn't look like a life insurance document. We expect a "
            "Customer Information Sheet (CIS) or policy bond from an Indian life insurer."
        ),
        "user_action": (
            "Try your CIS or policy bond — usually a 1-3 page PDF with "
            "sum assured, premium, and nominee details."
        ),
    }


async def _life_preflight_gate(
    pdf_bytes: bytes,
    *,
    db: Any,
    user_id: str | None,
    ip_hash: str | None,
) -> PreflightResult:
    outcome = preflight_check_life(pdf_bytes)
    await _log_life_preflight_attempt(db, user_id=user_id, preflight=outcome, ip_hash=ip_hash)
    if outcome.outcome == LIFE_PF_STRUCTURAL:
        raw_err = outcome.error or "invalid_pdf"
        raise HTTPException(
            status_code=400,
            detail=_life_structural_http_detail(raw_err, outcome.page_count or None),
        )
    if outcome.outcome == LIFE_PF_REJECT:
        raise HTTPException(status_code=400, detail=_life_not_insurance_detail(outcome))
    return outcome


@router.post("/extract")
async def extract_life_documents(
    request: Request,
    cis: Optional[UploadFile] = File(None),
    bond: Optional[UploadFile] = File(None),
    insurer_id: str = Form(""),
) -> dict[str, Any]:
    """Extract a structured Life Schedule from CIS + policy bond PDFs (text + optional OCR)."""
    if cis is None or bond is None:
        raise HTTPException(status_code=400, detail="cis_and_bond_required")

    cis_bytes = await _require_pdf(cis, "cis")
    bond_bytes = await _require_pdf(bond, "bond")

    db = request.app.state.db
    user_id_life_extract: str | None = None
    ip_hash = _life_client_ip_hash(request)

    await _life_preflight_gate(
        cis_bytes, db=db, user_id=user_id_life_extract, ip_hash=ip_hash,
    )
    await _life_preflight_gate(
        bond_bytes, db=db, user_id=user_id_life_extract, ip_hash=ip_hash,
    )

    # Rate limit counts only uploads that survived preflight (cheap reject path is free).
    enforce_extract_rate_limit(request)

    try:
        cis_text = pdf_bytes_to_text(cis_bytes, cis.filename or "cis.pdf")
        bond_text = pdf_bytes_to_text(bond_bytes, bond.filename or "bond.pdf")
    except RuntimeError as e:
        logger.warning("life.extract.pdf_error error=%s", e)
        raise HTTPException(status_code=500, detail="pdf_engine_unavailable") from e
    except Exception as e:  # pragma: no cover — fitz errors
        logger.warning("life.extract.read_failed error=%s", e)
        raise HTTPException(status_code=422, detail="pdf_unreadable") from e

    hint = insurer_id.strip() or None
    result = extract_life_schedule(cis_text, bond_text, insurer_id=hint)

    meta_extra: dict[str, Any] = {}
    llm_on = os.environ.get("LIFE_EXTRACT_LLM_FALLBACK", "").lower() in ("1", "true", "yes")
    llm_threshold = float(os.environ.get("LIFE_EXTRACT_LLM_THRESHOLD", "0.45"))
    merge_threshold = float(os.environ.get("LIFE_EXTRACT_LLM_MERGE_THRESHOLD", "0.45"))

    if llm_on and (result.get("confidence") or {}).get("overall", 1) < llm_threshold:
        llm_out = await llm_refine_life_schedule(cis_text, bond_text, hint)
        if llm_out:
            result = merge_heuristic_and_llm(result, llm_out, threshold=merge_threshold)
            meta_extra["llmRefinement"] = True
            meta_extra["llmModel"] = os.environ.get("LIFE_LLM_MODEL", "claude-3-5-haiku-20241022")
        else:
            logger.info("life.extract.llm_skipped_or_failed metrics=%s", llm_metrics_snapshot())

    payload = {
        **result,
        "meta": {
            "cisFilename": cis.filename,
            "bondFilename": bond.filename,
            "insurerId": hint,
            "extractedAt": datetime.now(timezone.utc).isoformat(),
            "textCharsTotal": (result.get("textChars") or {}).get("cis", 0)
            + (result.get("textChars") or {}).get("bond", 0),
            **meta_extra,
        },
    }
    logger.info(
        "life.extract.ok insurer_hint=%s overall_conf=%s llm=%s rate_limit=%s",
        hint,
        result.get("confidence", {}).get("overall"),
        meta_extra.get("llmRefinement", False),
        rate_limit_metrics_snapshot(),
    )
    return _ok(payload)


@router.get("/overlap-hints")
async def life_overlap_hints(
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Education-only hints comparing latest saved life schedule vs health policies."""
    db = request.app.state.db
    cursor = db.life_schedules.find({"user_id": user["user_id"]}).sort("created_at", -1).limit(1)
    docs = await cursor.to_list(1)
    latest_doc = docs[0] if docs else None
    life_schedule = (latest_doc.get("life_schedule") if latest_doc else None) or None

    policies = await db.policies.find({"user_id": user["user_id"]}).to_list(length=100)
    data = build_overlap_hints(life_schedule, policies)
    data["lastRefreshedAt"] = (
        latest_doc.get("created_at") if latest_doc and latest_doc.get("created_at") else datetime.now(timezone.utc).isoformat()
    )
    return _ok(data)


# ----- Persisted schedules (authenticated) -----


class LifeScheduleSaveBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    life_schedule: dict[str, Any] = Field(alias="lifeSchedule")
    confidence: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
    field_confidence_ui: list[dict[str, Any]] = Field(default_factory=list, alias="fieldConfidenceUi")


@router.post("/schedules")
async def save_life_schedule(
    request: Request,
    body: LifeScheduleSaveBody,
    user: dict = Depends(get_current_user),
    _: None = Depends(verify_csrf),
) -> dict[str, Any]:
    """Persist an extracted life schedule for the logged-in user."""
    db = request.app.state.db
    doc: dict[str, Any] = {
        "user_id": user["user_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "life_schedule": body.life_schedule,
        "confidence": body.confidence,
        "warnings": body.warnings,
        "meta": body.meta,
        "field_confidence_ui": body.field_confidence_ui,
    }
    result = await db.life_schedules.insert_one(doc)
    logger.info("life.schedule.saved user=%s id=%s", user["user_id"], result.inserted_id)
    return _ok({"id": str(result.inserted_id)})


@router.get("/schedules")
async def list_life_schedules(
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Recent saved life schedules for the current user."""
    db = request.app.state.db
    cursor = db.life_schedules.find({"user_id": user["user_id"]}).sort("created_at", -1).limit(25)
    items: list[dict[str, Any]] = []
    async for row in cursor:
        items.append(
            {
                "id": str(row["_id"]),
                "createdAt": row.get("created_at"),
                "meta": row.get("meta") or {},
                "overallConfidence": (row.get("confidence") or {}).get("overall"),
            }
        )
    return _ok({"schedules": items})


@router.get("/schedules/{schedule_id}")
async def get_life_schedule(
    request: Request,
    schedule_id: str,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Load one saved schedule (must belong to the user)."""
    try:
        oid = ObjectId(schedule_id)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail="invalid_schedule_id") from None

    db = request.app.state.db
    row = await db.life_schedules.find_one({"_id": oid, "user_id": user["user_id"]})
    if not row:
        raise HTTPException(status_code=404, detail="schedule_not_found")

    data = {
        "id": str(row["_id"]),
        "lifeSchedule": row.get("life_schedule"),
        "confidence": row.get("confidence") or {},
        "warnings": row.get("warnings") or [],
        "meta": row.get("meta") or {},
        "fieldConfidenceUi": row.get("field_confidence_ui") or [],
        "createdAt": row.get("created_at"),
    }
    return _ok(data)


@router.post("/audit", dependencies=[Depends(verify_csrf)])
async def generate_life_audit(
    request: Request,
    current: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Run life audit from the user's latest saved life schedule."""
    db = request.app.state.db
    schedule_row = await db.life_schedules.find_one(
        {"user_id": current["user_id"]},
        sort=[("created_at", -1)],
    )
    if not schedule_row:
        raise HTTPException(status_code=404, detail="life_schedule_not_found")

    user_doc = await db.users.find_one({"id": current["user_id"]}, {"_id": 0})
    if not user_doc:
        user_doc = await db.users.find_one({"user_id": current["user_id"]}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="user_not_found")

    profile = LifeUserProfile.from_dict(user_doc)
    schedule = LifeScheduleInput.from_dict(
        schedule_row.get("life_schedule") or {},
        schedule_id=str(schedule_row.get("_id") or ""),
    )
    life_policy_count = await db.life_schedules.count_documents({"user_id": current["user_id"]})
    has_pa_anywhere = (await db.policies.count_documents({"user_id": current["user_id"], "type": {"$in": ["pa", "personal_accident"]}})) > 0

    result = run_life_audit(
        profile,
        schedule,
        life_policy_count=life_policy_count,
        has_personal_accident_anywhere=has_pa_anywhere,
    )
    audit_doc = result.to_dict()
    audit_doc["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.life_audits.insert_one(dict(audit_doc))
    return _ok({"audit": audit_doc})


@router.get("/audit/latest")
async def get_latest_life_audit(
    request: Request,
    current: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Return most recent saved life audit for the logged-in user."""
    db = request.app.state.db
    row = await db.life_audits.find_one(
        {"user_id": current["user_id"]},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    if not row:
        raise HTTPException(status_code=404, detail="life_audit_not_found")
    return _ok({"audit": row})


@router.get("/recommendations")
async def get_life_recommendations(
    request: Request,
    current: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Generate recommendations from the user's latest life audit."""
    db = request.app.state.db
    audit_row = await db.life_audits.find_one(
        {"user_id": current["user_id"]},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    if not audit_row:
        raise HTTPException(status_code=404, detail="life_audit_not_found")

    user_doc = await db.users.find_one({"id": current["user_id"]}, {"_id": 0})
    if not user_doc:
        user_doc = await db.users.find_one({"user_id": current["user_id"]}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="user_not_found")

    profile = LifeUserProfile.from_dict(user_doc)
    recommendations = generate_life_recommendations(audit_row, profile)
    return _ok(
        {
            "recommendations": [rec.to_dict() for rec in recommendations],
        }
    )
