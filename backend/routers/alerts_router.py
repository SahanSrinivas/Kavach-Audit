"""Stage 8 — Alerts inbox. Skeleton mode: returns 3 hardcoded alerts.

TODO(alert-triggers): Replace mocked alerts with real triggers:
  - Renewal watcher: cron 60 days before policy.end_date
  - Life-event detector: profile delta watcher
  - Annual re-audit: cron 365 days after audits.generated_at
Real notification delivery via WhatsApp Business API + SendGrid.
"""
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from auth import get_current_user, verify_csrf
from mocks.fixtures import make_mock_alerts

router = APIRouter(prefix="/alerts", tags=["alerts"])

USE_MOCKS = os.environ.get("USE_MOCKS", "true").lower() == "true"


def _ok(data=None):
    return {"success": True, "data": data or {}, "error": None}


def _iso():
    return datetime.now(timezone.utc).isoformat()


@router.get("")
async def list_alerts(request: Request, current=Depends(get_current_user)):
    db = request.app.state.db
    # Seed mock alerts on first read so they have stable IDs and are queryable
    existing = await db.alerts.count_documents({"user_id": current["user_id"]})
    if existing == 0:
        for a in make_mock_alerts(current["user_id"]):
            doc = dict(a)
            doc["_id"] = a["id"]
            try:
                await db.alerts.insert_one(doc)
            except Exception:
                # short_token unique conflict → ignore
                pass
    rows = await db.alerts.find(
        {"user_id": current["user_id"]}, {"_id": 0}
    ).sort("triggered_at", -1).to_list(50)
    return _ok({"alerts": rows})


@router.post("/{alert_id}/read", dependencies=[Depends(verify_csrf)])
async def mark_read(alert_id: str, request: Request, current=Depends(get_current_user)):
    db = request.app.state.db
    res = await db.alerts.update_one(
        {"id": alert_id, "user_id": current["user_id"]},
        {"$set": {"read_status": True, "read_at": _iso()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="alert_not_found")
    return _ok({"read": True})
