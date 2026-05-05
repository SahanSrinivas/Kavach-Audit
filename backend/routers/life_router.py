"""Life insurance: IRDAI stat packs + CIS/bond PDF extraction (heuristic, no LLM)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from services.life.extract_schedule import extract_life_schedule
from services.life.pdf_text import pdf_bytes_to_text

logger = logging.getLogger("kavach.life")

router = APIRouter(prefix="/life", tags=["life"])

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
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


@router.post("/extract")
async def extract_life_documents(
    cis: Optional[UploadFile] = File(None),
    bond: Optional[UploadFile] = File(None),
    insurer_id: str = Form(""),
) -> dict[str, Any]:
    """Extract a structured Life Schedule from CIS + policy bond PDFs (plain-text heuristics)."""
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

    payload = {
        **result,
        "meta": {
            "cisFilename": cis.filename,
            "bondFilename": bond.filename,
            "insurerId": hint,
            "extractedAt": datetime.now(timezone.utc).isoformat(),
        },
    }
    logger.info(
        "life.extract.ok insurer_hint=%s overall_conf=%s",
        hint,
        result.get("confidence", {}).get("overall"),
    )
    return _ok(payload)
