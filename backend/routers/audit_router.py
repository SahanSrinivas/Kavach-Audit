"""Stage 6 — Audit. Skeleton mode: returns hardcoded mock audit.

TODO(audit-engine): When USE_MOCKS=false, replace _generate_audit with the
real scoring engine in /backend/services/audit.py:
  - Coverage Score weighting: Health 0.35 + Life 0.30 + Motor 0.15 + PA 0.10 + Other 0.10
  - Cost Score: percentile vs market median (use Riskcovry data when integrated)
  - Claim-Readiness Score: parse-field deductions per spec
  - Gap Score: standard checklist with deductions
  - For each red flag, generate user-facing explanation via cached Anthropic call
"""
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from auth import get_current_user, verify_csrf
from mocks.fixtures import make_mock_audit

router = APIRouter(prefix="/audit", tags=["audit"])

USE_MOCKS = os.environ.get("USE_MOCKS", "true").lower() == "true"


def _ok(data=None):
    return {"success": True, "data": data or {}, "error": None}


def _iso():
    return datetime.now(timezone.utc).isoformat()


async def _generate_audit(db, user_id: str) -> dict:
    """TODO(audit-engine): replace with real scoring on user + policies."""
    audit = make_mock_audit(user_id)
    await db.audits.insert_one(dict(audit))
    audit.pop("_id", None)
    return audit


@router.post("/generate", dependencies=[Depends(verify_csrf)])
async def generate_audit(request: Request, current=Depends(get_current_user)):
    db = request.app.state.db
    audit = await _generate_audit(db, current["user_id"])
    return _ok({"audit": audit})


@router.get("/latest")
async def get_latest(request: Request, current=Depends(get_current_user)):
    db = request.app.state.db
    audit = await db.audits.find_one(
        {"user_id": current["user_id"]},
        {"_id": 0},
        sort=[("generated_at", -1)],
    )
    if not audit:
        # Auto-generate on first read (skeleton convenience)
        audit = await _generate_audit(db, current["user_id"])
    return _ok({"audit": audit})
