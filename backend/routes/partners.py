"""
Partner endpoints — CRUD with Google Drive logo support.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pymongo import ASCENDING

from auth import require_admin
from config import paginated, tq, tenant, user_email
from database import partners_col
from models import PartnerIn, PartnerUpdate
from security import require_public_access
from services.formatters import fmt_partner, validate_drive_link

router = APIRouter(prefix="/api/partners", tags=["Partners"])


@router.get("")
def list_partners(
    show_all: bool = False,
    search: Optional[str] = None,
    page: Optional[int] = None,
    limit: int = 20,
    _: None = Depends(require_public_access),
):
    q = tq() if show_all else tq({"active": True})
    if search:
        q["name"] = {"$regex": search, "$options": "i"}
    return paginated(partners_col, q, sort_field="order", sort_dir=ASCENDING,
                     fmt_fn=fmt_partner, page=page, limit=limit)


@router.post("", status_code=201)
def create_partner(body: PartnerIn, _: None = Depends(require_admin)):
    validate_drive_link(body.logo_drive_link)
    doc = body.model_dump()
    doc["tenant_name"] = tenant()
    doc["created_at"]  = datetime.now(timezone.utc)
    doc["updated_by"]  = user_email()
    result = partners_col.insert_one(doc)
    return {"success": True, "id": str(result.inserted_id)}


@router.patch("/{partner_id}")
def update_partner(partner_id: str, body: PartnerUpdate, _: None = Depends(require_admin)):
    try:
        oid = ObjectId(partner_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "No fields to update")
    validate_drive_link(updates.get("logo_drive_link"))
    updates["updated_by"] = user_email()
    result = partners_col.update_one(tq({"_id": oid}), {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@router.delete("/{partner_id}")
def delete_partner(partner_id: str, _: None = Depends(require_admin)):
    try:
        oid = ObjectId(partner_id)
    except Exception:
        raise HTTPException(400, "Invalid id")
    result = partners_col.delete_one(tq({"_id": oid}))
    if result.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}
