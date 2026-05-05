"""Life insurance: IRDAI stat packs + CIS/bond PDF extraction + saved schedules."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from auth import get_current_user, verify_csrf
from services.life.extract_schedule import extract_life_schedule
from services.life.llm_schedule import (
    llm_metrics_snapshot,
    llm_refine_life_schedule,
    merge_heuristic_and_llm,
)
from services.life.overlap import build_overlap_hints
from services.life.pdf_text import pdf_bytes_to_text
from services.rate_limit import enforce_extract_rate_limit, rate_limit_metrics_snapshot

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


@router.post("/extract", dependencies=[Depends(enforce_extract_rate_limit)])
async def extract_life_documents(
    cis: Optional[UploadFile] = File(None),
    bond: Optional[UploadFile] = File(None),
    insurer_id: str = Form(""),
) -> dict[str, Any]:
    """Extract a structured Life Schedule from CIS + policy bond PDFs (text + optional OCR)."""
    if cis is None or bond is None:
        raise HTTPException(status_code=400, detail="cis_and_bond_required")

    cis_bytes = await _require_pdf(cis, "cis")
    bond_bytes = await _require_pdf(bond, "bond")

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
