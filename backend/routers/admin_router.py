"""Admin routes — basic password gate for early debugging.

Auth: pass `Authorization: Bearer <ADMIN_PASSWORD>` header. Wrong/missing → 401.
"""
from __future__ import annotations

import logging
import os
import secrets
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from pydantic import BaseModel

from services.beta import (
    VALID_FEATURES,
    add_beta_user,
    list_beta_users,
    remove_beta_user,
)

logger = logging.getLogger("kavach.beta")

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
