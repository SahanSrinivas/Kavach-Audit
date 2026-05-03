"""Stage 7 — Recommendations. Skeleton mode: returns 3 hardcoded cards.

TODO(real-quotes): When USE_MOCKS=false, fetch live quotes via Riskcovry API
or equivalent, ranked by FIT (not cheapest), with transparent commission
disclosure per card. Personal info collection (full name, DOB, gender, PIN,
email) for the chosen quote happens in a follow-up endpoint.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr

from auth import get_current_user, verify_csrf
from mocks.fixtures import make_mock_recommendations

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

USE_MOCKS = os.environ.get("USE_MOCKS", "true").lower() == "true"


def _ok(data=None):
    return {"success": True, "data": data or {}, "error": None}


def _iso():
    return datetime.now(timezone.utc).isoformat()


@router.get("")
async def get_recommendations(
    request: Request,
    finding_id: Optional[str] = None,
    current=Depends(get_current_user),
):
    db = request.app.state.db
    options = make_mock_recommendations(finding_id)
    rec = {
        "id": str(uuid.uuid4()),
        "user_id": current["user_id"],
        "finding_id": finding_id,
        "options": options,
        "generated_at": _iso(),
    }
    await db.recommendations.insert_one(dict(rec))
    rec.pop("_id", None)
    return _ok(rec)


# ---------- Stage 7 mocked "Buy" — early-access email capture ----------
class EarlyAccessSignup(BaseModel):
    email: EmailStr
    rec_id: Optional[str] = None
    insurer: Optional[str] = None


@router.post("/early-access", dependencies=[Depends(verify_csrf)])
async def early_access(
    body: EarlyAccessSignup, request: Request, current=Depends(get_current_user)
):
    db = request.app.state.db
    await db.early_access.insert_one(
        {
            "_id": str(uuid.uuid4()),
            "user_id": current["user_id"],
            "email": body.email,
            "rec_id": body.rec_id,
            "insurer": body.insurer,
            "created_at": _iso(),
        }
    )
    return _ok({"signed_up": True})
