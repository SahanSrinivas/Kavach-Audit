"""Admin routes — basic password gate for early debugging.

Auth: pass `Authorization: Bearer <ADMIN_PASSWORD>` header. Wrong/missing → 401.
"""
from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from pydantic import BaseModel

from services import wordings as wordings_service
from services.beta import (
    VALID_FEATURES,
    add_beta_user,
    list_beta_users,
    remove_beta_user,
)
from services.parser import ParseFailureError, parse_policy_pdf
from services.parser.canonical_vocabulary import CANONICAL_INSURER_NAMES

logger = logging.getLogger("kavach.beta")
wordings_logger = logging.getLogger("kavach.wordings")

# Cap on PDF size for the admin parse endpoint. Wording PDFs are
# typically 500 KB - 2 MB; 10 MB is a generous safety cap that prevents
# accidentally feeding a giant scanned-image PDF to Claude (would blow
# the API token budget). Mirror the user-upload cap from policies_router.
MAX_WORDING_PDF_BYTES = 10 * 1024 * 1024

router = APIRouter(prefix="/admin", tags=["admin"])


def _check(authorization: Optional[str]) -> str:
    """Validates the bearer token, returns the admin identity tag.

    Returns "admin" on success — used for the `added_by` audit field on
    beta_allowlist rows. We don't have per-admin identities yet (single
    shared password), so all admin actions are attributed to "admin".
    """
    expected = os.environ.get("ADMIN_PASSWORD", "")
    if not expected:
        raise HTTPException(status_code=503, detail="admin_disabled")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="admin_unauthorized")
    token = authorization[7:].strip()
    if not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="admin_unauthorized")
    return "admin"


def _ok(data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"success": True, "data": data or {}, "error": None}


@router.get("/users")
async def list_users(
    request: Request, authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _check(authorization)
    db = request.app.state.db
    rows = await db.users.find({}, {"_id": 0}).to_list(500)
    return {"success": True, "data": {"users": rows, "count": len(rows)}, "error": None}


@router.get("/audits")
async def list_audits(
    request: Request, authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _check(authorization)
    db = request.app.state.db
    rows = await db.audits.find({}, {"_id": 0}).to_list(500)
    return {"success": True, "data": {"audits": rows, "count": len(rows)}, "error": None}


# ---------- Beta allowlist CRUD ----------

class BetaAllowlistAdd(BaseModel):
    user_id: str
    feature: str
    notes: Optional[str] = None


class BetaAllowlistRemove(BaseModel):
    user_id: str
    feature: str


@router.post("/beta-allowlist")
async def beta_allowlist_add(
    body: BetaAllowlistAdd,
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    """Add a user to the beta allowlist for a specific feature.

    Idempotent: duplicate (user_id, feature) raises pymongo
    DuplicateKeyError due to the unique compound index — we surface that
    as 409 Conflict so the admin sees they're re-adding.
    """
    admin_id = _check(authorization)
    if body.feature not in VALID_FEATURES:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_feature",
                    "message": f"feature must be one of {sorted(VALID_FEATURES)}"},
        )
    db = request.app.state.db
    try:
        doc = await add_beta_user(
            db, body.user_id, body.feature, added_by=admin_id, notes=body.notes,
        )
    except Exception as e:  # noqa: BLE001
        # Most likely a DuplicateKeyError from the unique index. We don't
        # import pymongo.errors at the router boundary to keep the import
        # graph thin; surface as 409 with the original message.
        if "duplicate" in str(e).lower() or "E11000" in str(e):
            raise HTTPException(
                status_code=409,
                detail={"error": "already_allowlisted",
                        "message": f"user {body.user_id} already has {body.feature}"},
            )
        raise
    return _ok({"added": True, "entry": doc})


@router.delete("/beta-allowlist")
async def beta_allowlist_remove(
    body: BetaAllowlistRemove,
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    admin_id = _check(authorization)
    if body.feature not in VALID_FEATURES:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_feature",
                    "message": f"feature must be one of {sorted(VALID_FEATURES)}"},
        )
    db = request.app.state.db
    deleted = await remove_beta_user(db, body.user_id, body.feature)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_allowlisted",
                    "message": f"user {body.user_id} not on {body.feature} allowlist"},
        )
    logger.info("beta.admin_remove admin=%s user_id=%s feature=%s",
                admin_id, body.user_id, body.feature)
    return _ok({"removed": True})


@router.get("/beta-allowlist")
async def beta_allowlist_list(
    request: Request,
    feature: Optional[str] = Query(default=None),
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _check(authorization)
    if feature and feature not in VALID_FEATURES:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_feature",
                    "message": f"feature must be one of {sorted(VALID_FEATURES)}"},
        )
    db = request.app.state.db
    rows = await list_beta_users(db, feature=feature)
    return _ok({"entries": rows, "count": len(rows)})


# ==========================================================================
# Wordings DB CRUD (Phase 1.5)
# ==========================================================================
# Admin-only endpoints. The CLI scripts at scripts/parse_wording.py and
# scripts/verify_wording.py drive these. Bearer-auth-protected like the
# other admin endpoints.
#
# Workflow:
#   1. POST   /api/admin/wordings/parse  → admin parses a wording PDF on
#      disk; result stored as qa_status="auto_parsed" pending review.
#   2. GET    /api/admin/wordings        → admin lists pending review.
#   3. GET    /api/admin/wordings/{id}   → admin reads the full rules
#      block for a single wording.
#   4. PATCH  /api/admin/wordings/{id}/qa → admin promotes to
#      "human_verified" or flags "needs_review".
#   5. DELETE /api/admin/wordings/{id}   → rare; remove a stale wording.

class WordingParseRequest(BaseModel):
    """Body for POST /api/admin/wordings/parse.

    `pdf_path` is a SERVER-LOCAL path — the admin's machine, since this
    is run via the CLI. The endpoint reads the file from disk and feeds
    bytes to the parser. There's no upload-via-multipart; admins use
    the CLI which writes PDFs to a local path first.
    """
    pdf_path: str
    insurer_canonical: str
    plan_name: str
    source_url: Optional[str] = None
    wording_uin: Optional[str] = None
    wording_version: Optional[str] = None


class WordingQAUpdate(BaseModel):
    """Body for PATCH /api/admin/wordings/{id}/qa."""
    status: str
    notes: Optional[str] = None


def _read_pdf_from_disk(pdf_path: str) -> bytes:
    """Validate + read a PDF from a server-local path. Admin auth gates
    arbitrary file reads (an attacker with ADMIN_PASSWORD can already
    run anything), so this just gives clear UX errors for the typical
    'wrong path' / 'not a PDF' / 'too large' mistakes."""
    p = Path(pdf_path).expanduser()
    if not p.exists():
        raise HTTPException(
            status_code=400,
            detail={"error": "pdf_not_found", "message": f"no file at {pdf_path!r}"},
        )
    if not p.is_file():
        raise HTTPException(
            status_code=400,
            detail={"error": "pdf_not_a_file", "message": f"{pdf_path!r} is not a regular file"},
        )
    if p.suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=400,
            detail={"error": "pdf_wrong_extension",
                    "message": f"{pdf_path!r} doesn't end in .pdf"},
        )
    size = p.stat().st_size
    if size > MAX_WORDING_PDF_BYTES:
        raise HTTPException(
            status_code=413,
            detail={"error": "pdf_too_large",
                    "message": f"{size:,} bytes exceeds {MAX_WORDING_PDF_BYTES:,} cap"},
        )
    return p.read_bytes()


@router.post("/wordings/parse")
async def wording_parse(
    body: WordingParseRequest,
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    """Parse a wording PDF from disk + store the result.

    Long-running (5-15s for a typical wording PDF — Claude API call).
    Cost: ~₹15-30 per parse. Stored with qa_status="auto_parsed";
    admin reviews via GET, promotes via PATCH /qa.
    """
    admin_id = _check(authorization)

    if body.insurer_canonical not in CANONICAL_INSURER_NAMES:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_insurer_canonical",
                    "message": f"{body.insurer_canonical!r} is not in CANONICAL_INSURER_NAMES. "
                               f"Add it to canonical_vocabulary.py first."},
        )

    pdf_bytes = _read_pdf_from_disk(body.pdf_path)
    filename = Path(body.pdf_path).name
    wordings_logger.info(
        "wordings.parse_start admin=%s filename=%s file_kb=%d insurer=%s plan=%s",
        admin_id, filename, len(pdf_bytes) // 1024,
        body.insurer_canonical, body.plan_name,
    )

    try:
        parsed = await parse_policy_pdf(pdf_bytes, filename)
    except ParseFailureError as e:
        wordings_logger.warning(
            "wordings.parse_failed filename=%s error_type=%s",
            filename, e.error_type,
        )
        raise HTTPException(
            status_code=502,
            detail={"error": "parse_failure",
                    "error_type": e.error_type,
                    "message": str(e)},
        )

    # Defensive cross-check: if the parser extracted a different insurer
    # than what the admin supplied, log it but use the admin's value.
    # Admins know better than the parser (e.g., insurer name doesn't
    # appear cleanly on the cover page; admin already verified the doc).
    if parsed.insurer_name != body.insurer_canonical and parsed.insurer_name != "_UNKNOWN":
        wordings_logger.warning(
            "wordings.insurer_mismatch admin_supplied=%r parser_extracted=%r filename=%s",
            body.insurer_canonical, parsed.insurer_name, filename,
        )

    # Compose the wording document via the shared composer (single
    # source of truth — also used by scripts/parse_wording.py --dry-run).
    wording_doc = wordings_service.compose_wording_doc(
        parsed,
        insurer_canonical=body.insurer_canonical,
        plan_name=body.plan_name,
        source_filename=filename,
        source_url=body.source_url,
        wording_uin=body.wording_uin,
        wording_version=body.wording_version,
    )

    db = request.app.state.db
    wording_id = await wordings_service.upsert_wording(db, wording_doc)
    stored = await wordings_service.get_wording(db, wording_id)
    return _ok({"wording_id": wording_id, "wording": stored})


@router.get("/wordings")
async def wordings_list(
    request: Request,
    qa_status: Optional[str] = Query(default=None),
    insurer: Optional[str] = Query(default=None),
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    """List wordings, optionally filtered by qa_status or insurer."""
    _check(authorization)
    if qa_status and qa_status not in wordings_service.VALID_QA_STATUSES:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_qa_status",
                    "message": f"qa_status must be one of "
                               f"{sorted(wordings_service.VALID_QA_STATUSES)}"},
        )
    if insurer and insurer not in CANONICAL_INSURER_NAMES:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_insurer",
                    "message": f"{insurer!r} is not in CANONICAL_INSURER_NAMES"},
        )
    db = request.app.state.db
    rows = await wordings_service.list_wordings(
        db, insurer_canonical=insurer, qa_status=qa_status,
    )
    return _ok({"wordings": rows, "count": len(rows)})


@router.get("/wordings/{wording_id}")
async def wordings_get(
    wording_id: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    """Fetch one wording by id (full rules block included)."""
    _check(authorization)
    db = request.app.state.db
    doc = await wordings_service.get_wording(db, wording_id)
    if doc is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "wording_not_found", "message": f"no wording with id={wording_id!r}"},
        )
    return _ok({"wording": doc})


@router.patch("/wordings/{wording_id}/qa")
async def wordings_update_qa(
    wording_id: str,
    body: WordingQAUpdate,
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    """Promote a wording to human_verified, or flag it as needs_review."""
    admin_id = _check(authorization)
    if body.status not in wordings_service.VALID_QA_STATUSES:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_qa_status",
                    "message": f"status must be one of "
                               f"{sorted(wordings_service.VALID_QA_STATUSES)}"},
        )
    db = request.app.state.db
    matched = await wordings_service.update_qa_status(
        db, wording_id, body.status, admin_id=admin_id, notes=body.notes,
    )
    if not matched:
        raise HTTPException(
            status_code=404,
            detail={"error": "wording_not_found", "message": f"no wording with id={wording_id!r}"},
        )
    updated = await wordings_service.get_wording(db, wording_id)
    return _ok({"wording": updated})


@router.delete("/wordings/{wording_id}")
async def wordings_delete(
    wording_id: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    """Remove a wording. Rare — typically when a plan is fully
    discontinued or the parse was corrupt and we want to re-parse fresh."""
    _check(authorization)
    db = request.app.state.db
    deleted = await wordings_service.delete_wording(db, wording_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail={"error": "wording_not_found", "message": f"no wording with id={wording_id!r}"},
        )
    return _ok({"deleted": True})
