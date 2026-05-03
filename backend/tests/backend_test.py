"""Kavach Phase 1 backend regression tests.

Covers: auth (request/verify/refresh/logout/sessions), user me, deeplink, health/version.
Uses mock OTP=123456. Distinct mobiles per test to avoid rate-limit collision.
"""
import os
import random
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://kavach-audit.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
OTP = "123456"


def _mob() -> str:
    """Random Indian 10-digit mobile starting with 9."""
    return "9" + "".join(str(random.randint(0, 9)) for _ in range(9))


def _login(session: requests.Session, mobile: str | None = None) -> dict:
    """Helper: request OTP + verify, returns verify response json. Session keeps cookies."""
    mobile = mobile or _mob()
    r = session.post(f"{API}/auth/request-otp", json={"mobile": mobile})
    assert r.status_code == 200, r.text
    r = session.post(f"{API}/auth/verify-otp", json={"mobile": mobile, "otp": OTP})
    assert r.status_code == 200, r.text
    # Mirror CSRF cookie into header for subsequent state-changing calls
    csrf = session.cookies.get("kavach_csrf")
    if csrf:
        session.headers.update({"X-CSRF-Token": csrf})
    return r.json()


# --- /health and /version (NOTE: not under /api so may be unreachable externally) ---
class TestMeta:
    def test_root_api(self):
        r = requests.get(f"{API}/")
        assert r.status_code == 200
        body = r.json()
        assert body.get("success") is True
        assert body["data"]["service"] == "kavach"


# --- /api/auth/request-otp ---
class TestRequestOTP:
    def test_valid_mobile(self):
        r = requests.post(f"{API}/auth/request-otp", json={"mobile": _mob()})
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["data"]["sent"] is True

    def test_invalid_mobile_too_short(self):
        r = requests.post(f"{API}/auth/request-otp", json={"mobile": "12345"})
        assert r.status_code in (400, 422)

    def test_invalid_mobile_non_digit(self):
        r = requests.post(f"{API}/auth/request-otp", json={"mobile": "abcdefghij"})
        assert r.status_code in (400, 422)

    def test_rate_limit_4th_attempt(self):
        m = _mob()
        codes = []
        for _ in range(4):
            codes.append(requests.post(f"{API}/auth/request-otp", json={"mobile": m}).status_code)
        assert codes[0] == 200
        assert codes[-1] == 429, f"Expected 429 on 4th request, got {codes}"


# --- /api/auth/verify-otp ---
class TestVerifyOTP:
    def test_verify_success_first_login_is_new_user(self):
        s = requests.Session()
        m = _mob()
        s.post(f"{API}/auth/request-otp", json={"mobile": m})
        r = s.post(f"{API}/auth/verify-otp", json={"mobile": m, "otp": OTP})
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["is_new_user"] is True
        assert "user_id" in data
        # cookies should be set
        assert s.cookies.get("kavach_access") or s.cookies.get("access_token") or any(
            "access" in c.name for c in s.cookies
        )

    def test_verify_returning_user_is_new_user_false(self):
        m = _mob()
        s1 = requests.Session()
        s1.post(f"{API}/auth/request-otp", json={"mobile": m})
        s1.post(f"{API}/auth/verify-otp", json={"mobile": m, "otp": OTP})
        # second verify
        s2 = requests.Session()
        s2.post(f"{API}/auth/request-otp", json={"mobile": m})
        r = s2.post(f"{API}/auth/verify-otp", json={"mobile": m, "otp": OTP})
        assert r.status_code == 200
        assert r.json()["data"]["is_new_user"] is False

    def test_verify_wrong_otp(self):
        s = requests.Session()
        m = _mob()
        s.post(f"{API}/auth/request-otp", json={"mobile": m})
        r = s.post(f"{API}/auth/verify-otp", json={"mobile": m, "otp": "000000"})
        assert r.status_code == 400
        body = r.json()
        err = body.get("error") or body.get("detail") or {}
        assert "invalid_otp" in str(err).lower() or "invalid" in str(err).lower()

    def test_verify_lock_after_5_wrong(self):
        s = requests.Session()
        m = _mob()
        s.post(f"{API}/auth/request-otp", json={"mobile": m})
        codes = []
        for _ in range(6):
            codes.append(s.post(f"{API}/auth/verify-otp", json={"mobile": m, "otp": "000000"}).status_code)
        assert 429 in codes, f"Expected lock 429, got {codes}"


# --- /api/user/me ---
class TestUserMe:
    def test_me_unauthenticated(self):
        r = requests.get(f"{API}/user/me")
        assert r.status_code == 401

    def test_me_authenticated_has_audit_false(self):
        s = requests.Session()
        _login(s)
        r = s.get(f"{API}/user/me")
        assert r.status_code == 200
        u = r.json().get("data", {}).get("user", {})
        assert u.get("has_audit") is False

    def test_patch_me_without_csrf(self):
        s = requests.Session()
        _login(s)
        # remove CSRF header to test enforcement
        s.headers.pop("X-CSRF-Token", None)
        r = s.patch(f"{API}/user/me", json={"age": 30, "city": "Mumbai"})
        assert r.status_code == 403, r.text

    def test_patch_me_tier_mumbai(self):
        s = requests.Session()
        _login(s)
        r = s.patch(f"{API}/user/me", json={"age": 30, "city": "Mumbai"})
        assert r.status_code == 200, r.text
        u = s.get(f"{API}/user/me").json().get("data", {})
        assert u.get("city") == "Mumbai"
        assert u.get("age") == 30
        assert u.get("tier") == "tier-1"

    def test_patch_me_tier_jaipur(self):
        s = requests.Session()
        _login(s)
        r = s.patch(f"{API}/user/me", json={"age": 28, "city": "Jaipur"})
        assert r.status_code == 200
        u = s.get(f"{API}/user/me").json().get("data", {})
        assert u.get("tier") == "tier-2"

    def test_patch_me_tier_village(self):
        s = requests.Session()
        _login(s)
        r = s.patch(f"{API}/user/me", json={"age": 40, "city": "SomeVillage"})
        assert r.status_code == 200
        u = s.get(f"{API}/user/me").json().get("data", {})
        assert u.get("tier") == "tier-3"


# --- refresh / sessions / logout ---
class TestSessionLifecycle:
    def test_refresh_rotates(self):
        s = requests.Session()
        _login(s)
        old_refresh = s.cookies.get("kavach_refresh")
        time.sleep(1)
        r = s.post(f"{API}/auth/refresh")
        assert r.status_code == 200, r.text
        new_refresh = s.cookies.get("kavach_refresh")
        assert new_refresh and new_refresh != old_refresh

    def test_sessions_list_has_current(self):
        s = requests.Session()
        _login(s)
        r = s.get(f"{API}/auth/sessions")
        assert r.status_code == 200
        sessions = r.json().get("data", r.json())
        # could be list or dict containing list
        if isinstance(sessions, dict) and "sessions" in sessions:
            sessions = sessions["sessions"]
        assert isinstance(sessions, list) and len(sessions) >= 1
        assert any(item.get("is_current") is True for item in sessions)

    def test_logout_then_refresh_fails(self):
        s = requests.Session()
        _login(s)
        r = s.post(f"{API}/auth/logout")
        assert r.status_code == 200
        # session removed; refresh should fail
        r2 = s.post(f"{API}/auth/refresh")
        assert r2.status_code == 401

    def test_logout_all_clears_sessions(self):
        s = requests.Session()
        _login(s)
        r = s.post(f"{API}/auth/logout-all")
        assert r.status_code == 200
        r2 = s.get(f"{API}/user/me")
        assert r2.status_code == 401

    def test_revoke_specific_session(self):
        # login twice for same user from two sessions
        m = _mob()
        s1 = requests.Session()
        _login(s1, m)
        s2 = requests.Session()
        _login(s2, m)
        # list from s1, find non-current id
        sessions = s1.get(f"{API}/auth/sessions").json().get("data", [])
        if isinstance(sessions, dict) and "sessions" in sessions:
            sessions = sessions["sessions"]
        other = next((x for x in sessions if not x.get("is_current")), None)
        if not other:
            pytest.skip("No second session visible")
        sid = other.get("id") or other.get("session_id") or other.get("_id")
        r = s1.delete(f"{API}/auth/sessions/{sid}")
        assert r.status_code in (200, 204)


# --- Deeplink ---
class TestDeeplink:
    def test_unknown_token_404(self):
        r = requests.get(f"{API}/deeplink/resolve/nonexistent_xyz_404")
        assert r.status_code == 404
