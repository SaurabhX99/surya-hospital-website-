"""
Vedansh Medicare — Appointment Booking API
Run : uvicorn main:app --reload --port 8000
Docs: http://localhost:8000/docs
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Optional

import certifi
from bson import ObjectId
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient, DESCENDING

load_dotenv()

# ── App ────────────────────────────────────────────────────────────
app = FastAPI(title="Vedansh Medicare API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000"],
    allow_credentials=True,
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
_col    = _mdb["appointments"]
_dcol   = _mdb["doctors"]


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
    department: str
    date: Optional[str] = None
    message: Optional[str] = None


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
        "name":           body.name,
        "mobile":         body.mobile,
        "department":     body.department,
        "preferred_date": body.date,
        "message":        body.message,
        "status":         "pending",
        "created_at":     datetime.now(timezone.utc),
    }
    result = _col.insert_one(doc)
    _notify(body.name, body.mobile, body.department, body.date)
    return {"success": True, "id": str(result.inserted_id)}


# NOTE: /stats must come before /{appt_id} to avoid route conflict
@app.get("/api/appointments/stats")
def get_stats():
    total     = _col.count_documents({})
    pending   = _col.count_documents({"status": {"$in": ["pending", "PENDING"]}})
    confirmed = _col.count_documents({"status": {"$in": ["confirmed", "BOOKED"]}})
    start_of_today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_oid = ObjectId.from_datetime(start_of_today)
    today     = _col.count_documents({"_id": {"$gte": today_oid}})
    return {"total": total, "pending": pending, "confirmed": confirmed, "today": today}


@app.get("/api/appointments")
def list_appointments(status: Optional[str] = None):
    query = {"status": status} if status else {}
    docs  = list(_col.find(query).sort("createdAt", DESCENDING))
    return [_fmt(d) for d in docs]


@app.get("/api/appointments/{appt_id}")
def get_appointment(appt_id: str):
    try:
        doc = _col.find_one({"_id": ObjectId(appt_id)})
    except Exception:
        raise HTTPException(400, "Invalid id")
    if not doc:
        raise HTTPException(404, "Not found")
    return _fmt(doc)


def _gdrive_direct(url: Optional[str]) -> Optional[str]:
    """Convert Google Drive share URL to a directly embeddable image URL."""
    if not url:
        return url
    m = re.search(r'drive\.google\.com/file/d/([^/?]+)', url)
    if m:
        return f"https://drive.google.com/uc?export=view&id={m.group(1)}"
    m = re.search(r'drive\.google\.com/open\?id=([^&\s]+)', url)
    if m:
        return f"https://drive.google.com/uc?export=view&id={m.group(1)}"
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
    allowed = {"pending", "confirmed", "cancelled", "completed"}
    if body.status not in allowed:
        raise HTTPException(400, f"status must be one of {allowed}")
    try:
        oid = ObjectId(appt_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    result = _col.update_one({"_id": oid}, {"$set": {"status": body.status}})
    if result.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


# ── Doctor Routes ───────────────────────────────────────────────────
@app.get("/api/doctors")
def list_doctors(featured: Optional[bool] = None, show_all: bool = False):
    try:
        # show_all=true is for admin panel — returns all doctors including inactive
        query: dict = {} if show_all else {"active": True}
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
        doc["created_at"] = datetime.now(timezone.utc)
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
        result = _dcol.update_one({"_id": oid}, {"$set": updates})
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
        result = _dcol.delete_one({"_id": oid})
        if result.deleted_count == 0:
            raise HTTPException(404, "Not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] delete_doctor: {e}")
        raise HTTPException(503, "Database temporarily unavailable")
