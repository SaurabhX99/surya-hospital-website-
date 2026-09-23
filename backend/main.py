"""
Vedansh Medicare — Appointment Booking API
Run : uvicorn main:app --reload --port 8000
Docs: http://localhost:8000/docs

This is the application entry point. It creates the FastAPI app, applies
middleware, mounts all route modules, and runs startup migrations.
"""
from __future__ import annotations

from datetime import datetime, timezone

import bcrypt
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import (
    ENABLE_DOCS, TENANT_NAME, ADMIN_EMAIL, ADMIN_PASSWORD,
    _request_tenant, _request_user_email,
)
from database import appointments_col, users_col, awards_col
from encryption import apply_encryption
from logging_config import setup_logging, get_logger
from security import apply_security, require_public_access, issue_page_token, rate_limit, ALLOWED_ORIGINS, IS_PROD

# ── Initialise structured logging ────────────────────────────────────
setup_logging()
logger = get_logger(__name__)

# ── Create FastAPI app ───────────────────────────────────────────────
app = FastAPI(
    title="Vedansh Medicare API",
    version="1.0.0",
    docs_url="/docs" if ENABLE_DOCS else None,
    redoc_url="/redoc" if ENABLE_DOCS else None,
    openapi_url="/openapi.json" if ENABLE_DOCS else None,
)

# ── Middleware stack (order matters: first added = innermost layer) ───
# 1. Encryption — innermost, closest to route handlers
apply_encryption(app)

# 2. CORS — strict in PROD (only whitelisted origins), open in DEV
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if (IS_PROD and ALLOWED_ORIGINS) else ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Security layers (API key, origin allowlist, page token, rate limiting)
apply_security(app)


# ── Tenant + user middleware — resolves tenant and logged-in user ─────
@app.middleware("http")
async def tenant_middleware(request: Request, call_next):
    tenant     = TENANT_NAME
    user_email = ""

    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if token:
        user = users_col.find_one(
            {"active_token": token},
            {"tenant_name": 1, "token_expires_at": 1, "email": 1, "active": 1},
        )
        if user:
            if not user.get("active", True):
                users_col.update_one({"_id": user["_id"]}, {"$unset": {"active_token": ""}})
            else:
                exp = user.get("token_expires_at")
                if exp:
                    if exp.tzinfo is None:
                        exp = exp.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) <= exp:
                        if user.get("tenant_name"):
                            tenant = user["tenant_name"]
                        user_email = user.get("email", "")

    _request_tenant.set(tenant)
    _request_user_email.set(user_email)
    return await call_next(request)


# ── Global exception handler ─────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception",
                 extra={"method": request.method, "path": request.url.path,
                        "error_type": type(exc).__name__, "error": str(exc)})
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error"},
    )


# ── Startup: seed admin user and run migrations ─────────────────────
# Migrate legacy "Super Admin" role to canonical "SUPER_ADMIN"
users_col.update_many({"role": "Super Admin"}, {"$set": {"role": "SUPER_ADMIN"}})
# Back-fill active flag for pre-existing users
users_col.update_many({"active": {"$exists": False}}, {"$set": {"active": True}})
# Back-fill tenant_name for seeded admin
if ADMIN_EMAIL:
    users_col.update_one(
        {"email": ADMIN_EMAIL, "tenant_name": {"$exists": False}},
        {"$set": {"tenant_name": TENANT_NAME}},
    )
# Create first SUPER_ADMIN from env vars if no users exist
if ADMIN_EMAIL and ADMIN_PASSWORD and users_col.count_documents({}) == 0:
    pw_hash = bcrypt.hashpw(ADMIN_PASSWORD.encode(), bcrypt.gensalt())
    users_col.insert_one({
        "email":         ADMIN_EMAIL,
        "password_hash": pw_hash,
        "name":          "Hospital Admin",
        "role":          "SUPER_ADMIN",
        "tenant_name":   TENANT_NAME,
        "active":        True,
        "created_at":    datetime.now(timezone.utc),
    })
    logger.info("Created SUPER_ADMIN user", extra={"user_email": ADMIN_EMAIL})

# Drop non-_id unique indexes on appointments (legacy cleanup)
for idx_name, idx_info in list(appointments_col.index_information().items()):
    if idx_name == "_id_" or not idx_info.get("unique"):
        continue
    try:
        appointments_col.drop_index(idx_name)
        logger.info("Dropped unique index", extra={"index": idx_name})
    except Exception as e:
        logger.warning("Could not drop index", extra={"index": idx_name, "error": str(e)})


# ── Seed default awards if collection is empty ──────────────────────
if awards_col.count_documents({"tenant_name": TENANT_NAME}) == 0:
    _default_awards = [
        {"title": "Best Hospital — Greater Noida & Noida", "description": "Certified as the best multi-speciality hospital in the region for clinical excellence and patient satisfaction.", "order": 0},
        {"title": "24×7 Emergency Excellence", "description": "Recognised for maintaining the highest standards of emergency medical care and rapid response protocols.", "order": 1},
        {"title": "Advanced Dialysis Centre", "description": "Awarded for state-of-the-art nephrology and dialysis services with the highest patient care standards.", "order": 2},
        {"title": "Patient Satisfaction Leader", "description": "Consistently rated highly for patient experience, staff behaviour, cleanliness, and clinical outcomes.", "order": 3},
        {"title": "NICU Excellence Award", "description": "Recognised for exceptional neonatal intensive care services and outcomes for premature and critically ill newborns.", "order": 4},
        {"title": "Trusted Maternity Hospital", "description": "Preferred choice for maternity care in Greater Noida, with exceptional delivery outcomes and postnatal support.", "order": 5},
    ]
    for a in _default_awards:
        a["tenant_name"] = TENANT_NAME
        a["active"] = True
        a["image"] = None
        a["created_at"] = datetime.now(timezone.utc)
        a["updated_by"] = "system"
    awards_col.insert_many(_default_awards)
    logger.info("Seeded default awards", extra={"count": len(_default_awards)})


# ── Root and public-token endpoints ──────────────────────────────────
@app.get("/")
def root():
    return {"status": "ok", "docs": "/docs"}


@app.get("/api/public-token")
def get_page_token(request: Request, _: None = Depends(rate_limit(20, 60))):
    """Issue a short-lived page token for public website API access."""
    return issue_page_token()


# ── Mount all route modules ──────────────────────────────────────────
from routes.appointments import router as appointments_router
from routes.doctors import router as doctors_router
from routes.departments import router as departments_router
from routes.blogs import router as blogs_router
from routes.testimonials import router as testimonials_router
from routes.media import router as media_router
from routes.offers import router as offers_router
from routes.insurance import router as insurance_router
from routes.partners import router as partners_router
from routes.hero_stats import router as hero_stats_router
from routes.facilities import router as facilities_router
from routes.faqs import router as faqs_router
from routes.sms import router as sms_router
from routes.site_config import router as site_config_router
from routes.auth import router as auth_router
from routes.admin_users import router as admin_users_router
from routes.audit_logs import router as audit_logs_router
from routes.api_keys import router as api_keys_router
from routes.awards import router as awards_router
from routes.uploads import router as uploads_router

app.include_router(appointments_router)
app.include_router(doctors_router)
app.include_router(departments_router)
app.include_router(blogs_router)
app.include_router(testimonials_router)
app.include_router(media_router)
app.include_router(offers_router)
app.include_router(insurance_router)
app.include_router(partners_router)
app.include_router(hero_stats_router)
app.include_router(facilities_router)
app.include_router(faqs_router)
app.include_router(sms_router)
app.include_router(site_config_router)
app.include_router(auth_router)
app.include_router(admin_users_router)
app.include_router(audit_logs_router)
app.include_router(api_keys_router)
app.include_router(awards_router)
app.include_router(uploads_router)

logger.info("Application started", extra={"tenant": TENANT_NAME})
