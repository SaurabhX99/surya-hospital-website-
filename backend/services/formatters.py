"""
Document formatters — convert MongoDB documents to JSON-serialisable dicts.

Each formatter normalises field names, handles datetime conversion, and
sets sensible defaults for optional fields.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from config import BASE_URL, STATUS_MAP


# ── Google Drive URL helpers ─────────────────────────────────────────

_DRIVE_RE = re.compile(r'drive\.google\.com|docs\.google\.com')


def extract_drive_id(url: str) -> Optional[str]:
    """Extract a Google Drive file ID from a share URL."""
    m = re.search(r'drive\.google\.com/file/d/([^/?]+)', url)
    if m:
        return m.group(1)
    m = re.search(r'drive\.google\.com/open\?id=([^&\s]+)', url)
    if m:
        return m.group(1)
    return None


def gdrive_direct(url: Optional[str]) -> Optional[str]:
    """Convert Google Drive share URL to a backend proxy URL."""
    if not url:
        return url
    fid = extract_drive_id(url)
    if fid:
        return f"{BASE_URL}/api/proxy/image?id={fid}"
    return url


def drive_content_url(link: str) -> str:
    """Convert a Google Drive / Docs share link to a direct content URL."""
    m = re.search(r'docs\.google\.com/document/d/([^/?]+)', link)
    if m:
        return f"https://docs.google.com/document/d/{m.group(1)}/export?format=html"
    m = re.search(r'drive\.google\.com/file/d/([^/?]+)', link)
    if m:
        return f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    m = re.search(r'drive\.google\.com/open\?id=([^&\s]+)', link)
    if m:
        return f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    return link


def validate_drive_link(url: Optional[str], field: str = "logo_drive_link") -> None:
    """Raise HTTP 400 if the URL is not a Google Drive link."""
    from fastapi import HTTPException
    if url and not _DRIVE_RE.search(url):
        raise HTTPException(400, f"{field} must be a Google Drive or Docs URL")


# ── Document formatters ──────────────────────────────────────────────

def fmt_appointment(doc: dict) -> dict:
    """Format an appointment document for API response."""
    doc["id"] = str(doc.pop("_id"))
    doc["name"]           = doc.get("patientName") or doc.get("name") or ""
    doc["mobile"]         = doc.get("phoneNumber")  or doc.get("mobile") or ""
    doc["preferred_date"] = doc.get("appointmentDate") or doc.get("preferred_date") or "—"
    doc["appt_time"]      = doc.get("appointmentTime") or ""
    doc["doctor"]         = doc.get("doctorName") or ""
    doc["message"]        = doc.get("reason") or doc.get("message") or ""
    doc["appt_id"]        = doc.get("appointmentId") or ""
    ca = doc.get("createdAt") or doc.get("created_at")
    if isinstance(ca, datetime):
        doc["created_at"] = ca.isoformat()
    else:
        doc["created_at"] = str(ca) if ca else ""
    raw = doc.get("status", "pending")
    doc["status"] = STATUS_MAP.get(raw, raw.lower() if raw else "pending")
    return doc


def fmt_doctor(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    ca = doc.get("created_at")
    if isinstance(ca, datetime):
        doc["created_at"] = ca.isoformat()
    doc.setdefault("photo", None)
    doc.setdefault("featured", False)
    doc.setdefault("active", True)
    # photo = original Drive link (for edit forms)
    # photo_url = proxy URL (for <img> display)
    doc["photo_url"] = gdrive_direct(doc["photo"]) if doc.get("photo") else None
    return doc


def fmt_department(doc: dict) -> dict:
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


def fmt_blog(doc: dict) -> dict:
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


def fmt_testimonial(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    ca = doc.get("created_at")
    if isinstance(ca, datetime):
        doc["created_at"] = ca.isoformat()
    doc.setdefault("approved", False)
    doc.setdefault("rating", 5)
    return doc


def fmt_media(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    ca = doc.get("created_at")
    if isinstance(ca, datetime):
        doc["created_at"] = ca.isoformat()
    link = doc.get("drive_link", "")
    fid  = extract_drive_id(link)
    if doc.get("type") == "video":
        doc["display_url"] = f"{BASE_URL}/api/proxy/video?id={fid}" if fid else link
    else:
        doc["display_url"] = f"{BASE_URL}/api/proxy/image?id={fid}" if fid else link
    doc["thumb_url"] = f"{BASE_URL}/api/proxy/image?id={fid}" if fid else None
    return doc


def fmt_offer(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    ca = doc.get("created_at")
    if isinstance(ca, datetime):
        doc["created_at"] = ca.isoformat()
    doc.setdefault("active", True)
    doc.setdefault("order", 0)
    return doc


def fmt_insurance(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    ca = doc.get("created_at")
    if isinstance(ca, datetime):
        doc["created_at"] = ca.isoformat()
    doc.setdefault("active", True)
    doc.setdefault("order", 0)
    doc.setdefault("logo_drive_link", None)
    link = doc.get("logo_drive_link") or ""
    fid  = extract_drive_id(link)
    doc["logo_url"] = f"{BASE_URL}/api/proxy/image?id={fid}" if fid else None
    return doc


def fmt_partner(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    ca = doc.get("created_at")
    if isinstance(ca, datetime):
        doc["created_at"] = ca.isoformat()
    doc.setdefault("active", True)
    doc.setdefault("order", 0)
    doc.setdefault("logo_drive_link", None)
    link = doc.get("logo_drive_link") or ""
    fid  = extract_drive_id(link)
    doc["logo_url"] = f"{BASE_URL}/api/proxy/image?id={fid}" if fid else None
    return doc


def fmt_stat(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    ca = doc.get("created_at")
    if isinstance(ca, datetime):
        doc["created_at"] = ca.isoformat()
    doc.setdefault("active", True)
    doc.setdefault("order", 0)
    doc.setdefault("suffix", "+")
    doc.setdefault("icon_key", "patients")
    return doc


def fmt_facility(d: dict) -> dict:
    d["id"] = str(d.pop("_id"))
    return d


def fmt_faq(d: dict) -> dict:
    d["id"] = str(d.pop("_id"))
    return d
