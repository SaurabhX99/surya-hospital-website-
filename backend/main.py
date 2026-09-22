"""
Vedansh Medicare — Appointment Booking API
Run : uvicorn main:app --reload --port 8000
Docs: http://localhost:8000/docs
"""
from __future__ import annotations

import contextvars
import os
import re
import secrets
import pyotp
from datetime import datetime, timezone, timedelta
from typing import Optional

import bcrypt
import certifi
import httpx
from bson import ObjectId
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

load_dotenv()

from security import apply_security, require_public_access, issue_page_token, rate_limit
from encryption import apply_encryption

# ── Tenant & upload config ──────────────────────────────────────────
TENANT_NAME = os.getenv("TENANT_NAME", "vedansh_medicare").strip()
BASE_URL    = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")

# Per-request tenant (set by middleware from auth token; defaults to TENANT_NAME)
_request_tenant: contextvars.ContextVar[str] = contextvars.ContextVar("_request_tenant")

# Per-request user email — set by middleware when a valid admin token is present.
# Used by write routes to populate the `updated_by` audit field without needing
# to change every function signature.
_request_user_email: contextvars.ContextVar[str] = contextvars.ContextVar("_request_user_email", default="")

def _tenant() -> str:
    return _request_tenant.get(TENANT_NAME)

def _user_email() -> str:
    """Return the email of the currently authenticated admin, or empty string."""
    return _request_user_email.get("")

def _tq(extra: dict | None = None) -> dict:
    """Return a base query scoped to the current request's tenant."""
    return {"tenant_name": _tenant(), **(extra or {})}


def _paginated(collection, query: dict, *, sort_field: str = "created_at",
               sort_dir: int = DESCENDING, fmt_fn, page: int | None = None,
               limit: int = 20):
    """
    Return items from *collection* matching *query*.

    If *page* is provided (>=1), return a paginated envelope:
        {"total": N, "page": P, "limit": L, "items": [...]}
    Otherwise return a flat list for backward compatibility with the
    public website which expects a plain JSON array.
    """
    cursor = collection.find(query).sort(sort_field, sort_dir)
    if page is not None:
        page = max(1, page)
        total = collection.count_documents(query)
        cursor = cursor.skip((page - 1) * limit).limit(limit)
        items = [fmt_fn(d) for d in cursor]
        return {"total": total, "page": page, "limit": limit, "items": items}
    return [fmt_fn(d) for d in cursor]

# ── App ────────────────────────────────────────────────────────────
_docs_enabled = os.getenv("ENABLE_DOCS", "false").lower() == "true"
app = FastAPI(
    title="Vedansh Medicare API",
    version="1.0.0",
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

# Encryption middleware — innermost layer, closest to route handlers.
# Must be added FIRST so it sits inside CORS and security middleware.
apply_encryption(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Apply all four security layers (API key, origin allowlist, page token, rate limiting).
apply_security(app)

# ── MongoDB ────────────────────────────────────────────────────────
_client = MongoClient(
    os.getenv("MONGO_URI", ""),
    tls=True,
    tlsAllowInvalidCertificates=True,
)
_mdb    = _client[os.getenv("DATABASE_NAME", "").strip()]
_col     = _mdb["appointments"]
_dcol    = _mdb["doctors"]
_deptcol = _mdb["departments"]
_bcol    = _mdb["blogs"]
_mediacol  = _mdb["media"]
_gcfgcol   = _mdb["gallery_config"]
_testcol   = _mdb["testimonials"]
_usercol   = _mdb["admin_users"]
_offercol  = _mdb["offers"]
_inscol    = _mdb["insurance_providers"]
_partnercol = _mdb["partners"]
_statscol   = _mdb["hero_stats"]
_smscfgcol  = _mdb["sms_config"]        # stores admin-configured SMS provider settings & template
_sitecfgcol = _mdb["site_config"]       # stores site-wide settings like hospital phone number
_smslogcol      = _mdb["sms_logs"]       # append-only audit log of every SMS attempt
_facilitiescol  = _mdb["facilities"]    # hospital facilities (ICU, OT, etc.)
_faqcol         = _mdb["faqs"]          # FAQ question/answer pairs shown in chat + site
_auditcol       = _mdb["audit_logs"]    # purge/deletion audit trail for SUPER_ADMIN

# ── Tenant + user middleware — resolves tenant and logged-in user per request ──
@app.middleware("http")
async def _tenant_middleware(request: Request, call_next):
    tenant     = TENANT_NAME
    user_email = ""

    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if token:
        # Fetch the fields we need for tenant resolution AND audit logging.
        # Also fetch `active` so deactivated users are locked out at the middleware level.
        user = _usercol.find_one(
            {"active_token": token},
            {"tenant_name": 1, "token_expires_at": 1, "email": 1, "active": 1},
        )
        if user:
            # Deactivated users: clear their stored token immediately so the
            # next request (without Bearer header) falls back to the public path.
            if not user.get("active", True):
                _usercol.update_one({"_id": user["_id"]}, {"$unset": {"active_token": ""}})
            else:
                exp = user.get("token_expires_at")
                if exp:
                    if exp.tzinfo is None:
                        exp = exp.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) <= exp:
                        if user.get("tenant_name"):
                            tenant = user["tenant_name"]
                        # Store the email in the per-request context var so write
                        # routes can log it as `updated_by` without extra DB calls.
                        user_email = user.get("email", "")

    _request_tenant.set(tenant)
    _request_user_email.set(user_email)
    return await call_next(request)

# ── Seed / migrate admin users on startup ──────────────────────────
_admin_email    = os.getenv("ADMIN_EMAIL", "").strip().lower()
_admin_password = os.getenv("ADMIN_PASSWORD", "").strip()

# Migrate any legacy "Super Admin" role string to the canonical "SUPER_ADMIN"
# value used by the new role-based access control system.
_usercol.update_many({"role": "Super Admin"}, {"$set": {"role": "SUPER_ADMIN"}})

# Back-fill `active: True` for any existing users that predate this field.
_usercol.update_many({"active": {"$exists": False}}, {"$set": {"active": True}})

# Back-fill tenant_name for any seeded user that was created without it.
if _admin_email:
    _usercol.update_one(
        {"email": _admin_email, "tenant_name": {"$exists": False}},
        {"$set": {"tenant_name": TENANT_NAME}},
    )

# Create the first SUPER_ADMIN from env vars if no users exist yet.
if _admin_email and _admin_password and _usercol.count_documents({}) == 0:
    _pw_hash = bcrypt.hashpw(_admin_password.encode(), bcrypt.gensalt())
    _usercol.insert_one({
        "email":        _admin_email,
        "password_hash":_pw_hash,
        "name":         "Hospital Admin",
        "role":         "SUPER_ADMIN",   # canonical role for the initial admin
        "tenant_name":  TENANT_NAME,
        "active":       True,
        "created_at":   datetime.now(timezone.utc),
    })
    print(f"[STARTUP] Created SUPER_ADMIN user: {_admin_email}")

# Drop ALL non-_id unique indexes on appointments — let MongoDB _id be the only PK.
for _idx_name, _idx_info in list(_col.index_information().items()):
    if _idx_name == "_id_" or not _idx_info.get("unique"):
        continue
    try:
        _col.drop_index(_idx_name)
        print(f"[STARTUP] Dropped unique index: {_idx_name}")
    except Exception as _e:
        print(f"[STARTUP] Could not drop index {_idx_name}: {_e}")

_STATUS_MAP = {
    "BOOKED": "confirmed", "PENDING": "pending",
    "CANCELLED": "cancelled", "COMPLETED": "completed",
}

def _fmt(doc: dict) -> dict:
    """Convert a MongoDB document to a JSON-serialisable dict."""
    doc["id"] = str(doc.pop("_id"))
    # Normalise field names from Atlas schema
    doc["name"]           = doc.get("patientName") or doc.get("name") or ""
    doc["mobile"]         = doc.get("phoneNumber")  or doc.get("mobile") or ""
    doc["preferred_date"] = doc.get("appointmentDate") or doc.get("preferred_date") or "—"
    doc["appt_time"]      = doc.get("appointmentTime") or ""
    doc["doctor"]         = doc.get("doctorName") or ""
    doc["message"]        = doc.get("reason") or doc.get("message") or ""
    doc["appt_id"]        = doc.get("appointmentId") or ""
    # Normalise created_at
    ca = doc.get("createdAt") or doc.get("created_at")
    if isinstance(ca, datetime):
        doc["created_at"] = ca.isoformat()
    else:
        doc["created_at"] = str(ca) if ca else ""
    # Normalise status
    raw = doc.get("status", "pending")
    doc["status"] = _STATUS_MAP.get(raw, raw.lower() if raw else "pending")
    return doc


# ── Schemas ────────────────────────────────────────────────────────
class AppointmentIn(BaseModel):
    name: str
    mobile: str
    department: Optional[str] = None
    doctor: Optional[str] = None
    date: Optional[str] = None
    message: Optional[str] = None


class OfferIn(BaseModel):
    text: str
    active: bool = True
    order: int = 0


class OfferUpdate(BaseModel):
    text: Optional[str] = None
    active: Optional[bool] = None
    order: Optional[int] = None


class InsuranceIn(BaseModel):
    name: str
    logo_drive_link: Optional[str] = None
    active: bool = True
    order: int = 0


class InsuranceUpdate(BaseModel):
    name: Optional[str] = None
    logo_drive_link: Optional[str] = None
    active: Optional[bool] = None
    order: Optional[int] = None


class PartnerIn(BaseModel):
    name: str
    logo_drive_link: Optional[str] = None
    active: bool = True
    order: int = 0


class PartnerUpdate(BaseModel):
    name: Optional[str] = None
    logo_drive_link: Optional[str] = None
    active: Optional[bool] = None
    order: Optional[int] = None


class StatIn(BaseModel):
    label: str
    count: int
    suffix: str = '+'
    icon_key: str = 'patients'
    order: int = 0
    active: bool = True


class StatUpdate(BaseModel):
    label: Optional[str] = None
    count: Optional[int] = None
    suffix: Optional[str] = None
    icon_key: Optional[str] = None
    order: Optional[int] = None
    active: Optional[bool] = None


# ── SMS Configuration models ─────────────────────────────────────────
# All SMS credentials and the message template are stored in MongoDB
# (not .env) so admins can update them via the portal without a redeploy.

class SmsConfigIn(BaseModel):
    """Full SMS configuration document saved to the sms_config collection.
    Supports two providers selectable at runtime:
      - "twilio"   : uses account_sid + auth_token + from_number
      - "gupshup"  : uses gupshup_api_key + gupshup_app_name + from_number
    Sensitive fields (account_sid, auth_token, gupshup_api_key) are masked
    in the GET response and the mask placeholder is preserved on save if unchanged.
    """
    enabled:           bool = False
    provider:          str  = "twilio"      # "twilio" | "gupshup"
    # Twilio credentials
    account_sid:       Optional[str] = None  # Twilio Account SID (AC…), masked in GET
    auth_token:        Optional[str] = None  # Twilio Auth Token, masked in GET
    # Gupshup credentials
    gupshup_api_key:   Optional[str] = None  # Gupshup API key, masked in GET
    gupshup_app_name:  Optional[str] = None  # Gupshup registered app / sender name
    # Shared
    from_number:       Optional[str] = None  # Sender ID or number (E.164 / DLT registered)
    # Template supports: {name} {mobile} {department} {doctor} {date} {appointment_id}
    template: str = (
        "Dear {name}, your appointment has been received. "
        "Ref: {appointment_id}. Dept: {department}. "
        "Date: {date}. We will call you shortly to confirm."
    )


class SmsTestIn(BaseModel):
    """Body for the test-SMS endpoint — just a destination phone number."""
    phone: str   # will be normalised to E.164 before sending


class SiteConfigIn(BaseModel):
    """
    Site-wide settings stored as a single document per tenant.
    Currently holds the hospital contact number; extend as needed.
    """
    phone: Optional[str] = None   # hospital's public contact number shown on the site


class UserCreateIn(BaseModel):
    """Body for SUPER_ADMIN creating a new admin user."""
    email:    str
    name:     str
    password: str
    role:     str = "ADMIN"   # ADMIN | SUPER_ADMIN

class UserUpdateIn(BaseModel):
    """Body for SUPER_ADMIN editing an existing admin user. All fields optional."""
    email:    Optional[str] = None
    name:     Optional[str] = None
    password: Optional[str] = None   # if provided, hash and replace; if omitted, keep existing
    role:     Optional[str] = None


class FacilityIn(BaseModel):
    name:        str
    short_desc:  str = ""
    description: str = ""
    category:    str = "general"   # critical | surgery | maternity | diagnostics | general
    color:       str = "#0A4D8C"
    order:       int  = 0
    active:      bool = True

class FacilityUpdate(BaseModel):
    name:        Optional[str]  = None
    short_desc:  Optional[str]  = None
    description: Optional[str]  = None
    category:    Optional[str]  = None
    color:       Optional[str]  = None
    order:       Optional[int]  = None
    active:      Optional[bool] = None

class FaqIn(BaseModel):
    question: str
    answer:   str
    order:    int  = 0
    active:   bool = True

class FaqUpdate(BaseModel):
    question: Optional[str]  = None
    answer:   Optional[str]  = None
    order:    Optional[int]  = None
    active:   Optional[bool] = None

class StatusIn(BaseModel):
    status: str

class DoctorIn(BaseModel):
    name: str
    qualification: str
    specialty: str
    department: str
    experience: str
    timing: str
    photo: Optional[str] = None
    featured: bool = False
    active: bool = True

class DepartmentIn(BaseModel):
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    head_doctor: Optional[str] = None
    order: int = 0
    active: bool = True


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    head_doctor: Optional[str] = None
    order: Optional[int] = None
    active: Optional[bool] = None


class DoctorUpdate(BaseModel):
    name: Optional[str] = None
    qualification: Optional[str] = None
    specialty: Optional[str] = None
    department: Optional[str] = None
    experience: Optional[str] = None
    timing: Optional[str] = None
    photo: Optional[str] = None
    featured: Optional[bool] = None
    active: Optional[bool] = None


class BlogIn(BaseModel):
    title: str
    author: str
    category: str
    drive_link: str
    excerpt: Optional[str] = None
    thumbnail: Optional[str] = None
    tags: Optional[str] = None
    published: bool = True


class BlogUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    category: Optional[str] = None
    excerpt: Optional[str] = None
    thumbnail: Optional[str] = None
    tags: Optional[str] = None
    published: Optional[bool] = None
    drive_link: Optional[str] = None


class MediaIn(BaseModel):
    title: str
    type: str = "image"          # "image" or "video"
    drive_link: str
    alt: Optional[str] = None
    show_in_gallery: bool = True
    order: int = 0


class MediaUpdate(BaseModel):
    title: Optional[str] = None
    type: Optional[str] = None
    drive_link: Optional[str] = None
    alt: Optional[str] = None
    show_in_gallery: Optional[bool] = None
    order: Optional[int] = None


class GalleryConfigIn(BaseModel):
    autoplay: Optional[bool] = None
    interval: Optional[int] = None      # milliseconds between slides
    transition: Optional[str] = None    # "fade" or "slide"
    show_captions: Optional[bool] = None


class TestimonialIn(BaseModel):
    name: str
    text: str
    rating: int = 5
    approved: bool = False


class TestimonialUpdate(BaseModel):
    name: Optional[str] = None
    text: Optional[str] = None
    rating: Optional[int] = None
    approved: Optional[bool] = None


class LoginIn(BaseModel):
    email: str
    password: str


class MFAVerifyIn(BaseModel):
    pre_token: str
    code: str


# ── Auth Helpers ────────────────────────────────────────────────────
def _get_bearer(request: Request) -> str:
    return request.headers.get("Authorization", "").removeprefix("Bearer ").strip()


def _verify_token(token: str) -> dict | None:
    """
    Return user doc if token is valid, not expired, and the user is active.
    Returns None for missing/invalid tokens, expired tokens, or deactivated users.
    """
    if not token:
        return None
    user = _usercol.find_one({"active_token": token})
    if not user:
        return None
    # Block deactivated users — SUPER_ADMIN can toggle this via the Users page.
    if not user.get("active", True):
        return None
    exp = user.get("token_expires_at")
    if not exp:
        return None
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > exp:
        return None
    return user


def _require_admin(request: Request) -> dict:
    """
    FastAPI dependency — allows any authenticated admin user (any role).
    Raises HTTP 401 if the bearer token is missing, invalid, expired, or the
    user account has been deactivated by a SUPER_ADMIN.
    """
    token = _get_bearer(request)
    user  = _verify_token(token)
    if not user:
        raise HTTPException(401, "Admin authentication required")
    return user


def _require_super_admin(request: Request) -> dict:
    """
    FastAPI dependency — allows only users with the SUPER_ADMIN role.
    Used on privileged routes such as SMS/API credentials management and
    the user activation/deactivation endpoints.
    Raises HTTP 403 (not 401) so the frontend can distinguish "not logged in"
    from "logged in but insufficient permissions".
    """
    token = _get_bearer(request)
    user  = _verify_token(token)
    if not user:
        raise HTTPException(401, "Admin authentication required")
    if user.get("role") != "SUPER_ADMIN":
        raise HTTPException(403, "This action requires SUPER_ADMIN privileges")
    return user


# ── Notifications ──────────────────────────────────────────────────
_SID   = os.getenv("TWILIO_ACCOUNT_SID",  "")
_TOKEN = os.getenv("TWILIO_AUTH_TOKEN",    "")
_FROM  = os.getenv("TWILIO_FROM_NUMBER",   "")
_WA    = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")


def _e164(mobile: str) -> str:
    d = "".join(c for c in mobile if c.isdigit())
    if len(d) == 10:
        return f"+91{d}"
    if d.startswith("91") and len(d) == 12:
        return f"+{d}"
    return f"+{d}"


def _send_sms(to: str, body: str) -> None:
    if not (_SID and _TOKEN and _FROM):
        print(f"[SMS-SKIP] {to}: {body[:60]}…")
        return
    from twilio.rest import Client
    Client(_SID, _TOKEN).messages.create(to=to, from_=_FROM, body=body)


def _send_whatsapp(to: str, body: str) -> None:
    if not (_SID and _TOKEN):
        print(f"[WA-SKIP]  {to}: {body[:60]}…")
        return
    from twilio.rest import Client
    Client(_SID, _TOKEN).messages.create(to=f"whatsapp:{to}", from_=_WA, body=body)


def _notify(name: str, mobile: str, dept: str, date: Optional[str]) -> None:
    to  = _e164(mobile)
    msg = (
        f"Hi {name}! Your appointment at Vedansh Medicare has been received.\n"
        f"Department : {dept}\n"
        f"Pref. date : {date or 'to be confirmed'}\n"
        f"Our team will call you within 30 minutes to confirm.\n"
        f"Helpline   : +91 9650494019"
    )
    try:
        _send_sms(to, msg)
    except Exception as e:
        print(f"[SMS-ERR] {e}")
    try:
        _send_whatsapp(to, msg)
    except Exception as e:
        print(f"[WA-ERR]  {e}")


def _send_appointment_sms(
    appointment_id: str,
    name: str,
    mobile: str,
    department: str,
    doctor: str,
    date: Optional[str],
) -> None:
    """
    Send a patient confirmation SMS using the admin-configured SMS settings.

    Reads provider credentials and the message template fresh from MongoDB on
    every call so changes made in the admin portal take effect immediately —
    no server restart needed.

    Placeholders supported in the template:
        {name}           – patient full name
        {mobile}         – patient mobile number
        {department}     – department selected at booking
        {doctor}         – preferred doctor (falls back to "To be assigned")
        {date}           – preferred appointment date (falls back to "To be confirmed")
        {appointment_id} – first 8 characters of the MongoDB ObjectId, uppercased,
                           used as a short human-readable reference number
    """
    # Fetch the current SMS configuration for this tenant from the database
    cfg = _smscfgcol.find_one(_tq())

    # Bail out silently if SMS is disabled or not yet configured
    if not cfg or not cfg.get("enabled"):
        print(f"[SMS-CONFIG] SMS disabled or not configured — skipping for appointment {appointment_id}")
        return

    provider = cfg.get("provider", "twilio")

    template  = cfg.get("template", "").strip()
    from_num  = cfg.get("from_number", "").strip()

    # Build the short appointment reference (first 8 chars of ObjectId, uppercase)
    short_id = appointment_id[:8].upper()

    # Render the template with live appointment data
    try:
        message = template.format(
            name           = name,
            mobile         = mobile,
            department     = department or "General",
            doctor         = doctor or "To be assigned",
            date           = date or "To be confirmed",
            appointment_id = short_id,
        )
    except KeyError as ke:
        print(f"[SMS-TEMPLATE] Unknown placeholder {ke} in template — skipping SMS")
        return

    # Normalise the patient's mobile to E.164 / numeric for sending
    to = _e164(mobile)

    # Base audit log entry — updated with outcome after the send attempt
    log_entry = {
        "tenant_name":    _tenant(),
        "appointment_id": appointment_id,
        "ref_id":         short_id,
        "to":             to,
        "patient_name":   name,
        "department":     department or "General",
        "doctor":         doctor or "To be assigned",
        "date":           date or "To be confirmed",
        "message":        message,
        "provider":       provider,
        "status":         "pending",
        "error":          None,
        "sent_at":        datetime.now(timezone.utc),
    }

    try:
        if provider == "twilio":
            sid   = cfg.get("account_sid", "").strip()
            token = cfg.get("auth_token", "").strip()
            if not (sid and token and from_num and template):
                print("[SMS-CONFIG] Twilio credentials incomplete — skipping SMS")
                return
            from twilio.rest import Client
            Client(sid, token).messages.create(to=to, from_=from_num, body=message)
            print(f"[SMS-OK] Twilio SMS sent to {to} (ref {short_id})")
            log_entry["status"] = "success"

        elif provider == "gupshup":
            # Gupshup enterprise SMS API
            # Docs: https://docs.gupshup.io/docs/send-message-sms
            gs_api_key  = cfg.get("gupshup_api_key", "").strip()
            gs_app_name = cfg.get("gupshup_app_name", "").strip()
            if not (gs_api_key and from_num and template):
                print("[SMS-CONFIG] Gupshup credentials incomplete — skipping SMS")
                return
            # Gupshup expects the destination as digits only (e.g. 919876543210)
            gs_to = to.lstrip("+")
            import httpx as _httpx
            resp = _httpx.post(
                "https://api.gupshup.io/sm/api/v1/msg",
                headers={"apikey": gs_api_key, "Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "channel":    "sms",
                    "source":     from_num,
                    "destination": gs_to,
                    "message":    message,
                    "src.name":   gs_app_name or from_num,
                },
                timeout=15,
            )
            resp.raise_for_status()
            result_json = resp.json()
            # Gupshup returns {"status":"submitted"} on success
            if result_json.get("status") not in ("submitted", "success"):
                raise RuntimeError(f"Gupshup response: {result_json}")
            print(f"[SMS-OK] Gupshup SMS sent to {gs_to} (ref {short_id})")
            log_entry["status"] = "success"

        else:
            print(f"[SMS-CONFIG] Unsupported provider '{provider}' — skipping SMS")
            return

    except Exception as e:
        print(f"[SMS-ERR] Failed to send via {provider} to {to}: {e}")
        log_entry["status"] = "failed"
        log_entry["error"]  = str(e)
    finally:
        try:
            _smslogcol.insert_one(log_entry)
        except Exception as le:
            print(f"[SMS-LOG-ERR] Could not write audit log: {le}")


# ── Global exception handler (ensures CORS headers on all errors) ───
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"[ERROR] {request.method} {request.url.path} → {type(exc).__name__}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error"},
    )

# ── Routes ─────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "ok", "docs": "/docs"}


@app.get("/api/public-token")
def get_page_token(request: Request, _: None = Depends(rate_limit(20, 60))):
    """Issue a short-lived page token for public website API access (Layer 3)."""
    return issue_page_token()


@app.post("/api/appointments", status_code=201)
def create_appointment(request: Request, body: AppointmentIn,
                       _auth: None = Depends(require_public_access),
                       _rl:   None = Depends(rate_limit(10, 60))):
    doc = {
        "tenant_name":    _tenant(),
        "name":           body.name,
        "mobile":         body.mobile,
        "department":     body.department,
        "doctor":         body.doctor or "",
        "preferred_date": body.date,
        "message":        body.message,
        "status":         "pending",
        "created_at":     datetime.now(timezone.utc),
    }
    try:
        result = _col.insert_one(doc)
    except DuplicateKeyError as _dke:
        # Drop whatever unique index caused the conflict, then retry
        print(f"[WARN] DuplicateKeyError on insert: {_dke}. Dropping all unique indexes and retrying.")
        for _idx_name, _idx_info in list(_col.index_information().items()):
            if _idx_name != "_id_" and _idx_info.get("unique"):
                try:
                    _col.drop_index(_idx_name)
                except Exception:
                    pass
        doc.pop("_id", None)
        try:
            result = _col.insert_one(doc)
        except DuplicateKeyError:
            doc.pop("_id", None)
            result = _col.insert_one(doc)
    # Legacy WhatsApp notification (env-var-based, kept for backward compatibility)
    _notify(body.name, body.mobile, body.department, body.date)

    # Admin-configured SMS notification — credentials and template live in DB
    _send_appointment_sms(
        appointment_id = str(result.inserted_id),
        name           = body.name,
        mobile         = body.mobile,
        department     = body.department or "",
        doctor         = body.doctor or "",
        date           = body.date,
    )

    return {"success": True, "id": str(result.inserted_id)}


# NOTE: /stats must come before /{appt_id} to avoid route conflict
@app.get("/api/appointments/stats")
def get_stats():
    total     = _col.count_documents(_tq())
    pending   = _col.count_documents(_tq({"status": {"$in": ["pending", "PENDING"]}}))
    confirmed = _col.count_documents(_tq({"status": {"$in": ["confirmed", "BOOKED"]}}))
    start_of_today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_oid = ObjectId.from_datetime(start_of_today)
    today     = _col.count_documents(_tq({"_id": {"$gte": today_oid}}))
    return {"total": total, "pending": pending, "confirmed": confirmed, "today": today}


@app.get("/api/appointments")
def list_appointments(
    status: Optional[str] = None,
    search: Optional[str] = None,
    department: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: Optional[int] = None,
    limit: int = 20,
):
    extra: dict = {}
    if status:
        extra["status"] = status
    if department:
        extra["department"] = {"$regex": department, "$options": "i"}
    if date_from or date_to:
        date_filter: dict = {}
        if date_from:
            date_filter["$gte"] = date_from
        if date_to:
            date_filter["$lte"] = date_to
        extra["preferred_date"] = date_filter
    if search:
        search_or = [
            {"name": {"$regex": search, "$options": "i"}},
            {"patientName": {"$regex": search, "$options": "i"}},
            {"mobile": {"$regex": search}},
            {"phoneNumber": {"$regex": search}},
        ]
        extra["$or"] = search_or
    query = _tq(extra)
    return _paginated(_col, query, sort_field="createdAt", sort_dir=DESCENDING,
                      fmt_fn=_fmt, page=page, limit=limit)


# ── Appointment Export & Purge ─────────────────────────────────────
# NOTE: These must be defined BEFORE /{appt_id} to avoid path conflict.

def _appt_purge_query(date_from: str | None, date_to: str | None, status: str | None) -> dict:
    """Build a tenant-scoped MongoDB query for appointment purge/export."""
    extra: dict = {}
    if status:
        extra["status"] = status
    if date_from or date_to:
        df: dict = {}
        if date_from:
            df["$gte"] = date_from
        if date_to:
            df["$lte"] = date_to
        extra["preferred_date"] = df
    return _tq(extra)


class PurgeIn(BaseModel):
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    status: Optional[str] = None


@app.get("/api/appointments/export")
def export_appointments(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    _admin: dict = Depends(_require_admin),
):
    """Export matching appointments as an Excel (.xlsx) file."""
    import io
    from openpyxl import Workbook

    q = _appt_purge_query(date_from, date_to, status)
    docs = list(_col.find(q).sort("createdAt", DESCENDING))

    wb = Workbook()
    ws = wb.active
    ws.title = "Appointments"
    headers = ["ID", "Patient", "Mobile", "Department", "Doctor",
               "Preferred Date", "Time", "Reason", "Status", "Created At"]
    ws.append(headers)
    for d in docs:
        f = _fmt(d)
        ws.append([
            f.get("appt_id") or f.get("id", ""),
            f.get("name", ""),
            f.get("mobile", ""),
            f.get("department", ""),
            f.get("doctor", ""),
            f.get("preferred_date", ""),
            f.get("appt_time", ""),
            f.get("message", ""),
            f.get("status", ""),
            f.get("created_at", ""),
        ])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"appointments_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/appointments/count")
def count_appointments_for_purge(body: PurgeIn, _admin: dict = Depends(_require_admin)):
    """Return the number of appointments that match the purge filters (preview)."""
    q = _appt_purge_query(body.date_from, body.date_to, body.status)
    return {"count": _col.count_documents(q)}


@app.post("/api/appointments/purge")
def purge_appointments(body: PurgeIn, _admin: dict = Depends(_require_admin)):
    """Delete appointments matching the given date range and status filters."""
    q = _appt_purge_query(body.date_from, body.date_to, body.status)
    count = _col.count_documents(q)
    result = _col.delete_many(q)
    # Audit log entry
    _auditcol.insert_one({
        "tenant_name": _tenant(),
        "action":      "purge_appointments",
        "performed_by": _user_email(),
        "timestamp":   datetime.now(timezone.utc),
        "records_deleted": result.deleted_count,
        "filters": {
            "date_from": body.date_from,
            "date_to":   body.date_to,
            "status":    body.status,
        },
    })
    return {"success": True, "deleted": result.deleted_count}


@app.get("/api/appointments/{appt_id}")
def get_appointment(appt_id: str):
    try:
        doc = _col.find_one(_tq({"_id": ObjectId(appt_id)}))
    except Exception:
        raise HTTPException(400, "Invalid id")
    if not doc:
        raise HTTPException(404, "Not found")
    return _fmt(doc)


def _gdrive_direct(url: Optional[str]) -> Optional[str]:
    """Convert Google Drive share URL to a backend proxy URL for reliable image display."""
    if not url:
        return url
    m = re.search(r'drive\.google\.com/file/d/([^/?]+)', url)
    if m:
        return f"{BASE_URL}/api/proxy/image?id={m.group(1)}"
    m = re.search(r'drive\.google\.com/open\?id=([^&\s]+)', url)
    if m:
        return f"{BASE_URL}/api/proxy/image?id={m.group(1)}"
    return url


def _fmt_doctor(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    ca = doc.get("created_at")
    if isinstance(ca, datetime):
        doc["created_at"] = ca.isoformat()
    doc.setdefault("photo", None)
    doc.setdefault("featured", False)
    doc.setdefault("active", True)
    if doc.get("photo"):
        doc["photo"] = _gdrive_direct(doc["photo"])
    return doc


@app.patch("/api/appointments/{appt_id}/status")
def update_status(appt_id: str, body: StatusIn):
    allowed = {"pending", "confirmed", "cancelled", "completed", "rejected"}
    if body.status not in allowed:
        raise HTTPException(400, f"status must be one of {allowed}")
    try:
        oid = ObjectId(appt_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    result = _col.update_one(_tq({"_id": oid}), {"$set": {"status": body.status}})
    if result.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


# ── Doctor Routes ───────────────────────────────────────────────────
@app.get("/api/doctors")
def list_doctors(
    featured: Optional[bool] = None,
    show_all: bool = False,
    search: Optional[str] = None,
    department: Optional[str] = None,
    page: Optional[int] = None,
    limit: int = 20,
    _: None = Depends(require_public_access),
):
    try:
        query = _tq() if show_all else _tq({"active": True})
        if featured is not None:
            query["featured"] = featured
        if department:
            query["department"] = {"$regex": department, "$options": "i"}
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"specialty": {"$regex": search, "$options": "i"}},
                {"qualification": {"$regex": search, "$options": "i"}},
            ]
        return _paginated(_dcol, query, sort_field="created_at", sort_dir=DESCENDING,
                          fmt_fn=_fmt_doctor, page=page, limit=limit)
    except Exception as e:
        print(f"[ERROR] list_doctors: {e}")
        raise HTTPException(503, "Database temporarily unavailable")


@app.post("/api/doctors", status_code=201)
def create_doctor(body: DoctorIn, _: None = Depends(_require_admin)):
    try:
        doc = body.model_dump()
        doc["tenant_name"] = _tenant()
        doc["created_at"]  = datetime.now(timezone.utc)
        doc["updated_by"]  = _user_email()   # audit: who created this record
        result = _dcol.insert_one(doc)
        return {"success": True, "id": str(result.inserted_id)}
    except Exception as e:
        print(f"[ERROR] create_doctor: {e}")
        raise HTTPException(503, "Database temporarily unavailable")


@app.patch("/api/doctors/{doctor_id}")
def update_doctor(doctor_id: str, body: DoctorUpdate, _: None = Depends(_require_admin)):
    try:
        oid = ObjectId(doctor_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    try:
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(400, "No fields to update")
        updates["updated_by"] = _user_email()   # audit: who last modified this record
        result = _dcol.update_one(_tq({"_id": oid}), {"$set": updates})
        if result.matched_count == 0:
            raise HTTPException(404, "Not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] update_doctor: {e}")
        raise HTTPException(503, "Database temporarily unavailable")


@app.delete("/api/doctors/{doctor_id}")
def delete_doctor(doctor_id: str, _: None = Depends(_require_admin)):
    try:
        oid = ObjectId(doctor_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    try:
        result = _dcol.delete_one(_tq({"_id": oid}))
        if result.deleted_count == 0:
            raise HTTPException(404, "Not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] delete_doctor: {e}")
        raise HTTPException(503, "Database temporarily unavailable")


# ── Department Routes ────────────────────────────────────────────────
def _fmt_department(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    ca = doc.get("created_at")
    if isinstance(ca, datetime):
        doc["created_at"] = ca.isoformat()
    doc.setdefault("description", None)
    doc.setdefault("icon", None)
    doc.setdefault("head_doctor", None)
    doc.setdefault("order", 0)
    doc.setdefault("active", True)
    return doc


@app.get("/api/departments")
def list_departments(
    show_all: bool = False,
    search: Optional[str] = None,
    page: Optional[int] = None,
    limit: int = 20,
    _: None = Depends(require_public_access),
):
    try:
        query = _tq() if show_all else _tq({"active": True})
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}},
                {"head_doctor": {"$regex": search, "$options": "i"}},
            ]
        return _paginated(_deptcol, query, sort_field="order", sort_dir=ASCENDING,
                          fmt_fn=_fmt_department, page=page, limit=limit)
    except Exception as e:
        print(f"[ERROR] list_departments: {e}")
        raise HTTPException(503, "Database temporarily unavailable")


@app.post("/api/departments", status_code=201)
def create_department(body: DepartmentIn, _: None = Depends(_require_admin)):
    try:
        doc = body.model_dump()
        doc["tenant_name"] = _tenant()
        doc["created_at"]  = datetime.now(timezone.utc)
        doc["updated_by"]  = _user_email()
        result = _deptcol.insert_one(doc)
        return {"success": True, "id": str(result.inserted_id)}
    except Exception as e:
        print(f"[ERROR] create_department: {e}")
        raise HTTPException(503, "Database temporarily unavailable")


@app.patch("/api/departments/{dept_id}")
def update_department(dept_id: str, body: DepartmentUpdate, _: None = Depends(_require_admin)):
    try:
        oid = ObjectId(dept_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    try:
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(400, "No fields to update")
        updates["updated_by"] = _user_email()
        result = _deptcol.update_one(_tq({"_id": oid}), {"$set": updates})
        if result.matched_count == 0:
            raise HTTPException(404, "Not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] update_department: {e}")
        raise HTTPException(503, "Database temporarily unavailable")


@app.delete("/api/departments/{dept_id}")
def delete_department(dept_id: str, _: None = Depends(_require_admin)):
    try:
        oid = ObjectId(dept_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    try:
        result = _deptcol.delete_one(_tq({"_id": oid}))
        if result.deleted_count == 0:
            raise HTTPException(404, "Not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] delete_department: {e}")
        raise HTTPException(503, "Database temporarily unavailable")


# ── Blog Routes ──────────────────────────────────────────────────────

def _drive_content_url(link: str) -> str:
    """Convert a Google Drive / Docs share link to a direct content URL."""
    # Google Docs → export as HTML
    m = re.search(r'docs\.google\.com/document/d/([^/?]+)', link)
    if m:
        return f"https://docs.google.com/document/d/{m.group(1)}/export?format=html"
    # Drive file (file/d/ID or open?id=ID) → direct download
    m = re.search(r'drive\.google\.com/file/d/([^/?]+)', link)
    if m:
        return f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    m = re.search(r'drive\.google\.com/open\?id=([^&\s]+)', link)
    if m:
        return f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    return link


def _fmt_blog(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    ca = doc.get("created_at")
    if isinstance(ca, datetime):
        doc["created_at"] = ca.isoformat()
    doc.setdefault("excerpt",    None)
    doc.setdefault("thumbnail",  None)
    doc.setdefault("tags",       None)
    doc.setdefault("published",  True)
    doc.setdefault("drive_link", None)
    return doc


@app.get("/api/blogs")
def list_blogs(
    show_all: bool = False,
    search: Optional[str] = None,
    category: Optional[str] = None,
    page: Optional[int] = None,
    limit: int = 20,
    _: None = Depends(require_public_access),
):
    try:
        query = _tq() if show_all else _tq({"published": True})
        if category:
            query["category"] = {"$regex": category, "$options": "i"}
        if search:
            query["$or"] = [
                {"title": {"$regex": search, "$options": "i"}},
                {"author": {"$regex": search, "$options": "i"}},
                {"tags": {"$regex": search, "$options": "i"}},
            ]
        return _paginated(_bcol, query, sort_field="created_at", sort_dir=DESCENDING,
                          fmt_fn=_fmt_blog, page=page, limit=limit)
    except Exception as e:
        print(f"[ERROR] list_blogs: {e}")
        raise HTTPException(503, "Database temporarily unavailable")


@app.get("/api/blogs/{blog_id}")
def get_blog(blog_id: str, _: None = Depends(require_public_access)):
    try:
        doc = _bcol.find_one(_tq({"_id": ObjectId(blog_id)}))
    except Exception:
        raise HTTPException(400, "Invalid id")
    if not doc:
        raise HTTPException(404, "Not found")
    return _fmt_blog(doc)


@app.post("/api/blogs", status_code=201)
def create_blog(body: BlogIn, _: None = Depends(_require_admin)):
    doc = {
        "tenant_name": _tenant(),
        "title":       body.title,
        "author":      body.author,
        "category":    body.category,
        "drive_link":  body.drive_link,
        "excerpt":     body.excerpt,
        "thumbnail":   body.thumbnail,
        "tags":        body.tags,
        "published":   body.published,
        "created_at":  datetime.now(timezone.utc),
        "updated_by":  _user_email(),
    }
    try:
        result = _bcol.insert_one(doc)
        return {"success": True, "id": str(result.inserted_id)}
    except Exception as e:
        print(f"[ERROR] create_blog: {e}")
        raise HTTPException(503, "Database temporarily unavailable")


@app.patch("/api/blogs/{blog_id}")
def update_blog(blog_id: str, body: BlogUpdate, _: None = Depends(_require_admin)):
    try:
        oid = ObjectId(blog_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    try:
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(400, "No fields to update")
        updates["updated_by"] = _user_email()
        result = _bcol.update_one(_tq({"_id": oid}), {"$set": updates})
        if result.matched_count == 0:
            raise HTTPException(404, "Not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] update_blog: {e}")
        raise HTTPException(503, "Database temporarily unavailable")


@app.get("/api/blogs/{blog_id}/content")
async def get_blog_content(blog_id: str, _: None = Depends(require_public_access)):
    """Proxy the blog article content from Google Drive."""
    try:
        oid = ObjectId(blog_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    doc = _bcol.find_one(_tq({"_id": oid}), {"drive_link": 1})
    if not doc or not doc.get("drive_link"):
        raise HTTPException(404, "No content available for this blog post")
    content_url = _drive_content_url(doc["drive_link"])
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            r = await client.get(content_url)
        if r.status_code != 200:
            raise HTTPException(502, "Could not fetch content from Drive")
        media_type = r.headers.get("content-type", "text/html").split(";")[0]
        return Response(content=r.content, media_type=media_type)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] get_blog_content: {e}")
        raise HTTPException(502, "Could not fetch content from Drive")


# ── Testimonial Routes ───────────────────────────────────────────────
def _fmt_testimonial(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    ca = doc.get("created_at")
    if isinstance(ca, datetime):
        doc["created_at"] = ca.isoformat()
    doc.setdefault("approved", False)
    doc.setdefault("rating", 5)
    return doc


@app.get("/api/testimonials")
def list_testimonials(
    show_all: bool = False,
    search: Optional[str] = None,
    approved: Optional[bool] = None,
    page: Optional[int] = None,
    limit: int = 20,
    _: None = Depends(require_public_access),
):
    q = _tq() if show_all else _tq({"approved": True})
    if approved is not None and show_all:
        q["approved"] = approved
    if search:
        q["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"text": {"$regex": search, "$options": "i"}},
        ]
    return _paginated(_testcol, q, sort_field="created_at", sort_dir=DESCENDING,
                      fmt_fn=_fmt_testimonial, page=page, limit=limit)


@app.post("/api/testimonials", status_code=201)
def create_testimonial(request: Request, body: TestimonialIn,
                       _auth: None = Depends(require_public_access),
                       _rl:   None = Depends(rate_limit(5, 60))):
    doc = body.model_dump()
    doc["approved"]    = False          # always pending until admin approves
    doc["tenant_name"] = _tenant()
    doc["created_at"]  = datetime.now(timezone.utc)
    result = _testcol.insert_one(doc)
    return {"success": True, "id": str(result.inserted_id)}


@app.patch("/api/testimonials/{test_id}")
def update_testimonial(test_id: str, body: TestimonialUpdate, _: None = Depends(_require_admin)):
    try:
        oid = ObjectId(test_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")
    updates["updated_by"] = _user_email()
    result = _testcol.update_one(_tq({"_id": oid}), {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@app.delete("/api/testimonials/{test_id}")
def delete_testimonial(test_id: str):
    try:
        oid = ObjectId(test_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    result = _testcol.delete_one(_tq({"_id": oid}))
    if result.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


# ── Media Routes ─────────────────────────────────────────────────────
def _extract_drive_id(url: str) -> Optional[str]:
    m = re.search(r'drive\.google\.com/file/d/([^/?]+)', url)
    if m:
        return m.group(1)
    m = re.search(r'drive\.google\.com/open\?id=([^&\s]+)', url)
    if m:
        return m.group(1)
    return None


def _fmt_media(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    ca = doc.get("created_at")
    if isinstance(ca, datetime):
        doc["created_at"] = ca.isoformat()
    link = doc.get("drive_link", "")
    fid  = _extract_drive_id(link)
    if doc.get("type") == "video":
        doc["display_url"] = f"{BASE_URL}/api/proxy/video?id={fid}" if fid else link
    else:
        doc["display_url"] = f"{BASE_URL}/api/proxy/image?id={fid}" if fid else link
    doc["thumb_url"] = f"{BASE_URL}/api/proxy/image?id={fid}" if fid else None
    return doc


@app.get("/api/media")
def list_media(
    gallery: bool = False,
    search: Optional[str] = None,
    type: Optional[str] = None,
    page: Optional[int] = None,
    limit: int = 20,
    _: None = Depends(require_public_access),
):
    q = _tq({"show_in_gallery": True}) if gallery else _tq()
    if type:
        q["type"] = type
    if search:
        q["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"alt": {"$regex": search, "$options": "i"}},
        ]
    return _paginated(_mediacol, q, sort_field="order", sort_dir=ASCENDING,
                      fmt_fn=_fmt_media, page=page, limit=limit)


@app.post("/api/media", status_code=201)
def create_media(body: MediaIn, _: None = Depends(_require_admin)):
    doc = body.model_dump()
    doc["tenant_name"] = _tenant()
    doc["created_at"]  = datetime.now(timezone.utc)
    doc["updated_by"]  = _user_email()
    result = _mediacol.insert_one(doc)
    return {"success": True, "id": str(result.inserted_id)}


@app.patch("/api/media/{media_id}")
def update_media(media_id: str, body: MediaUpdate, _: None = Depends(_require_admin)):
    try:
        oid = ObjectId(media_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")
    updates["updated_by"] = _user_email()
    result = _mediacol.update_one(_tq({"_id": oid}), {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@app.delete("/api/media/{media_id}")
def delete_media(media_id: str, _: None = Depends(_require_admin)):
    try:
        oid = ObjectId(media_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    result = _mediacol.delete_one(_tq({"_id": oid}))
    if result.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@app.get("/api/gallery-config")
def get_gallery_config(_: None = Depends(require_public_access)):
    doc = _gcfgcol.find_one(_tq())
    if not doc:
        return {"autoplay": True, "interval": 5000, "transition": "fade", "show_captions": True}
    doc.pop("_id", None)
    doc.pop("tenant_name", None)
    return doc


@app.patch("/api/gallery-config")
def update_gallery_config(body: GalleryConfigIn, _: None = Depends(_require_admin)):
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    data["updated_by"] = _user_email()
    _gcfgcol.update_one(_tq(), {"$set": data}, upsert=True)
    return {"success": True}


@app.get("/api/proxy/image")
async def proxy_drive_image(id: str):
    """Proxy a Google Drive image by file ID to avoid CORS / auth walls."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://drive.google.com/",
    }
    # Try multiple URL patterns in order of reliability
    candidates = [
        f"https://drive.google.com/thumbnail?id={id}&sz=w1200-h900",
        f"https://lh3.googleusercontent.com/d/{id}",
        f"https://drive.google.com/uc?export=view&id={id}",
    ]
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20, headers=headers) as client:
            for url in candidates:
                r = await client.get(url)
                ct = r.headers.get("content-type", "")
                if r.status_code == 200 and "image" in ct:
                    return Response(content=r.content, media_type=ct.split(";")[0])
                print(f"[PROXY] {url} → {r.status_code} {ct[:60]}")
        raise HTTPException(502, "Could not fetch image from Drive — ensure the file is shared publicly")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] proxy_drive_image: {e}")
        raise HTTPException(502, "Could not fetch image from Drive")


@app.get("/api/proxy/video")
async def proxy_drive_video(id: str, request: Request):
    """Stream a Google Drive video by file ID so <video> autoplay works."""
    req_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    }
    if "range" in request.headers:
        req_headers["Range"] = request.headers["range"]

    candidates = [
        f"https://drive.google.com/uc?export=download&id={id}&confirm=t",
        f"https://drive.google.com/uc?export=view&id={id}",
    ]
    try:
        for url in candidates:
            client = httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(15, read=None))
            r = await client.get(url, headers=req_headers)
            ct = r.headers.get("content-type", "")
            if r.status_code in (200, 206) and "video" in ct:
                resp_headers = {
                    "Accept-Ranges": "bytes",
                    "Cache-Control": "max-age=3600",
                    "Access-Control-Allow-Origin": "*",
                }
                for h in ("content-length", "content-range", "last-modified"):
                    if h in r.headers:
                        resp_headers[h] = r.headers[h]

                async def _stream(r=r, client=client):
                    try:
                        async for chunk in r.aiter_bytes(65536):
                            yield chunk
                    finally:
                        await client.aclose()

                return StreamingResponse(
                    _stream(),
                    status_code=r.status_code,
                    headers=resp_headers,
                    media_type=ct.split(";")[0],
                )
            await client.aclose()
            print(f"[VIDEO-PROXY] {url} → {r.status_code} {ct[:60]}")
        raise HTTPException(502, "Could not stream video from Drive — ensure the file is shared publicly")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] proxy_drive_video: {e}")
        raise HTTPException(502, "Could not stream video from Drive")


# ── Offers Routes ───────────────────────────────────────────────────
def _fmt_offer(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    ca = doc.get("created_at")
    if isinstance(ca, datetime):
        doc["created_at"] = ca.isoformat()
    doc.setdefault("active", True)
    doc.setdefault("order", 0)
    return doc


@app.get("/api/offers")
def list_offers(
    show_all: bool = False,
    search: Optional[str] = None,
    page: Optional[int] = None,
    limit: int = 20,
    _: None = Depends(require_public_access),
):
    q = _tq() if show_all else _tq({"active": True})
    if search:
        q["text"] = {"$regex": search, "$options": "i"}
    return _paginated(_offercol, q, sort_field="order", sort_dir=ASCENDING,
                      fmt_fn=_fmt_offer, page=page, limit=limit)


@app.post("/api/offers", status_code=201)
def create_offer(body: OfferIn, _: None = Depends(_require_admin)):
    doc = body.model_dump()
    doc["tenant_name"] = _tenant()
    doc["created_at"]  = datetime.now(timezone.utc)
    doc["updated_by"]  = _user_email()
    result = _offercol.insert_one(doc)
    return {"success": True, "id": str(result.inserted_id)}


@app.patch("/api/offers/{offer_id}")
def update_offer(offer_id: str, body: OfferUpdate, _: None = Depends(_require_admin)):
    try:
        oid = ObjectId(offer_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")
    updates["updated_by"] = _user_email()
    result = _offercol.update_one(_tq({"_id": oid}), {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@app.delete("/api/offers/{offer_id}")
def delete_offer(offer_id: str, _: None = Depends(_require_admin)):
    try:
        oid = ObjectId(offer_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    result = _offercol.delete_one(_tq({"_id": oid}))
    if result.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


# ── Insurance Provider Routes ────────────────────────────────────────
def _fmt_insurance(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    ca = doc.get("created_at")
    if isinstance(ca, datetime):
        doc["created_at"] = ca.isoformat()
    doc.setdefault("active", True)
    doc.setdefault("order", 0)
    doc.setdefault("logo_drive_link", None)
    link = doc.get("logo_drive_link") or ""
    fid  = _extract_drive_id(link)
    doc["logo_url"] = f"{BASE_URL}/api/proxy/image?id={fid}" if fid else None
    return doc


@app.get("/api/insurance")
def list_insurance(
    show_all: bool = False,
    search: Optional[str] = None,
    page: Optional[int] = None,
    limit: int = 20,
    _: None = Depends(require_public_access),
):
    q = _tq() if show_all else _tq({"active": True})
    if search:
        q["name"] = {"$regex": search, "$options": "i"}
    return _paginated(_inscol, q, sort_field="order", sort_dir=ASCENDING,
                      fmt_fn=_fmt_insurance, page=page, limit=limit)


@app.post("/api/insurance", status_code=201)
def create_insurance(body: InsuranceIn, _: None = Depends(_require_admin)):
    _validate_drive_link(body.logo_drive_link)
    doc = body.model_dump()
    doc["tenant_name"] = _tenant()
    doc["created_at"]  = datetime.now(timezone.utc)
    doc["updated_by"]  = _user_email()
    result = _inscol.insert_one(doc)
    return {"success": True, "id": str(result.inserted_id)}


@app.patch("/api/insurance/{ins_id}")
def update_insurance(ins_id: str, body: InsuranceUpdate, _: None = Depends(_require_admin)):
    try:
        oid = ObjectId(ins_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")
    _validate_drive_link(updates.get("logo_drive_link"))
    updates["updated_by"] = _user_email()
    result = _inscol.update_one(_tq({"_id": oid}), {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@app.delete("/api/insurance/{ins_id}")
def delete_insurance(ins_id: str, _: None = Depends(_require_admin)):
    try:
        oid = ObjectId(ins_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    result = _inscol.delete_one(_tq({"_id": oid}))
    if result.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


# ── Partner Routes ────────────────────────────────────────────────────
_DRIVE_RE = re.compile(r'drive\.google\.com|docs\.google\.com')


def _validate_drive_link(url: Optional[str], field: str = "logo_drive_link") -> None:
    if url and not _DRIVE_RE.search(url):
        raise HTTPException(400, f"{field} must be a Google Drive or Docs URL")


def _fmt_partner(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    ca = doc.get("created_at")
    if isinstance(ca, datetime):
        doc["created_at"] = ca.isoformat()
    doc.setdefault("active", True)
    doc.setdefault("order", 0)
    doc.setdefault("logo_drive_link", None)
    link = doc.get("logo_drive_link") or ""
    fid  = _extract_drive_id(link)
    doc["logo_url"] = f"{BASE_URL}/api/proxy/image?id={fid}" if fid else None
    return doc


@app.get("/api/partners")
def list_partners(
    show_all: bool = False,
    search: Optional[str] = None,
    page: Optional[int] = None,
    limit: int = 20,
    _: None = Depends(require_public_access),
):
    q = _tq() if show_all else _tq({"active": True})
    if search:
        q["name"] = {"$regex": search, "$options": "i"}
    return _paginated(_partnercol, q, sort_field="order", sort_dir=ASCENDING,
                      fmt_fn=_fmt_partner, page=page, limit=limit)


@app.post("/api/partners", status_code=201)
def create_partner(body: PartnerIn, _: None = Depends(_require_admin)):
    _validate_drive_link(body.logo_drive_link)
    doc = body.model_dump()
    doc["tenant_name"] = _tenant()
    doc["created_at"]  = datetime.now(timezone.utc)
    doc["updated_by"]  = _user_email()
    result = _partnercol.insert_one(doc)
    return {"success": True, "id": str(result.inserted_id)}


@app.patch("/api/partners/{partner_id}")
def update_partner(partner_id: str, body: PartnerUpdate, _: None = Depends(_require_admin)):
    try:
        oid = ObjectId(partner_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")
    _validate_drive_link(updates.get("logo_drive_link"))
    updates["updated_by"] = _user_email()
    result = _partnercol.update_one(_tq({"_id": oid}), {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@app.delete("/api/partners/{partner_id}")
def delete_partner(partner_id: str, _: None = Depends(_require_admin)):
    try:
        oid = ObjectId(partner_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    result = _partnercol.delete_one(_tq({"_id": oid}))
    if result.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


# ── Hero Stats Routes ─────────────────────────────────────────────────
def _fmt_stat(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    ca = doc.get("created_at")
    if isinstance(ca, datetime):
        doc["created_at"] = ca.isoformat()
    doc.setdefault("active", True)
    doc.setdefault("order", 0)
    doc.setdefault("suffix", "+")
    doc.setdefault("icon_key", "patients")
    return doc


@app.get("/api/hero-stats")
def list_hero_stats(
    show_all: bool = False,
    page: Optional[int] = None,
    limit: int = 20,
    _: None = Depends(require_public_access),
):
    q = _tq() if show_all else _tq({"active": True})
    return _paginated(_statscol, q, sort_field="order", sort_dir=ASCENDING,
                      fmt_fn=_fmt_stat, page=page, limit=limit)


@app.post("/api/hero-stats", status_code=201)
def create_hero_stat(body: StatIn, _: None = Depends(_require_admin)):
    doc = body.model_dump()
    doc["tenant_name"] = _tenant()
    doc["created_at"]  = datetime.now(timezone.utc)
    doc["updated_by"]  = _user_email()
    result = _statscol.insert_one(doc)
    return {"success": True, "id": str(result.inserted_id)}


@app.patch("/api/hero-stats/{stat_id}")
def update_hero_stat(stat_id: str, body: StatUpdate, _: None = Depends(_require_admin)):
    try:
        oid = ObjectId(stat_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "Nothing to update")
    updates["updated_by"] = _user_email()
    _statscol.update_one(_tq({"_id": oid}), {"$set": updates})
    return {"success": True}


@app.delete("/api/hero-stats/{stat_id}")
def delete_hero_stat(stat_id: str, _: None = Depends(_require_admin)):
    try:
        oid = ObjectId(stat_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    result = _statscol.delete_one(_tq({"_id": oid}))
    if result.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


# ── Facilities Routes ─────────────────────────────────────────────────

def _fmt_facility(d: dict) -> dict:
    d["id"] = str(d.pop("_id"))
    return d

@app.get("/api/facilities")
def list_facilities(
    show_all: bool = False,
    search: Optional[str] = None,
    category: Optional[str] = None,
    page: Optional[int] = None,
    limit: int = 20,
    _: None = Depends(require_public_access),
):
    q = _tq() if show_all else _tq({"active": True})
    if category:
        q["category"] = category
    if search:
        q["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"short_desc": {"$regex": search, "$options": "i"}},
        ]
    return _paginated(_facilitiescol, q, sort_field="order", sort_dir=ASCENDING,
                      fmt_fn=_fmt_facility, page=page, limit=limit)

@app.post("/api/facilities", status_code=201)
def create_facility(body: FacilityIn, _: None = Depends(_require_admin)):
    doc = body.model_dump()
    doc["tenant_name"] = _tenant()
    doc["updated_by"]  = _user_email()
    result = _facilitiescol.insert_one(doc)
    return {"success": True, "id": str(result.inserted_id)}

@app.patch("/api/facilities/{facility_id}")
def update_facility(facility_id: str, body: FacilityUpdate, _: None = Depends(_require_admin)):
    try:
        oid = ObjectId(facility_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    patch["updated_by"] = _user_email()
    result = _facilitiescol.update_one(_tq({"_id": oid}), {"$set": patch})
    if result.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}

@app.delete("/api/facilities/{facility_id}")
def delete_facility(facility_id: str, _: None = Depends(_require_admin)):
    try:
        oid = ObjectId(facility_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    result = _facilitiescol.delete_one(_tq({"_id": oid}))
    if result.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


# ── FAQ Routes ────────────────────────────────────────────────────────

def _fmt_faq(d: dict) -> dict:
    d["id"] = str(d.pop("_id"))
    return d

@app.get("/api/faqs")
def list_faqs(
    show_all: bool = False,
    search: Optional[str] = None,
    page: Optional[int] = None,
    limit: int = 20,
    _: None = Depends(require_public_access),
):
    q = _tq() if show_all else _tq({"active": True})
    if search:
        q["$or"] = [
            {"question": {"$regex": search, "$options": "i"}},
            {"answer": {"$regex": search, "$options": "i"}},
        ]
    return _paginated(_faqcol, q, sort_field="order", sort_dir=ASCENDING,
                      fmt_fn=_fmt_faq, page=page, limit=limit)

@app.post("/api/faqs", status_code=201)
def create_faq(body: FaqIn, _: None = Depends(_require_admin)):
    doc = body.model_dump()
    doc["tenant_name"] = _tenant()
    doc["updated_by"]  = _user_email()
    result = _faqcol.insert_one(doc)
    return {"success": True, "id": str(result.inserted_id)}

@app.patch("/api/faqs/{faq_id}")
def update_faq(faq_id: str, body: FaqUpdate, _: None = Depends(_require_admin)):
    try:
        oid = ObjectId(faq_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    patch["updated_by"] = _user_email()
    result = _faqcol.update_one(_tq({"_id": oid}), {"$set": patch})
    if result.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}

@app.delete("/api/faqs/{faq_id}")
def delete_faq(faq_id: str, _: None = Depends(_require_admin)):
    try:
        oid = ObjectId(faq_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    result = _faqcol.delete_one(_tq({"_id": oid}))
    if result.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


# ── SMS Config Routes ────────────────────────────────────────────────
# These routes are admin-only: they require a valid admin bearer token.
# The auth_token (Twilio credential) is never returned in plain text —
# the GET endpoint replaces it with a bullet-mask so the admin UI can
# show that a token is saved without exposing its value.

@app.get("/api/sms-config")
def get_sms_config(_admin: dict = Depends(_require_super_admin)):
    """
    Return the current SMS configuration for this tenant.
    Both sensitive fields (account_sid and auth_token) are masked before
    returning so credentials are never exposed to the browser.
    """
    cfg = _smscfgcol.find_one(_tq()) or {}
    # Strip internal MongoDB/tenant fields — frontend doesn't need them
    cfg.pop("_id", None)
    cfg.pop("tenant_name", None)
    # Mask all sensitive credentials — replace with a bullet placeholder.
    # The frontend tracks whether each field is masked and sends the placeholder
    # back on save so the backend knows to preserve the real stored values.
    if cfg.get("account_sid"):     cfg["account_sid"]     = "••••••••"
    if cfg.get("auth_token"):      cfg["auth_token"]      = "••••••••"
    if cfg.get("gupshup_api_key"): cfg["gupshup_api_key"] = "••••••••"
    return cfg


@app.put("/api/sms-config")
def save_sms_config(body: SmsConfigIn, _admin: dict = Depends(_require_super_admin)):
    """
    Upsert (create or replace) the SMS configuration for this tenant.
    If the client sends the masked placeholder for auth_token it means
    the admin didn't change it — we keep the existing DB value instead
    of overwriting with the placeholder string.
    """
    update = body.model_dump()

    # If any sensitive field still holds the mask placeholder it means the
    # admin didn't change it — fetch the real values from DB and restore them
    # so we don't overwrite with the placeholder string.
    _MASK = "••••••••"
    masked_fields = [f for f in ("account_sid", "auth_token", "gupshup_api_key")
                     if update.get(f) == _MASK]
    if masked_fields:
        existing = _smscfgcol.find_one(_tq()) or {}
        for f in masked_fields:
            update[f] = existing.get(f, "")

    _smscfgcol.update_one(
        _tq(),                                          # filter: match this tenant
        {"$set": {**update, "tenant_name": _tenant()}}, # update: replace all fields
        upsert=True,                                    # create doc if none exists yet
    )
    return {"success": True}


@app.post("/api/sms-config/test")
def test_sms(body: SmsTestIn, _admin: dict = Depends(_require_super_admin)):
    """
    Send a test SMS to the supplied phone number using the saved config.
    Used by admins to verify credentials and the from-number are correct
    before going live. Raises HTTP 400/500 with a descriptive message on failure.
    """
    cfg = _smscfgcol.find_one(_tq())

    # Allow testing even when SMS is disabled — the admin needs to verify
    # credentials before enabling it for live patient notifications.
    if not cfg:
        raise HTTPException(400, "No SMS configuration found. Please save your settings first.")

    provider = cfg.get("provider", "twilio")

    from_num = cfg.get("from_number", "").strip()
    test_body = "Test SMS from your hospital system. Your SMS configuration is working correctly!"

    try:
        if provider == "twilio":
            sid   = cfg.get("account_sid", "").strip()
            token = cfg.get("auth_token", "").strip()
            if not (sid and token and from_num):
                return {"success": False, "error": "Twilio credentials incomplete — fill Account SID, Auth Token, and From Number."}
            to = _e164(body.phone)
            from twilio.rest import Client
            Client(sid, token).messages.create(to=to, from_=from_num, body=test_body)
            return {"success": True, "message": f"Test SMS sent via Twilio to {to}"}

        elif provider == "gupshup":
            gs_api_key  = cfg.get("gupshup_api_key", "").strip()
            gs_app_name = cfg.get("gupshup_app_name", "").strip()
            if not (gs_api_key and from_num):
                return {"success": False, "error": "Gupshup credentials incomplete — fill API Key and From Number."}
            to    = _e164(body.phone)
            gs_to = to.lstrip("+")
            import httpx as _httpx
            resp = _httpx.post(
                "https://api.gupshup.io/sm/api/v1/msg",
                headers={"apikey": gs_api_key, "Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "channel":    "sms",
                    "source":     from_num,
                    "destination": gs_to,
                    "message":    test_body,
                    "src.name":   gs_app_name or from_num,
                },
                timeout=15,
            )
            resp.raise_for_status()
            result_json = resp.json()
            if result_json.get("status") not in ("submitted", "success"):
                return {"success": False, "error": f"Gupshup error: {result_json}"}
            return {"success": True, "message": f"Test SMS sent via Gupshup to {to}"}

        else:
            return {"success": False, "error": f"Unsupported provider: {provider}"}

    except Exception as e:
        err_msg = str(e)
        print(f"[SMS-TEST-ERR] {err_msg}")
        return {"success": False, "error": err_msg}


# ── Site Config Routes ────────────────────────────────────────────────
# Stores site-wide settings like the hospital phone number.
# GET is public so the homepage can read it; PUT is admin-only.

@app.get("/api/site-config")
def get_site_config(_: None = Depends(require_public_access)):
    """Return site-wide config (e.g. hospital phone number) for the current tenant."""
    cfg = _sitecfgcol.find_one(_tq()) or {}
    cfg.pop("_id", None)
    cfg.pop("tenant_name", None)
    return cfg


@app.put("/api/site-config")
def save_site_config(body: SiteConfigIn, _admin: dict = Depends(_require_admin)):
    """Upsert site-wide configuration for this tenant."""
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    _sitecfgcol.update_one(
        _tq(),
        {"$set": {**update, "tenant_name": _tenant()}},
        upsert=True,
    )
    return {"success": True}


# ── Auth Routes ──────────────────────────────────────────────────────
@app.post("/api/auth/login")
def auth_login(body: LoginIn):
    email = body.email.strip().lower()
    user  = _usercol.find_one({"email": email})
    if not user:
        raise HTTPException(401, "Invalid email or password")
    pw_hash = user.get("password_hash")
    # bcrypt 5.x requires bytes — encode if the stored hash came back as a str
    if isinstance(pw_hash, str):
        pw_hash = pw_hash.encode()
    if not pw_hash or not bcrypt.checkpw(body.password.encode(), pw_hash):
        raise HTTPException(401, "Invalid email or password")

    # MFA disabled — issue full session token immediately.
    return _complete_mfa_login(user)


def _complete_mfa_login(user: dict) -> dict:
    """Issue a full session token, enforcing single active session."""
    token      = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
    _usercol.update_one(
        {"_id": user["_id"]},
        {
            "$set":   {"active_token": token, "token_expires_at": expires_at, "last_login": datetime.now(timezone.utc)},
            "$unset": {"pre_auth_token": "", "pre_auth_expires_at": ""},
        },
    )
    return {
        "token":         token,
        "name":          user.get("name", "Admin"),
        "role":          user.get("role", "Admin"),
        "email":         user["email"],
        "expires_at":    expires_at.isoformat(),
        "tenant_name":   user.get("tenant_name", TENANT_NAME),
        "hospital_name": user.get("hospital_name", "Hospital Admin"),
    }


def _resolve_pre_token(pre_token: str) -> dict:
    """Look up and validate a pre-auth token; raises 401 on failure."""
    user = _usercol.find_one({"pre_auth_token": pre_token})
    if not user:
        raise HTTPException(401, "Invalid or expired session. Please login again.")
    exp = user.get("pre_auth_expires_at")
    if not exp:
        raise HTTPException(401, "Session expired. Please login again.")
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > exp:
        raise HTTPException(401, "Session expired. Please login again.")
    return user


@app.post("/api/auth/mfa/verify")
def mfa_verify(body: MFAVerifyIn):
    """Step 2 for users who already have TOTP set up."""
    user = _resolve_pre_token(body.pre_token)
    totp_secret = user.get("totp_secret")
    if not totp_secret:
        raise HTTPException(400, "MFA not configured for this account.")
    if not pyotp.TOTP(totp_secret).verify(body.code.strip(), valid_window=1):
        raise HTTPException(401, "Invalid verification code. Please try again.")
    return _complete_mfa_login(user)


@app.post("/api/auth/mfa/setup")
def mfa_setup_confirm(body: MFAVerifyIn):
    """Step 2 for first-time setup: confirm TOTP code and activate MFA."""
    user = _resolve_pre_token(body.pre_token)
    totp_secret = user.get("totp_secret_pending")
    if not totp_secret:
        raise HTTPException(400, "No pending MFA setup found.")
    if not pyotp.TOTP(totp_secret).verify(body.code.strip(), valid_window=1):
        raise HTTPException(401, "Invalid verification code. Please try again.")
    # Promote pending secret to active
    _usercol.update_one(
        {"_id": user["_id"]},
        {"$set": {"totp_secret": totp_secret}, "$unset": {"totp_secret_pending": ""}},
    )
    return _complete_mfa_login(user)


@app.post("/api/auth/logout")
def auth_logout(request: Request):
    token = _get_bearer(request)
    if token:
        _usercol.update_one(
            {"active_token": token},
            {"$unset": {"active_token": "", "token_expires_at": ""}}
        )
    return {"success": True}


@app.get("/api/auth/verify")
def auth_verify(request: Request):
    token = _get_bearer(request)
    user  = _verify_token(token)
    if not user:
        raise HTTPException(401, "Token invalid or expired")
    exp = user["token_expires_at"]
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return {
        "name":          user.get("name", "Admin"),
        "role":          user.get("role", "Admin"),
        "email":         user["email"],
        "expires_at":    exp.isoformat(),
        "tenant_name":   user.get("tenant_name", TENANT_NAME),
        "hospital_name": user.get("hospital_name", "Hospital Admin"),
    }


@app.post("/api/auth/refresh")
def auth_refresh(request: Request):
    token = _get_bearer(request)
    user  = _verify_token(token)
    if not user:
        raise HTTPException(401, "Token invalid or expired")
    # Rotate: issue a completely new token (invalidates the old one)
    new_token = secrets.token_urlsafe(32)
    new_exp   = datetime.now(timezone.utc) + timedelta(minutes=30)
    _usercol.update_one(
        {"_id": user["_id"]},
        {"$set": {"active_token": new_token, "token_expires_at": new_exp}},
    )
    return {"token": new_token, "expires_at": new_exp.isoformat()}


@app.delete("/api/blogs/{blog_id}")
def delete_blog(blog_id: str, _: None = Depends(_require_admin)):
    try:
        oid = ObjectId(blog_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    try:
        result = _bcol.delete_one(_tq({"_id": oid}))
        if result.deleted_count == 0:
            raise HTTPException(404, "Not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] delete_blog: {e}")
        raise HTTPException(503, "Database temporarily unavailable")


# ── Admin User Management Routes (SUPER_ADMIN only) ──────────────────
# Only a SUPER_ADMIN can list, create, and activate/deactivate other admins.

@app.get("/api/admin/users")
def list_admin_users(
    search: Optional[str] = None,
    role: Optional[str] = None,
    page: Optional[int] = None,
    limit: int = 20,
    _admin: dict = Depends(_require_super_admin),
):
    """Return admin users for this tenant (passwords excluded)."""
    q = _tq()
    if role:
        q["role"] = role
    if search:
        q["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
        ]
    projection = {"password_hash": 0, "active_token": 0, "token_expires_at": 0, "totp_secret": 0}

    def _fmt_user(d):
        d["id"] = str(d.pop("_id"))
        ca = d.get("created_at")
        if isinstance(ca, datetime):
            d["created_at"] = ca.isoformat()
        return d

    cursor = _usercol.find(q, projection).sort("created_at", DESCENDING)
    if page is not None:
        page = max(1, page)
        total = _usercol.count_documents(q)
        cursor = cursor.skip((page - 1) * limit).limit(limit)
        items = [_fmt_user(d) for d in cursor]
        return {"total": total, "page": page, "limit": limit, "items": items}
    return [_fmt_user(d) for d in cursor]


@app.post("/api/admin/users", status_code=201)
def create_admin_user(body: UserCreateIn, _admin: dict = Depends(_require_super_admin)):
    """Create a new admin user scoped to the current tenant. SUPER_ADMIN only."""
    existing = _usercol.find_one(_tq({"email": body.email}))
    if existing:
        raise HTTPException(409, "A user with that email already exists")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(body.password.encode(), salt).decode()
    doc = {
        "tenant_name":  _tenant(),
        "email":        body.email,
        "name":         body.name,
        "password_hash": hashed,
        "role":         body.role or "ADMIN",
        "active":       True,
        "created_at":   datetime.now(timezone.utc),
        "created_by":   _user_email(),
    }
    result = _usercol.insert_one(doc)
    return {"success": True, "id": str(result.inserted_id)}


@app.patch("/api/admin/users/{user_id}/status")
def toggle_admin_user_status(user_id: str, _admin: dict = Depends(_require_super_admin)):
    """Toggle the active flag for an admin user. SUPER_ADMIN only.
    A SUPER_ADMIN cannot deactivate themselves to prevent lockout.
    When a user is deactivated their active_token is cleared immediately,
    forcing them out of any current session.
    """
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    user = _usercol.find_one(_tq({"_id": oid}))
    if not user:
        raise HTTPException(404, "User not found")
    # Prevent SUPER_ADMIN from deactivating themselves
    if user.get("email") == _admin.get("email"):
        raise HTTPException(400, "You cannot deactivate your own account")
    new_active = not user.get("active", True)
    update: dict = {"$set": {"active": new_active}}
    # Immediately invalidate the session token when deactivating
    if not new_active:
        update["$unset"] = {"active_token": ""}
    _usercol.update_one({"_id": oid}, update)
    return {"success": True, "active": new_active}


@app.patch("/api/admin/users/{user_id}")
def update_admin_user(user_id: str, body: UserUpdateIn, _admin: dict = Depends(_require_super_admin)):
    """Edit an admin user's email, name, password, or role. SUPER_ADMIN only."""
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    user = _usercol.find_one(_tq({"_id": oid}))
    if not user:
        raise HTTPException(404, "User not found")
    updates: dict = {}
    if body.email is not None:
        # Ensure the new email isn't already taken by another user
        clash = _usercol.find_one(_tq({"email": body.email, "_id": {"$ne": oid}}))
        if clash:
            raise HTTPException(409, "That email is already used by another user")
        updates["email"] = body.email.strip().lower()
    if body.name is not None:
        updates["name"] = body.name.strip()
    if body.role is not None:
        updates["role"] = body.role
    if body.password:
        if len(body.password) < 8:
            raise HTTPException(400, "Password must be at least 8 characters")
        updates["password_hash"] = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
        # Invalidate active session so user must re-login with new password
        _usercol.update_one({"_id": oid}, {"$unset": {"active_token": ""}})
    if not updates:
        raise HTTPException(400, "No fields to update")
    updates["updated_by"] = _user_email()
    _usercol.update_one({"_id": oid}, {"$set": updates})
    return {"success": True}


# ── SMS Audit Log Route ───────────────────────────────────────────────
# Returns a paginated list of every SMS attempt for this tenant.
# SUPER_ADMIN only — contains patient names, phone numbers, message content.

@app.get("/api/sms-logs")
def list_sms_logs(
    page: int = 1,
    limit: int = 50,
    status: Optional[str] = None,
    search: Optional[str] = None,
    _admin: dict = Depends(_require_super_admin),
):
    """Return paginated SMS audit log for this tenant, newest first."""
    q = _tq()
    if status:
        q["status"] = status
    if search:
        q["$or"] = [
            {"patient_name": {"$regex": search, "$options": "i"}},
            {"to": {"$regex": search}},
            {"ref_id": {"$regex": search, "$options": "i"}},
        ]
    skip = (page - 1) * limit
    total = _smslogcol.count_documents(q)
    docs  = list(
        _smslogcol.find(q)
        .sort("sent_at", DESCENDING)
        .skip(skip)
        .limit(limit)
    )
    for d in docs:
        d["id"] = str(d.pop("_id"))
        d.pop("tenant_name", None)
        ts = d.get("sent_at")
        if isinstance(ts, datetime):
            d["sent_at"] = ts.isoformat()
    return {"total": total, "page": page, "limit": limit, "logs": docs}


# ── SMS Log Export & Purge ─────────────────────────────────────────

def _sms_purge_query(date_from: str | None, date_to: str | None, status: str | None) -> dict:
    """Build a tenant-scoped MongoDB query for SMS log purge/export."""
    q = _tq()
    if status:
        q["status"] = status
    if date_from or date_to:
        df: dict = {}
        if date_from:
            df["$gte"] = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
        if date_to:
            # Include the entire end-of-day
            df["$lte"] = datetime.fromisoformat(date_to).replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
        q["sent_at"] = df
    return q


@app.get("/api/sms-logs/export")
def export_sms_logs(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    _admin: dict = Depends(_require_super_admin),
):
    """Export matching SMS logs as an Excel (.xlsx) file."""
    import io
    from openpyxl import Workbook

    q = _sms_purge_query(date_from, date_to, status)
    docs = list(_smslogcol.find(q).sort("sent_at", DESCENDING))

    wb = Workbook()
    ws = wb.active
    ws.title = "SMS Logs"
    headers = ["Sent At", "Ref ID", "Patient", "To Number",
               "Department", "Status", "Message", "Error"]
    ws.append(headers)
    for d in docs:
        ts = d.get("sent_at")
        ws.append([
            ts.isoformat() if isinstance(ts, datetime) else str(ts or ""),
            d.get("ref_id", ""),
            d.get("patient_name", ""),
            d.get("to", ""),
            d.get("department", ""),
            d.get("status", ""),
            d.get("message", ""),
            d.get("error", ""),
        ])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"sms_logs_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/sms-logs/count")
def count_sms_logs_for_purge(body: PurgeIn, _admin: dict = Depends(_require_super_admin)):
    """Return the number of SMS logs that match the purge filters (preview)."""
    q = _sms_purge_query(body.date_from, body.date_to, body.status)
    return {"count": _smslogcol.count_documents(q)}


@app.post("/api/sms-logs/purge")
def purge_sms_logs(body: PurgeIn, _admin: dict = Depends(_require_super_admin)):
    """Delete SMS logs matching the given date range and status filters."""
    q = _sms_purge_query(body.date_from, body.date_to, body.status)
    result = _smslogcol.delete_many(q)
    _auditcol.insert_one({
        "tenant_name": _tenant(),
        "action":      "purge_sms_logs",
        "performed_by": _user_email(),
        "timestamp":   datetime.now(timezone.utc),
        "records_deleted": result.deleted_count,
        "filters": {
            "date_from": body.date_from,
            "date_to":   body.date_to,
            "status":    body.status,
        },
    })
    return {"success": True, "deleted": result.deleted_count}


# ── Audit Log Route ────────────────────────────────────────────────

@app.get("/api/audit-logs")
def list_audit_logs(
    page: int = 1,
    limit: int = 50,
    _admin: dict = Depends(_require_super_admin),
):
    """Return paginated audit log entries for this tenant, newest first."""
    q = _tq()
    skip = (page - 1) * limit
    total = _auditcol.count_documents(q)
    docs = list(
        _auditcol.find(q)
        .sort("timestamp", DESCENDING)
        .skip(skip)
        .limit(limit)
    )
    for d in docs:
        d["id"] = str(d.pop("_id"))
        d.pop("tenant_name", None)
        ts = d.get("timestamp")
        if isinstance(ts, datetime):
            d["timestamp"] = ts.isoformat()
    return {"total": total, "page": page, "limit": limit, "logs": docs}
