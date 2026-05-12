# main.py
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import engine, Base
from app.db import models  # noqa: F401 – registers models with Base

from app.api.auth import router as auth_router
from app.api.jd import router as jd_router
from app.api.cv_analysis import router as cv_router
from app.api.job_requests import router as jobs_router
from app.api.notifications import router as notif_router
from app.api.analytics import router as analytics_router
from app.utils.scheduler import start_scheduler, shutdown_scheduler, reschedule_active_jobs
from app.utils.llm import get_usage, reset_usage, _manager, GROQ_MODEL, GEMINI_MODEL


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all tables on startup
    Base.metadata.create_all(bind=engine)
    # Start background scheduler
    start_scheduler()
    reschedule_active_jobs()
    yield
    # Shutdown scheduler
    shutdown_scheduler()


app = FastAPI(title="Recruitment AI Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health():
    return {"status": "Backend running"}


@app.get("/admin/token-usage")
def token_usage():
    return get_usage()


@app.post("/admin/token-usage/reset")
def token_usage_reset():
    reset_usage()
    return {"status": "reset"}


@app.get("/admin/llm-status")
def llm_status():
    provider, key = _manager.current
    return {
        "active_provider": provider,
        "active_key_suffix": f"...{key[-6:]}",
        "model": GROQ_MODEL if provider == "groq" else GEMINI_MODEL,
        "total_providers": _manager.count,
    }


app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(notif_router)
app.include_router(analytics_router)
app.include_router(jd_router, prefix="/jd", tags=["JD"])
app.include_router(cv_router, prefix="/cv", tags=["CV Analysis"])


