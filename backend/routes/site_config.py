"""
Site config endpoints — site-wide settings like hospital phone number.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from auth import require_admin
from config import tq, tenant
from database import site_config_col
from models import SiteConfigIn
from security import require_public_access

router = APIRouter(prefix="/api/site-config", tags=["Site Config"])


@router.get("")
def get_site_config(_: None = Depends(require_public_access)):
    """Return site-wide config for the current tenant."""
    cfg = site_config_col.find_one(tq()) or {}
    cfg.pop("_id", None)
    cfg.pop("tenant_name", None)
    return cfg


@router.put("")
def save_site_config(body: SiteConfigIn, _admin: dict = Depends(require_admin)):
    """Upsert site-wide configuration."""
    update = body.model_dump(exclude_unset=True)
    site_config_col.update_one(
        tq(),
        {"$set": {**update, "tenant_name": tenant()}},
        upsert=True,
    )
    return {"success": True}
