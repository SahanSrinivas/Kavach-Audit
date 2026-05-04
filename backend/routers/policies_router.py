"""Stage 4 — Existing policies. Real Claude PDF parser when USE_MOCKS=false.

When USE_MOCKS=true (default in dev), returns hardcoded mock_parsed_policy.
When USE_MOCKS=false, calls services.parser.parse_policy_pdf which sends
the PDF to Anthropic's Claude API. A SHA256 cache short-circuits repeat
uploads of the same file, and parse failures are recorded to
db.parse_failures with structured error_type for triage.

Env vars:
  USE_MOCKS=true|false                    — toggle real-vs-mock parsing
  PARSER_FALLBACK_TO_MOCK_ON_ERROR=true|false  — soft-launch safety net
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel

from auth import get_current_user, verify_csrf
from mocks.fixtures import make_mock_parsed_policy
from services.beta import resolve_engine_mode
from services.parser import ParseFailureError, parse_policy_pdf
from services.parser.response_validator import to_engine_shape

logger = logging.getLogger("kavach.parser")

router = APIRouter(prefix="/policies", tags=["policies"])

USE_MOCKS = os.environ.get("USE_MOCKS", "true").lower() == "true"
FALLBACK_TO_MOCK = os.environ.get("PARSER_FALLBACK_TO_MOCK_ON_ERROR", "false").lower() == "true"
PARSER_BETA_FEATURE = "parser-real"

UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
PARSE_LIMIT_PER_HOUR = 5
MAX_PDF_BYTES = 15 * 1024 * 1024


def _ok(data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"success": True, "data": data or {}, "error": None}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# TODO(rate-limit-after-cache-check): the rate-limit insertion fires
# before the SHA256 cache check, so cached re-uploads still consume a
# slot. Out of scope for this pass; revisit when we next touch this
# router. Move parse_attempts.insert_one() to after the cache miss.
async def _check_parse_rate_limit(db: Any, user_id: str) -> None:
    since = _iso(_utcnow() - timedelta(hours=1))
    count = await db.parse_attempts.count_documents(
        {"user_id": user_id, "created_at": {"$gte": since}}
    )
    if count >= PARSE_LIMIT_PER_HOUR:
        raise HTTPException(status_code=429, detail="parse_rate_limited")


async def _record_failure(
    db: Any, user_id: str, sha: str, filename: str,
    error_type: str, message: str,
) -> None:
    """Structured logging for triage. Never includes PDF content."""
    await db.parse_failures.insert_one({
        "_id": str(uuid.uuid4()),
        "user_id": user_id,
        "sha": sha,
        "filename": filename,
        "error_type": error_type,
        "message": message,
        "created_at": _iso(_utcnow()),
    })


async def _build_parsed_policy(
    pdf_bytes: bytes,
    user_id: str,
    raw_path: str,
    filename: str,
    db: Any,
    sha: str,
    *,
    mode: str,
    beta_invocation: bool,
) -> dict[str, Any]:
    """Returns the policy dict ready to insert into db.policies.

    Two-layer storage shape (per Step 2 architecture):
      - parsed_fields: flat shape the audit engine reads
      - parser_output: full rich shape from Claude (for "show your work"
                        UX and future analytics)
    Mock branch produces only parsed_fields (parser_output absent),
    matching the existing fixture exactly. Both branches stamp
    `parser_mode` + `beta_invocation` so Mongo records which path ran.
    """
    if mode == "mock":
        logger.info("parser.mock filename=%s file_kb=%d", filename, len(pdf_bytes) // 1024)
        await asyncio.sleep(4)  # preserve UX timing of the mocked parse
        doc = make_mock_parsed_policy(user_id=user_id, raw_pdf_path=raw_path)
        doc["parser_mode"] = "mock"
        doc["beta_invocation"] = beta_invocation
        return doc

    try:
        parsed = await parse_policy_pdf(pdf_bytes, filename)
    except ParseFailureError as e:
        await _record_failure(db, user_id, sha, filename, e.error_type, str(e))
        if FALLBACK_TO_MOCK:
            logger.warning("parser.fallback_to_mock filename=%s error=%s",
                           filename, e.error_type)
            doc = make_mock_parsed_policy(user_id=user_id, raw_pdf_path=raw_path)
            doc["parser_mode"] = "mock"  # fallback served mock
            doc["beta_invocation"] = beta_invocation
            return doc
        raise HTTPException(status_code=502, detail={
            "error": "parse_failure",
            "error_type": e.error_type,
            "message": str(e),
        })

    # Convert ParsedPolicy → storage dict with both rich + flat shapes.
    rich = parsed.model_dump()
    flat = to_engine_shape(parsed)

    # `type` is the engine-facing 5-value enum; the parser produces a
    # finer-grained policy_type. Map down for engine compatibility.
    engine_type = _engine_type_for(parsed.policy_type)

    return {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        # ---- engine-facing top-level (matches mock) ----
        "type": engine_type,
        "insurer": parsed.insurer_name,           # canonical → CSR table key
        "policy_name": _derive_policy_name(parsed),
        "policy_number": parsed.policy_number,
        "sum_insured": parsed.sum_insured,
        "premium": parsed.premium_annual,
        "start_date": parsed.policy_start_date,
        "end_date": parsed.policy_end_date,
        "raw_pdf_path": raw_path,
        "parsed_fields": flat,                    # ← engine reads this
        "is_employer_group": parsed.is_employer_group,
        # ---- rich extras (frontend ignores; future analytics) ----
        "parser_output": rich,
        "insurer_name_raw": parsed.insurer_name_raw,
        "covered_members": [m.model_dump() for m in parsed.covered_members],
        "parse_confidence": parsed.confidence.model_dump(),
        # ---- mode tracking ----
        "parser_mode": "real",
        "beta_invocation": beta_invocation,
        # ---- metadata ----
        "created_at": _iso(_utcnow()),
        "source": "upload",
    }


def _engine_type_for(policy_type: str) -> str:
    """Map the parser's fine-grained policy_type (14 values) to the engine's
    coarser type enum used in coverage/cost/claim-readiness/gap scoring.

    Notes on the non-obvious collapses:
      - super_topup → health: engine treats it as health for scoring; a
        separate "is_topup" finding is planned for the next pass.
      - ulip → endowment: both are investment-disguised-as-insurance from
        the engine's POV; coverage.py credits both at 30% face value.
      - personal_accident, critical_illness stay in their own categories
        (pa, ci) so Gap Score can flag them as missing-but-required.
    """
    mapping = {
        "health_individual":     "health",
        "health_family_floater": "health",
        "health_senior":         "health",
        "super_topup":           "health",
        "term_life":             "term",
        "endowment":             "endowment",
        "ulip":                  "endowment",
        "motor_private_car":     "motor",
        "motor_two_wheeler":     "motor",
        "personal_accident":     "pa",
        "critical_illness":      "ci",
        "travel_international":  "travel",
        "travel_domestic":       "travel",
        "home":                  "home",
    }
    return mapping.get(policy_type, "other")


def _derive_policy_name(parsed: Any) -> str:
    """Best-effort product name from the rich parse. Falls back to insurer
    name + policy_type so the UI always has something to display."""
    return f"{parsed.insurer_name} {parsed.policy_type.replace('_', ' ').title()}"


# ---------- Path A: Upload ----------
@router.post("/upload", dependencies=[Depends(verify_csrf)])
async def upload_policy(
    request: Request,
    file: UploadFile = File(...),
    current: dict[str, Any] = Depends(get_current_user),
    beta: Optional[str] = Query(default=None),
) -> dict[str, Any]:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="only_pdf_supported")
    db = request.app.state.db
    mode, beta_invocation = await resolve_engine_mode(
        db=db,
        user_id=current["user_id"],
        beta_param=beta,
        feature=PARSER_BETA_FEATURE,
        use_mocks_global=USE_MOCKS,
    )

    await _check_parse_rate_limit(db, current["user_id"])

    raw = await file.read()
    if len(raw) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="file_too_large")

    sha = hashlib.sha256(raw).hexdigest()
    safe_name = f"{current['user_id']}_{sha[:16]}.pdf"
    target = UPLOADS_DIR / safe_name
    if not target.exists():
        target.write_bytes(raw)

    # Track the parse attempt for rate-limiting
    # TODO(rate-limit-after-cache-check): see _check_parse_rate_limit comment
    await db.parse_attempts.insert_one({
        "_id": str(uuid.uuid4()),
        "user_id": current["user_id"],
        "sha": sha,
        "created_at": _iso(_utcnow()),
    })

    # Cache hit: re-uploads of the same PDF don't re-call Claude
    cached = await db.policies.find_one(
        {"user_id": current["user_id"], "raw_sha": sha}, {"_id": 0}
    )
    if cached:
        logger.info("parser.cache_hit user=%s sha=%s", current["user_id"], sha[:8])
        return _ok({"policy": cached, "cached": True})

    logger.info("parser.cache_miss user=%s sha=%s file_kb=%d",
                current["user_id"], sha[:8], len(raw) // 1024)
    parsed_doc = await _build_parsed_policy(
        pdf_bytes=raw,
        mode=mode,
        beta_invocation=beta_invocation,
        user_id=current["user_id"],
        raw_path=str(target),
        filename=file.filename,
        db=db,
        sha=sha,
    )
    parsed_doc["raw_sha"] = sha
    await db.policies.insert_one(dict(parsed_doc))
    parsed_doc.pop("_id", None)
    return _ok({"policy": parsed_doc, "cached": False})


# ---------- Path B: Quick declaration ----------
class DeclarePolicy(BaseModel):
    type: str  # health | term | endowment | motor | travel
    insurer: str
    sum_insured: int
    premium: int
    notes: Optional[str] = None


@router.post("/declare", dependencies=[Depends(verify_csrf)])
async def declare_policy(
    body: DeclarePolicy, request: Request,
    current: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    db = request.app.state.db
    pid = str(uuid.uuid4())
    doc = {
        "id": pid,
        "user_id": current["user_id"],
        "type": body.type,
        "insurer": body.insurer,
        "sum_insured": body.sum_insured,
        "premium": body.premium,
        "notes": body.notes,
        "source": "declared",
        "parsed_fields": None,
        "created_at": _iso(_utcnow()),
    }
    await db.policies.insert_one(dict(doc))
    doc.pop("_id", None)
    return _ok({"policy": doc})


# ---------- List user's policies ----------
@router.get("")
async def list_policies(
    request: Request, current: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    db = request.app.state.db
    rows = await db.policies.find(
        {"user_id": current["user_id"]}, {"_id": 0}
    ).to_list(100)
    return _ok({"policies": rows})


@router.delete("/{policy_id}", dependencies=[Depends(verify_csrf)])
async def delete_policy(
    policy_id: str, request: Request,
    current: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    db = request.app.state.db
    res = await db.policies.delete_one(
        {"id": policy_id, "user_id": current["user_id"]}
    )
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="policy_not_found")
    return _ok({"deleted": True})
