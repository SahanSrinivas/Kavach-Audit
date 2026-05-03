"""Household — add/list members. Persistence only, no household audit logic yet.

TODO(household-logic): Phase 4 — household-aggregate audit + per-member policy
mapping + invitation flow.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from auth import get_current_user, verify_csrf

router = APIRouter(prefix="/family", tags=["family"])


def _ok(data=None):
    return {"success": True, "data": data or {}, "error": None}


def _iso():
    return datetime.now(timezone.utc).isoformat()


class FamilyMember(BaseModel):
    relation: Literal["spouse", "father", "mother", "child", "sibling", "other"]
    name: Optional[str] = None
    age: Optional[int] = None
    pre_existing: Optional[list[str]] = None


@router.post("/members", dependencies=[Depends(verify_csrf)])
async def add_member(
    body: FamilyMember, request: Request, current=Depends(get_current_user)
):
    db = request.app.state.db
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": current["user_id"],
        **body.model_dump(),
        "created_at": _iso(),
    }
    await db.family_members.insert_one(dict(doc))
    doc.pop("_id", None)
    return _ok({"member": doc})


@router.get("/members")
async def list_members(request: Request, current=Depends(get_current_user)):
    db = request.app.state.db
    rows = await db.family_members.find(
        {"user_id": current["user_id"]}, {"_id": 0}
    ).to_list(50)
    return _ok({"members": rows})
