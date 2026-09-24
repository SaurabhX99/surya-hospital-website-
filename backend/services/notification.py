"""
SMS and WhatsApp notification services.

Supports two providers:
  - Twilio (SMS + WhatsApp via env vars for legacy, or DB config for admin-managed)
  - Gupshup (SMS via DB config)

All SMS attempts are logged to the sms_logs collection for audit purposes.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

import httpx

from config import TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM, TWILIO_WA, tenant, tq
from database import sms_config_col, sms_logs_col, doctors_col
from logging_config import get_logger

logger = get_logger(__name__)


def e164(mobile: str) -> str:
    """Normalise a phone number to E.164 format (defaults to +91 for 10-digit Indian numbers)."""
    d = "".join(c for c in mobile if c.isdigit())
    if len(d) == 10:
        return f"+91{d}"
    if d.startswith("91") and len(d) == 12:
        return f"+{d}"
    return f"+{d}"


def _lookup_doctor_timing(doctor_name: str) -> str:
    """Look up a doctor's OPD timing from the doctors collection."""
    if not doctor_name:
        return ""
    try:
        doc = doctors_col.find_one(
            {"name": {"$regex": re.escape(doctor_name), "$options": "i"}, "active": True},
            {"timing": 1},
        )
        return doc.get("timing", "") if doc else ""
    except Exception:
        return ""


# ── Legacy env-var-based notifications ───────────────────────────────

def _send_sms_legacy(to: str, body: str) -> None:
    if not (TWILIO_SID and TWILIO_TOKEN and TWILIO_FROM):
        logger.debug("Legacy SMS skipped (no Twilio env vars)", extra={"to": to})
        return
    from twilio.rest import Client
    Client(TWILIO_SID, TWILIO_TOKEN).messages.create(to=to, from_=TWILIO_FROM, body=body)


def _send_whatsapp_legacy(to: str, body: str) -> None:
    if not (TWILIO_SID and TWILIO_TOKEN):
        logger.debug("Legacy WhatsApp skipped (no Twilio env vars)", extra={"to": to})
        return
    from twilio.rest import Client
    Client(TWILIO_SID, TWILIO_TOKEN).messages.create(
        to=f"whatsapp:{to}", from_=TWILIO_WA, body=body
    )


def notify_legacy(name: str, mobile: str, dept: str, date: Optional[str], doctor: str = "") -> None:
    """Send appointment notification via legacy env-var-based Twilio."""
    to  = e164(mobile)
    timing = _lookup_doctor_timing(doctor) if doctor else ""
    msg = (
        f"Hi {name}! Your appointment at Vedansh Medicare has been received.\n"
        f"Department : {dept}\n"
        f"Pref. date : {date or 'to be confirmed'}\n"
    )
    if doctor:
        msg += f"Doctor     : {doctor}\n"
    if timing:
        msg += f"Timings    : {timing}\n"
    msg += (
        f"Please reach out to the hospital desk in case of any queries.\n"
        f"Helpline   : +91 9650494019"
    )
    try:
        _send_sms_legacy(to, msg)
    except Exception as e:
        logger.error("Legacy SMS failed", extra={"error": str(e), "to": to})
    try:
        _send_whatsapp_legacy(to, msg)
    except Exception as e:
        logger.error("Legacy WhatsApp failed", extra={"error": str(e), "to": to})


# ── Admin-configured SMS (reads credentials from DB) ─────────────────

def send_appointment_sms(
    appointment_id: str,
    name: str,
    mobile: str,
    department: str,
    doctor: str,
    date: Optional[str],
) -> None:
    """
    Send a patient confirmation SMS using admin-configured settings from MongoDB.

    Reads provider credentials and template fresh on every call so portal
    changes take effect immediately without a server restart.
    """
    cfg = sms_config_col.find_one(tq())
    if not cfg or not cfg.get("enabled"):
        logger.info("SMS disabled or not configured", extra={"appointment_id": appointment_id})
        return

    provider = cfg.get("provider", "twilio")
    template = cfg.get("template", "").strip()
    from_num = cfg.get("from_number", "").strip()
    short_id = appointment_id[:8].upper()

    timing = _lookup_doctor_timing(doctor) if doctor else ""

    try:
        message = template.format(
            name=name,
            mobile=mobile,
            department=department or "General",
            doctor=doctor or "To be assigned",
            date=date or "To be confirmed",
            appointment_id=short_id,
            timing=timing or "Please contact hospital desk",
        )
    except KeyError as ke:
        logger.warning("Unknown template placeholder", extra={"error": str(ke)})
        return

    to = e164(mobile)

    # Audit log entry
    log_entry = {
        "tenant_name":    tenant(),
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
                logger.warning("Twilio credentials incomplete — skipping SMS")
                return
            from twilio.rest import Client
            Client(sid, token).messages.create(to=to, from_=from_num, body=message)
            logger.info("Twilio SMS sent", extra={"to": to, "ref_id": short_id})
            log_entry["status"] = "success"

        elif provider == "gupshup":
            gs_api_key  = cfg.get("gupshup_api_key", "").strip()
            gs_app_name = cfg.get("gupshup_app_name", "").strip()
            if not (gs_api_key and from_num and template):
                logger.warning("Gupshup credentials incomplete — skipping SMS")
                return
            gs_to = to.lstrip("+")
            resp = httpx.post(
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
            if result_json.get("status") not in ("submitted", "success"):
                raise RuntimeError(f"Gupshup response: {result_json}")
            logger.info("Gupshup SMS sent", extra={"to": gs_to, "ref_id": short_id})
            log_entry["status"] = "success"

        else:
            logger.warning("Unsupported SMS provider", extra={"provider": provider})
            return

    except Exception as e:
        logger.error("SMS send failed", extra={"error": str(e), "provider": provider, "to": to})
        log_entry["status"] = "failed"
        log_entry["error"]  = str(e)
    finally:
        try:
            sms_logs_col.insert_one(log_entry)
        except Exception as le:
            logger.error("Failed to write SMS audit log", extra={"error": str(le)})
