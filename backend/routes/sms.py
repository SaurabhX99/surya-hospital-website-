"""
SMS configuration, test, and audit log endpoints.

SMS config routes are SUPER_ADMIN only. Sensitive credentials are masked in GET responses.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pymongo import DESCENDING

from auth import require_super_admin
from config import tq, tenant, user_email
from database import sms_config_col, sms_logs_col, audit_logs_col
from logging_config import get_logger
from models import SmsConfigIn, SmsTestIn, PurgeIn
from services.notification import e164

logger = get_logger(__name__)
router = APIRouter(tags=["SMS"])

_MASK = "••••••••"


# ── SMS Config ───────────────────────────────────────────────────────

@router.get("/api/sms-config")
def get_sms_config(_admin: dict = Depends(require_super_admin)):
    """Return current SMS configuration with sensitive fields masked."""
    cfg = sms_config_col.find_one(tq()) or {}
    cfg.pop("_id", None)
    cfg.pop("tenant_name", None)
    if cfg.get("account_sid"):     cfg["account_sid"]     = _MASK
    if cfg.get("auth_token"):      cfg["auth_token"]      = _MASK
    if cfg.get("gupshup_api_key"): cfg["gupshup_api_key"] = _MASK
    return cfg


@router.put("/api/sms-config")
def save_sms_config(body: SmsConfigIn, _admin: dict = Depends(require_super_admin)):
    """Upsert SMS configuration. Preserves masked fields that weren't changed."""
    update = body.model_dump()
    masked_fields = [f for f in ("account_sid", "auth_token", "gupshup_api_key")
                     if update.get(f) == _MASK]
    if masked_fields:
        existing = sms_config_col.find_one(tq()) or {}
        for f in masked_fields:
            update[f] = existing.get(f, "")
    sms_config_col.update_one(
        tq(),
        {"$set": {**update, "tenant_name": tenant()}},
        upsert=True,
    )
    return {"success": True}


@router.post("/api/sms-config/test")
def test_sms(body: SmsTestIn, _admin: dict = Depends(require_super_admin)):
    """Send a test SMS to verify configuration."""
    cfg = sms_config_col.find_one(tq())
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
            to = e164(body.phone)
            from twilio.rest import Client
            Client(sid, token).messages.create(to=to, from_=from_num, body=test_body)
            return {"success": True, "message": f"Test SMS sent via Twilio to {to}"}

        elif provider == "gupshup":
            gs_api_key  = cfg.get("gupshup_api_key", "").strip()
            gs_app_name = cfg.get("gupshup_app_name", "").strip()
            if not (gs_api_key and from_num):
                return {"success": False, "error": "Gupshup credentials incomplete — fill API Key and From Number."}
            to    = e164(body.phone)
            gs_to = to.lstrip("+")
            resp = httpx.post(
                "https://api.gupshup.io/sm/api/v1/msg",
                headers={"apikey": gs_api_key, "Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "channel": "sms", "source": from_num,
                    "destination": gs_to, "message": test_body,
                    "src.name": gs_app_name or from_num,
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
        logger.error("SMS test failed", extra={"error": str(e)})
        return {"success": False, "error": str(e)}


# ── SMS Logs ─────────────────────────────────────────────────────────

@router.get("/api/sms-logs")
def list_sms_logs(
    page: int = 1,
    limit: int = 50,
    status: Optional[str] = None,
    search: Optional[str] = None,
    _admin: dict = Depends(require_super_admin),
):
    """Return paginated SMS audit log for this tenant."""
    q = tq()
    if status:
        q["status"] = status
    if search:
        q["$or"] = [
            {"patient_name": {"$regex": search, "$options": "i"}},
            {"to": {"$regex": search}},
            {"ref_id": {"$regex": search, "$options": "i"}},
        ]
    skip = (page - 1) * limit
    total = sms_logs_col.count_documents(q)
    docs  = list(sms_logs_col.find(q).sort("sent_at", DESCENDING).skip(skip).limit(limit))
    for d in docs:
        d["id"] = str(d.pop("_id"))
        d.pop("tenant_name", None)
        ts = d.get("sent_at")
        if isinstance(ts, datetime):
            d["sent_at"] = ts.isoformat()
    return {"total": total, "page": page, "limit": limit, "logs": docs}


# ── SMS Log Export & Purge ───────────────────────────────────────────

def _sms_purge_query(date_from, date_to, status):
    q = tq()
    if status:
        q["status"] = status
    if date_from or date_to:
        df: dict = {}
        if date_from:
            df["$gte"] = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
        if date_to:
            df["$lte"] = datetime.fromisoformat(date_to).replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
        q["sent_at"] = df
    return q


@router.get("/api/sms-logs/export")
def export_sms_logs(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    _admin: dict = Depends(require_super_admin),
):
    """Export matching SMS logs as an Excel (.xlsx) file."""
    from openpyxl import Workbook

    q = _sms_purge_query(date_from, date_to, status)
    docs = list(sms_logs_col.find(q).sort("sent_at", DESCENDING))

    wb = Workbook()
    ws = wb.active
    ws.title = "SMS Logs"
    ws.append(["Sent At", "Ref ID", "Patient", "To Number",
               "Department", "Status", "Message", "Error"])
    for d in docs:
        ts = d.get("sent_at")
        ws.append([
            ts.isoformat() if isinstance(ts, datetime) else str(ts or ""),
            d.get("ref_id", ""), d.get("patient_name", ""), d.get("to", ""),
            d.get("department", ""), d.get("status", ""),
            d.get("message", ""), d.get("error", ""),
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


@router.post("/api/sms-logs/count")
def count_sms_logs_for_purge(body: PurgeIn, _admin: dict = Depends(require_super_admin)):
    q = _sms_purge_query(body.date_from, body.date_to, body.status)
    return {"count": sms_logs_col.count_documents(q)}


@router.post("/api/sms-logs/purge")
def purge_sms_logs(body: PurgeIn, _admin: dict = Depends(require_super_admin)):
    """Delete SMS logs matching the given filters."""
    q = _sms_purge_query(body.date_from, body.date_to, body.status)
    result = sms_logs_col.delete_many(q)
    audit_logs_col.insert_one({
        "tenant_name": tenant(),
        "action":      "purge_sms_logs",
        "performed_by": user_email(),
        "timestamp":   datetime.now(timezone.utc),
        "records_deleted": result.deleted_count,
        "filters": {"date_from": body.date_from, "date_to": body.date_to, "status": body.status},
    })
    logger.info("SMS logs purged", extra={"deleted": result.deleted_count})
    return {"success": True, "deleted": result.deleted_count}
