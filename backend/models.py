"""Pydantic models for Kavachly."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Literal, Dict, Any
from datetime import datetime, timezone
import uuid


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class APIResponse(BaseModel):
    success: bool = True
    data: Optional[dict] = None
    error: Optional[str] = None


# ----- Auth -----
class RequestOTPInput(BaseModel):
    mobile: str = Field(..., min_length=10, max_length=10)


class VerifyOTPInput(BaseModel):
    mobile: str = Field(..., min_length=10, max_length=10)
    otp: str = Field(..., min_length=6, max_length=6)


# ----- Profile update — accepts any of the audit-flow fields -----
class UserProfileUpdate(BaseModel):
    age: Optional[int] = Field(None, ge=18, le=80)
    city: Optional[str] = None
    tier: Optional[Literal["tier-1", "tier-2", "tier-3"]] = None

    # Stage 2 — Family
    family_composition: Optional[
        Literal["self", "self_spouse", "self_spouse_kids", "self_parents", "full_family"]
    ] = None
    spouse_age: Optional[int] = Field(None, ge=18, le=90)
    kids_count: Optional[int] = Field(None, ge=0, le=8)
    kids_youngest_age: Optional[int] = Field(None, ge=0, le=30)
    parents_ages: Optional[Dict[str, int]] = None
    parents_pec: Optional[List[str]] = None

    # Stage 3 — Money
    income: Optional[int] = Field(None, ge=0)
    emis: Optional[int] = Field(None, ge=0)
    monthly_expenses: Optional[int] = Field(None, ge=0)

    # Stage 5 — Lifestyle
    lifestyle: Optional[Dict[str, Any]] = None

    # Audit metadata
    audit_completed: Optional[bool] = None
