"""Stage 4 — Existing policies. Skeleton mode: PDF saved, mocked parse returned.

TODO(claude-api): When USE_MOCKS=false, replace _parse_pdf_with_claude with the
real Anthropic Claude integration:
    - Use anthropic.AsyncAnthropic, model claude-sonnet-4-* (user to pick)
    - Send PDF as base64 document content block
    - Apply rate limit: max 5 PDF parses per user per hour (use the
      ParseRateLimit helper below — already wired)
    - On failure (timeout, anthropic.APIStatusError), fall back to manual entry
      and log to db.parse_failures
    - Cache parsed result keyed by SHA256(pdf bytes) into policies.parsed_fields
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from auth import get_current_user, verify_csrf
from mocks.fixtures import make_mock_parsed_policy

router = APIRouter(prefix="/policies", tags=["policies"])

USE_MOCKS = os.environ.get("USE_MOCKS", "true").lower() == "true"
UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
PARSE_LIMIT_PER_HOUR = 5


def _ok(data=None):
    return {"success": True, "data": data or {}, "error": None}


def _utcnow():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.isoformat()


async def _check_parse_rate_limit(db, user_id: str) -> None:
    since = _iso(_utcnow() - timedelta(hours=1))
    count = await db.parse_attempts.count_documents(
        {"user_id": user_id, "created_at": {"$gte": since}}
    )
    if count >= PARSE_LIMIT_PER_HOUR:
        raise HTTPException(status_code=429, detail="parse_rate_limited")


async def _parse_pdf_with_claude(pdf_bytes: bytes, user_id: str, raw_path: str) -> dict:
    """TODO(claude-api): Replace this stub with the real Anthropic call.
    For skeleton mode: simulate ~4s parse, then return mock fixture."""
    await asyncio.sleep(4)
    return make_mock_parsed_policy(user_id=user_id, raw_pdf_path=raw_path)


# ---------- Path A: Upload ----------
@router.post("/upload", dependencies=[Depends(verify_csrf)])
async def upload_policy(
    request: Request,
    file: UploadFile = File(...),
    current=Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="only_pdf_supported")
    db = request.app.state.db

    await _check_parse_rate_limit(db, current["user_id"])

    raw = await file.read()
    if len(raw) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="file_too_large")

    sha = hashlib.sha256(raw).hexdigest()
    safe_name = f"{current['user_id']}_{sha[:16]}.pdf"
    target = UPLOADS_DIR / safe_name
    if not target.exists():
        target.write_bytes(raw)

    # Track the parse attempt for rate-limiting
    await db.parse_attempts.insert_one(
        {
            "_id": str(uuid.uuid4()),
            "user_id": current["user_id"],
            "sha": sha,
            "created_at": _iso(_utcnow()),
        }
    )

    # Cache hit: re-uploads of same PDF don't re-bill the API
    cached = await db.policies.find_one(
        {"user_id": current["user_id"], "raw_sha": sha}, {"_id": 0}
    )
    if cached:
        return _ok({"policy": cached, "cached": True})

    try:
        if USE_MOCKS:
            parsed = await _parse_pdf_with_claude(raw, current["user_id"], str(target))
        else:
            # TODO(claude-api): real Anthropic call goes here.
            parsed = await _parse_pdf_with_claude(raw, current["user_id"], str(target))
    except Exception as e:  # noqa: BLE001
        await db.parse_failures.insert_one(
            {
                "_id": str(uuid.uuid4()),
                "user_id": current["user_id"],
                "sha": sha,
                "error": str(e),
                "created_at": _iso(_utcnow()),
            }
        )
        raise HTTPException(status_code=502, detail="parse_failed")

    parsed["raw_sha"] = sha
    await db.policies.insert_one(dict(parsed))
    parsed.pop("_id", None)
    return _ok({"policy": parsed, "cached": False})


# ---------- Path B: Quick declaration ----------
class DeclarePolicy(BaseModel):
    type: str  # health | term | endowment | motor | travel
    insurer: str
    sum_insured: int
    premium: int
    notes: Optional[str] = None


@router.post("/declare", dependencies=[Depends(verify_csrf)])
async def declare_policy(
    body: DeclarePolicy, request: Request, current=Depends(get_current_user)
):
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
async def list_policies(request: Request, current=Depends(get_current_user)):
    db = request.app.state.db
    rows = await db.policies.find(
        {"user_id": current["user_id"]}, {"_id": 0}
    ).to_list(100)
    return _ok({"policies": rows})


@router.delete("/{policy_id}", dependencies=[Depends(verify_csrf)])
async def delete_policy(
    policy_id: str, request: Request, current=Depends(get_current_user)
):
    db = request.app.state.db
    res = await db.policies.delete_one({"id": policy_id, "user_id": current["user_id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="policy_not_found")
    return _ok({"deleted": True})
