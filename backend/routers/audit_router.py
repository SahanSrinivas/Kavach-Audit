"""Stage 6 — Audit. Mocked when USE_MOCKS=true; real engine when false.

Single-DB-read pattern (spec Section 7): pull user + policies in one async
gather, hand to engine.generate_audit() which is pure-Python.

Beta gating (per-user opt-in to the real engine):
  POST /audit/generate?beta=audit-real → if user is in beta_allowlist for
  feature "audit-real", run the real engine even when USE_MOCKS=true.
  GET /audit/latest is unaffected (it's a SELECT, not a generate).

Every audit row written to db.audits carries `engine_mode` ("real"|"mock")
and `beta_invocation` (bool) so Mongo is the source of truth for which
audits were produced by which path.
"""
from __future__ import annotations

import asyncio
import dataclasses
import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from auth import get_current_user, verify_csrf
from mocks.fixtures import make_mock_audit
from services.audit import generate_audit
from services.audit.types import Policy, UserProfile
from services.beta import resolve_engine_mode

logger = logging.getLogger("kavach.audit")

router = APIRouter(prefix="/audit", tags=["audit"])

USE_MOCKS = os.environ.get("USE_MOCKS", "true").lower() == "true"
AUDIT_BETA_FEATURE = "audit-real"


def _ok(data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"success": True, "data": data or {}, "error": None}


async def _generate_audit(
    db: Any,
    user_id: str,
    *,
    mode: str,
    beta_invocation: bool,
) -> dict[str, Any]:
    """Build the audit JSON. `mode` decides the path:
       "mock" → fixture; "real" → services.audit.engine over user + policies.

    The written row carries `engine_mode` + `beta_invocation` for analytics.
    """
    if mode == "mock":
        audit = make_mock_audit(user_id)
        audit["engine_mode"] = "mock"
        audit["beta_invocation"] = beta_invocation
        await db.audits.insert_one(dict(audit))
        audit.pop("_id", None)
        return audit

    user_doc, policy_docs = await asyncio.gather(
        db.users.find_one({"id": user_id}, {"_id": 0}),
        db.policies.find({"user_id": user_id}, {"_id": 0}).to_list(100),
    )
    if not user_doc:
        raise HTTPException(status_code=404, detail="user_not_found")

    profile = UserProfile.from_dict(user_doc)
    policies = [Policy.from_dict(p) for p in policy_docs]

    try:
        result = generate_audit(profile, policies)
    except Exception:  # noqa: BLE001
        logger.exception("audit engine crashed for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="audit_engine_error")

    audit = dataclasses.asdict(result)
    audit["engine_mode"] = "real"
    audit["beta_invocation"] = beta_invocation
    await db.audits.insert_one(dict(audit))
    audit.pop("_id", None)
    return audit


@router.post("/generate", dependencies=[Depends(verify_csrf)])
async def generate_audit_endpoint(
    request: Request,
    current: dict[str, Any] = Depends(get_current_user),
    beta: Optional[str] = Query(default=None),
) -> dict[str, Any]:
    db = request.app.state.db
    mode, beta_invocation = await resolve_engine_mode(
        db=db,
        user_id=current["user_id"],
        beta_param=beta,
        feature=AUDIT_BETA_FEATURE,
        use_mocks_global=USE_MOCKS,
    )
    audit = await _generate_audit(
        db, current["user_id"], mode=mode, beta_invocation=beta_invocation,
    )
    return _ok({"audit": audit})


@router.get("/latest")
async def get_latest(
    request: Request,
    current: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Return the latest audit if one exists, else `{audit: null}`.

    No auto-generate (changed in Phase 2B): generation is explicit via
    POST /audit/generate. The dashboard already guards on `audit && ...`
    and the audit/report page is only reached after Stage 5 awaits the
    generate call, so this is safe.

    No beta gating here — this is a SELECT. Whichever engine ran at
    generate time produced the row stored in db.audits.
    """
    db = request.app.state.db
    audit = await db.audits.find_one(
        {"user_id": current["user_id"]},
        {"_id": 0},
        sort=[("generated_at", -1)],
    )
    return _ok({"audit": audit})
