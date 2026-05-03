"""Kavach main app — composition root."""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from routers.auth_router import router as auth_router  # noqa: E402
from routers.user_router import router as user_router  # noqa: E402
from routers.deeplink_router import router as deeplink_router  # noqa: E402

# --- Mongo ---
mongo_url = os.environ["MONGO_URL"]
mongo_client = AsyncIOMotorClient(mongo_url)
db = mongo_client[os.environ["DB_NAME"]]

app = FastAPI(title="Kavach API", version="0.1.0")
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


api_router.include_router(auth_router)
api_router.include_router(user_router)
api_router.include_router(deeplink_router)
app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/version")
async def version():
    return {"version": app.version, "service": "kavach"}


# --- Startup: ensure indexes ---
@app.on_event("startup")
async def ensure_indexes():
    await db.users.create_index("mobile", unique=True)
    await db.otp_attempts.create_index([("mobile", 1), ("created_at", -1)])
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
