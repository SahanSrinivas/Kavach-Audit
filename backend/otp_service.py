"""Pluggable OTP delivery service.

v1: mock — always succeeds without sending. OTP value always 123456 in dev.
v2: swap `_send_sms_mock` for MSG91 / WhatsApp Business API.
"""
import os
import bcrypt
import secrets
import logging

logger = logging.getLogger("kavach.otp")

MOCK_OTP = os.environ.get("OTP_MOCK_CODE", "123456")


def generate_otp() -> str:
    """Always return mock code in dev. Replace with `secrets.randbelow(1_000_000):06d` in prod."""
    return MOCK_OTP


def hash_otp(otp: str) -> str:
    return bcrypt.hashpw(otp.encode("utf-8"), bcrypt.gensalt(rounds=10)).decode("utf-8")


def verify_otp(otp: str, otp_hash: str) -> bool:
    try:
        return bcrypt.checkpw(otp.encode("utf-8"), otp_hash.encode("utf-8"))
    except Exception:
        return False


def send_otp(mobile: str, code: str) -> bool:
    """Pluggable SMS/WhatsApp sender. v1 returns True without sending.

    Returns True on successful delivery.
    """
    logger.info("Mock OTP dispatch → mobile=+91%s code=%s", mobile, code)
    return True


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return bcrypt.hashpw(token.encode("utf-8"), bcrypt.gensalt(rounds=10)).decode("utf-8")


def verify_token_hash(token: str, token_hash: str) -> bool:
    try:
        return bcrypt.checkpw(token.encode("utf-8"), token_hash.encode("utf-8"))
    except Exception:
        return False
