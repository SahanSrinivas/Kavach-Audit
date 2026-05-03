"""Pydantic models for Kavach."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Literal
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
    mobile: str = Field(..., min_length=10, max_length=10, description="10-digit Indian mobile")


class VerifyOTPInput(BaseModel):
    mobile: str = Field(..., min_length=10, max_length=10)
    otp: str = Field(..., min_length=6, max_length=6)


# ----- User -----
class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mobile: str
    age: Optional[int] = None
    city: Optional[str] = None
    tier: Optional[Literal["tier-1", "tier-2", "tier-3"]] = None
    family_composition: Optional[str] = None
    spouse_age: Optional[int] = None
    kids_count: Optional[int] = None
    kids_youngest_age: Optional[int] = None
    parents_ages: Optional[dict] = None  # {mother: int, father: int}
    parents_pec: Optional[List[str]] = None
    income: Optional[int] = None
    emis: Optional[int] = None
    monthly_expenses: Optional[int] = None
    lifestyle: Optional[dict] = None
    created_at: datetime = Field(default_factory=utcnow)


class UserProfileUpdate(BaseModel):
    age: Optional[int] = Field(None, ge=18, le=80)
    city: Optional[str] = None
    tier: Optional[Literal["tier-1", "tier-2", "tier-3"]] = None
