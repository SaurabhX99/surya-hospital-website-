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
from datetime import datetime, timezone, timedelta
from typing import Optional

import bcrypt
import certifi
import httpx
from bson import ObjectId
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient, DESCENDING
from pymongo.errors import DuplicateKeyError

load_dotenv()

# ── Tenant & upload config ──────────────────────────────────────────
TENANT_NAME = os.getenv("TENANT_NAME", "vedansh_medicare").strip()

# Per-request tenant (set by middleware from auth token; defaults to TENANT_NAME)
_request_tenant: contextvars.ContextVar[str] = contextvars.ContextVar("_request_tenant")

def _tenant() -> str:
    return _request_tenant.get(TENANT_NAME)

def _tq(extra: dict | None = None) -> dict:
    """Return a base query scoped to the current request's tenant."""
    return {"tenant_name": _tenant(), **(extra or {})}

# ── App ────────────────────────────────────────────────────────────
app = FastAPI(title="Vedansh Medicare API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── MongoDB ────────────────────────────────────────────────────────
_client = MongoClient(
    os.getenv("MONGO_URI", ""),
    tls=True,
    tlsAllowInvalidCertificates=True,
)
_mdb    = _client[os.getenv("DATABASE_NAME", "NIMMS_HOSPITAL").strip()]
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

# ── Tenant middleware — resolves tenant from auth token per request ──
@app.middleware("http")
async def _tenant_middleware(request: Request, call_next):
    tenant = TENANT_NAME
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if token:
        user = _usercol.find_one(
            {"active_token": token},
            {"tenant_name": 1, "token_expires_at": 1},
        )
        if user and user.get("tenant_name"):
            exp = user.get("token_expires_at")
            if exp:
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) <= exp:
                    tenant = user["tenant_name"]
    _request_tenant.set(tenant)
    return await call_next(request)

# ── Seed first admin user from env if the collection is empty ──────
_admin_email    = os.getenv("ADMIN_EMAIL", "").strip().lower()
_admin_password = os.getenv("ADMIN_PASSWORD", "").strip()
if _admin_email and _admin_password and _usercol.count_documents({}) == 0:
    _pw_hash = bcrypt.hashpw(_admin_password.encode(), bcrypt.gensalt())
    _usercol.insert_one({
        "email":         _admin_email,
        "password_hash": _pw_hash,
        "name":          "Hospital Admin",
        "role":          "Super Admin",
        "created_at":    datetime.now(timezone.utc),
    })
    print(f"[STARTUP] Created admin user: {_admin_email}")

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


# ── Auth Helpers ────────────────────────────────────────────────────
def _get_bearer(request: Request) -> str:
    return request.headers.get("Authorization", "").removeprefix("Bearer ").strip()


def _verify_token(token: str) -> dict | None:
    """Return user doc if token is valid and not expired, else None."""
    if not token:
        return None
    user = _usercol.find_one({"active_token": token})
    if not user:
        return None
    exp = user.get("token_expires_at")
    if not exp:
        return None
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > exp:
        return None
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


@app.post("/api/appointments", status_code=201)
def create_appointment(body: AppointmentIn):
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
    _notify(body.name, body.mobile, body.department, body.date)
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
def list_appointments(status: Optional[str] = None):
    query = _tq({"status": status} if status else {})
    docs  = list(_col.find(query).sort("createdAt", DESCENDING))
    return [_fmt(d) for d in docs]


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
        return f"http://localhost:8000/api/proxy/image?id={m.group(1)}"
    m = re.search(r'drive\.google\.com/open\?id=([^&\s]+)', url)
    if m:
        return f"http://localhost:8000/api/proxy/image?id={m.group(1)}"
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
def list_doctors(featured: Optional[bool] = None, show_all: bool = False):
    try:
        query = _tq() if show_all else _tq({"active": True})
        if featured is not None:
            query["featured"] = featured
        docs = list(_dcol.find(query).sort("created_at", DESCENDING))
        return [_fmt_doctor(d) for d in docs]
    except Exception as e:
        print(f"[ERROR] list_doctors: {e}")
        raise HTTPException(503, "Database temporarily unavailable")


@app.post("/api/doctors", status_code=201)
def create_doctor(body: DoctorIn):
    try:
        doc = body.model_dump()
        doc["tenant_name"] = _tenant()
        doc["created_at"]  = datetime.now(timezone.utc)
        result = _dcol.insert_one(doc)
        return {"success": True, "id": str(result.inserted_id)}
    except Exception as e:
        print(f"[ERROR] create_doctor: {e}")
        raise HTTPException(503, "Database temporarily unavailable")


@app.patch("/api/doctors/{doctor_id}")
def update_doctor(doctor_id: str, body: DoctorUpdate):
    try:
        oid = ObjectId(doctor_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    try:
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(400, "No fields to update")
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
def delete_doctor(doctor_id: str):
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
def list_departments(show_all: bool = False):
    try:
        query = _tq() if show_all else _tq({"active": True})
        docs = list(_deptcol.find(query).sort("order", 1))
        return [_fmt_department(d) for d in docs]
    except Exception as e:
        print(f"[ERROR] list_departments: {e}")
        raise HTTPException(503, "Database temporarily unavailable")


@app.post("/api/departments", status_code=201)
def create_department(body: DepartmentIn):
    try:
        doc = body.model_dump()
        doc["tenant_name"] = _tenant()
        doc["created_at"]  = datetime.now(timezone.utc)
        result = _deptcol.insert_one(doc)
        return {"success": True, "id": str(result.inserted_id)}
    except Exception as e:
        print(f"[ERROR] create_department: {e}")
        raise HTTPException(503, "Database temporarily unavailable")


@app.patch("/api/departments/{dept_id}")
def update_department(dept_id: str, body: DepartmentUpdate):
    try:
        oid = ObjectId(dept_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    try:
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(400, "No fields to update")
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
def delete_department(dept_id: str):
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
def list_blogs(show_all: bool = False):
    try:
        query = _tq() if show_all else _tq({"published": True})
        docs = list(_bcol.find(query).sort("created_at", DESCENDING))
        return [_fmt_blog(d) for d in docs]
    except Exception as e:
        print(f"[ERROR] list_blogs: {e}")
        raise HTTPException(503, "Database temporarily unavailable")


@app.get("/api/blogs/{blog_id}")
def get_blog(blog_id: str):
    try:
        doc = _bcol.find_one(_tq({"_id": ObjectId(blog_id)}))
    except Exception:
        raise HTTPException(400, "Invalid id")
    if not doc:
        raise HTTPException(404, "Not found")
    return _fmt_blog(doc)


@app.post("/api/blogs", status_code=201)
def create_blog(body: BlogIn):
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
    }
    try:
        result = _bcol.insert_one(doc)
        return {"success": True, "id": str(result.inserted_id)}
    except Exception as e:
        print(f"[ERROR] create_blog: {e}")
        raise HTTPException(503, "Database temporarily unavailable")


@app.patch("/api/blogs/{blog_id}")
def update_blog(blog_id: str, body: BlogUpdate):
    try:
        oid = ObjectId(blog_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    try:
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(400, "No fields to update")
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
async def get_blog_content(blog_id: str):
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
def list_testimonials(show_all: bool = False):
    q = _tq() if show_all else _tq({"approved": True})
    docs = list(_testcol.find(q).sort("created_at", DESCENDING))
    return [_fmt_testimonial(d) for d in docs]


@app.post("/api/testimonials", status_code=201)
def create_testimonial(body: TestimonialIn):
    doc = body.model_dump()
    doc["approved"]    = False          # always pending until admin approves
    doc["tenant_name"] = _tenant()
    doc["created_at"]  = datetime.now(timezone.utc)
    result = _testcol.insert_one(doc)
    return {"success": True, "id": str(result.inserted_id)}


@app.patch("/api/testimonials/{test_id}")
def update_testimonial(test_id: str, body: TestimonialUpdate):
    try:
        oid = ObjectId(test_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")
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
        doc["display_url"] = f"https://drive.google.com/file/d/{fid}/preview" if fid else link
    else:
        doc["display_url"] = f"http://localhost:8000/api/proxy/image?id={fid}" if fid else link
    doc["thumb_url"] = f"http://localhost:8000/api/proxy/image?id={fid}" if fid else None
    return doc


@app.get("/api/media")
def list_media(gallery: bool = False):
    q = _tq({"show_in_gallery": True}) if gallery else _tq()
    docs = list(_mediacol.find(q).sort("order", 1))
    return [_fmt_media(d) for d in docs]


@app.post("/api/media", status_code=201)
def create_media(body: MediaIn):
    doc = body.model_dump()
    doc["tenant_name"] = _tenant()
    doc["created_at"]  = datetime.now(timezone.utc)
    result = _mediacol.insert_one(doc)
    return {"success": True, "id": str(result.inserted_id)}


@app.patch("/api/media/{media_id}")
def update_media(media_id: str, body: MediaUpdate):
    try:
        oid = ObjectId(media_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")
    result = _mediacol.update_one(_tq({"_id": oid}), {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@app.delete("/api/media/{media_id}")
def delete_media(media_id: str):
    try:
        oid = ObjectId(media_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    result = _mediacol.delete_one(_tq({"_id": oid}))
    if result.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@app.get("/api/gallery-config")
def get_gallery_config():
    doc = _gcfgcol.find_one(_tq())
    if not doc:
        return {"autoplay": True, "interval": 5000, "transition": "fade", "show_captions": True}
    doc.pop("_id", None)
    doc.pop("tenant_name", None)
    return doc


@app.patch("/api/gallery-config")
def update_gallery_config(body: GalleryConfigIn):
    data = {k: v for k, v in body.model_dump().items() if v is not None}
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
def list_offers(show_all: bool = False):
    q = _tq() if show_all else _tq({"active": True})
    docs = list(_offercol.find(q).sort("order", 1))
    return [_fmt_offer(d) for d in docs]


@app.post("/api/offers", status_code=201)
def create_offer(body: OfferIn):
    doc = body.model_dump()
    doc["tenant_name"] = _tenant()
    doc["created_at"]  = datetime.now(timezone.utc)
    result = _offercol.insert_one(doc)
    return {"success": True, "id": str(result.inserted_id)}


@app.patch("/api/offers/{offer_id}")
def update_offer(offer_id: str, body: OfferUpdate):
    try:
        oid = ObjectId(offer_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")
    result = _offercol.update_one(_tq({"_id": oid}), {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@app.delete("/api/offers/{offer_id}")
def delete_offer(offer_id: str):
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
    doc["logo_url"] = f"http://localhost:8000/api/proxy/image?id={fid}" if fid else None
    return doc


@app.get("/api/insurance")
def list_insurance(show_all: bool = False):
    q = _tq() if show_all else _tq({"active": True})
    docs = list(_inscol.find(q).sort("order", 1))
    return [_fmt_insurance(d) for d in docs]


@app.post("/api/insurance", status_code=201)
def create_insurance(body: InsuranceIn):
    doc = body.model_dump()
    doc["tenant_name"] = _tenant()
    doc["created_at"]  = datetime.now(timezone.utc)
    result = _inscol.insert_one(doc)
    return {"success": True, "id": str(result.inserted_id)}


@app.patch("/api/insurance/{ins_id}")
def update_insurance(ins_id: str, body: InsuranceUpdate):
    try:
        oid = ObjectId(ins_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")
    result = _inscol.update_one(_tq({"_id": oid}), {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@app.delete("/api/insurance/{ins_id}")
def delete_insurance(ins_id: str):
    try:
        oid = ObjectId(ins_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    result = _inscol.delete_one(_tq({"_id": oid}))
    if result.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


# ── Auth Routes ──────────────────────────────────────────────────────
@app.post("/api/auth/login")
def auth_login(body: LoginIn):
    email = body.email.strip().lower()
    user  = _usercol.find_one({"email": email})
    if not user:
        raise HTTPException(401, "Invalid email or password")
    pw_hash = user.get("password_hash")
    if not pw_hash or not bcrypt.checkpw(body.password.encode(), pw_hash):
        raise HTTPException(401, "Invalid email or password")
    token      = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
    _usercol.update_one(
        {"_id": user["_id"]},
        {"$set": {"active_token": token, "token_expires_at": expires_at, "last_login": datetime.now(timezone.utc)}}
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
    new_exp = datetime.now(timezone.utc) + timedelta(minutes=30)
    _usercol.update_one({"_id": user["_id"]}, {"$set": {"token_expires_at": new_exp}})
    return {"expires_at": new_exp.isoformat()}


@app.delete("/api/blogs/{blog_id}")
def delete_blog(blog_id: str):
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
