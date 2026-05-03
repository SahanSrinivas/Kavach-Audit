"""Kavach main app — composition root."""
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# Production safety: refuse to start if JWT_SECRET is missing.
if os.environ.get("ENVIRONMENT", "development").lower() == "production":
    if not os.environ.get("JWT_SECRET"):
        sys.stderr.write("FATAL: JWT_SECRET is required in production.\n")
        sys.exit(1)

from routers.auth_router import router as auth_router  # noqa: E402
from routers.user_router import router as user_router  # noqa: E402
from routers.deeplink_router import router as deeplink_router  # noqa: E402
from routers.admin_router import router as admin_router  # noqa: E402

VERSION = "0.1.0"
BUILD_TIME = datetime.now(timezone.utc).isoformat()
GIT_SHA = os.environ.get("GIT_SHA", "dev")

# --- Mongo ---
mongo_url = os.environ["MONGO_URL"]
mongo_client = AsyncIOMotorClient(mongo_url)
db = mongo_client[os.environ["DB_NAME"]]

app = FastAPI(title="Kavach API", version=VERSION)
app.state.db = db

# --- CORS ---
origins = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API router ---
api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root():
    return {"success": True, "data": {"service": "kavach", "status": "ok"}, "error": None}


@api_router.get("/health")
async def health():
    db_status = "connected"
    try:
        await db.command("ping")
    except Exception:
        db_status = "disconnected"
    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "db": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@api_router.get("/version")
async def version():
    return {"version": VERSION, "git_sha": GIT_SHA, "build_time": BUILD_TIME}


api_router.include_router(auth_router)
api_router.include_router(user_router)
api_router.include_router(deeplink_router)
api_router.include_router(admin_router)
app.include_router(api_router)


# --- Startup: ensure indexes ---
@app.on_event("startup")
async def ensure_indexes():
    await db.users.create_index("mobile", unique=True)
    await db.otp_attempts.create_index([("mobile", 1), ("created_at", -1)])
    # TTL: auto-delete OTP attempts 24h after creation
    try:
        await db.otp_attempts.create_index("created_at_dt", expireAfterSeconds=86400)
    except Exception:
        pass
    await db.sessions.create_index("user_id")
    await db.sessions.create_index("expires_at")
    await db.alerts.create_index("short_token", unique=True, sparse=True)


@app.on_event("shutdown")
async def shutdown_db_client():
    mongo_client.close()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("kavach")
