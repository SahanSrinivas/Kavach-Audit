"""Deep-link resolution for alert SMS/email short tokens.

Frontend path: /r/:token → calls /api/deeplink/resolve/:token.
"""
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request
from typing import Optional

from auth import decode_access_token

router = APIRouter(prefix="/deeplink", tags=["deeplink"])


def _ok(data=None):
    return {"success": True, "data": data or {}, "error": None}


@router.get("/resolve/{token}")
async def resolve_token(token: str, request: Request,
                        kavach_access: Optional[str] = Cookie(default=None)):
    db = request.app.state.db
    alert = await db.alerts.find_one({"short_token": token}, {"_id": 0})
    if not alert:
        raise HTTPException(status_code=404, detail="token_not_found")

    authed = False
    if kavach_access:
        try:
            decode_access_token(kavach_access)
            authed = True
        except Exception:
            authed = False

    return _ok({
        "target_url": alert.get("target_url"),
        "authenticated": authed,
        "alert_id": alert.get("id"),
    })
