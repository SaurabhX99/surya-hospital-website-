"""
Appointment endpoints — CRUD, stats, export, and purge.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pymongo import DESCENDING
from pymongo.errors import DuplicateKeyError

from auth import require_admin
from config import paginated, tq, tenant, user_email
from database import appointments_col, audit_logs_col
from logging_config import get_logger
from models import AppointmentIn, PurgeIn, StatusIn
from security import require_public_access, rate_limit
from services.formatters import fmt_appointment
from services.notification import notify_legacy, send_appointment_sms

logger = get_logger(__name__)
router = APIRouter(prefix="/api/appointments", tags=["Appointments"])


@router.post("", status_code=201)
def create_appointment(body: AppointmentIn,
                       _auth: None = Depends(require_public_access),
                       _rl:   None = Depends(rate_limit(10, 60))):
    doc = {
        "tenant_name":    tenant(),
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
        result = appointments_col.insert_one(doc)
    except DuplicateKeyError:
        logger.warning("DuplicateKeyError — dropping unique indexes and retrying")
        for idx_name, idx_info in list(appointments_col.index_information().items()):
            if idx_name != "_id_" and idx_info.get("unique"):
                try:
                    appointments_col.drop_index(idx_name)
                except Exception:
                    pass
        doc.pop("_id", None)
        try:
            result = appointments_col.insert_one(doc)
        except DuplicateKeyError:
            doc.pop("_id", None)
            result = appointments_col.insert_one(doc)

    # Legacy WhatsApp notification (env-var-based)
    notify_legacy(body.name, body.mobile, body.department, body.date, body.doctor or "")
    # Admin-configured SMS notification
    send_appointment_sms(
        appointment_id=str(result.inserted_id),
        name=body.name,
        mobile=body.mobile,
        department=body.department or "",
        doctor=body.doctor or "",
        date=body.date,
    )
    return {"success": True, "id": str(result.inserted_id)}


# NOTE: /stats must come before /{appt_id} to avoid route conflict
@router.get("/stats")
def get_stats():
    total     = appointments_col.count_documents(tq())
    pending   = appointments_col.count_documents(tq({"status": {"$in": ["pending", "PENDING"]}}))
    confirmed = appointments_col.count_documents(tq({"status": {"$in": ["confirmed", "BOOKED"]}}))
    start_of_today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_oid = ObjectId.from_datetime(start_of_today)
    today     = appointments_col.count_documents(tq({"_id": {"$gte": today_oid}}))
    return {"total": total, "pending": pending, "confirmed": confirmed, "today": today}


@router.get("")
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
        extra["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"patientName": {"$regex": search, "$options": "i"}},
            {"mobile": {"$regex": search}},
            {"phoneNumber": {"$regex": search}},
        ]
    query = tq(extra)
    return paginated(appointments_col, query, sort_field="createdAt", sort_dir=DESCENDING,
                     fmt_fn=fmt_appointment, page=page, limit=limit)


# ── Export & Purge (must be before /{appt_id}) ───────────────────────

def _appt_purge_query(date_from, date_to, status):
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
    return tq(extra)


@router.get("/export")
def export_appointments(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    _admin: dict = Depends(require_admin),
):
    """Export matching appointments as an Excel (.xlsx) file."""
    from openpyxl import Workbook

    q = _appt_purge_query(date_from, date_to, status)
    docs = list(appointments_col.find(q).sort("createdAt", DESCENDING))

    wb = Workbook()
    ws = wb.active
    ws.title = "Appointments"
    ws.append(["ID", "Patient", "Mobile", "Department", "Doctor",
               "Preferred Date", "Time", "Reason", "Status", "Created At"])
    for d in docs:
        f = fmt_appointment(d)
        ws.append([
            f.get("appt_id") or f.get("id", ""),
            f.get("name", ""), f.get("mobile", ""), f.get("department", ""),
            f.get("doctor", ""), f.get("preferred_date", ""), f.get("appt_time", ""),
            f.get("message", ""), f.get("status", ""), f.get("created_at", ""),
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


@router.post("/count")
def count_appointments_for_purge(body: PurgeIn, _admin: dict = Depends(require_admin)):
    q = _appt_purge_query(body.date_from, body.date_to, body.status)
    return {"count": appointments_col.count_documents(q)}


@router.post("/purge")
def purge_appointments(body: PurgeIn, _admin: dict = Depends(require_admin)):
    """Delete appointments matching the given date range and status filters."""
    q = _appt_purge_query(body.date_from, body.date_to, body.status)
    result = appointments_col.delete_many(q)
    audit_logs_col.insert_one({
        "tenant_name": tenant(),
        "action":      "purge_appointments",
        "performed_by": user_email(),
        "timestamp":   datetime.now(timezone.utc),
        "records_deleted": result.deleted_count,
        "filters": {"date_from": body.date_from, "date_to": body.date_to, "status": body.status},
    })
    logger.info("Appointments purged", extra={"deleted": result.deleted_count})
    return {"success": True, "deleted": result.deleted_count}


@router.get("/{appt_id}")
def get_appointment(appt_id: str):
    try:
        doc = appointments_col.find_one(tq({"_id": ObjectId(appt_id)}))
    except Exception:
        raise HTTPException(400, "Invalid id")
    if not doc:
        raise HTTPException(404, "Not found")
    return fmt_appointment(doc)


@router.patch("/{appt_id}/status")
def update_status(appt_id: str, body: StatusIn):
    allowed = {"pending", "confirmed", "completed", "rejected"}
    if body.status not in allowed:
        raise HTTPException(400, f"status must be one of {allowed}")
    try:
        oid = ObjectId(appt_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    update: dict = {"status": body.status}
    if body.reason:
        update["status_reason"] = body.reason
    result = appointments_col.update_one(tq({"_id": oid}), {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}
