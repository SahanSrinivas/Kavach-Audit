"""JWT + session helpers for Kavach."""
import os
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

import jwt
from fastapi import Cookie, Depends, HTTPException, Request, Response, status

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGO = "HS256"
ACCESS_EXP_HOURS = int(os.environ.get("ACCESS_TOKEN_EXP_HOURS", "24"))
REFRESH_EXP_DAYS = int(os.environ.get("REFRESH_TOKEN_EXP_DAYS", "90"))

ACCESS_COOKIE = "kavach_access"
REFRESH_COOKIE = "kavach_refresh"
CSRF_COOKIE = "kavach_csrf"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def make_access_token(user_id: str, mobile: str) -> str:
    payload = {
        "user_id": user_id,
        "mobile": mobile,
        "iat": int(utcnow().timestamp()),
        "exp": int((utcnow() + timedelta(hours=ACCESS_EXP_HOURS)).timestamp()),
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])


def device_fingerprint(request: Request) -> str:
    ua = request.headers.get("user-agent", "")
    # Prefer X-Forwarded-For since we are behind k8s ingress
    ip = request.headers.get("x-forwarded-for", "") or (request.client.host if request.client else "")
    return hashlib.sha256(f"{ua}|{ip}".encode("utf-8")).hexdigest()


def set_auth_cookies(response: Response, access: str, refresh: str) -> str:
    """Sets httpOnly access/refresh cookies and a readable CSRF cookie.

    Returns the csrf token (also set as cookie) for the client to echo back.
    """
    csrf = secrets.token_urlsafe(24)
    common = dict(httponly=True, secure=True, samesite="lax", path="/")
    response.set_cookie(ACCESS_COOKIE, access, max_age=ACCESS_EXP_HOURS * 3600, **common)
    response.set_cookie(REFRESH_COOKIE, refresh, max_age=REFRESH_EXP_DAYS * 86400, **common)
    # CSRF token is NOT httpOnly so JS can read and echo it.
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        max_age=ACCESS_EXP_HOURS * 3600,
        httponly=False,
        secure=True,
        samesite="lax",
        path="/",
    )
    return csrf


def clear_auth_cookies(response: Response) -> None:
    for name in (ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, path="/")


async def get_current_user(
    request: Request,
    kavach_access: Optional[str] = Cookie(default=None),
) -> dict:
    """Dependency: returns { user_id, mobile } from a valid access cookie."""
    if not kavach_access:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
    try:
        payload = decode_access_token(kavach_access)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="access_expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token_type")
    return {"user_id": payload["user_id"], "mobile": payload["mobile"]}


async def verify_csrf(request: Request) -> None:
    """Double-submit cookie CSRF check. Call as a dependency on state-changing routes that
    are called from the browser with cookies. Skipped for OTP endpoints (they don't yet
    have a session)."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    header = request.headers.get("x-csrf-token")
    cookie = request.cookies.get(CSRF_COOKIE)
    if not header or not cookie or not secrets.compare_digest(header, cookie):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="csrf_failed")
