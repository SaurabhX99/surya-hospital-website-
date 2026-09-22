"""
Dynamic API key management — SUPER_ADMIN only.

External callers (third-party integrations, mobile apps, scripts) need
their own API key to call the backend. These keys:
  - Are generated via POST /api/admin/api-keys
  - Bypass origin checks (unlike the site key in _config.js)
  - Can be scoped to specific IP addresses
  - Have configurable expiry
  - Can be revoked (deactivated) at any time
  - Track last usage time and IP

The site's own PUBLIC_API_KEY (shared via _config.js) is NOT stored here —
it lives in the .env file and only works from ALLOWED_ORIGINS in PROD.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pymongo import DESCENDING

from auth import require_super_admin
from config import tq, tenant, user_email
from database import api_keys_col
from logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/admin/api-keys", tags=["API Keys"])


class ApiKeyCreateIn(BaseModel):
    """Body for creating a new external API key."""
    label: str                          # human-readable name ("Mobile App", "CRM Integration")
    expires_in_days: int = 90           # key lifetime in days (0 = never expires)
    allowed_ips: Optional[list[str]] = None  # restrict to specific IPs (empty = any IP)


@router.get("")
def list_api_keys(_admin: dict = Depends(require_super_admin)):
    """List all API keys for this tenant (key values are masked)."""
    q = tq()
    docs = list(api_keys_col.find(q).sort("created_at", DESCENDING))
    result = []
    for d in docs:
        d["id"] = str(d.pop("_id"))
        d.pop("tenant_name", None)
        # Mask the key — show first 8 chars only
        full_key = d.get("key", "")
        d["key_preview"] = full_key[:8] + "••••••••" if len(full_key) > 8 else full_key
        d.pop("key", None)
        # Format dates
        for field in ("created_at", "expires_at", "last_used_at"):
            val = d.get(field)
            if isinstance(val, datetime):
                d[field] = val.isoformat()
        result.append(d)
    return result


@router.post("", status_code=201)
def create_api_key(body: ApiKeyCreateIn, _admin: dict = Depends(require_super_admin)):
    """
    Generate a fresh API key for external callers.

    The full key is returned ONLY in this response — it is never shown
    again. The caller must save it immediately.
    """
    key_value = secrets.token_urlsafe(48)  # 64-char URL-safe string
    now = datetime.now(timezone.utc)

    doc = {
        "tenant_name": tenant(),
        "key":         key_value,
        "label":       body.label.strip(),
        "active":      True,
        "allowed_ips": body.allowed_ips or [],
        "created_at":  now,
        "created_by":  user_email(),
        "expires_at":  now + timedelta(days=body.expires_in_days) if body.expires_in_days > 0 else None,
        "last_used_at": None,
        "last_used_ip": None,
    }
    result = api_keys_col.insert_one(doc)
    logger.info("API key created", extra={"label": body.label, "created_by": user_email()})

    return {
        "success": True,
        "id":      str(result.inserted_id),
        "key":     key_value,  # shown ONCE — save it now
        "label":   body.label,
        "expires_at": doc["expires_at"].isoformat() if doc["expires_at"] else None,
        "message": "Save this key now — it will not be shown again.",
    }


@router.patch("/{key_id}/status")
def toggle_api_key_status(key_id: str, _admin: dict = Depends(require_super_admin)):
    """Activate or deactivate an API key."""
    try:
        oid = ObjectId(key_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    doc = api_keys_col.find_one(tq({"_id": oid}))
    if not doc:
        raise HTTPException(404, "API key not found")
    new_active = not doc.get("active", True)
    api_keys_col.update_one({"_id": oid}, {"$set": {"active": new_active}})
    logger.info("API key status changed", extra={"key_id": key_id, "active": new_active})
    return {"success": True, "active": new_active}


@router.delete("/{key_id}")
def delete_api_key(key_id: str, _admin: dict = Depends(require_super_admin)):
    """Permanently delete an API key."""
    try:
        oid = ObjectId(key_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    result = api_keys_col.delete_one(tq({"_id": oid}))
    if result.deleted_count == 0:
        raise HTTPException(404, "API key not found")
    logger.info("API key deleted", extra={"key_id": key_id})
    return {"success": True}
