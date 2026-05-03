"""User profile routes."""
from fastapi import APIRouter, Depends, HTTPException, Request

from auth import get_current_user
from models import UserProfileUpdate

router = APIRouter(prefix="/user", tags=["user"])


def _ok(data=None):
    return {"success": True, "data": data or {}, "error": None}


def _tier_for_city(city: str) -> str:
    tier_1 = {"mumbai", "delhi", "bengaluru", "bangalore", "chennai", "kolkata", "hyderabad", "pune", "ahmedabad"}
    tier_2 = {
        "jaipur", "lucknow", "surat", "kanpur", "nagpur", "indore", "thane", "bhopal", "visakhapatnam",
        "patna", "vadodara", "ghaziabad", "ludhiana", "agra", "nashik", "faridabad", "meerut", "rajkot",
        "kalyan", "vasai", "varanasi", "srinagar", "aurangabad", "dhanbad", "amritsar", "navi mumbai",
        "allahabad", "ranchi", "howrah", "coimbatore", "jabalpur", "gwalior", "vijayawada", "jodhpur",
        "madurai", "raipur", "kota", "chandigarh", "guwahati", "solapur", "hubli", "mysuru", "mysore",
        "noida", "gurgaon", "gurugram",
    }
    c = city.strip().lower()
    if c in tier_1:
        return "tier-1"
    if c in tier_2:
        return "tier-2"
    return "tier-3"


@router.get("/me")
async def get_me(request: Request, current=Depends(get_current_user)):
    db = request.app.state.db
    user = await db.users.find_one({"id": current["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")
    # Does the user have at least one audit?
    has_audit = await db.audits.count_documents({"user_id": current["user_id"]}) > 0
    user["has_audit"] = has_audit
    return _ok({"user": user})


@router.patch("/me")
async def update_me(body: UserProfileUpdate, request: Request, current=Depends(get_current_user)):
    db = request.app.state.db
    update = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if "city" in update and "tier" not in update:
        update["tier"] = _tier_for_city(update["city"])
    if not update:
        return _ok({"updated": False})
    await db.users.update_one({"id": current["user_id"]}, {"$set": update})
    user = await db.users.find_one({"id": current["user_id"]}, {"_id": 0})
    return _ok({"user": user})
