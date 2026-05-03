"""Admin routes — basic password gate for early debugging.

Auth: pass `Authorization: Bearer <ADMIN_PASSWORD>` header. Wrong/missing → 401.
"""
import os
import secrets
from fastapi import APIRouter, Header, HTTPException, Request, status

router = APIRouter(prefix="/admin", tags=["admin"])


def _check(authorization: str | None) -> None:
    expected = os.environ.get("ADMIN_PASSWORD", "")
    if not expected:
        raise HTTPException(status_code=503, detail="admin_disabled")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="admin_unauthorized")
    token = authorization[7:].strip()
    if not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="admin_unauthorized")


@router.get("/users")
async def list_users(request: Request, authorization: str | None = Header(default=None)):
    _check(authorization)
    db = request.app.state.db
    rows = await db.users.find({}, {"_id": 0}).to_list(500)
    return {"success": True, "data": {"users": rows, "count": len(rows)}, "error": None}


@router.get("/audits")
async def list_audits(request: Request, authorization: str | None = Header(default=None)):
    _check(authorization)
    db = request.app.state.db
    rows = await db.audits.find({}, {"_id": 0}).to_list(500)
    return {"success": True, "data": {"audits": rows, "count": len(rows)}, "error": None}
