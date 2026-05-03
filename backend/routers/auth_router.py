"""Auth routes: OTP request/verify, refresh, logout, sessions."""
import os
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status

from auth import (
    ACCESS_COOKIE,
    CSRF_COOKIE,
    REFRESH_COOKIE,
    REFRESH_EXP_DAYS,
    clear_auth_cookies,
    device_fingerprint,
    get_current_user,
    make_access_token,
    set_auth_cookies,
    verify_csrf,
)
from otp_service import (
    generate_otp,
    hash_otp,
    hash_token,
    new_refresh_token,
    send_otp,
    verify_otp,
    verify_token_hash,
)
from models import RequestOTPInput, VerifyOTPInput

router = APIRouter(prefix="/auth", tags=["auth"])


def _ok(data=None):
    return {"success": True, "data": data or {}, "error": None}


def _fail(msg: str, code: int = 400):
    raise HTTPException(status_code=code, detail=msg)


def _utcnow():
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ----- Rate limits -----
MAX_OTP_PER_HOUR = 3
MAX_VERIFY_ATTEMPTS = 5
VERIFY_LOCK_MIN = 60  # minutes
LOCKED_STATUS = 423  # HTTP 423 Locked
RATE_LIMIT_STATUS = 429


async def _is_mobile_locked(db, mobile: str) -> bool:
    doc = await db.otp_attempts.find_one(
        {"mobile": mobile, "locked_until": {"$gt": _iso(_utcnow())}},
        {"_id": 0, "locked_until": 1},
    )
    return bool(doc)


async def _count_requests_last_hour(db, mobile: str) -> int:
    since = _iso(_utcnow() - timedelta(hours=1))
    return await db.otp_attempts.count_documents({"mobile": mobile, "created_at": {"$gte": since}})


# ----- Endpoints -----
@router.post("/request-otp")
async def request_otp(body: RequestOTPInput, request: Request):
    db = request.app.state.db
    mobile = body.mobile.strip()
    if not mobile.isdigit() or len(mobile) != 10:
        _fail("invalid_mobile")

    if await _is_mobile_locked(db, mobile):
        _fail("locked_try_later", LOCKED_STATUS)

    if await _count_requests_last_hour(db, mobile) >= MAX_OTP_PER_HOUR:
        _fail("rate_limited", RATE_LIMIT_STATUS)

    code = generate_otp()
    otp_hash = hash_otp(code)
    now = _utcnow()
    await db.otp_attempts.insert_one(
        {
            "_id": str(uuid.uuid4()),
            "mobile": mobile,
            "otp_hash": otp_hash,
            "attempts_count": 0,
            "created_at": _iso(now),
            "expires_at": _iso(now + timedelta(minutes=10)),
            "locked_until": None,
        }
    )
    send_otp(mobile, code)
    return _ok({"sent": True, "dev_hint": "Use 123456 in development"})


@router.post("/verify-otp")
async def verify_otp_endpoint(body: VerifyOTPInput, request: Request, response: Response):
    db = request.app.state.db
    mobile = body.mobile.strip()
    otp = body.otp.strip()

    if await _is_mobile_locked(db, mobile):
        _fail("locked_try_later", LOCKED_STATUS)

    # Latest OTP record for this mobile, regardless of expiry (replay check first).
    record = await db.otp_attempts.find_one(
        {"mobile": mobile},
        sort=[("created_at", -1)],
    )
    if not record:
        _fail("otp_expired_or_missing", 400)

    # 1) Replay-attack guard: any already-consumed OTP is permanently rejected.
    if record.get("consumed"):
        _fail("otp_already_used", 400)

    # 2) Expiry guard.
    if record["expires_at"] <= _iso(_utcnow()):
        _fail("otp_expired_or_missing", 400)

    # 3) Verify the OTP.
    if not verify_otp(otp, record["otp_hash"]):
        new_count = int(record.get("attempts_count", 0)) + 1
        update = {"$set": {"attempts_count": new_count}}
        locked = new_count >= MAX_VERIFY_ATTEMPTS
        if locked:
            update["$set"]["locked_until"] = _iso(_utcnow() + timedelta(minutes=VERIFY_LOCK_MIN))
        await db.otp_attempts.update_one({"_id": record["_id"]}, update)
        _fail("locked_try_later" if locked else "invalid_otp", LOCKED_STATUS if locked else 401)

    # Mark this OTP as consumed and expire any older un-consumed ones for this mobile.
    await db.otp_attempts.update_one(
        {"_id": record["_id"]},
        {"$set": {"consumed": True, "consumed_at": _iso(_utcnow())}},
    )
    await db.otp_attempts.update_many(
        {"mobile": mobile, "_id": {"$ne": record["_id"]}, "consumed": {"$ne": True}},
        {"$set": {"expires_at": _iso(_utcnow() - timedelta(seconds=1))}},
    )

    # User upsert
    user = await db.users.find_one({"mobile": mobile}, {"_id": 0})
    is_new_user = user is None
    if is_new_user:
        user = {
            "id": str(uuid.uuid4()),
            "mobile": mobile,
            "created_at": _iso(_utcnow()),
        }
        await db.users.insert_one(dict(user))

    # Issue tokens
    access = make_access_token(user["id"], user["mobile"])
    refresh_plain = new_refresh_token()
    refresh_hash = hash_token(refresh_plain)
    session_doc = {
        "_id": str(uuid.uuid4()),
        "user_id": user["id"],
        "refresh_token_hash": refresh_hash,
        "device_fingerprint": device_fingerprint(request),
        "user_agent": request.headers.get("user-agent", "")[:256],
        "created_at": _iso(_utcnow()),
        "last_used_at": _iso(_utcnow()),
        "expires_at": _iso(_utcnow() + timedelta(days=REFRESH_EXP_DAYS)),
    }
    await db.sessions.insert_one(session_doc)
    # Signed refresh cookie value encodes session_id to avoid scanning all sessions
    refresh_cookie_value = f"{session_doc['_id']}.{refresh_plain}"
    set_auth_cookies(response, access, refresh_cookie_value)

    return _ok({"user_id": user["id"], "is_new_user": is_new_user})


@router.post("/refresh")
async def refresh_token_endpoint(
    request: Request,
    response: Response,
    kavach_refresh: Optional[str] = Cookie(default=None),
):
    db = request.app.state.db
    if not kavach_refresh or "." not in kavach_refresh:
        _fail("no_refresh", 401)

    session_id, plain = kavach_refresh.split(".", 1)
    session = await db.sessions.find_one({"_id": session_id})
    if not session:
        _fail("session_not_found", 401)
    if session["expires_at"] <= _iso(_utcnow()):
        await db.sessions.delete_one({"_id": session_id})
        _fail("session_expired", 401)
    if not verify_token_hash(plain, session["refresh_token_hash"]):
        _fail("invalid_refresh", 401)

    user = await db.users.find_one({"id": session["user_id"]}, {"_id": 0})
    if not user:
        _fail("user_missing", 401)

    # Rotate refresh token
    new_plain = new_refresh_token()
    await db.sessions.update_one(
        {"_id": session_id},
        {"$set": {"refresh_token_hash": hash_token(new_plain), "last_used_at": _iso(_utcnow())}},
    )
    new_cookie = f"{session_id}.{new_plain}"
    access = make_access_token(user["id"], user["mobile"])
    set_auth_cookies(response, access, new_cookie)
    return _ok({"refreshed": True})


@router.post("/logout", dependencies=[Depends(verify_csrf)])
async def logout(
    request: Request,
    response: Response,
    kavach_refresh: Optional[str] = Cookie(default=None),
):
    db = request.app.state.db
    if kavach_refresh and "." in kavach_refresh:
        session_id = kavach_refresh.split(".", 1)[0]
        await db.sessions.delete_one({"_id": session_id})
    clear_auth_cookies(response)
    return _ok({"logged_out": True})


@router.post("/logout-all", dependencies=[Depends(verify_csrf)])
async def logout_all(
    request: Request,
    response: Response,
    current=Depends(get_current_user),
):
    db = request.app.state.db
    await db.sessions.delete_many({"user_id": current["user_id"]})
    clear_auth_cookies(response)
    return _ok({"logged_out_all": True})


@router.get("/sessions")
async def list_sessions(request: Request, current=Depends(get_current_user),
                        kavach_refresh: Optional[str] = Cookie(default=None)):
    db = request.app.state.db
    rows = await db.sessions.find(
        {"user_id": current["user_id"]},
        {"refresh_token_hash": 0},
    ).to_list(100)
    current_id = kavach_refresh.split(".", 1)[0] if kavach_refresh and "." in kavach_refresh else None
    out = []
    for r in rows:
        out.append(
            {
                "id": r["_id"],
                "user_agent": r.get("user_agent", ""),
                "created_at": r.get("created_at"),
                "last_used_at": r.get("last_used_at"),
                "expires_at": r.get("expires_at"),
                "is_current": r["_id"] == current_id,
            }
        )
    return _ok({"sessions": out})


@router.delete("/sessions/{session_id}", dependencies=[Depends(verify_csrf)])
async def revoke_session(session_id: str, request: Request, current=Depends(get_current_user)):
    db = request.app.state.db
    res = await db.sessions.delete_one({"_id": session_id, "user_id": current["user_id"]})
    if res.deleted_count == 0:
        _fail("session_not_found", 404)
    return _ok({"revoked": True})
